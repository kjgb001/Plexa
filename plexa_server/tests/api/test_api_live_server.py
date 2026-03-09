import threading
import time
import requests

import uvicorn
from plexa_server.api.app import build_app
from plexa_server.inference.stub import StubInference


def run_server():
    app = build_app(StubInference())

    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        ws="none"
    )

    server = uvicorn.Server(config)
    server.run()


def test_server_health_endpoint(tmp_path):
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Give server time to boot
    time.sleep(0.5)

    response = requests.get("http://127.0.0.1:8000/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"