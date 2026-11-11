import socket

from app.serve import listening_socket


def test_be07_api_processes_can_share_one_port() -> None:
    """Each worker binds its own socket; SO_REUSEPORT lets the kernel balance them (k6 p95)."""
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    first = listening_socket("127.0.0.1", port)
    second = listening_socket("127.0.0.1", port)
    try:
        first.listen()
        second.listen()
        assert first.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT)
        assert second.getsockname() == first.getsockname()
    finally:
        first.close()
        second.close()
