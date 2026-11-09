import httpx
import pytest
from fastapi import HTTPException

from app import history


def test_prediction_waits_for_storage_and_sends_write_once(monkeypatch):
    received = []

    def upstream(request):
        received.append((request.method, request.url.path))
        if len(received) == 1:
            return httpx.Response(503)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, json={"id": 42})

    client = httpx.Client(base_url="https://storage.test", transport=httpx.MockTransport(upstream))
    monkeypatch.setattr(history, "DATA_URL", "https://storage.test")
    monkeypatch.setattr(history.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(history.time, "sleep", lambda seconds: None)

    assert history.history_request("POST", "/records", payload={}) == {"id": 42}
    assert received == [("GET", "/health"), ("GET", "/health"), ("POST", "/records")]


def test_prediction_does_not_retry_a_write_after_transport_failure(monkeypatch):
    requests = []

    def upstream(request):
        requests.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"status": "ok"})
        raise httpx.ReadTimeout("The server might already have saved the record")

    client = httpx.Client(base_url="https://storage.test", transport=httpx.MockTransport(upstream))
    monkeypatch.setattr(history, "DATA_URL", "https://storage.test")
    monkeypatch.setattr(history.httpx, "Client", lambda **kwargs: client)

    with pytest.raises(HTTPException) as error:
        history.history_request("POST", "/records", payload={})

    assert error.value.status_code == 503
    assert requests == ["GET", "POST"]
