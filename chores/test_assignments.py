from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ChoreInstance, ChoreTemplate, Household, Membership


class AssignmentTransitionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="assignment-owner",
            password="safe-owner-password",
        )
        self.member = user_model.objects.create_user(
            username="assignment-member",
            password="safe-member-password",
        )
        self.other_member = user_model.objects.create_user(
            username="assignment-other",
            password="safe-other-password",
        )
        self.pending_user = user_model.objects.create_user(
            username="assignment-pending",
            password="safe-pending-password",
        )
        self.household = Household.objects.create(
            name="Assignment House",
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
        self.template = ChoreTemplate.objects.create(
            household=self.household,
            title="Vacuum",
            schedule_type=ChoreTemplate.ScheduleType.ONE_TIME,
            created_by=self.owner,
        )
        self.instance = ChoreInstance.objects.create(
            household=self.household,
            template=self.template,
            title_snapshot=self.template.title,
        )

    def action_url(self, action):
        return reverse(
            "assignment_action",
            kwargs={
                "household_id": self.household.id,
                "instance_id": self.instance.id,
                "action": action,
            },
        )

    def assign_url(self):
        return reverse(
            "chore_assign",
            kwargs={
                "household_id": self.household.id,
                "instance_id": self.instance.id,
            },
        )

    def test_member_can_claim_unassigned_chore(self):
        self.client.force_login(self.member)

        response = self.client.post(self.action_url("claim"))

        self.assertEqual(response.status_code, 302)
        self.instance.refresh_from_db()
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.ACCEPTED,
        )
        self.assertEqual(self.instance.assigned_to, self.member)
        self.assertEqual(self.instance.assigned_by, self.member)
        self.assertIsNotNone(self.instance.assigned_at)
        self.assertIsNotNone(self.instance.accepted_at)

    def test_member_can_propose_and_assignee_can_accept(self):
        self.client.force_login(self.owner)
        self.client.post(self.assign_url(), {"assignee": self.member.id})
        self.instance.refresh_from_db()
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.PENDING,
        )
        self.assertEqual(self.instance.assigned_to, self.member)
        self.assertEqual(self.instance.assigned_by, self.owner)
        self.assertIsNone(self.instance.accepted_at)

        self.client.force_login(self.member)
        response = self.client.post(self.action_url("accept"))

        self.assertEqual(response.status_code, 302)
        self.instance.refresh_from_db()
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.ACCEPTED,
        )
        self.assertIsNotNone(self.instance.accepted_at)

    def test_only_proposed_assignee_can_accept_or_decline(self):
        self.instance.assignment_status = ChoreInstance.AssignmentStatus.PENDING
        self.instance.assigned_to = self.member
        self.instance.assigned_by = self.owner
        self.instance.save()
        self.client.force_login(self.other_member)

        self.assertEqual(self.client.post(self.action_url("accept")).status_code, 403)
        self.assertEqual(self.client.post(self.action_url("decline")).status_code, 403)
        self.instance.refresh_from_db()
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.PENDING,
        )

    def test_decline_returns_chore_to_unassigned(self):
        self.instance.assignment_status = ChoreInstance.AssignmentStatus.PENDING
        self.instance.assigned_to = self.member
        self.instance.assigned_by = self.owner
        self.instance.save()
        self.client.force_login(self.member)

        self.client.post(self.action_url("decline"))

        self.instance.refresh_from_db()
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.UNASSIGNED,
        )
        self.assertIsNone(self.instance.assigned_to)
        self.assertIsNone(self.instance.assigned_by)
        self.assertIsNone(self.instance.assigned_at)
        self.assertIsNone(self.instance.accepted_at)

    def test_only_current_assignee_can_unclaim(self):
        self.instance.assignment_status = ChoreInstance.AssignmentStatus.ACCEPTED
        self.instance.assigned_to = self.member
        self.instance.assigned_by = self.member
        self.instance.save()
        self.client.force_login(self.other_member)
        self.assertEqual(self.client.post(self.action_url("unclaim")).status_code, 403)

        self.client.force_login(self.member)
        self.assertEqual(self.client.post(self.action_url("unclaim")).status_code, 302)
        self.instance.refresh_from_db()
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.UNASSIGNED,
        )
        self.assertIsNone(self.instance.assigned_to)

    def test_accepted_chore_reassignment_requires_confirmation(self):
        self.instance.assignment_status = ChoreInstance.AssignmentStatus.ACCEPTED
        self.instance.assigned_to = self.member
        self.instance.assigned_by = self.owner
        self.instance.save()
        self.client.force_login(self.owner)

        response = self.client.post(
            self.assign_url(),
            {"assignee": self.other_member.id},
        )

        self.assertEqual(response.status_code, 302)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.assigned_to, self.member)
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.ACCEPTED,
        )

        self.client.post(
            self.assign_url(),
            {"assignee": self.other_member.id, "confirm": "yes"},
        )
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.assigned_to, self.other_member)
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.PENDING,
        )
        self.assertIsNone(self.instance.accepted_at)

    def test_non_approved_user_cannot_change_assignments(self):
        self.client.force_login(self.pending_user)

        claim = self.client.post(self.action_url("claim"))
        assign = self.client.post(
            self.assign_url(),
            {"assignee": self.member.id},
        )

        self.assertEqual(claim.status_code, 404)
        self.assertEqual(assign.status_code, 404)
        self.instance.refresh_from_db()
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.UNASSIGNED,
        )

    def test_board_shows_pending_in_open_and_accepted_chore_in_mine(self):
        self.instance.assignment_status = ChoreInstance.AssignmentStatus.PENDING
        self.instance.assigned_to = self.member
        self.instance.assigned_by = self.owner
        self.instance.save()
        self.client.force_login(self.member)
        board_url = reverse(
            "household_detail",
            kwargs={"household_id": self.household.id},
        )

        pending_board = self.client.get(board_url)

        self.assertContains(pending_board, "Pending: assignment-member")
        self.assertContains(pending_board, "Accept")
        self.client.post(self.action_url("accept"))

        accepted_board = self.client.get(board_url)

        self.assertContains(accepted_board, "Mine")
        self.assertContains(accepted_board, "Accepted: assignment-member")
        self.assertContains(accepted_board, "Unclaim")