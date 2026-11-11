"""API entry point of the image: N uvicorn processes, each on its own SO_REUSEPORT socket.

`uvicorn --workers` shares one listening socket, and asyncio accepts a whole burst of connections
in the first process that wakes: 50 keep-alive clients pile onto one or two workers while the rest
idle (k6 p95 of GET /documents, TZ-backend DoD 4). With SO_REUSEPORT the kernel spreads new
connections across the processes. Workers: `WEB_CONCURRENCY` (uvicorn's variable), default 4.
A worker that dies (for example OOM-killed) is replaced, as uvicorn's own supervisor does.
"""

import multiprocessing
import os
import signal
import socket
import sys
from multiprocessing.connection import wait
from multiprocessing.context import SpawnProcess
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
    stopping = False

    def start(n: int) -> SpawnProcess:
        process = context.Process(target=_serve, name=f"api-{n}")
        process.start()
        return process

    processes = [start(n) for n in range(workers)]

    def on_signal(signum: int, _frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True
        for process in processes:
            if process.is_alive() and process.pid is not None:
                os.kill(process.pid, signum)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    while not stopping:
        wait([process.sentinel for process in processes])
        for n, process in enumerate(processes):
            if not stopping and not process.is_alive():
                print(f"api worker {process.pid} exited with {process.exitcode}; restarting")
                processes[n] = start(n)
    for process in processes:
        process.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
