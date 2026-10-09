"""Per-run execution context; ordinary API calls remain usable without a worker."""
from contextlib import contextmanager
from contextvars import ContextVar


_context = ContextVar('forecast_execution', default=None)


class ForecastCancelled(BaseException):
    """Do not let model-level Exception handlers disguise cancellation as a fit failure."""


@contextmanager
def execution_context(output_directory, progress):
    token = _context.set((output_directory, progress))
    try:
        yield
    finally:
        _context.reset(token)


def output_directory(default):
    context = _context.get()
    return context[0] if context else default


def checkpoint(message=None):
    context = _context.get()
    if context:
        context[1](message)
