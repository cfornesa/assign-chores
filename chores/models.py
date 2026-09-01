import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


def generate_invite_token():
    """Generate a reusable, high-entropy token for household invitations."""
    return secrets.token_urlsafe(32)


class Household(models.Model):
    name = models.CharField(max_length=120)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_households",
    )
    invite_token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_invite_token,
        editable=False,
    )
    timezone = models.CharField(
        max_length=64,
        default=settings.TIME_ZONE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="household_memberships",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="membership_approvals",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["household", "user"],
                name="unique_household_membership",
            )
        ]

    def __str__(self):
        return f"{self.user} in {self.household} ({self.status})"


class ChoreTemplate(models.Model):
    class ScheduleType(models.TextChoices):
        ONE_TIME = "one_time", "One time"
        WEEKLY = "weekly", "Weekly"

    class Weekday(models.IntegerChoices):
        SUNDAY = 0, "Sunday"
        MONDAY = 1, "Monday"
        TUESDAY = 2, "Tuesday"
        WEDNESDAY = 3, "Wednesday"
        THURSDAY = 4, "Thursday"
        FRIDAY = 5, "Friday"
        SATURDAY = 6, "Saturday"

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="chore_templates",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    schedule_type = models.CharField(
        max_length=10,
        choices=ScheduleType.choices,
    )
    weekly_due_weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices,
        null=True,
        blank=True,
    )
    one_time_due_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_chore_templates",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(weekly_due_weekday__isnull=True)
                | Q(weekly_due_weekday__range=(0, 6)),
                name="valid_weekly_due_weekday",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.schedule_type == self.ScheduleType.WEEKLY
            and self.weekly_due_weekday is None
        ):
            raise ValidationError(
                {"weekly_due_weekday": "Weekly chores require a due weekday."}
            )
        if (
            self.schedule_type == self.ScheduleType.ONE_TIME
            and self.weekly_due_weekday is not None
        ):
            raise ValidationError(
                {"weekly_due_weekday": "One-time chores cannot have a due weekday."}
            )
        if (
            self.schedule_type == self.ScheduleType.WEEKLY
            and self.one_time_due_at is not None
        ):
            raise ValidationError(
                {"one_time_due_at": "Weekly chores cannot have a one-time due date."}
            )

    def __str__(self):
        return self.title


class ChoreInstance(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        COMPLETED = "completed", "Completed"

    class AssignmentStatus(models.TextChoices):
        UNASSIGNED = "unassigned", "Unassigned"
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="chore_instances",
    )
    template = models.ForeignKey(
        ChoreTemplate,
        on_delete=models.SET_NULL,
        related_name="instances",
        null=True,
        blank=True,
    )
    week_start_date = models.DateField(null=True, blank=True)
    title_snapshot = models.CharField(max_length=200)
    description_snapshot = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    assignment_status = models.CharField(
        max_length=12,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.UNASSIGNED,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_chore_instances",
        null=True,
        blank=True,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_chore_actions",
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="completed_chore_instances",
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["template", "week_start_date"],
                condition=Q(week_start_date__isnull=False),
                name="unique_template_week_instance",
            ),
        ]

    def clean(self):
        super().clean()
        if self.template_id and self.household_id:
            if self.template.household_id != self.household_id:
                raise ValidationError(
                    {"household": "Instance household must match its template."}
                )
        if (
            self.assignment_status != self.AssignmentStatus.UNASSIGNED
            and self.assigned_to_id is None
        ):
            raise ValidationError(
                {"assigned_to": "Pending and accepted chores require an assignee."}
            )

    def __str__(self):
        return self.title_snapshot

    @property
    def is_overdue(self):
        return (
            self.status == self.Status.OPEN
            and self.due_at is not None
            and self.due_at < timezone.now()
        )
