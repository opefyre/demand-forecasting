"""Use the existing Huey worker with an explicit, validated company workspace."""
import asyncio
from .company_workspace import CompanyWorkspaces
from .jobs import ROOT, huey, execute_job
from .forecast_orders import finalize


def execute_company_job(workspace, key):
    from .main import SavedRunConfig, calculate_saved
    execute_job(key, workspace.jobs,
        executor=lambda payload: asyncio.run(calculate_saved(SavedRunConfig(**payload), workspace)),
        finalizer=lambda result, snapshot, folder: finalize(workspace.datasets,
            workspace.sales, result, snapshot, folder, site=workspace.site))


@huey.task()
def company_forecast_job(company_id, key):
    workspaces = CompanyWorkspaces(ROOT / 'data' / 'companies')
    try:
        execute_company_job(workspaces.for_principal({'company_id':company_id}), key)
    finally:
        workspaces.close()


def dispatch(workspace, key):
    if workspace.root.parent != (ROOT / 'data' / 'companies').resolve():
        raise ValueError('The company worker storage root is not configured.')
    company_forecast_job(workspace.company_id, key)


def recover_companies(workspaces, *, enqueue=False):
    """Recover durable jobs on worker restart without scanning client files."""
    if not workspaces.root.exists():
        return
    for path in workspaces.root.iterdir():
        if not path.is_dir() or path.is_symlink() or not (path / 'jobs.sqlite3').is_file():
            continue
        try:
            workspace = workspaces.for_principal({'company_id':path.name})
            workspace.jobs.recover()
            if enqueue:
                for key in workspace.jobs.queued():
                    dispatch(workspace, key)
        except ValueError:
            continue
