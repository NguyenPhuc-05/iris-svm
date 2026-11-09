"""SQLite-backed data service for Iris prediction records and Iris profiles."""

import os
from datetime import datetime
from secrets import compare_digest

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from database.db import SessionLocal
from database.models import PredictionRecord, register_iris_user


class RecordInput(BaseModel):
    user_id: str
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    kernel: str
    prediction: str
    class_id: int
    probability: float
    model_version: str
    created_at: datetime


def authorize(authorization: str = Header(default="")) -> None:
    token = os.environ.get("IRIS_DATA_TOKEN", "")
    expected = f"Bearer {token}".encode()
    if len(token) < 32 or not compare_digest(authorization.encode(), expected):
        raise HTTPException(status_code=401, detail="Service authentication required")


def create_record(payload: RecordInput) -> dict:
    with SessionLocal.begin() as session:
        register_iris_user(session, payload.user_id, payload.created_at)
        record = PredictionRecord(**payload.model_dump(mode="json", exclude={"created_at"}),
                                  created_at=payload.created_at.isoformat())
        session.add(record)
        session.flush()
        return {"id": record.id}


def serialize_records(query) -> list[dict]:
    fields = set(RecordInput.model_fields) - {"user_id"}
    return [dict(id=record.id, **{field: getattr(record, field) for field in fields})
            for record in query.all()]


def read_records(user_id: str, since: str, limit: int | None = None) -> list[dict]:
    with SessionLocal() as session:
        query = session.query(PredictionRecord).filter(
            PredictionRecord.user_id == user_id,
            PredictionRecord.created_at >= since,
        ).order_by(PredictionRecord.id.desc())
        return serialize_records(query.limit(limit))


def delete_records(user_id: str) -> dict:
    with SessionLocal.begin() as session:
        session.query(PredictionRecord).filter_by(user_id=user_id).delete()
    return {"status": "cleared"}


def read_all_records(limit: int) -> list[dict]:
    with SessionLocal() as session:
        return serialize_records(session.query(PredictionRecord)
                                 .order_by(PredictionRecord.id.desc()).limit(limit))


app = FastAPI(title="Iris Data Service", docs_url=None, redoc_url=None, openapi_url=None)
protected = APIRouter(dependencies=[Depends(authorize)])
protected.add_api_route("/records", create_record, methods=["POST"])
protected.add_api_route("/records", read_records, methods=["GET"])
protected.add_api_route("/records", delete_records, methods=["DELETE"])
protected.add_api_route("/admin/records", read_all_records, methods=["GET"])
app.include_router(protected)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
