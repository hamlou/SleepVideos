import sys
import time

_T0 = time.time()


def log(msg: str) -> None:
    m, s = divmod(int(time.time() - _T0), 60)
    print(f"[{m:03d}:{s:02d}] {msg}", flush=True)


def step(msg: str) -> None:
    log(f"━━ {msg}")
    sys.stdout.flush()
