from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ChoreInstance, ChoreTemplate, Household, Membership
from .scheduling import current_week_range, generate_current_week_instances


class WeeklySchedulingTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="weekly-owner",
            password="safe-owner-password",
        )
        self.member = user_model.objects.create_user(
            username="weekly-member",
            password="safe-member-password",
        )
        self.household = Household.objects.create(
            name="Weekly House",
            owner=self.owner,
        )
        Membership.objects.bulk_create(
            [
                Membership(
                    household=self.household,
                    user=self.owner,
                    status=Membership.Status.APPROVED,
                ),
                Membership(
                    household=self.household,
                    user=self.member,
                    status=Membership.Status.APPROVED,
                ),
            ]
        )

    def board_url(self):
        return reverse(
            "household_detail",
            kwargs={"household_id": self.household.id},
        )

    def create_weekly_template(self, title="Clean kitchen"):
        return ChoreTemplate.objects.create(
            household=self.household,
            title=title,
            schedule_type=ChoreTemplate.ScheduleType.WEEKLY,
            weekly_due_weekday=ChoreTemplate.Weekday.FRIDAY,
            created_by=self.owner,
        )

    def test_weekly_form_requires_due_weekday(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse(
                "weekly_chore_create",
                kwargs={"household_id": self.household.id},
            ),
            {
                "title": "Missing weekday",
                "description": "",
                "weekly_due_weekday": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weekly chores require a due weekday.")
        self.assertFalse(
            ChoreTemplate.objects.filter(title="Missing weekday").exists()
        )

    def test_create_weekly_chore_generates_current_unassigned_instance(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse(
                "weekly_chore_create",
                kwargs={"household_id": self.household.id},
            ),
            {
                "title": "Clean bathroom",
                "description": "Sink, mirror, and floor.",
                "weekly_due_weekday": ChoreTemplate.Weekday.THURSDAY,
            },
        )

        self.assertRedirects(response, self.board_url())
        template = ChoreTemplate.objects.get(title="Clean bathroom")
        instance = template.instances.get()
        week_start, week_end = current_week_range()
        self.assertEqual(instance.week_start_date, week_start.date())
        self.assertEqual(
            instance.assignment_status,
            ChoreInstance.AssignmentStatus.UNASSIGNED,
        )
        local_due = timezone.localtime(instance.due_at)
        self.assertEqual(local_due.weekday(), 3)
        self.assertEqual(local_due.hour, 23)
        self.assertLess(instance.due_at, week_end)

    def test_board_generation_is_idempotent_and_current_week_only(self):
        template = self.create_weekly_template()
        self.client.force_login(self.owner)

        self.client.get(self.board_url())
        self.client.get(self.board_url())
        generate_current_week_instances(self.household)

        self.assertEqual(template.instances.count(), 1)
        week_start, _ = current_week_range()
        self.assertEqual(
            template.instances.get().week_start_date,
            week_start.date(),
        )

    def test_completing_weekly_instance_does_not_create_another_same_week(self):
        template = self.create_weekly_template()
        instance = generate_current_week_instances(self.household)[0]
        instance.status = ChoreInstance.Status.COMPLETED
        instance.completed_by = self.owner
        instance.completed_at = timezone.now()
        instance.save()
        self.client.force_login(self.owner)

        self.client.get(self.board_url())

        self.assertEqual(template.instances.count(), 1)
        self.assertEqual(
            template.instances.get().status,
            ChoreInstance.Status.COMPLETED,
        )

    def test_edit_weekly_chore_updates_current_open_instance(self):
        template = self.create_weekly_template()
        instance = generate_current_week_instances(self.household)[0]
        self.client.force_login(self.member)

        response = self.client.post(
            reverse(
                "chore_edit",
                kwargs={
                    "household_id": self.household.id,
                    "template_id": template.id,
                },
            ),
            {
                "title": "Deep clean kitchen",
                "description": "Include the refrigerator.",
                "weekly_due_weekday": ChoreTemplate.Weekday.SATURDAY,
            },
        )

        self.assertRedirects(response, self.board_url())
        instance.refresh_from_db()
        self.assertEqual(instance.title_snapshot, "Deep clean kitchen")
        self.assertEqual(instance.description_snapshot, "Include the refrigerator.")
        self.assertEqual(timezone.localtime(instance.due_at).weekday(), 5)

    def test_inactive_weekly_template_does_not_generate_instances(self):
        template = self.create_weekly_template()
        template.is_active = False
        template.save()

        created = generate_current_week_instances(self.household)

        self.assertEqual(created, [])
        self.assertFalse(template.instances.exists())

    def test_generation_does_not_backfill_or_create_future_weeks(self):
        template = self.create_weekly_template()
        generate_current_week_instances(self.household)
        week_start, _ = current_week_range()

        dates = list(template.instances.values_list("week_start_date", flat=True))

        self.assertEqual(dates, [week_start.date()])
        self.assertNotIn(week_start.date() - timedelta(days=7), dates)
        self.assertNotIn(week_start.date() + timedelta(days=7), dates)