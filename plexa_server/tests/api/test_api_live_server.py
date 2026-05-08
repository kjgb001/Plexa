import threading
import time
import socket
import requests

import uvicorn


def _find_free_port() -> int:
    """Return an available loopback TCP port for a test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_server(app, port: int) -> None:
    """Run a Uvicorn server for the supplied test app on the given port."""
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        ws="none"
    )

    server = uvicorn.Server(config)
    server.run()


def test_server_health_endpoint(app, storage_backend):
    port = _find_free_port()
    thread = threading.Thread(target=run_server, args=(app, port), daemon=True)
    thread.start()

    # Give server time to boot
    time.sleep(0.5)

    response = requests.get(f"http://127.0.0.1:{port}/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"
