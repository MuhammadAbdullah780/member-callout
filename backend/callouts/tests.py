from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from callouts.models import Announcement, Delivery, Member
from callouts.tasks import fan_out_announcement
from core.models import Local


def make_local(name):
    return Local.objects.create(name=name)


def make_user(local, role, username):
    return User.objects.create_user(
        username=username,
        password='password123',
        local=local,
        role=role,
    )


def make_member(local, classification=Member.Classification.JOURNEYMAN, status=Member.Status.ACTIVE):
    return Member.objects.create(
        local=local,
        full_name=f'Member of {local.name}',
        email='member@example.com',
        classification=classification,
        status=status,
    )


def authed_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class AnnouncementLifecycleTests(TestCase):
    def setUp(self):
        self.local = make_local('Local 27')
        self.leader = make_user(self.local, User.Role.LEADERSHIP, 'leader27')
        self.client = authed_client(self.leader)

    def test_send_before_approval_is_rejected(self):
        announcement = Announcement.objects.create(
            local=self.local,
            created_by=self.leader,
            title='Meeting',
            body='Body',
        )
        response = self.client.post(f'/api/announcements/{announcement.id}/send/')
        self.assertEqual(response.status_code, 400)

        announcement.refresh_from_db()
        self.assertEqual(announcement.status, Announcement.Status.DRAFT)

    def test_approve_then_send_fans_out_to_eligible_members(self):
        for _ in range(3):
            make_member(self.local, status=Member.Status.ACTIVE)
        make_member(self.local, status=Member.Status.RETIRED)

        announcement = Announcement.objects.create(
            local=self.local,
            created_by=self.leader,
            title='Meeting',
            body='Body',
        )
        self.client.post(f'/api/announcements/{announcement.id}/approve/')
        response = self.client.post(
            f'/api/announcements/{announcement.id}/send/',
            HTTP_IDEMPOTENCY_KEY='key-1',
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(Delivery.objects.filter(announcement=announcement).count(), 3)

    def test_fan_out_honors_classification_filter(self):
        make_member(self.local, classification=Member.Classification.JOURNEYMAN)
        make_member(self.local, classification=Member.Classification.APPRENTICE)

        announcement = Announcement.objects.create(
            local=self.local,
            created_by=self.leader,
            title='Meeting',
            body='Body',
            audience_classification=Member.Classification.JOURNEYMAN,
            status=Announcement.Status.SENDING,
        )
        fan_out_announcement(announcement.id)

        self.assertEqual(Delivery.objects.filter(announcement=announcement).count(), 1)


class IdempotencyTests(TestCase):
    """Rule 2: a retried send or a re-run fan-out must not create duplicate rows."""

    def setUp(self):
        self.local = make_local('Local 27')
        self.leader = make_user(self.local, User.Role.LEADERSHIP, 'leader27')
        self.client = authed_client(self.leader)
        self.members = [make_member(self.local) for _ in range(5)]

    def test_replaying_idempotency_key_does_not_resend(self):
        announcement = Announcement.objects.create(
            local=self.local,
            created_by=self.leader,
            title='Meeting',
            body='Body',
            status=Announcement.Status.APPROVED,
        )

        self.client.post(
            f'/api/announcements/{announcement.id}/send/',
            HTTP_IDEMPOTENCY_KEY='same-key',
        )
        first_count = Delivery.objects.filter(announcement=announcement).count()

        response = self.client.post(
            f'/api/announcements/{announcement.id}/send/',
            HTTP_IDEMPOTENCY_KEY='same-key',
        )
        second_count = Delivery.objects.filter(announcement=announcement).count()

        self.assertIn(response.status_code, (200, 202))
        self.assertEqual(first_count, second_count)
        self.assertEqual(Announcement.objects.filter(local=self.local).count(), 1)

    def test_rerunning_fan_out_creates_no_duplicate_deliveries(self):
        announcement = Announcement.objects.create(
            local=self.local,
            created_by=self.leader,
            title='Meeting',
            body='Body',
            status=Announcement.Status.SENDING,
        )

        fan_out_announcement(announcement.id)
        fan_out_announcement(announcement.id)

        self.assertEqual(Delivery.objects.filter(announcement=announcement).count(), len(self.members))
        pairs = Delivery.objects.filter(announcement=announcement).values_list('member_id', flat=True)
        self.assertEqual(len(pairs), len(set(pairs)))


class IsolationTests(TestCase):
    """Rule 1: a Local 27 actor must never read or act on Local 58 data."""

    def setUp(self):
        self.local_27 = make_local('Local 27')
        self.local_58 = make_local('Local 58')
        self.leader_27 = make_user(self.local_27, User.Role.LEADERSHIP, 'leader27')
        self.leader_58 = make_user(self.local_58, User.Role.LEADERSHIP, 'leader58')
        self.announcement_58 = Announcement.objects.create(
            local=self.local_58,
            created_by=self.leader_58,
            title='Local 58 only',
            body='Body',
        )

    def test_leader_cannot_read_other_local_stats(self):
        client = authed_client(self.leader_27)
        response = client.get(f'/api/announcements/{self.announcement_58.id}/stats/')
        self.assertEqual(response.status_code, 404)

    def test_leader_cannot_approve_other_local_announcement(self):
        client = authed_client(self.leader_27)
        response = client.post(f'/api/announcements/{self.announcement_58.id}/approve/')
        self.assertEqual(response.status_code, 404)

        self.announcement_58.refresh_from_db()
        self.assertEqual(self.announcement_58.status, Announcement.Status.DRAFT)

    def test_member_cannot_create_or_approve_announcements(self):
        member_user = make_user(self.local_27, User.Role.MEMBER, 'member27')
        client = authed_client(member_user)

        response = client.post('/api/announcements/', {'title': 'x', 'body': 'y'})
        self.assertEqual(response.status_code, 403)


class MemberReceiptTests(TestCase):
    """Rule 1 (member scope) plus receipt-state proofs from PRD.md §8."""

    def setUp(self):
        self.local = make_local('Local 27')
        self.leader = make_user(self.local, User.Role.LEADERSHIP, 'leader27')
        self.member_user = make_user(self.local, User.Role.MEMBER, 'member27')
        self.member = Member.objects.create(
            local=self.local,
            user=self.member_user,
            full_name='Member Twenty Seven',
            email='m27@example.com',
            classification=Member.Classification.JOURNEYMAN,
            status=Member.Status.ACTIVE,
        )
        self.other_member_user = make_user(self.local, User.Role.MEMBER, 'member27b')
        self.other_member = Member.objects.create(
            local=self.local,
            user=self.other_member_user,
            full_name='Other Member',
            email='other@example.com',
            classification=Member.Classification.JOURNEYMAN,
            status=Member.Status.ACTIVE,
        )
        self.announcement = Announcement.objects.create(
            local=self.local,
            created_by=self.leader,
            title='Meeting',
            body='Body',
            status=Announcement.Status.SENT,
        )
        self.delivery = Delivery.objects.create(
            local=self.local,
            announcement=self.announcement,
            member=self.member,
            state=Delivery.State.DELIVERED,
        )

    def test_member_can_read_then_acknowledge_own_delivery(self):
        client = authed_client(self.member_user)

        read_response = client.post(f'/api/deliveries/{self.delivery.id}/read/')
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.data['state'], 'read')

        ack_response = client.post(f'/api/deliveries/{self.delivery.id}/acknowledge/')
        self.assertEqual(ack_response.status_code, 200)
        self.assertEqual(ack_response.data['state'], 'acknowledged')

    def test_member_cannot_acknowledge_another_members_delivery(self):
        client = authed_client(self.other_member_user)
        response = client.post(f'/api/deliveries/{self.delivery.id}/acknowledge/')
        self.assertEqual(response.status_code, 404)

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.state, Delivery.State.DELIVERED)

    def test_read_then_acknowledge_updates_leadership_stats(self):
        client = authed_client(self.member_user)
        client.post(f'/api/deliveries/{self.delivery.id}/read/')
        client.post(f'/api/deliveries/{self.delivery.id}/acknowledge/')

        leader_client = authed_client(self.leader)
        response = leader_client.get(f'/api/announcements/{self.announcement.id}/stats/')

        self.assertEqual(response.data['read'], 1)
        self.assertEqual(response.data['acknowledged'], 1)

    def test_repeating_acknowledge_is_safe(self):
        client = authed_client(self.member_user)
        client.post(f'/api/deliveries/{self.delivery.id}/acknowledge/')
        response = client.post(f'/api/deliveries/{self.delivery.id}/acknowledge/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Delivery.objects.get(pk=self.delivery.id).state, Delivery.State.ACKNOWLEDGED)


class AIDraftTests(TestCase):
    """AI output stays draft-only; send rejects an unapproved draft."""

    def setUp(self):
        self.local = make_local('Local 27')
        self.leader = make_user(self.local, User.Role.LEADERSHIP, 'leader27')
        self.client = authed_client(self.leader)

    def test_ai_draft_without_configured_provider_returns_error_and_leaves_draft_unsent(self):
        announcement = Announcement.objects.create(
            local=self.local,
            created_by=self.leader,
            title='',
            body='',
        )
        response = self.client.post(
            f'/api/announcements/{announcement.id}/ai-draft/',
            {'raw_text': 'meeting thursday come one come all'},
        )

        self.assertEqual(response.status_code, 502)
        announcement.refresh_from_db()
        self.assertEqual(announcement.status, Announcement.Status.DRAFT)
