"""Cooperative process lease for offline maintenance on macOS/Linux."""
from pathlib import Path
import fcntl
import atexit


class WorkspaceLease:
    def __init__(self, root, *, exclusive=False):
        path = Path(root) / '.workspace.lock'
        self.file = path.open('a+b')
        try:
            fcntl.flock(self.file, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close()
            raise RuntimeError('Workspace is in use. Stop the web app and forecast workers before maintenance; wait for maintenance to finish before starting them.') from None
        if not exclusive and (Path(root) / 'RESTORE_INCOMPLETE').exists():
            self.file.close()
            raise RuntimeError('This restore is incomplete. Recover into a new directory before starting the app.')
        atexit.register(self.close)

    def close(self):
        self.file.close()
        atexit.unregister(self.close)

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
