from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ChoreInstance, ChoreTemplate, Household, Membership


class OneTimeChoreTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="crud-owner",
            password="safe-owner-password",
        )
        self.member = user_model.objects.create_user(
            username="crud-member",
            password="safe-member-password",
        )
        self.pending_user = user_model.objects.create_user(
            username="crud-pending",
            password="safe-pending-password",
        )
        self.household = Household.objects.create(
            name="CRUD House",
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
                Membership(
                    household=self.household,
                    user=self.pending_user,
                    status=Membership.Status.PENDING,
                ),
            ]
        )

    def create_chore(self, title="Wash dishes"):
        due_at = timezone.make_aware(datetime(2026, 9, 3, 18, 30))
        template = ChoreTemplate.objects.create(
            household=self.household,
            title=title,
            description="Load and run the dishwasher.",
            schedule_type=ChoreTemplate.ScheduleType.ONE_TIME,
            one_time_due_at=due_at,
            created_by=self.owner,
        )
        instance = ChoreInstance.objects.create(
            household=self.household,
            template=template,
            title_snapshot=template.title,
            description_snapshot=template.description,
            due_at=due_at,
        )
        return template, instance

    def test_approved_member_can_create_one_time_chore_and_instance(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse(
                "chore_create",
                kwargs={"household_id": self.household.id},
            ),
            {
                "title": "Take out trash",
                "description": "Use the outside bin.",
                "one_time_due_at": "2026-09-04T19:00",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "household_detail",
                kwargs={"household_id": self.household.id},
            ),
        )
        template = ChoreTemplate.objects.get(title="Take out trash")
        instance = template.instances.get()
        self.assertEqual(
            template.schedule_type,
            ChoreTemplate.ScheduleType.ONE_TIME,
        )
        self.assertEqual(template.created_by, self.member)
        self.assertEqual(instance.title_snapshot, template.title)
        self.assertEqual(instance.description_snapshot, template.description)
        self.assertEqual(instance.assignment_status, "unassigned")

    def test_title_is_required(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse(
                "chore_create",
                kwargs={"household_id": self.household.id},
            ),
            {"title": "", "description": "", "one_time_due_at": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertEqual(ChoreTemplate.objects.count(), 0)
        self.assertEqual(ChoreInstance.objects.count(), 0)

    def test_open_board_shows_card_details_and_assignment_state(self):
        self.create_chore()
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                "household_detail",
                kwargs={"household_id": self.household.id},
            )
        )

        self.assertContains(response, "Open")
        self.assertContains(response, "Wash dishes")
        self.assertContains(response, "Load and run the dishwasher.")
        self.assertContains(response, "Assignment:")
        self.assertContains(response, "Unassigned")
        self.assertContains(response, "Sep 3, 2026")

    def test_approved_member_can_edit_open_chore_snapshot(self):
        template, instance = self.create_chore()
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
                "title": "Wash all dishes",
                "description": "Include pots and pans.",
                "one_time_due_at": "",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "household_detail",
                kwargs={"household_id": self.household.id},
            ),
        )
        template.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(template.title, "Wash all dishes")
        self.assertEqual(instance.title_snapshot, "Wash all dishes")
        self.assertEqual(instance.description_snapshot, "Include pots and pans.")
        self.assertIsNone(instance.due_at)

    def test_approved_member_can_hide_chore_without_erasing_instance_history(self):
        template, instance = self.create_chore()
        self.client.force_login(self.member)

        response = self.client.post(
            reverse(
                "chore_delete",
                kwargs={
                    "household_id": self.household.id,
                    "template_id": template.id,
                },
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "household_detail",
                kwargs={"household_id": self.household.id},
            ),
        )
        template.refresh_from_db()
        instance.refresh_from_db()
        self.assertFalse(template.is_active)
        self.assertEqual(instance.template, template)
        board = self.client.get(
            reverse(
                "household_detail",
                kwargs={"household_id": self.household.id},
            )
        )
        self.assertNotContains(board, instance.title_snapshot)

    def test_pending_member_cannot_create_edit_or_delete_chores(self):
        template, _ = self.create_chore()
        self.client.force_login(self.pending_user)

        create_response = self.client.post(
            reverse(
                "chore_create",
                kwargs={"household_id": self.household.id},
            ),
            {"title": "Unauthorized"},
        )
        edit_response = self.client.post(
            reverse(
                "chore_edit",
                kwargs={
                    "household_id": self.household.id,
                    "template_id": template.id,
                },
            ),
            {"title": "Unauthorized edit"},
        )
        delete_response = self.client.post(
            reverse(
                "chore_delete",
                kwargs={
                    "household_id": self.household.id,
                    "template_id": template.id,
                },
            )
        )

        self.assertEqual(create_response.status_code, 404)
        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        template.refresh_from_db()
        self.assertEqual(template.title, "Wash dishes")