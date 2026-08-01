import socket
import threading
import time

import httpx
import uvicorn


def _find_free_port() -> int:
    """Return an available loopback TCP port for a test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_server(app, port: int) -> uvicorn.Server:
    """Build a Uvicorn server for the supplied test app on the given port."""
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        ws="none",
    )
    return uvicorn.Server(config)


def test_server_health_endpoint(app, storage_backend):
    port = _find_free_port()
    server = build_server(app, port)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5
    response = None
    try:
        while time.monotonic() < deadline:
            try:
                response = httpx.get(
                    f"http://127.0.0.1:{port}/api/health",
                    timeout=0.5,
                )
                break
            except httpx.ConnectError:
                time.sleep(0.05)

        assert response is not None, "Live test server did not start within 5 seconds"
        assert response.status_code == 200
        assert response.json()["status"] == "alive"
    finally:
        server.should_exit = True
        thread.join(timeout=5)

    assert not thread.is_alive(), "Live test server did not stop within 5 seconds"
