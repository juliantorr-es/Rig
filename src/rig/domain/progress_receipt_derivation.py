from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from rig.domain.progress_events import ProgressEvent

ALLOWED_RECEIPT_KINDS = {
    "operational_transcript",
    "validation_summary",
    "workspace_scan_summary",
    "reserved_future",
}

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


@dataclass(frozen=True, slots=True)
class ProgressReceiptEligibility:
    eligible: bool
    reason: str
    warnings: tuple[str, ...] = ()
    receipt_kind: str = "reserved_future"


@dataclass(frozen=True, slots=True)
class ProgressReceiptPlan:
    operation_id: str
    eligible: ProgressReceiptEligibility
    receipt_kind: str = "reserved_future"
    events: tuple[ProgressEvent, ...] = ()
    transcript_summary: str = ""
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProgressReceiptDerivationError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _sorted_events(events: Sequence[ProgressEvent]) -> list[ProgressEvent]:
    return sorted(events, key=lambda event: (event.sequence, event.timestamp))


def derive_progress_receipt_plan(events: Sequence[ProgressEvent]) -> ProgressReceiptPlan:
    if not events:
        raise ProgressReceiptDerivationError("Progress receipt derivation requires at least one event.")

    if any(not isinstance(event, ProgressEvent) for event in events):
        raise ProgressReceiptDerivationError("Progress receipt derivation requires ProgressEvent objects.")

    operation_ids = {event.operation_id for event in events}
    if len(operation_ids) != 1:
        raise ProgressReceiptDerivationError("Progress receipt derivation requires one operation_id.")

    operation_id = next(iter(operation_ids))
    for previous, current in zip(events, events[1:]):
        if current.sequence <= previous.sequence:
            raise ProgressReceiptDerivationError("Progress event sequence numbers must be strictly monotonic.")

    sorted_events = _sorted_events(events)

    if any(not event.event_id for event in sorted_events):
        raise ProgressReceiptDerivationError("Progress events must have stable event_id values.")
    if any(not event.command for event in sorted_events):
        raise ProgressReceiptDerivationError("Progress events must include command.")
    if any(not event.status for event in sorted_events):
        raise ProgressReceiptDerivationError("Progress events must include status.")

    terminal = sorted_events[-1]
    if terminal.status not in TERMINAL_STATUSES:
        raise ProgressReceiptDerivationError("Progress receipt sequences must end in a terminal status.")

    warnings: list[str] = []
    first = sorted_events[0]
    if not all(event.receipt_candidate is False for event in sorted_events):
        warnings.append("receipt_candidate is advisory only and not receipt authority.")
    else:
        return ProgressReceiptPlan(
            operation_id=operation_id,
            eligible=ProgressReceiptEligibility(
                eligible=False,
                reason="Progress events are not marked as receipt candidates.",
                warnings=tuple(warnings),
                receipt_kind="reserved_future",
            ),
            receipt_kind="reserved_future",
            events=tuple(sorted_events),
            transcript_summary=terminal.message,
            evidence_refs=tuple(),
            metadata={"terminal_status": terminal.status},
        )

    if any(event.command.startswith("workspace.status") or event.command.startswith("workspace.refresh") for event in sorted_events):
        receipt_kind = "operational_transcript"
    else:
        receipt_kind = "reserved_future"

    if receipt_kind != "operational_transcript":
        return ProgressReceiptPlan(
            operation_id=operation_id,
            eligible=ProgressReceiptEligibility(
                eligible=False,
                reason="Only read-only operational transcripts are eligible in this slice.",
                warnings=tuple(warnings),
                receipt_kind=receipt_kind,
            ),
            receipt_kind=receipt_kind,
            events=tuple(sorted_events),
            transcript_summary=terminal.message,
            evidence_refs=tuple(),
            metadata={"terminal_status": terminal.status},
        )

    if any(event.workspace_path or event.workspace_id for event in sorted_events):
        warnings.append("workspace context is carried through as metadata only.")

    return ProgressReceiptPlan(
        operation_id=operation_id,
        eligible=ProgressReceiptEligibility(
            eligible=True,
            reason="Read-only operational transcript is eligible for future receipt promotion.",
            warnings=tuple(warnings),
            receipt_kind=receipt_kind,
        ),
        receipt_kind=receipt_kind,
        events=tuple(sorted_events),
        transcript_summary=terminal.message,
        evidence_refs=tuple(ref for event in sorted_events for ref in event.evidence_refs),
        metadata={
            "command": first.command,
            "terminal_status": terminal.status,
            "phase": terminal.phase,
        },
    )
