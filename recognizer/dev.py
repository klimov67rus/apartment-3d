"""Start the local recognition service and Vite together."""
import os
import signal
import subprocess
import sys
import time


def main():
    processes = []
    try:
        processes.append(subprocess.Popen([sys.executable, '-m', 'recognizer.server'], start_new_session=True))
        processes.append(subprocess.Popen(['npm', 'run', 'dev'], start_new_session=True))
        while all(process.poll() is None for process in processes):
            time.sleep(.2)
        code = next(process.returncode for process in processes if process.poll() is not None)
        return code or 1
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            process.wait()

if __name__ == '__main__':
    raise SystemExit(main())
