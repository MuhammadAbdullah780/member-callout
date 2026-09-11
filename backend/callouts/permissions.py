from rest_framework.permissions import BasePermission

from accounts.models import User


class IsLeadership(BasePermission):
    """Restricts a view to authenticated leadership users of any local."""

    message = 'Only leadership may perform this action.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.LEADERSHIP
        )


class IsMember(BasePermission):
    """Restricts a view to authenticated member users of any local."""

    message = 'Only members may perform this action.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.MEMBER
        )
