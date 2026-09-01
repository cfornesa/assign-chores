from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ChoreInstance, ChoreTemplate, Household, Membership


class CompletionAndLaneTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="completion-owner",
            password="safe-owner-password",
        )
        self.member = user_model.objects.create_user(
            username="completion-member",
            password="safe-member-password",
        )
        self.other_member = user_model.objects.create_user(
            username="completion-other",
            password="safe-other-password",
        )
        self.pending_user = user_model.objects.create_user(
            username="completion-pending",
            password="safe-pending-password",
        )
        self.household = Household.objects.create(
            name="Completion House",
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
                    user=self.other_member,
                    status=Membership.Status.APPROVED,
                ),
                Membership(
                    household=self.household,
                    user=self.pending_user,
                    status=Membership.Status.PENDING,
                ),
            ]
        )

    def create_instance(self, title, **overrides):
        template = ChoreTemplate.objects.create(
            household=self.household,
            title=title,
            schedule_type=ChoreTemplate.ScheduleType.ONE_TIME,
            created_by=self.owner,
        )
        defaults = {
            "household": self.household,
            "template": template,
            "title_snapshot": title,
        }
        defaults.update(overrides)
        return ChoreInstance.objects.create(**defaults)

    def complete_url(self, instance):
        return reverse(
            "chore_complete",
            kwargs={
                "household_id": self.household.id,
                "instance_id": instance.id,
            },
        )

    def board_url(self):
        return reverse(
            "household_detail",
            kwargs={"household_id": self.household.id},
        )

    def test_approved_member_can_complete_unassigned_chore(self):
        instance = self.create_instance("Unassigned completion")
        self.client.force_login(self.member)

        response = self.client.post(self.complete_url(instance))

        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.status, ChoreInstance.Status.COMPLETED)
        self.assertEqual(instance.completed_by, self.member)
        self.assertIsNotNone(instance.completed_at)

    def test_completing_another_members_chore_requires_confirmation(self):
        instance = self.create_instance(
            "Assigned completion",
            assignment_status=ChoreInstance.AssignmentStatus.ACCEPTED,
            assigned_to=self.member,
            assigned_by=self.owner,
            assigned_at=timezone.now(),
            accepted_at=timezone.now(),
        )
        self.client.force_login(self.other_member)

        response = self.client.post(self.complete_url(instance))

        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.status, ChoreInstance.Status.OPEN)

        self.client.post(self.complete_url(instance), {"confirm": "yes"})
        instance.refresh_from_db()
        self.assertEqual(instance.status, ChoreInstance.Status.COMPLETED)
        self.assertEqual(instance.assigned_to, self.member)
        self.assertEqual(instance.completed_by, self.other_member)

    def test_pending_user_cannot_complete_chore(self):
        instance = self.create_instance("Protected completion")
        self.client.force_login(self.pending_user)

        response = self.client.post(self.complete_url(instance))

        self.assertEqual(response.status_code, 404)
        instance.refresh_from_db()
        self.assertEqual(instance.status, ChoreInstance.Status.OPEN)

    def test_board_derives_open_mine_overdue_and_current_week_completed(self):
        now = timezone.now()
        open_instance = self.create_instance(
            "Open future",
            due_at=now + timedelta(days=1),
        )
        mine_instance = self.create_instance(
            "Mine accepted",
            assignment_status=ChoreInstance.AssignmentStatus.ACCEPTED,
            assigned_to=self.member,
            assigned_by=self.owner,
            assigned_at=now,
            accepted_at=now,
            due_at=now + timedelta(days=2),
        )
        overdue_instance = self.create_instance(
            "Open overdue",
            due_at=now - timedelta(hours=1),
        )
        current_completed = self.create_instance(
            "Completed this week",
            status=ChoreInstance.Status.COMPLETED,
            completed_by=self.member,
            completed_at=now,
        )
        old_completed = self.create_instance(
            "Completed long ago",
            status=ChoreInstance.Status.COMPLETED,
            completed_by=self.member,
            completed_at=now - timedelta(days=14),
        )
        self.client.force_login(self.member)

        response = self.client.get(self.board_url())

        self.assertContains(response, "Open future")
        self.assertContains(response, "Mine accepted")
        self.assertContains(response, "Open overdue", count=2)
        self.assertContains(response, "Overdue")
        self.assertContains(response, "Completed this week")
        self.assertContains(response, "Completed by")
        self.assertNotContains(response, "Completed long ago")
        self.assertNotContains(
            response,
            f'data-chore-id="{old_completed.id}"',
        )
        self.assertContains(
            response,
            f'data-chore-id="{open_instance.id}"',
        )
        self.assertContains(
            response,
            f'data-chore-id="{mine_instance.id}"',
        )
        self.assertContains(
            response,
            f'data-chore-id="{overdue_instance.id}"',
            count=2,
        )
        self.assertContains(
            response,
            f'data-chore-id="{current_completed.id}"',
        )