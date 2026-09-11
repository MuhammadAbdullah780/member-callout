from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from callouts.ai_provider import AIProviderError, generate_draft
from callouts.models import Announcement, Delivery, DeliveryEvent
from callouts.permissions import IsLeadership, IsMember
from callouts.querysets import announcements_for_local, deliveries_for_member
from callouts.serializers import (
    AIDraftRequestSerializer,
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
    AnnouncementStatsSerializer,
    DeliverySerializer,
)
from callouts.tasks import fan_out_announcement


def _announcement_for_actor(request, announcement_id):
    """Fetches an announcement scoped to the caller's own local, or 404s."""
    return get_object_or_404(
        announcements_for_local(request.user.local_id),
        pk=announcement_id,
    )


class AnnouncementCreateView(APIView):
    """POST /api/announcements/ - leader creates a draft announcement."""

    permission_classes = (IsAuthenticated, IsLeadership)

    def post(self, request):
        serializer = AnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = Announcement.objects.create(
            local_id=request.user.local_id,
            created_by=request.user,
            **serializer.validated_data,
        )
        return Response(
            AnnouncementSerializer(announcement).data,
            status=status.HTTP_201_CREATED,
        )


class AnnouncementAIDraftView(APIView):
    """POST /api/announcements/{id}/ai-draft/ - AI-clean messy source text into a draft."""

    permission_classes = (IsAuthenticated, IsLeadership)

    def post(self, request, announcement_id):
        announcement = _announcement_for_actor(request, announcement_id)

        request_serializer = AIDraftRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        try:
            draft = generate_draft(request_serializer.validated_data['raw_text'])
        except AIProviderError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        announcement.title = draft['title']
        announcement.body = draft['body']
        announcement.push_preview = draft['push_preview']
        announcement.save(update_fields=['title', 'body', 'push_preview'])

        return Response(AnnouncementSerializer(announcement).data)


class AnnouncementApproveView(APIView):
    """POST /api/announcements/{id}/approve/ - leader approves the displayed draft."""

    permission_classes = (IsAuthenticated, IsLeadership)

    def post(self, request, announcement_id):
        announcement = _announcement_for_actor(request, announcement_id)

        if announcement.status != Announcement.Status.DRAFT:
            raise ValidationError('Only a draft announcement can be approved.')

        announcement.status = Announcement.Status.APPROVED
        announcement.approved_by = request.user
        announcement.approved_at = timezone.now()
        announcement.save(update_fields=['status', 'approved_by', 'approved_at'])

        return Response(AnnouncementSerializer(announcement).data)


class AnnouncementSendView(APIView):
    """
    POST /api/announcements/{id}/send/ - leader sends an approved announcement.

    Rule 2: the Idempotency-Key header, combined with the (local, key) unique
    constraint on Announcement, means a retried request resolves to the same
    announcement instead of starting a second send.
    """

    permission_classes = (IsAuthenticated, IsLeadership)

    def post(self, request, announcement_id):
        idempotency_key = request.headers.get('Idempotency-Key', '')
        announcement = _announcement_for_actor(request, announcement_id)

        if announcement.status == Announcement.Status.SENDING:
            return Response(
                AnnouncementSerializer(announcement).data,
                status=status.HTTP_202_ACCEPTED,
            )
        if announcement.status == Announcement.Status.SENT:
            return Response(AnnouncementSerializer(announcement).data)
        if announcement.status != Announcement.Status.APPROVED:
            raise ValidationError('Only an approved announcement can be sent.')

        if idempotency_key:
            announcement.client_idempotency_key = idempotency_key
        announcement.status = Announcement.Status.SENDING
        announcement.sent_at = timezone.now()
        announcement.save(update_fields=['client_idempotency_key', 'status', 'sent_at'])

        fan_out_announcement.delay(announcement.id)

        return Response(
            AnnouncementSerializer(announcement).data,
            status=status.HTTP_202_ACCEPTED,
        )


class AnnouncementStatsView(APIView):
    """GET /api/announcements/{id}/stats/ - leader reads sent/read/acknowledged counts."""

    permission_classes = (IsAuthenticated, IsLeadership)

    def get(self, request, announcement_id):
        announcement = _announcement_for_actor(request, announcement_id)
        deliveries = announcement.deliveries

        stats = {
            'sent': deliveries.exclude(state=Delivery.State.PENDING).count(),
            'read': deliveries.filter(
                state__in=[Delivery.State.READ, Delivery.State.ACKNOWLEDGED],
            ).count(),
            'acknowledged': deliveries.filter(state=Delivery.State.ACKNOWLEDGED).count(),
        }
        return Response(AnnouncementStatsSerializer(stats).data)


class MyDeliveriesView(ListAPIView):
    """GET /api/me/deliveries/ - the authenticated member's own inbox."""

    permission_classes = (IsAuthenticated, IsMember)
    serializer_class = DeliverySerializer

    def get_queryset(self):
        member_profile = getattr(self.request.user, 'member_profile', None)
        if member_profile is None:
            return Delivery.objects.none()
        return deliveries_for_member(member_profile).select_related('announcement')


def _delivery_for_member(request, delivery_id):
    """Fetches a delivery owned by the authenticated member only, or 404s."""
    member_profile = getattr(request.user, 'member_profile', None)
    if member_profile is None:
        return None
    return deliveries_for_member(member_profile).filter(pk=delivery_id).first()


class DeliveryReadView(APIView):
    """POST /api/deliveries/{id}/read/ - member marks their own delivery read."""

    permission_classes = (IsAuthenticated, IsMember)

    def post(self, request, delivery_id):
        delivery = _delivery_for_member(request, delivery_id)
        if delivery is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if delivery.state == Delivery.State.DELIVERED:
            delivery.state = Delivery.State.READ
            delivery.read_at = timezone.now()
            delivery.save(update_fields=['state', 'read_at'])
            DeliveryEvent.objects.create(
                delivery=delivery,
                type=DeliveryEvent.Type.READ,
                actor_user=request.user,
            )

        return Response(DeliverySerializer(delivery).data)


class DeliveryAcknowledgeView(APIView):
    """POST /api/deliveries/{id}/acknowledge/ - member acknowledges their own delivery."""

    permission_classes = (IsAuthenticated, IsMember)

    def post(self, request, delivery_id):
        delivery = _delivery_for_member(request, delivery_id)
        if delivery is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if delivery.state != Delivery.State.ACKNOWLEDGED:
            delivery.state = Delivery.State.ACKNOWLEDGED
            delivery.acknowledged_at = timezone.now()
            if delivery.read_at is None:
                delivery.read_at = delivery.acknowledged_at
            delivery.save(update_fields=['state', 'acknowledged_at', 'read_at'])
            DeliveryEvent.objects.create(
                delivery=delivery,
                type=DeliveryEvent.Type.ACKNOWLEDGED,
                actor_user=request.user,
            )

        return Response(DeliverySerializer(delivery).data)
