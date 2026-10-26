"""Bearer-authenticated ingestion with atomic event and alert persistence."""

import hashlib
import json
from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from platform_app.database import get_db
from platform_app.detection.persistence import reconcile
from platform_app.extensions import csrf, limiter
from platform_app.models import ApiKey, Event
from platform_app.schemas import SecurityEvent

bp = Blueprint("ingestion", __name__)


def key_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def error_response(code, message, status, fields=None):
    return jsonify(error={"code": code, "message": message, "fields": fields or []}), status


@bp.post("/api/v1/events")
@csrf.exempt
@limiter.limit(
    "120 per minute", key_func=lambda: key_digest(request.headers.get("Authorization", ""))
)
def ingest_event():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return error_response("unauthorized", "A valid ingestion key is required", 401)
    if request.mimetype != "application/json":
        return error_response("content_type", "Use application/json", 415)
    database = get_db()
    try:
        # Acquire the SQLite writer before deduplication; concurrent deliveries serialize.
        database.connection().exec_driver_sql("BEGIN IMMEDIATE")
        api_key = database.scalar(
            select(ApiKey).where(
                ApiKey.digest == key_digest(authorization[7:]),
                ApiKey.revoked_at.is_(None),
            )
        )
        if api_key is None:
            database.rollback()
            return error_response("unauthorized", "A valid ingestion key is required", 401)
        payload = request.get_json()
        try:
            validated = SecurityEvent.model_validate(payload)
        except ValidationError as error:
            database.rollback()
            fields = sorted({str(item["loc"][0]) for item in error.errors() if item["loc"]})
            return error_response("validation", "Invalid event fields", 422, fields)
        canonical = validated.model_dump()
        fingerprint = key_digest(json.dumps(canonical, sort_keys=True, separators=(",", ":")))
        existing = database.scalar(
            select(Event).where(
                Event.app_id == api_key.app_id,
                Event.event_id == validated.event_id,
            )
        )
        if existing is not None:
            database.rollback()
            if existing.payload_hash != fingerprint:
                return error_response("conflict", "Event ID already has different content", 409)
            return jsonify(event_id=validated.event_id, status="duplicate"), 200
        try:
            validated.validate_freshness(datetime.now(UTC))
        except ValueError:
            database.rollback()
            return error_response(
                "timestamp", "Event timestamp is outside the accepted range", 422, ["occurred_at"]
            )
        record = Event(
            app_id=api_key.app_id,
            event_id=validated.event_id,
            occurred_at=validated.occurred_at,
            subject_id=validated.subject_id,
            source_ip=validated.source_ip,
            session_id=validated.session_id,
            outcome=validated.outcome,
            response_duration_ms=validated.response_duration_ms,
            payload=canonical,
            payload_hash=fingerprint,
        )
        database.add(record)
        database.flush()
        alert_ids = reconcile(database, api_key.app_id, record)
        database.commit()
        return jsonify(event_id=validated.event_id, status="accepted", alert_ids=alert_ids), 201
    except Exception as error:
        database.rollback()
        # HTTP parsing errors retain their correct status; do not turn them into retryable 503s.
        from werkzeug.exceptions import HTTPException

        if isinstance(error, HTTPException):
            raise
        current_app.logger.error("Event transaction failed (%s)", type(error).__name__)
        return error_response("unavailable", "Event was not accepted; retry later", 503)
