"""Route history operations to the data service, or SQLite for local development."""

import os

import httpx
from fastapi import HTTPException


DATA_URL = os.getenv("IRIS_DATA_URL", "").rstrip("/")
DATA_TOKEN = os.getenv("IRIS_DATA_TOKEN", "")
if os.getenv("RENDER") and (not DATA_URL.startswith("https://") or len(DATA_TOKEN) < 32):
    raise RuntimeError("Render requires IRIS_DATA_URL (HTTPS) and IRIS_DATA_TOKEN.")


def history_request(method, path, *, params=None, payload=None):
    if DATA_URL:
        try:
            response = httpx.request(
                method, f"{DATA_URL}{path}", params=params, json=payload,
                headers={"Authorization": f"Bearer {DATA_TOKEN}"}, timeout=65, trust_env=False,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(status_code=503, detail="Iris data service unavailable") from None

    from database.service import RecordInput, create_record, delete_records, read_all_records, read_records

    if method == "POST":
        return create_record(RecordInput.model_validate(payload))
    if method == "DELETE":
        return delete_records(**params)
    if path == "/admin/records":
        return read_all_records(**params)
    return read_records(**params)
