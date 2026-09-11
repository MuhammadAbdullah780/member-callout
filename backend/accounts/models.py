from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Authentication identity. Every user belongs to exactly one local and has one role."""

    class Role(models.TextChoices):
        LEADERSHIP = 'leadership', 'Leadership'
        MEMBER = 'member', 'Member'

    local = models.ForeignKey(
        'core.Local',
        on_delete=models.CASCADE,
        related_name='users',
    )
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        indexes = [
            models.Index(fields=['local', 'role']),
        ]

    def __str__(self):
        return self.username

    @property
    def is_leadership(self):
        return self.role == self.Role.LEADERSHIP
