"""Explicit company-scoped store factory; no global/default-company fallback."""
from dataclasses import dataclass
from pathlib import Path
from .platform_identity import COMPANY_ID
from .customers import CustomerStore


@dataclass(frozen=True)
class CompanyWorkspace:
    root: Path
    company_id: str

    @property
    def customers(self):
        return CustomerStore(self.root / 'customers.sqlite3')


class CompanyWorkspaces:
    def __init__(self, root):
        self.root = Path(root).resolve()

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
        return CompanyWorkspace(path, company)
