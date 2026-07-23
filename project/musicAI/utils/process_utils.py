import os
import signal
import subprocess


# =============================
# Process termination
# =============================

def terminate_process_tree(process, timeout=3):
    """
    Terminates the entire process group because Demucs may create
    child processes.

    On macOS and Linux, the process must be started with
    start_new_session=True to terminate its process group safely.
    """
    if not process or process.poll() is not None:
        return

    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()

        try:
            process.wait(timeout=timeout)

        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()

            process.wait(timeout=timeout)

    except ProcessLookupError:
        pass

    except (OSError, subprocess.SubprocessError):
        try:
            process.kill()
            process.wait(timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            pass