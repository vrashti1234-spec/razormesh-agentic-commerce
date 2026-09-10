from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class AuditEvent:
    event_id: str
    transaction_id: str
    event_type: str
    status: str
    details: dict[str, Any]
    timestamp: str


audit_log: list[AuditEvent] = []


def record_audit_event(
    transaction_id: str,
    event_type: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_id=str(uuid4()),
        transaction_id=transaction_id,
        event_type=event_type,
        status=status,
        details=details or {},
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    audit_log.append(event)

    return event


def get_audit_log(
    transaction_id: str | None = None,
) -> list[dict[str, Any]]:
    events = audit_log

    if transaction_id is not None:
        events = [
            event
            for event in events
            if event.transaction_id == transaction_id
        ]

    return [asdict(event) for event in events]