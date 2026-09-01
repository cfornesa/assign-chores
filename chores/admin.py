from django.contrib import admin

from .models import ChoreInstance, ChoreTemplate, Household, Membership


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__username")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("household", "user", "status", "requested_at", "approved_at")
    list_filter = ("status",)
    search_fields = ("household__name", "user__username")


@admin.register(ChoreTemplate)
class ChoreTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "household", "schedule_type", "is_active", "created_at")
    list_filter = ("schedule_type", "is_active")
    search_fields = ("title", "household__name")


@admin.register(ChoreInstance)
class ChoreInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "title_snapshot",
        "household",
        "status",
        "assignment_status",
        "due_at",
    )
    list_filter = ("status", "assignment_status")
    search_fields = ("title_snapshot", "household__name")