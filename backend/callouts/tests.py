from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from callouts import ai_provider
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

    @patch.dict('os.environ', {'AI_PROVIDER_API_KEY': ''}, clear=False)
    def test_ai_draft_without_configured_provider_returns_error_and_leaves_draft_unsent(self):
        # The env var is cleared explicitly: this test must assert the
        # unconfigured path whether or not the developer has a real key set,
        # and must never reach the network.
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


class AIDraftApprovalGateTests(TestCase):
    """Generated text must never reach members without a human approving it."""

    FAKE_DRAFT = {
        'title': 'AI TITLE',
        'body': 'AI BODY',
        'push_preview': 'AI PUSH',
    }

    def setUp(self):
        self.local = make_local('Local 27')
        self.leader = make_user(self.local, User.Role.LEADERSHIP, 'leader27')
        self.client = authed_client(self.leader)

    def _announcement(self, status):
        return Announcement.objects.create(
            local=self.local,
            created_by=self.leader,
            title='Human title',
            body='Human body',
            status=status,
        )

    @patch('callouts.views.generate_draft')
    def test_ai_draft_rewrites_a_draft(self, mock_generate):
        mock_generate.return_value = self.FAKE_DRAFT
        announcement = self._announcement(Announcement.Status.DRAFT)

        response = self.client.post(
            f'/api/announcements/{announcement.id}/ai-draft/',
            {'raw_text': 'messy note'},
        )

        self.assertEqual(response.status_code, 200)
        announcement.refresh_from_db()
        self.assertEqual(announcement.title, 'AI TITLE')
        self.assertEqual(announcement.status, Announcement.Status.DRAFT)

    @patch('callouts.views.generate_draft')
    def test_ai_draft_cannot_rewrite_an_approved_announcement(self, mock_generate):
        mock_generate.return_value = self.FAKE_DRAFT
        announcement = self._announcement(Announcement.Status.APPROVED)

        response = self.client.post(
            f'/api/announcements/{announcement.id}/ai-draft/',
            {'raw_text': 'messy note'},
        )

        self.assertEqual(response.status_code, 400)
        announcement.refresh_from_db()
        self.assertEqual(announcement.title, 'Human title')
        mock_generate.assert_not_called()

    @patch('callouts.views.generate_draft')
    def test_ai_draft_cannot_rewrite_a_sent_announcement(self, mock_generate):
        mock_generate.return_value = self.FAKE_DRAFT
        announcement = self._announcement(Announcement.Status.SENT)

        response = self.client.post(
            f'/api/announcements/{announcement.id}/ai-draft/',
            {'raw_text': 'messy note'},
        )

        self.assertEqual(response.status_code, 400)
        announcement.refresh_from_db()
        self.assertEqual(announcement.title, 'Human title')
        mock_generate.assert_not_called()


class AIProviderAdapterTests(TestCase):
    """A degraded provider must surface a clean error, never a 500."""

    def setUp(self):
        self.local = make_local('Local 27')
        self.leader = make_user(self.local, User.Role.LEADERSHIP, 'leader27')
        self.client = authed_client(self.leader)
        self.announcement = Announcement.objects.create(
            local=self.local, created_by=self.leader, title='', body='',
        )

    def _post_draft(self):
        return self.client.post(
            f'/api/announcements/{self.announcement.id}/ai-draft/',
            {'raw_text': 'meeting thursday come one come all'},
        )

    @patch.dict('os.environ', {'AI_PROVIDER_API_KEY': 'test-key', 'AI_PROVIDER_MODEL': 'm1'})
    @patch('callouts.ai_provider.time.sleep', lambda _seconds: None)
    @patch('callouts.ai_provider.requests.post')
    def test_empty_content_from_reasoning_model_returns_502_not_500(self, mock_post):
        # A 200 whose token budget went entirely to the hidden reasoning channel.
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': None, 'reasoning': 'thinking...'}}],
        }

        response = self._post_draft()

        self.assertEqual(response.status_code, 502)
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.status, Announcement.Status.DRAFT)
        self.assertEqual(self.announcement.title, '')

    @patch.dict('os.environ', {'AI_PROVIDER_API_KEY': 'test-key', 'AI_PROVIDER_MODEL': 'm1'})
    @patch('callouts.ai_provider.time.sleep', lambda _seconds: None)
    @patch('callouts.ai_provider.requests.post')
    def test_rate_limited_provider_is_retried_then_reported(self, mock_post):
        mock_post.return_value.status_code = 429

        response = self._post_draft()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(mock_post.call_count, ai_provider.ATTEMPTS_PER_MODEL)

    @patch.dict('os.environ', {'AI_PROVIDER_API_KEY': 'test-key', 'AI_PROVIDER_MODEL': 'm1,m2'})
    @patch('callouts.ai_provider.time.sleep', lambda _seconds: None)
    @patch('callouts.ai_provider.requests.post')
    def test_falls_back_to_the_next_model_when_the_first_is_unavailable(self, mock_post):
        unavailable = _FakeResponse(404, {})
        good = _FakeResponse(200, {
            'choices': [{'message': {'content': 'TITLE: T\nBODY: B\nPUSH: P'}}],
        })
        mock_post.side_effect = [unavailable, good]

        response = self._post_draft()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'T')

    @patch.dict('os.environ', {'AI_PROVIDER_API_KEY': 'test-key', 'AI_PROVIDER_MODEL': 'm1'})
    @patch('callouts.ai_provider.time.sleep', lambda _seconds: None)
    @patch('callouts.ai_provider.requests.post')
    def test_push_preview_is_truncated_to_120_characters(self, mock_post):
        mock_post.return_value = _FakeResponse(200, {
            'choices': [{'message': {'content': 'TITLE: T\nBODY: B\nPUSH: ' + 'x' * 300}}],
        })

        response = self._post_draft()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['push_preview']), 120)


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class SendIdempotencyHeaderTests(TestCase):
    """The send endpoint requires an Idempotency-Key, as the README documents."""

    def setUp(self):
        self.local = make_local('Local 27')
        self.leader = make_user(self.local, User.Role.LEADERSHIP, 'leader27')
        self.client = authed_client(self.leader)
        make_member(self.local)

    def _approved(self):
        announcement = Announcement.objects.create(
            local=self.local, created_by=self.leader, title='T', body='B',
        )
        self.client.post(f'/api/announcements/{announcement.id}/approve/')
        return announcement

    def test_send_without_the_header_is_rejected(self):
        announcement = self._approved()

        response = self.client.post(f'/api/announcements/{announcement.id}/send/')

        self.assertEqual(response.status_code, 400)
        announcement.refresh_from_db()
        self.assertEqual(announcement.status, Announcement.Status.APPROVED)
        self.assertEqual(Delivery.objects.count(), 0)

    def test_losing_the_cross_instance_race_returns_409_not_500(self):
        """
        Behind a load balancer two instances can both pass the pre-check before
        either writes. Simulate that by neutralising the pre-check so only the
        database constraint is left to arbitrate.
        """
        winner = self._approved()
        self.client.post(
            f'/api/announcements/{winner.id}/send/', HTTP_IDEMPOTENCY_KEY='contended-key',
        )
        loser = self._approved()

        with patch('callouts.views.announcements_for_local') as mock_scope:
            # First call resolves the announcement; the conflict pre-check then
            # reports "no conflict", exactly as it would in a lost race.
            real_queryset = Announcement.objects.filter(local_id=self.local.id)
            mock_scope.side_effect = [real_queryset, Announcement.objects.none()]

            response = self.client.post(
                f'/api/announcements/{loser.id}/send/',
                HTTP_IDEMPOTENCY_KEY='contended-key',
            )

        self.assertEqual(response.status_code, 409)
        loser.refresh_from_db()
        self.assertEqual(loser.status, Announcement.Status.APPROVED)
        self.assertEqual(loser.client_idempotency_key, '')

    def test_reusing_a_key_for_a_different_announcement_conflicts(self):
        first = self._approved()
        self.client.post(
            f'/api/announcements/{first.id}/send/', HTTP_IDEMPOTENCY_KEY='shared-key',
        )
        second = self._approved()

        response = self.client.post(
            f'/api/announcements/{second.id}/send/', HTTP_IDEMPOTENCY_KEY='shared-key',
        )

        self.assertEqual(response.status_code, 409)
        second.refresh_from_db()
        self.assertEqual(second.status, Announcement.Status.APPROVED)
