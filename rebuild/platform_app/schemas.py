"""The only accepted wire format; unknown fields and implicit coercions are rejected."""

from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Count = Annotated[int, Field(ge=0, le=100000)]
Duration = Annotated[int, Field(ge=0, le=1800000)]


class Interaction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1]
    consent: Literal[True]
    pointer_type: Literal["mouse", "touch", "pen", "mixed", "unknown"]
    pointer_move_count: Count
    pointer_down_count: Count
    first_interaction_ms: Duration | None
    submit_elapsed_ms: Duration
    visibility_interrupted: bool

    @model_validator(mode="after")
    def validate_timing(self):
        if type(self.version) is not int or type(self.consent) is not bool:
            raise ValueError("Invalid version or consent type")
        if self.first_interaction_ms is not None:
            if self.first_interaction_ms > self.submit_elapsed_ms:
                raise ValueError("First interaction cannot follow submission")
        return self


class SecurityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    event_id: str
    occurred_at: str
    event_type: Literal["login"]
    outcome: Literal["success", "failure"]
    subject_id: Annotated[str, Field(min_length=1, max_length=128)]
    source_ip: str
    session_id: str
    route: Literal["/login"]
    response_duration_ms: Annotated[float, Field(ge=0, le=60000, allow_inf_nan=False)]
    interaction: Interaction | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError("Version must be an integer")
        return value

    @field_validator("event_id", "session_id")
    @classmethod
    def canonical_uuid(cls, value):
        return str(UUID(value))

    @field_validator("subject_id")
    @classmethod
    def nonblank_subject(cls, value):
        if not value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("Subject must be a nonblank identifier")
        return value

    @field_validator("source_ip")
    @classmethod
    def canonical_ip(cls, value):
        if "%" in value:
            raise ValueError("Scoped IP addresses are unsupported")
        return str(ip_address(value))

    @field_validator("occurred_at")
    @classmethod
    def canonical_time(cls, value):
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            raise ValueError("Timestamp must include an offset")
        return timestamp.astimezone(UTC).isoformat(timespec="microseconds")

    def validate_freshness(self, now: datetime) -> None:
        timestamp = datetime.fromisoformat(self.occurred_at)
        if not now - timedelta(hours=24) <= timestamp <= now + timedelta(seconds=60):
            raise ValueError("Event timestamp is outside the accepted time range")
