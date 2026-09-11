"""
Tenant-scoped queryset helpers.

Every lookup of a tenant-owned row must go through one of these instead of
`Model.objects.get(...)`, so a forgotten scope fails closed (404) rather than
leaking another local's data. Never trust a local_id from the request body,
query params, or URL - always scope by `request.user.local_id`.
"""

from callouts.models import Announcement, Delivery, Member


def announcements_for_local(local_id):
    return Announcement.objects.filter(local_id=local_id)


def members_for_local(local_id):
    return Member.objects.filter(local_id=local_id)


def deliveries_for_local(local_id):
    return Delivery.objects.filter(local_id=local_id)


def deliveries_for_member(member):
    """A member may only ever see their own deliveries, regardless of local scope."""
    return Delivery.objects.filter(member=member)
