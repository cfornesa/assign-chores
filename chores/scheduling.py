from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import ChoreInstance, ChoreTemplate


def current_week_range(now=None):
    """Return timezone-aware Sunday start and following Sunday end."""
    current = timezone.localtime(now or timezone.now())
    days_since_sunday = (current.weekday() + 1) % 7
    week_start_date = current.date() - timedelta(days=days_since_sunday)
    current_timezone = timezone.get_current_timezone()
    week_start = timezone.make_aware(
        datetime.combine(week_start_date, time.min),
        current_timezone,
    )
    return week_start, week_start + timedelta(days=7)


def weekly_due_at(week_start_date, due_weekday):
    due_date = week_start_date + timedelta(days=due_weekday)
    return timezone.make_aware(
        datetime.combine(due_date, time.max),
        timezone.get_current_timezone(),
    )


def generate_current_week_instances(household, now=None):
    week_start, _ = current_week_range(now)
    week_start_date = week_start.date()
    created_instances = []
    templates = household.chore_templates.filter(
        schedule_type=ChoreTemplate.ScheduleType.WEEKLY,
        is_active=True,
    )
    for template in templates:
        defaults = {
            "household": household,
            "title_snapshot": template.title,
            "description_snapshot": template.description,
            "due_at": weekly_due_at(
                week_start_date,
                template.weekly_due_weekday,
            ),
        }
        try:
            with transaction.atomic():
                instance, created = ChoreInstance.objects.get_or_create(
                    template=template,
                    week_start_date=week_start_date,
                    defaults=defaults,
                )
        except IntegrityError:
            instance = ChoreInstance.objects.get(
                template=template,
                week_start_date=week_start_date,
            )
            created = False
        if created:
            created_instances.append(instance)
    return created_instances