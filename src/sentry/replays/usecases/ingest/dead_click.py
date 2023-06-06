import datetime
import logging
from typing import Any, Dict

from sentry.issues.grouptype import ReplayDeadClickType
from sentry.replays.usecases.ingest.events import SentryEvent
from sentry.replays.usecases.issue import new_issue_occurrence

logger = logging.getLogger()


def report_dead_click_issue(project_id: int, replay_id: str, event: SentryEvent) -> bool:
    payload = event["data"]["payload"]

    # Only timeout reasons on <a> and <button> tags are accepted.
    if payload["data"]["endReason"] != "timeout":
        return False
    elif payload["data"]["node"]["tagName"] not in ("a", "button"):
        return False

    # Seconds since epoch is UTC.
    timestamp = datetime.datetime.fromtimestamp(payload["timestamp"])
    timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)

    _report_dead_click_issue(
        culprit=payload["message"].split(" > ")[-1],
        environment="prod",
        fingerprint=payload["message"],
        project_id=project_id,
        subtitle=payload["message"],
        timestamp=timestamp,
        extra_event_data={
            "contexts": {"replay": {"replay_id": replay_id}},
            "level": "warning",
            "tags": {"replayId": replay_id, "url": payload["data"]["url"]},
            "user": {
                "id": "1",
                "username": "Test User",
                "email": "test.user@sentry.io",
            },
        },
    )

    # Log dead click events.
    log = event["data"].get("payload", {}).copy()
    log["project_id"] = project_id
    log["replay_id"] = replay_id
    log["dom_tree"] = log.pop("message")
    logger.info("sentry.replays.dead_click", extra=log)

    return True


def _report_dead_click_issue(
    culprit: str,
    environment: str,
    fingerprint: str,
    project_id: int,
    subtitle: str,
    timestamp: datetime.datetime,
    extra_event_data: Dict[str, Any],
) -> None:
    """Produce a new dead click issue occurence to Kafka."""
    new_issue_occurrence(
        environment=environment,
        fingerprint=[fingerprint],
        issue_type=ReplayDeadClickType,
        level="warning",
        platform="javascript",
        project_id=project_id,
        subtitle=subtitle,
        timestamp=timestamp,
        title="Suspected Dead Click",
        culprit=culprit,
        extra_event_data=extra_event_data,
    )