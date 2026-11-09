"""Route history operations to the data service, or SQLite for local development."""

import logging
import os
import time

import httpx
from fastapi import HTTPException


logger = logging.getLogger(__name__)

DATA_URL = os.getenv("IRIS_DATA_URL", "").rstrip("/")
DATA_TOKEN = os.getenv("IRIS_DATA_TOKEN", "")
if os.getenv("RENDER") and (not DATA_URL.startswith("https://") or len(DATA_TOKEN) < 32):
    raise RuntimeError("Render requires IRIS_DATA_URL (HTTPS) and IRIS_DATA_TOKEN.")


def wait_for_data_service(client: httpx.Client) -> None:
    """Wake a sleeping instance with a read-only request before sending records."""
    deadline = time.monotonic() + 80
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            response = client.get("/health", timeout=min(remaining, 15))
            if response.status_code not in {502, 503, 504}:
                response.raise_for_status()
                if response.headers.get("content-type", "").startswith("application/json"):
                    if response.json() == {"status": "ok"}:
                        return
        except httpx.TransportError:
            pass
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    raise TimeoutError("Iris data service did not become ready")


def history_request(method, path, *, params=None, payload=None):
    if DATA_URL:
        try:
            with httpx.Client(base_url=DATA_URL, timeout=15, trust_env=False) as client:
                wait_for_data_service(client)
                response = client.request(
                    method, path, params=params, json=payload,
                    headers={"Authorization": f"Bearer {DATA_TOKEN}"},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Iris data request failed with HTTP %s", exc.response.status_code)
        except (httpx.TransportError, TimeoutError, ValueError) as exc:
            logger.warning("Iris data request failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ lưu lịch sử chưa sẵn sàng. Vui lòng thử lại sau ít giây.",
        )

    from database.service import RecordInput, create_record, delete_records, read_all_records, read_records

    if method == "POST":
        return create_record(RecordInput.model_validate(payload))
    if method == "DELETE":
        return delete_records(**params)
    if path == "/admin/records":
        return read_all_records(**params)
    return read_records(**params)
