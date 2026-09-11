from django.urls import path

from callouts.views import (
    AnnouncementAIDraftView,
    AnnouncementApproveView,
    AnnouncementCreateView,
    AnnouncementSendView,
    AnnouncementStatsView,
    DeliveryAcknowledgeView,
    DeliveryReadView,
    MyDeliveriesView,
)

urlpatterns = [
    path('announcements/', AnnouncementCreateView.as_view(), name='announcement-create'),
    path(
        'announcements/<int:announcement_id>/ai-draft/',
        AnnouncementAIDraftView.as_view(),
        name='announcement-ai-draft',
    ),
    path(
        'announcements/<int:announcement_id>/approve/',
        AnnouncementApproveView.as_view(),
        name='announcement-approve',
    ),
    path(
        'announcements/<int:announcement_id>/send/',
        AnnouncementSendView.as_view(),
        name='announcement-send',
    ),
    path(
        'announcements/<int:announcement_id>/stats/',
        AnnouncementStatsView.as_view(),
        name='announcement-stats',
    ),
    path('me/deliveries/', MyDeliveriesView.as_view(), name='my-deliveries'),
    path(
        'deliveries/<int:delivery_id>/read/',
        DeliveryReadView.as_view(),
        name='delivery-read',
    ),
    path(
        'deliveries/<int:delivery_id>/acknowledge/',
        DeliveryAcknowledgeView.as_view(),
        name='delivery-acknowledge',
    ),
]
