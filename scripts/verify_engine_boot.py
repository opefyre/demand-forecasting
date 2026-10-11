"""Offline boot receipt; starts only a disposable container-local engine."""
import json
import subprocess
import time
import urllib.request

started=time.monotonic()
process=subprocess.Popen(['uvicorn','app.cloud_compute:app','--host','127.0.0.1','--port','8080',
                          '--no-access-log','--log-level','critical'])
try:
    while time.monotonic()-started<60:
        if process.poll() is not None:
            raise RuntimeError('Engine exited during startup: '+str(process.returncode))
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/ready',timeout=1) as response:
                if response.status==200:
                    print(json.dumps({'ready':True,'startup_seconds':round(time.monotonic()-started,3)}),flush=True)
                    break
        except OSError:
            time.sleep(.1)
    else:
        raise RuntimeError('Engine did not become ready within sixty seconds.')
finally:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill();process.wait()
