"""Explicit company-scoped store factory; no global/default-company fallback."""
from dataclasses import dataclass, field
import json
from pathlib import Path
from threading import RLock
from .platform_identity import COMPANY_ID
from .customers import CustomerStore


@dataclass(frozen=True)
class CompanyWorkspace:
    root: Path
    company_id: str
    _store_lock: RLock = field(default_factory=RLock, repr=False, compare=False)
    _stores: dict = field(default_factory=dict, repr=False, compare=False)

    def store(self, name, factory):
        # cached_property alone is not synchronized on Python 3.12+.
        with self._store_lock:
            if name not in self._stores:
                self._stores[name] = factory()
            return self._stores[name]

    def path(self, name):
        path = self.root / name
        if path.is_symlink() or (path.exists() and path.resolve().parent != self.root):
            raise ValueError('Company storage path is invalid.')
        return path

    @property
    def customers(self):
        return self.store('customers', lambda: CustomerStore(self.path('customers.sqlite3')))

    @property
    def units(self):
        from .units import UnitStore
        return self.store('units', lambda: UnitStore(self.path('units.sqlite3')))

    @property
    def datasets(self):
        from .datasets import DatasetStore
        return self.store('datasets', lambda: DatasetStore(self.path('datasets'), self.units))

    @property
    def sales(self):
        from .sales_demand import DemandStore
        return self.store('sales', lambda: DemandStore(self.path('sales-demand.sqlite3')))

    @property
    def factors(self):
        from .factors import FactorStore
        return self.store('factors', lambda: FactorStore(self.path('factors')))

    @property
    def live_sources(self):
        from .live_sources import LiveSources, KeyVault
        return self.store('live_sources', lambda: LiveSources(self.path('live-sources.sqlite3'), self.factors,
                           vault=KeyVault(self.root)))

    @property
    def connections(self):
        import os
        from .business_connections import BusinessConnections,InputFetcher,TargetPolicy,ConnectionError
        try:
            targets = json.loads(os.environ.get('DEMANDLAB_CONNECTOR_PRIVATE_TARGETS','{}'))
            approved = targets.get(self.company_id,[])
            if not isinstance(approved,list) or any(not isinstance(v,str) for v in approved): raise ValueError()
        except (ValueError,AttributeError):
            raise ConnectionError('Company connection settings are invalid. Ask an administrator.') from None
        return self.store('connections',lambda:BusinessConnections(self.path('connections.sqlite3'),self.datasets,
                          fetcher=InputFetcher(TargetPolicy(v.strip().lower() for v in approved))))

    @property
    def site(self):
        path = self.path('site.json')
        if path.exists():
            return json.loads(path.read_text())
        # A client-independent starting profile; never read the legacy site file.
        return {'id':'main-site', 'name':'Manufacturing site', 'country':'Iran',
                'province':'Tehran', 'timezone':'Asia/Tehran', 'currency':'IRR',
                'calendar':'Jalali + Gregorian'}

    @property
    def order_books(self):
        from .order_books import OrderBooks
        return self.store('order_books', lambda: OrderBooks(self.path('orders.sqlite3'), self.datasets, self.customers,
                          site=self.site))

    @property
    def runs(self):
        path = self.path('runs')
        path.mkdir(exist_ok=True)
        return path

    @property
    def jobs(self):
        from .jobs import JobStore
        return self.store('jobs', lambda: JobStore(self.path('jobs.sqlite3'), self.runs))

    @property
    def journal(self):
        from .ai_workspace import AIJournal
        return self.store('journal', lambda: AIJournal(self.path('assistant.sqlite3')))

    @property
    def ai_ledger(self):
        from .ai_provider import AICallLedger
        return self.store('ai_ledger', lambda: AICallLedger(self.path('assistant.sqlite3')))

    @property
    def views(self):
        from .forecast_views import ViewStore
        return self.store('views', lambda: ViewStore(self.path('views.sqlite3')))

    @property
    def actuals(self):
        from .actuals import ActualsStore
        return self.store('actuals', lambda: ActualsStore(self.path('actuals.sqlite3'), self.datasets))

    @property
    def profiles(self):
        from .factor_profiles import FactorProfiles
        return self.store('profiles', lambda: FactorProfiles(self.customers))

    def save_site(self, values):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(values['timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Use a recognised time zone, such as Asia/Tehran.') from None
        with self._store_lock:
            value = {**self.site, **values}
            path = self.path('site.json')
            temp = self.path('site.tmp')
            temp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            temp.replace(path)
            # Order starters use the current location, not a cached old profile.
            self._stores.pop('order_books', None)
            return value

    def load_run(self, identifier):
        if not isinstance(identifier, str) or len(identifier) not in {12,32} or any(
                c not in '0123456789abcdef' for c in identifier):
            raise ValueError('Forecast not found.')
        folder = self.runs / identifier
        path = folder / 'result.json'
        if folder.is_symlink() or path.is_symlink() or not path.is_file():
            raise ValueError('Forecast not found.')
        value = json.loads(path.read_text())
        # In-flight/abandoned results must never escape the job ledger gate.
        if value.get('job_id'):
            job = self.jobs.get(value['job_id'])
            if job['state'] != 'succeeded' or job['run_id'] != identifier or job['owner'] != value.get('job_owner'):
                raise ValueError('Forecast is not ready.')
        return value

    def list_runs(self):
        rows = []
        for path in self.runs.glob('*/result.json'):
            try:
                rows.append(self.load_run(path.parent.name))
            except ValueError:
                continue
        return sorted(rows, key=lambda row: row.get('issued_at',''), reverse=True)

    @property
    def releases(self):
        from .demand_releases import DemandReleases
        return self.store('releases', lambda: DemandReleases(self.sales, self.load_run))


class CompanyWorkspaces:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self._workspaces = {}
        self._lock = RLock()

    def for_principal(self, who):
        company = who.get('company_id')
        if not isinstance(company, str) or not COMPANY_ID.fullmatch(company):
            raise ValueError('A validated company identity is required.')
        path = self.root / company
        if path.exists() and (path.is_symlink() or path.resolve().parent != self.root):
            raise ValueError('Company workspace path is invalid.')
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Individual store constructors receive this exact root. Background jobs
        # must explicitly carry company_id; never infer one from a browser header.
        with self._lock:
            if company not in self._workspaces:
                self._workspaces[company] = CompanyWorkspace(path, company)
            return self._workspaces[company]

    def close(self):
        for workspace in self._workspaces.values():
            for store in workspace._stores.values():
                if hasattr(store, 'close'):
                    store.close()
                elif hasattr(store, 'engine'):
                    store.engine.dispose()

    def refresh_sources(self):
        if not self.root.exists():return
        for path in self.root.iterdir():
            if not path.is_dir() or path.is_symlink() or not COMPANY_ID.fullmatch(path.name):continue
            if not (path/'live-sources.sqlite3').is_file():continue
            self.for_principal({'company_id':path.name}).live_sources.tick()
