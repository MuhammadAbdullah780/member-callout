from django.contrib import admin

from callouts.models import (
    Announcement,
    Delivery,
    DeliveryEvent,
    Member,
    NotificationAttempt,
    OutboxEvent,
)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'local', 'classification', 'status')
    list_filter = ('local', 'classification', 'status')
    search_fields = ('full_name', 'email')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'local', 'status', 'created_by', 'sent_at')
    list_filter = ('local', 'status')
    search_fields = ('title',)


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('announcement', 'member', 'state', 'rsvp')
    list_filter = ('local', 'state')


@admin.register(DeliveryEvent)
class DeliveryEventAdmin(admin.ModelAdmin):
    list_display = ('delivery', 'type', 'occurred_at', 'actor_user')
    list_filter = ('type',)


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'aggregate_id', 'created_at', 'published_at')
    list_filter = ('type',)


@admin.register(NotificationAttempt)
class NotificationAttemptAdmin(admin.ModelAdmin):
    list_display = ('delivery', 'provider', 'status', 'attempted_at')
    list_filter = ('status', 'provider')
