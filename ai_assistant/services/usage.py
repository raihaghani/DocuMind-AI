"""Daily usage accounting.

Enforces a configurable per-user daily question quota. Consumption is atomic:
``select_for_update`` serializes concurrent attempts so two simultaneous
requests cannot push a user over the limit. The daily boundary uses
``timezone.localdate()`` which respects settings.TIME_ZONE (documented in the
README and docs/engineering-decisions.md).

Accounting policy: a request consumes quota once it is *accepted for answer
processing* (valid form, owned & ready document, quota available). Invalid or
unauthorized requests, and requests rejected because the quota is already
exhausted, do not consume quota. Accepted requests whose provider later fails
or returns "unsupported" DO consume quota (the work was attempted).
"""
from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ai_assistant.models import UsageRecord


def _today():
    return timezone.localdate()


def get_usage_summary(user) -> dict:
    """Return today's usage figures for `user` (read-only)."""
    limit = settings.DAILY_QUESTION_LIMIT
    record = UsageRecord.objects.filter(user=user, date=_today()).first()
    used = record.count if record else 0
    remaining = max(limit - used, 0)
    percent = int(min(used / limit, 1) * 100) if limit else 0
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "percent": percent,
        "at_limit": used >= limit,
    }


def has_quota(user) -> bool:
    return get_usage_summary(user)["remaining"] > 0


def try_consume(user) -> bool:
    """Atomically consume one unit of today's quota.

    Returns True if a unit was consumed, False if the user is already at the
    limit. Safe under concurrency via row-level locking (PostgreSQL); on SQLite
    the database serializes writes, which is sufficient for the MVP.
    """
    limit = settings.DAILY_QUESTION_LIMIT
    today = _today()
    with transaction.atomic():
        record, _ = UsageRecord.objects.select_for_update().get_or_create(
            user=user, date=today
        )
        if record.count >= limit:
            return False
        record.count = F("count") + 1
        record.save(update_fields=["count"])
    return True


def refund(user) -> None:
    """Return one consumed unit (used only if processing is aborted before work).

    Not part of the default flow but available for callers that want to undo a
    consumption. Never drops below zero.
    """
    today = _today()
    with transaction.atomic():
        record = (
            UsageRecord.objects.select_for_update()
            .filter(user=user, date=today)
            .first()
        )
        if record and record.count > 0:
            record.count = F("count") - 1
            record.save(update_fields=["count"])
