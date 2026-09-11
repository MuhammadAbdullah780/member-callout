from django.db import models


class Local(models.Model):
    """A union local. The tenant boundary for every other model in the system."""

    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
