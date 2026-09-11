import uuid

from django.conf import settings
from django.db import models


class Member(models.Model):
    """A union member. Distinct from `accounts.User`: not every member has a login."""

    class Classification(models.TextChoices):
        JOURNEYMAN = 'journeyman', 'Journeyman'
        APPRENTICE = 'apprentice', 'Apprentice'
        FOREMAN = 'foreman', 'Foreman'
        RETIREE = 'retiree', 'Retiree'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        RETIRED = 'retired', 'Retired'
        SUSPENDED = 'suspended', 'Suspended'

    local = models.ForeignKey(
        'core.Local',
        on_delete=models.CASCADE,
        related_name='members',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='member_profile',
        null=True,
        blank=True,
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    classification = models.CharField(max_length=20, choices=Classification.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['local', 'status']),
            models.Index(fields=['local', 'classification']),
        ]

    def __str__(self):
        return self.full_name


class Announcement(models.Model):
    """A leadership message, targeted at a local (optionally narrowed by classification)."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        APPROVED = 'approved', 'Approved'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        CANCELLED = 'cancelled', 'Cancelled'

    local = models.ForeignKey(
        'core.Local',
        on_delete=models.CASCADE,
        related_name='announcements',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='announcements_created',
    )
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    push_preview = models.CharField(max_length=120, blank=True)
    audience_classification = models.CharField(
        max_length=20,
        choices=Member.Classification.choices,
        blank=True,
    )
    needs_ack = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='announcements_approved',
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    client_idempotency_key = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['local', 'client_idempotency_key'],
                condition=~models.Q(client_idempotency_key=''),
                name='unique_local_idempotency_key',
            ),
        ]
        indexes = [
            models.Index(fields=['local', 'status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f'Announcement {self.pk}'


class Delivery(models.Model):
    """One recipient's copy of an announcement. The unit of idempotency and status tracking."""

    class State(models.TextChoices):
        PENDING = 'pending', 'Pending'
        DELIVERED = 'delivered', 'Delivered'
        READ = 'read', 'Read'
        ACKNOWLEDGED = 'acknowledged', 'Acknowledged'
        FAILED = 'failed', 'Failed'

    class Rsvp(models.TextChoices):
        COMING = 'coming', 'Coming'
        CANNOT_ATTEND = 'cannot_attend', 'Cannot attend'

    local = models.ForeignKey(
        'core.Local',
        on_delete=models.CASCADE,
        related_name='deliveries',
    )
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='deliveries',
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='deliveries',
    )
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    rsvp = models.CharField(max_length=20, choices=Rsvp.choices, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['announcement', 'member'],
                name='unique_delivery_per_announcement_member',
            ),
        ]
        indexes = [
            models.Index(fields=['announcement', 'state']),
            models.Index(fields=['member', 'state']),
        ]

    def __str__(self):
        return f'Delivery({self.announcement_id}, {self.member_id})'


class DeliveryEvent(models.Model):
    """Immutable audit trail of a delivery's state and RSVP changes."""

    class Type(models.TextChoices):
        DELIVERED = 'delivered', 'Delivered'
        READ = 'read', 'Read'
        ACKNOWLEDGED = 'acknowledged', 'Acknowledged'
        RSVP_RECORDED = 'rsvp_recorded', 'RSVP recorded'
        FAILED = 'failed', 'Failed'

    delivery = models.ForeignKey(
        Delivery,
        on_delete=models.CASCADE,
        related_name='events',
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='delivery_events',
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['delivery', 'type']),
        ]
        ordering = ['occurred_at']

    def __str__(self):
        return f'{self.type} @ {self.occurred_at}'


class OutboxEvent(models.Model):
    """Durable record of a side effect to publish, written in the same transaction as its cause."""

    class Type(models.TextChoices):
        ANNOUNCEMENT_SEND = 'announcement.send', 'Announcement send'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, choices=Type.choices)
    aggregate_id = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['published_at']),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f'{self.type}({self.aggregate_id})'


class NotificationAttempt(models.Model):
    """A logged/simulated push attempt for one delivery."""

    class Status(models.TextChoices):
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    delivery = models.ForeignKey(
        Delivery,
        on_delete=models.CASCADE,
        related_name='notification_attempts',
    )
    provider = models.CharField(max_length=50, default='log')
    status = models.CharField(max_length=20, choices=Status.choices)
    attempted_at = models.DateTimeField(auto_now_add=True)
    provider_message_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['delivery', 'attempted_at']),
        ]
        ordering = ['attempted_at']

    def __str__(self):
        return f'NotificationAttempt({self.delivery_id}, {self.status})'
