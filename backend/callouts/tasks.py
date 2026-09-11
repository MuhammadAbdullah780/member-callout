"""
Fan-out and notification tasks.

Rule 2 (no double delivery) lives here: batched inserts rely on the database's
unique (announcement_id, member_id) constraint, so a retried task or a task
running on two workers concurrently still produces exactly one Delivery row
per eligible member.
"""

from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone

from config.celery import app
from callouts.models import Announcement, Delivery, Member, NotificationAttempt

FAN_OUT_BATCH_SIZE = 500


@app.task
def fan_out_announcement(announcement_id):
    """Expands an approved, sending announcement into one Delivery row per eligible member."""
    announcement = Announcement.objects.select_related('local').get(pk=announcement_id)

    members = Member.objects.filter(
        local_id=announcement.local_id,
        status=Member.Status.ACTIVE,
    )
    if announcement.audience_classification:
        members = members.filter(classification=announcement.audience_classification)

    member_ids = list(members.values_list('id', flat=True).order_by('id'))

    for start in range(0, len(member_ids), FAN_OUT_BATCH_SIZE):
        batch_ids = member_ids[start:start + FAN_OUT_BATCH_SIZE]
        _insert_delivery_batch(announcement, batch_ids)

    announcement.status = Announcement.Status.SENT
    announcement.save(update_fields=['status'])


def _insert_delivery_batch(announcement, member_ids):
    for member_id in member_ids:
        try:
            with transaction.atomic():
                delivery = Delivery.objects.create(
                    local_id=announcement.local_id,
                    announcement=announcement,
                    member_id=member_id,
                    state=Delivery.State.DELIVERED,
                    delivered_at=timezone.now(),
                )
        except IntegrityError:
            # Already inserted by a previous attempt at this batch - safe to skip.
            continue

        notify_delivery.delay(delivery.id)


@app.task
def notify_delivery(delivery_id):
    """Logs a simulated push notification attempt for one delivery."""
    already_attempted = NotificationAttempt.objects.filter(delivery_id=delivery_id).exists()
    if already_attempted:
        return

    NotificationAttempt.objects.create(
        delivery_id=delivery_id,
        provider='log',
        status=NotificationAttempt.Status.SENT,
    )
