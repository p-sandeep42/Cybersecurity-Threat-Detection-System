"""Count attributable HTTP outcomes without affecting the ingestion transaction."""

from flask import current_app, request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from platform_app.ingestion import key_digest
from platform_app.models import ApiKey, IngestionReceipt


def record_outcome(response):
    if request.path != "/api/v1/events" or request.method != "POST":
        return response
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return response
    # Ingestion has committed or rolled back before this hook. A separate session
    # also handles early rejects (body size, content type and rate limiting).
    try:
        with Session(current_app.extensions["database_engine"]) as database:
            app_id = database.scalar(
                select(ApiKey.app_id).where(
                    ApiKey.digest == key_digest(authorization[7:]),
                    ApiKey.revoked_at.is_(None),
                )
            )
            if app_id is not None:
                outcome = {201: "accepted", 200: "duplicate"}.get(response.status_code, "rejected")
                database.add(
                    IngestionReceipt(
                        app_id=app_id, outcome=outcome, http_status=response.status_code
                    )
                )
                database.commit()
    except SQLAlchemyError:
        # If storage itself is unavailable a receipt cannot be guaranteed. Do not
        # turn a committed event into an apparent delivery failure.
        current_app.logger.warning("Delivery counter unavailable; response unchanged")
    return response
