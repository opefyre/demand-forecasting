"""Run with `python -m app.worker`; run.py starts this alongside the web server."""
import logging
import argparse
import os
import signal
from threading import Event, Thread

from huey.consumer import Consumer

from .jobs import STORE, forecast_job, huey


def parent_is_current(parent_pid):
    return parent_pid is None or os.getppid() == parent_pid


def main(parent_pid=None):
    logging.basicConfig(level=logging.INFO)
    stop = Event()

    def watch_parent():
        # A terminated web process can bypass its Python finally block. Do not
        # leave an old-code consumer claiming jobs after its owner disappears.
        while not stop.wait(1):
            if not parent_is_current(parent_pid):
                logging.warning('Owning app stopped; shutting down its forecast worker.')
                os.kill(os.getpid(), signal.SIGTERM)
                return

    if not parent_is_current(parent_pid):
        return
    if parent_pid is not None:
        Thread(target=watch_parent, daemon=True).start()

    def health():
        while not stop.is_set():
            try:
                STORE.pulse_worker()
                STORE.recover()
            except Exception:
                logging.exception('Worker health update failed')
            stop.wait(5)

    thread = Thread(target=health, daemon=True)
    thread.start()
    for key in STORE.queued():
        forecast_job(key)
    try:
        Consumer(huey, workers=1, worker_type='thread', periodic=False,
                 max_delay=1, shutdown_timeout=10).run()
    finally:
        stop.set()
        thread.join(timeout=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent-pid', type=int)
    main(parser.parse_args().parent_pid)
