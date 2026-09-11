"""
Re-runnable seed data for reviewers.

Creates Local 27 (~2,000 members) and Local 58 (~200 members), classifications,
active/retired/suspended members, one leader and one member login per local,
and one already-sent Local 27 announcement with its delivery rows.

Safe to run more than once: every object is looked up by a stable natural key
(local name, username, announcement title) via get_or_create, so re-running
does not create duplicates.
"""

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from callouts.models import Announcement, Delivery, Member, NotificationAttempt

SEED_PASSWORD = 'crewlink-dev-2026'

LOCAL_27_MEMBER_COUNT = 2000
LOCAL_58_MEMBER_COUNT = 200

CLASSIFICATIONS = [
    Member.Classification.JOURNEYMAN,
    Member.Classification.APPRENTICE,
    Member.Classification.FOREMAN,
    Member.Classification.RETIREE,
]


class Command(BaseCommand):
    help = 'Seed deterministic locals, members, users, and one sent announcement.'

    @transaction.atomic
    def handle(self, *args, **options):
        local_27 = self._seed_local('Local 27')
        local_58 = self._seed_local('Local 58')

        self._seed_members(local_27, LOCAL_27_MEMBER_COUNT)
        self._seed_members(local_58, LOCAL_58_MEMBER_COUNT)

        leader_27 = self._seed_user('leader27', local_27, User.Role.LEADERSHIP)
        member_27_user, member_27 = self._seed_member_login(
            'member27', local_27, 'Sample Member 27',
        )
        leader_58 = self._seed_user('leader58', local_58, User.Role.LEADERSHIP)
        member_58_user, member_58 = self._seed_member_login(
            'member58', local_58, 'Sample Member 58',
        )

        announcement = self._seed_sent_announcement(local_27, leader_27)

        self.stdout.write(self.style.SUCCESS('Seed complete.'))
        self.stdout.write('')
        self.stdout.write('## TEST ACCOUNTS')
        self.stdout.write(f'  Local 27 leader:  leader27 / {SEED_PASSWORD}')
        self.stdout.write(f'  Local 27 member:  member27 / {SEED_PASSWORD} (member id {member_27.id})')
        self.stdout.write(f'  Local 58 leader:  leader58 / {SEED_PASSWORD}')
        self.stdout.write(f'  Local 58 member:  member58 / {SEED_PASSWORD} (member id {member_58.id})')
        self.stdout.write(f'  Sent announcement (Local 27): id {announcement.id}')

    def _seed_local(self, name):
        from core.models import Local

        local, _ = Local.objects.get_or_create(name=name)
        return local

    def _seed_members(self, local, count):
        existing = Member.objects.filter(local=local).count()
        if existing >= count:
            return

        statuses = (
            [Member.Status.ACTIVE] * 8
            + [Member.Status.RETIRED] * 1
            + [Member.Status.SUSPENDED] * 1
        )

        members = [
            Member(
                local=local,
                full_name=f'{local.name} Member {i:05d}',
                email=f'{local.name.lower().replace(" ", "")}.member{i:05d}@example.com',
                classification=CLASSIFICATIONS[i % len(CLASSIFICATIONS)],
                status=statuses[i % len(statuses)],
            )
            for i in range(existing, count)
        ]
        Member.objects.bulk_create(members, batch_size=500)

    def _seed_user(self, username, local, role):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'local': local,
                'role': role,
                'password': make_password(SEED_PASSWORD),
            },
        )
        if not created:
            user.local = local
            user.role = role
            user.set_password(SEED_PASSWORD)
            user.save(update_fields=['local', 'role', 'password'])
        return user

    def _seed_member_login(self, username, local, full_name):
        user = self._seed_user(username, local, User.Role.MEMBER)
        member, _ = Member.objects.get_or_create(
            user=user,
            defaults={
                'local': local,
                'full_name': full_name,
                'email': f'{username}@example.com',
                'classification': Member.Classification.JOURNEYMAN,
                'status': Member.Status.ACTIVE,
            },
        )
        return user, member

    def _seed_sent_announcement(self, local, leader):
        announcement, created = Announcement.objects.get_or_create(
            local=local,
            title='Emergency Membership Meeting - Seeded',
            defaults={
                'created_by': leader,
                'body': 'All active members: report to the union hall Thursday at 6pm.',
                'push_preview': 'Emergency meeting Thursday 6pm - see details in app.',
                'needs_ack': True,
                'status': Announcement.Status.SENT,
                'approved_by': leader,
                'approved_at': timezone.now(),
                'sent_at': timezone.now(),
            },
        )
        if not created:
            return announcement

        active_members = Member.objects.filter(local=local, status=Member.Status.ACTIVE)
        deliveries = [
            Delivery(
                local=local,
                announcement=announcement,
                member=member,
                state=Delivery.State.DELIVERED,
                delivered_at=timezone.now(),
            )
            for member in active_members
        ]
        Delivery.objects.bulk_create(deliveries, batch_size=500)

        attempts = [
            NotificationAttempt(delivery=delivery, provider='log', status=NotificationAttempt.Status.SENT)
            for delivery in Delivery.objects.filter(announcement=announcement)
        ]
        NotificationAttempt.objects.bulk_create(attempts, batch_size=500)

        return announcement
