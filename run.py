import subprocess
import sys
import os
from pathlib import Path
from threading import Event, Thread

import uvicorn
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / 'secrets' / '.env.local', override=False)


def supervise_worker(stop):
    """Local process lifecycle only; Huey handles queue delivery and worker health."""
    root = Path(__file__).resolve().parent
    while not stop.is_set():
        process = subprocess.Popen([sys.executable, '-m', 'app.worker', '--parent-pid', str(os.getpid())], cwd=root)
        while process.poll() is None and not stop.wait(2):
            pass
        if stop.is_set() and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if not stop.is_set():
            stop.wait(5)

if __name__ == "__main__":
    print("\nDemand Signal Lab → http://127.0.0.1:8010\n")
    stop = Event()
    worker = Thread(target=supervise_worker, args=(stop,), daemon=True)
    worker.start()
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8010, reload=False)
    finally:
        stop.set()
        worker.join(timeout=15)
