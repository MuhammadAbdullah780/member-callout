from rest_framework import serializers

from callouts.models import Announcement, Delivery, Member


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = (
            'id',
            'title',
            'body',
            'push_preview',
            'audience_classification',
            'needs_ack',
            'status',
            'approved_by',
            'approved_at',
            'sent_at',
            'created_at',
        )
        read_only_fields = (
            'id',
            'status',
            'approved_by',
            'approved_at',
            'sent_at',
            'created_at',
        )


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ('title', 'body', 'audience_classification', 'needs_ack')

    def validate_audience_classification(self, value):
        if value and value not in Member.Classification.values:
            raise serializers.ValidationError('Unknown classification.')
        return value


class AIDraftRequestSerializer(serializers.Serializer):
    raw_text = serializers.CharField(allow_blank=False, trim_whitespace=True)


class AnnouncementStatsSerializer(serializers.Serializer):
    sent = serializers.IntegerField()
    read = serializers.IntegerField()
    acknowledged = serializers.IntegerField()


class DeliverySerializer(serializers.ModelSerializer):
    announcement_title = serializers.CharField(source='announcement.title', read_only=True)

    class Meta:
        model = Delivery
        fields = (
            'id',
            'announcement',
            'announcement_title',
            'state',
            'rsvp',
            'delivered_at',
            'read_at',
            'acknowledged_at',
        )
        read_only_fields = fields
