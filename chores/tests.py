from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import ChoreInstance, ChoreTemplate, Household, Membership
from .permissions import (
    get_approved_membership_or_404,
    get_chore_instance_for_user_or_404,
    get_chore_template_for_user_or_404,
)


class HomePageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alex",
            email="alex@example.com",
            password="safe-test-password",
            first_name="Alex",
            last_name="Member",
        )

    def test_home_page_requires_authentication(self):
        response = self.client.get(reverse("home"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('home')}",
        )

    def test_authenticated_user_can_see_identity_and_sign_out(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assign Chores")
        self.assertContains(response, "Alex Member")
        self.assertContains(response, "alex@example.com")
        self.assertContains(response, f'action="{reverse("logout")}"')

        logout_response = self.client.post(reverse("logout"))

        self.assertRedirects(logout_response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_user_can_sign_in_with_django_auth_view(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "alex",
                "password": "safe-test-password",
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_accepts_a_replit_preview_origin(self):
        csrf_client = Client(enforce_csrf_checks=True)
        login_page = csrf_client.get(reverse("login"))
        csrf_token = login_page.cookies["csrftoken"].value

        response = csrf_client.post(
            reverse("login"),
            {
                "username": "alex",
                "password": "safe-test-password",
                "csrfmiddlewaretoken": csrf_token,
            },
            HTTP_ORIGIN="https://preview.replit.dev",
        )

        self.assertRedirects(response, reverse("home"))


class HouseholdAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="safe-owner-password",
        )
        self.requester = user_model.objects.create_user(
            username="requester",
            email="requester@example.com",
            password="safe-requester-password",
        )
        self.outsider = user_model.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="safe-outsider-password",
        )

    def create_household(self):
        household = Household.objects.create(
            name="Maple House",
            owner=self.owner,
        )
        Membership.objects.create(
            household=household,
            user=self.owner,
            status=Membership.Status.APPROVED,
            approved_by=self.owner,
        )
        return household

    def test_authenticated_user_can_create_a_household_as_owner(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("household_create"),
            {"name": "Created House"},
        )

        household = Household.objects.get(name="Created House")
        membership = Membership.objects.get(
            household=household,
            user=self.owner,
        )
        self.assertRedirects(
            response,
            reverse("household_detail", kwargs={"household_id": household.id}),
        )
        self.assertEqual(membership.status, Membership.Status.APPROVED)
        self.assertEqual(household.owner, self.owner)
        self.assertGreaterEqual(len(household.invite_token), 40)

    def test_invite_request_is_pending_and_duplicate_posts_do_not_duplicate(self):
        household = self.create_household()
        self.client.force_login(self.requester)
        invite_url = reverse(
            "invite",
            kwargs={"token": household.invite_token},
        )

        response = self.client.get(invite_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.owner.username)

        self.client.post(invite_url)
        self.client.post(invite_url)

        self.assertEqual(
            Membership.objects.filter(
                household=household,
                user=self.requester,
            ).count(),
            1,
        )
        self.assertEqual(
            Membership.objects.get(
                household=household,
                user=self.requester,
            ).status,
            Membership.Status.PENDING,
        )

    def test_owner_can_approve_request_and_member_can_access_household(self):
        household = self.create_household()
        Membership.objects.create(
            household=household,
            user=self.requester,
            status=Membership.Status.PENDING,
        )
        pending_request = Membership.objects.get(
            household=household,
            user=self.requester,
        )
        self.client.force_login(self.owner)

        detail = self.client.get(
            reverse(
                "household_detail",
                kwargs={"household_id": household.id},
            )
        )
        self.assertContains(detail, self.requester.username)

        response = self.client.post(
            reverse(
                "membership_decision",
                kwargs={
                    "household_id": household.id,
                    "membership_id": pending_request.id,
                    "decision": "approve",
                },
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "household_detail",
                kwargs={"household_id": household.id},
            ),
        )
        pending_request.refresh_from_db()
        self.assertEqual(pending_request.status, Membership.Status.APPROVED)
        self.assertEqual(pending_request.approved_by, self.owner)
        self.client.force_login(self.requester)
        self.assertEqual(
            self.client.get(
                reverse(
                    "household_detail",
                    kwargs={"household_id": household.id},
                )
            ).status_code,
            200,
        )

    def test_rejected_or_pending_users_cannot_access_household_details(self):
        household = self.create_household()
        pending_request = Membership.objects.create(
            household=household,
            user=self.requester,
            status=Membership.Status.PENDING,
        )
        self.client.force_login(self.requester)

        detail_url = reverse(
            "household_detail",
            kwargs={"household_id": household.id},
        )
        self.assertEqual(self.client.get(detail_url).status_code, 404)

        self.client.force_login(self.owner)
        self.client.post(
            reverse(
                "membership_decision",
                kwargs={
                    "household_id": household.id,
                    "membership_id": pending_request.id,
                    "decision": "reject",
                },
            )
        )
        self.client.force_login(self.requester)
        self.assertEqual(self.client.get(detail_url).status_code, 404)

    def test_only_owner_can_decide_membership_requests(self):
        household = self.create_household()
        pending_request = Membership.objects.create(
            household=household,
            user=self.requester,
            status=Membership.Status.PENDING,
        )
        self.client.force_login(self.outsider)

        response = self.client.post(
            reverse(
                "membership_decision",
                kwargs={
                    "household_id": household.id,
                    "membership_id": pending_request.id,
                    "decision": "approve",
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        pending_request.refresh_from_db()
        self.assertEqual(pending_request.status, Membership.Status.PENDING)


class ChoreDataModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="model-owner",
            password="safe-owner-password",
        )
        self.approved_user = user_model.objects.create_user(
            username="approved-user",
            password="safe-approved-password",
        )
        self.pending_user = user_model.objects.create_user(
            username="pending-user",
            password="safe-pending-password",
        )
        self.rejected_user = user_model.objects.create_user(
            username="rejected-user",
            password="safe-rejected-password",
        )
        self.outsider = user_model.objects.create_user(
            username="model-outsider",
            password="safe-outsider-password",
        )
        self.household = Household.objects.create(
            name="Model House",
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
                    user=self.approved_user,
                    status=Membership.Status.APPROVED,
                ),
                Membership(
                    household=self.household,
                    user=self.pending_user,
                    status=Membership.Status.PENDING,
                ),
                Membership(
                    household=self.household,
                    user=self.rejected_user,
                    status=Membership.Status.REJECTED,
                ),
            ]
        )
        self.template = ChoreTemplate.objects.create(
            household=self.household,
            title="Clean the kitchen",
            description="Wipe counters and sweep.",
            schedule_type=ChoreTemplate.ScheduleType.WEEKLY,
            weekly_due_weekday=ChoreTemplate.Weekday.FRIDAY,
            created_by=self.owner,
        )
        self.instance = ChoreInstance.objects.create(
            household=self.household,
            template=self.template,
            week_start_date=date(2026, 8, 30),
            title_snapshot=self.template.title,
            description_snapshot=self.template.description,
        )

    def test_template_and_instance_preserve_actionable_snapshot(self):
        self.assertEqual(self.instance.household, self.household)
        self.assertEqual(self.instance.title_snapshot, "Clean the kitchen")
        self.assertEqual(
            self.instance.assignment_status,
            ChoreInstance.AssignmentStatus.UNASSIGNED,
        )
        self.assertEqual(self.instance.status, ChoreInstance.Status.OPEN)

    def test_weekly_template_requires_a_due_weekday(self):
        template = ChoreTemplate(
            household=self.household,
            title="No weekday",
            schedule_type=ChoreTemplate.ScheduleType.WEEKLY,
            created_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            template.full_clean()

    def test_weekly_instance_is_unique_for_template_and_week(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChoreInstance.objects.create(
                    household=self.household,
                    template=self.template,
                    week_start_date=date(2026, 8, 30),
                    title_snapshot=self.template.title,
                )

    def test_instance_household_must_match_template(self):
        other_household = Household.objects.create(
            name="Other House",
            owner=self.outsider,
        )
        mismatched = ChoreInstance(
            household=other_household,
            template=self.template,
            week_start_date=date(2026, 9, 6),
            title_snapshot=self.template.title,
        )

        with self.assertRaises(ValidationError):
            mismatched.full_clean()

    def test_approved_member_can_resolve_household_template_and_instance(self):
        membership = get_approved_membership_or_404(
            self.approved_user,
            self.household.id,
        )
        template = get_chore_template_for_user_or_404(
            self.approved_user,
            self.template.id,
        )
        instance = get_chore_instance_for_user_or_404(
            self.approved_user,
            self.instance.id,
        )

        self.assertEqual(membership.household, self.household)
        self.assertEqual(template, self.template)
        self.assertEqual(instance, self.instance)

    def test_non_approved_users_cannot_resolve_household_chore_data(self):
        for user in (self.pending_user, self.rejected_user, self.outsider):
            with self.subTest(user=user.username):
                with self.assertRaises(Http404):
                    get_approved_membership_or_404(user, self.household.id)
                with self.assertRaises(Http404):
                    get_chore_template_for_user_or_404(user, self.template.id)
                with self.assertRaises(Http404):
                    get_chore_instance_for_user_or_404(user, self.instance.id)