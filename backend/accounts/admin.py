from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'local', 'role', 'is_active')
    list_filter = ('local', 'role', 'is_active')
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('CrewLink', {'fields': ('local', 'role')}),
    )
