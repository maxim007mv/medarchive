"""API entry point of the image: N uvicorn processes, each on its own SO_REUSEPORT socket.

`uvicorn --workers` shares one listening socket, and asyncio accepts a whole burst of connections
in the first process that wakes: 50 keep-alive clients pile onto one or two workers while the rest
idle (k6 p95 of GET /documents, TZ-backend DoD 4). With SO_REUSEPORT the kernel spreads new
connections across the processes. Workers: `WEB_CONCURRENCY` (uvicorn's variable), default 4.
"""

import multiprocessing
import os
import signal
import socket
import sys
from multiprocessing.connection import wait
from types import FrameType

import uvicorn

HOST = "0.0.0.0"  # noqa: S104  # inside the container; compose publishes on 127.0.0.1 only
PORT = 8000
DEFAULT_WORKERS = 4


def listening_socket(host: str, port: int) -> socket.socket:
    """A socket other processes can bind to the same address; uvicorn calls listen()."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind((host, port))
    return sock


def _serve() -> None:
    config = uvicorn.Config("app.main:app", host=HOST, port=PORT, server_header=False)
    uvicorn.Server(config).run(sockets=[listening_socket(HOST, PORT)])


def main() -> int:
    workers = int(os.environ.get("WEB_CONCURRENCY", DEFAULT_WORKERS))
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=_serve, name=f"api-{n}") for n in range(workers)]
    for process in processes:
        process.start()

    requested = False

    def stop(signum: int, _frame: FrameType | None) -> None:
        for process in processes:
            if process.is_alive() and process.pid is not None:
                os.kill(process.pid, signum)

    def on_signal(signum: int, frame: FrameType | None) -> None:
        nonlocal requested
        requested = True
        stop(signum, frame)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    # The first process to exit ends the container: a dead worker must not leave a half API.
    wait([process.sentinel for process in processes])
    stop(signal.SIGTERM, None)
    for process in processes:
        process.join()
    # uvicorn re-raises the stop signal after a graceful shutdown (exit code -15).
    if requested:
        return 0
    return 1 if any(process.exitcode for process in processes) else 0


if __name__ == "__main__":
    sys.exit(main())
