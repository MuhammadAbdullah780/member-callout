from django.contrib import admin

from core.models import Local


@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name',)
