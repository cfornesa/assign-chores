from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse

from .models import ChoreInstance, ChoreTemplate, Household, Membership
from .scheduling import current_week_range


class BoardInteractionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="interaction-owner",
            password="safe-owner-password",
        )
        self.member = user_model.objects.create_user(
            username="interaction-member",
            password="safe-member-password",
        )
        self.household = Household.objects.create(
            name="Interaction House",
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
        template = ChoreTemplate.objects.create(
            household=self.household,
            title="Move me",
            schedule_type=ChoreTemplate.ScheduleType.ONE_TIME,
            created_by=self.owner,
        )
        self.instance = ChoreInstance.objects.create(
            household=self.household,
            template=template,
            title_snapshot=template.title,
        )

    def test_board_marks_supported_drop_targets_and_overdue_as_derived(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "household_detail",
                kwargs={"household_id": self.household.id},
            )
        )

        self.assertContains(response, 'data-drop-target="open"')
        self.assertContains(response, 'data-drop-target="mine"')
        self.assertContains(response, 'data-drop-target="completed"')
        self.assertContains(response, 'data-drop-target="overdue"')
        self.assertContains(response, 'aria-disabled="true"')

    def test_open_card_exposes_drag_urls_and_accessible_button_alternatives(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "household_detail",
                kwargs={"household_id": self.household.id},
            )
        )

        self.assertContains(response, 'draggable="true"')
        self.assertContains(response, "data-claim-url=")
        self.assertContains(response, "data-unclaim-url=")
        self.assertContains(response, "data-complete-url=")
        self.assertContains(response, ">Claim</button>")
        self.assertContains(response, ">Propose assignment</button>")
        self.assertContains(response, ">Complete</button>")

    def test_board_script_is_discoverable_and_rejects_overdue_drops(self):
        script_path = finders.find("chores/board.js")

        self.assertIsNotNone(script_path)
        with open(script_path, encoding="utf-8") as script:
            source = script.read()
        self.assertIn('targetName === "overdue"', source)
        self.assertIn('targetName === "mine"', source)
        self.assertIn('targetName === "open"', source)
        self.assertIn('targetName === "completed"', source)
        self.assertIn('body.set("confirm", "yes")', source)

    def test_week_boundaries_are_sunday_through_saturday(self):
        chicago = ZoneInfo("America/Chicago")
        sunday = datetime(2026, 9, 6, 12, tzinfo=chicago)
        saturday = datetime(2026, 9, 12, 23, tzinfo=chicago)

        sunday_start, sunday_end = current_week_range(sunday)
        saturday_start, saturday_end = current_week_range(saturday)

        self.assertEqual(sunday_start.date().isoformat(), "2026-09-06")
        self.assertEqual(sunday_end.date().isoformat(), "2026-09-13")
        self.assertEqual(saturday_start, sunday_start)
        self.assertEqual(saturday_end, sunday_end)

    def test_state_changes_require_post_and_csrf(self):
        self.client.force_login(self.member)
        claim_url = reverse(
            "assignment_action",
            kwargs={
                "household_id": self.household.id,
                "instance_id": self.instance.id,
                "action": "claim",
            },
        )

        self.assertEqual(self.client.get(claim_url).status_code, 405)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.member)
        self.assertEqual(csrf_client.post(claim_url).status_code, 403)
        self.instance.refresh_from_db()
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.UNASSIGNED,
        )