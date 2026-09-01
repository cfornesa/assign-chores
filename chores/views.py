from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import HouseholdForm, OneTimeChoreForm, WeeklyChoreForm
from .models import ChoreInstance, ChoreTemplate, Household, Membership
from .permissions import (
    get_approved_membership_or_404,
    get_chore_instance_for_user_or_404,
    get_chore_template_for_user_or_404,
)
from .scheduling import (
    current_week_range,
    generate_current_week_instances,
    weekly_due_at,
)


@login_required
def home(request):
    approved_memberships = (
        request.user.household_memberships.filter(
            status=Membership.Status.APPROVED
        )
        .select_related("household")
        .order_by("household__name")
    )
    pending_memberships = (
        request.user.household_memberships.filter(
            status=Membership.Status.PENDING
        )
        .select_related("household")
        .order_by("-requested_at")
    )
    return render(
        request,
        "chores/home.html",
        {
            "approved_memberships": approved_memberships,
            "pending_memberships": pending_memberships,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def household_create(request):
    if request.method == "POST":
        form = HouseholdForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                household = form.save(commit=False)
                household.owner = request.user
                household.save()
                Membership.objects.create(
                    household=household,
                    user=request.user,
                    status=Membership.Status.APPROVED,
                    approved_at=timezone.now(),
                    approved_by=request.user,
                )
            messages.success(request, "Your household was created.")
            return redirect("household_detail", household_id=household.id)
    else:
        form = HouseholdForm()
    return render(request, "chores/household_form.html", {"form": form})


@login_required
def household_detail(request, household_id):
    membership = get_approved_membership_or_404(request.user, household_id)
    household = membership.household
    generate_current_week_instances(household)
    pending_requests = []
    invite_link = None
    if request.user == household.owner:
        pending_requests = household.memberships.filter(
            status=Membership.Status.PENDING
        ).select_related("user")
        invite_link = request.build_absolute_uri(
            reverse("invite", kwargs={"token": household.invite_token})
        )
    open_instances = (
        household.chore_instances.filter(
            status=ChoreInstance.Status.OPEN,
            template__is_active=True,
            assignment_status__in=[
                ChoreInstance.AssignmentStatus.UNASSIGNED,
                ChoreInstance.AssignmentStatus.PENDING,
            ],
        )
        .select_related("assigned_to")
        .order_by("due_at", "created_at")
    )
    mine_instances = (
        household.chore_instances.filter(
            status=ChoreInstance.Status.OPEN,
            template__is_active=True,
            assignment_status=ChoreInstance.AssignmentStatus.ACCEPTED,
            assigned_to=request.user,
        )
        .select_related("assigned_to")
        .order_by("due_at", "created_at")
    )
    overdue_instances = (
        household.chore_instances.filter(
            status=ChoreInstance.Status.OPEN,
            template__is_active=True,
            due_at__lt=timezone.now(),
        )
        .select_related("assigned_to")
        .order_by("due_at", "created_at")
    )
    week_start, week_end = current_week_range()
    completed_instances = (
        household.chore_instances.filter(
            status=ChoreInstance.Status.COMPLETED,
            completed_at__gte=week_start,
            completed_at__lt=week_end,
        )
        .select_related("assigned_to", "completed_by")
        .order_by("-completed_at")
    )
    approved_members = household.memberships.filter(
        status=Membership.Status.APPROVED
    ).select_related("user")
    return render(
        request,
        "chores/household_detail.html",
        {
            "household": household,
            "invite_link": invite_link,
            "pending_requests": pending_requests,
            "open_instances": open_instances,
            "mine_instances": mine_instances,
            "overdue_instances": overdue_instances,
            "completed_instances": completed_instances,
            "approved_members": approved_members,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def invite(request, token):
    household = get_object_or_404(Household, invite_token=token)
    membership = Membership.objects.filter(
        household=household,
        user=request.user,
    ).first()

    if membership and membership.status == Membership.Status.APPROVED:
        return redirect("household_detail", household_id=household.id)

    if request.method == "POST":
        if membership is None:
            try:
                with transaction.atomic():
                    membership, created = Membership.objects.get_or_create(
                        household=household,
                        user=request.user,
                        defaults={"status": Membership.Status.PENDING},
                    )
            except IntegrityError:
                membership = Membership.objects.get(
                    household=household,
                    user=request.user,
                )
                created = False
            if created:
                messages.success(request, "Your request to join was sent.")
            else:
                messages.info(
                    request,
                    "Your request is already waiting for approval.",
                )
        elif membership.status == Membership.Status.PENDING:
            messages.info(request, "Your request is already waiting for approval.")
        else:
            membership.status = Membership.Status.PENDING
            membership.requested_at = timezone.now()
            membership.approved_at = None
            membership.approved_by = None
            membership.save(
                update_fields=[
                    "status",
                    "requested_at",
                    "approved_at",
                    "approved_by",
                ]
            )
            messages.success(request, "Your request to join was sent again.")
        return redirect("invite", token=token)

    return render(
        request,
        "chores/invite.html",
        {
            "household": household,
            "membership": membership,
        },
    )


@login_required
@require_POST
def membership_decision(request, household_id, membership_id, decision):
    membership = get_approved_membership_or_404(request.user, household_id)
    household = membership.household
    if request.user != household.owner:
        return HttpResponseForbidden("Only the household owner can decide requests.")

    pending_request = get_object_or_404(
        Membership,
        id=membership_id,
        household=household,
        status=Membership.Status.PENDING,
    )
    if decision == "approve":
        pending_request.status = Membership.Status.APPROVED
        pending_request.approved_at = timezone.now()
        pending_request.approved_by = request.user
        pending_request.save(update_fields=["status", "approved_at", "approved_by"])
        messages.success(request, f"{pending_request.user} was approved.")
    elif decision == "reject":
        pending_request.status = Membership.Status.REJECTED
        pending_request.approved_at = None
        pending_request.approved_by = None
        pending_request.save(update_fields=["status", "approved_at", "approved_by"])
        messages.success(request, f"{pending_request.user} was rejected.")
    else:
        raise Http404
    return redirect("household_detail", household_id=household.id)


@login_required
@require_http_methods(["GET", "POST"])
def chore_create(request, household_id):
    membership = get_approved_membership_or_404(request.user, household_id)
    household = membership.household
    if request.method == "POST":
        form = OneTimeChoreForm(request.POST)
        form.instance.household = household
        form.instance.created_by = request.user
        form.instance.schedule_type = ChoreTemplate.ScheduleType.ONE_TIME
        if form.is_valid():
            with transaction.atomic():
                template = form.save()
                ChoreInstance.objects.create(
                    household=household,
                    template=template,
                    title_snapshot=template.title,
                    description_snapshot=template.description,
                    due_at=template.one_time_due_at,
                )
            messages.success(request, "Chore created.")
            return redirect("household_detail", household_id=household.id)
    else:
        form = OneTimeChoreForm()
    return render(
        request,
        "chores/chore_form.html",
        {
            "form": form,
            "household": household,
            "form_title": "Create a one-time chore",
            "submit_label": "Create chore",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def chore_edit(request, household_id, template_id):
    membership = get_approved_membership_or_404(request.user, household_id)
    household = membership.household
    template = get_chore_template_for_user_or_404(request.user, template_id)
    if template.household_id != household.id or not template.is_active:
        raise Http404
    is_weekly = template.schedule_type == ChoreTemplate.ScheduleType.WEEKLY
    form_class = WeeklyChoreForm if is_weekly else OneTimeChoreForm

    if request.method == "POST":
        form = form_class(request.POST, instance=template)
        if form.is_valid():
            with transaction.atomic():
                template = form.save()
                instances = template.instances.filter(
                    status=ChoreInstance.Status.OPEN,
                )
                update_values = {
                    "title_snapshot": template.title,
                    "description_snapshot": template.description,
                }
                if is_weekly:
                    week_start, _ = current_week_range()
                    instances = instances.filter(
                        week_start_date=week_start.date(),
                    )
                    update_values["due_at"] = weekly_due_at(
                        week_start.date(),
                        template.weekly_due_weekday,
                    )
                else:
                    update_values["due_at"] = template.one_time_due_at
                instances.update(
                    title_snapshot=template.title,
                    description_snapshot=template.description,
                    due_at=update_values["due_at"],
                )
            messages.success(request, "Chore updated.")
            return redirect("household_detail", household_id=household.id)
    else:
        form = form_class(instance=template)
    return render(
        request,
        "chores/chore_form.html",
        {
            "form": form,
            "household": household,
            "form_title": "Edit weekly chore" if is_weekly else "Edit chore",
            "submit_label": "Save changes",
        },
    )


@login_required
@require_POST
def chore_delete(request, household_id, template_id):
    membership = get_approved_membership_or_404(request.user, household_id)
    household = membership.household
    template = get_chore_template_for_user_or_404(request.user, template_id)
    if template.household_id != household.id or not template.is_active:
        raise Http404
    with transaction.atomic():
        template.is_active = False
        template.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "Chore deleted.")
    return redirect("household_detail", household_id=household.id)


@login_required
@require_http_methods(["GET", "POST"])
def weekly_chore_create(request, household_id):
    membership = get_approved_membership_or_404(request.user, household_id)
    household = membership.household
    if request.method == "POST":
        form = WeeklyChoreForm(request.POST)
        form.instance.household = household
        form.instance.created_by = request.user
        form.instance.schedule_type = ChoreTemplate.ScheduleType.WEEKLY
        if form.is_valid():
            form.save()
            generate_current_week_instances(household)
            messages.success(request, "Weekly chore created.")
            return redirect("household_detail", household_id=household.id)
    else:
        form = WeeklyChoreForm()
    return render(
        request,
        "chores/chore_form.html",
        {
            "form": form,
            "household": household,
            "form_title": "Create a weekly chore",
            "submit_label": "Create weekly chore",
        },
    )


@login_required
@require_POST
def assignment_action(request, household_id, instance_id, action):
    membership = get_approved_membership_or_404(request.user, household_id)
    household = membership.household
    with transaction.atomic():
        instance = get_chore_instance_for_user_or_404(
            request.user,
            instance_id,
            for_update=True,
        )
        if (
            instance.household_id != household.id
            or instance.status != ChoreInstance.Status.OPEN
        ):
            raise Http404

        now = timezone.now()
        if (
            action == "claim"
            and instance.assignment_status
            == ChoreInstance.AssignmentStatus.UNASSIGNED
        ):
            instance.assignment_status = ChoreInstance.AssignmentStatus.ACCEPTED
            instance.assigned_to = request.user
            instance.assigned_by = request.user
            instance.assigned_at = now
            instance.accepted_at = now
            message = "Chore claimed."
        elif (
            action == "accept"
            and instance.assignment_status
            == ChoreInstance.AssignmentStatus.PENDING
            and instance.assigned_to_id == request.user.id
        ):
            instance.assignment_status = ChoreInstance.AssignmentStatus.ACCEPTED
            instance.accepted_at = now
            message = "Assignment accepted."
        elif (
            action == "decline"
            and instance.assignment_status
            == ChoreInstance.AssignmentStatus.PENDING
            and instance.assigned_to_id == request.user.id
        ):
            instance.assignment_status = ChoreInstance.AssignmentStatus.UNASSIGNED
            instance.assigned_to = None
            instance.assigned_by = None
            instance.assigned_at = None
            instance.accepted_at = None
            message = "Assignment declined."
        elif (
            action == "unclaim"
            and instance.assignment_status
            == ChoreInstance.AssignmentStatus.ACCEPTED
            and instance.assigned_to_id == request.user.id
        ):
            instance.assignment_status = ChoreInstance.AssignmentStatus.UNASSIGNED
            instance.assigned_to = None
            instance.assigned_by = None
            instance.assigned_at = None
            instance.accepted_at = None
            message = "Chore returned to Open."
        else:
            return HttpResponseForbidden("That assignment action is not allowed.")

        instance.save(
            update_fields=[
                "assignment_status",
                "assigned_to",
                "assigned_by",
                "assigned_at",
                "accepted_at",
                "updated_at",
            ]
        )
    messages.success(request, message)
    return redirect("household_detail", household_id=household.id)


@login_required
@require_POST
def chore_assign(request, household_id, instance_id):
    membership = get_approved_membership_or_404(request.user, household_id)
    household = membership.household
    target_membership = get_object_or_404(
        Membership,
        household=household,
        user_id=request.POST.get("assignee"),
        status=Membership.Status.APPROVED,
    )
    if target_membership.user_id == request.user.id:
        return HttpResponseBadRequest("Use Claim to assign this chore to yourself.")
    with transaction.atomic():
        instance = get_chore_instance_for_user_or_404(
            request.user,
            instance_id,
            for_update=True,
        )
        if (
            instance.household_id != household.id
            or instance.status != ChoreInstance.Status.OPEN
        ):
            raise Http404
        if instance.assignment_status not in [
            ChoreInstance.AssignmentStatus.UNASSIGNED,
            ChoreInstance.AssignmentStatus.ACCEPTED,
        ]:
            return HttpResponseForbidden("This chore cannot be assigned right now.")
        if (
            instance.assignment_status == ChoreInstance.AssignmentStatus.ACCEPTED
            and request.POST.get("confirm") != "yes"
        ):
            messages.error(
                request,
                "Confirm reassignment before changing the current assignee.",
            )
            return redirect("household_detail", household_id=household.id)

        instance.assignment_status = ChoreInstance.AssignmentStatus.PENDING
        instance.assigned_to = target_membership.user
        instance.assigned_by = request.user
        instance.assigned_at = timezone.now()
        instance.accepted_at = None
        instance.save(
            update_fields=[
                "assignment_status",
                "assigned_to",
                "assigned_by",
                "assigned_at",
                "accepted_at",
                "updated_at",
            ]
        )
    messages.success(
        request,
        f"Assignment proposed to {target_membership.user}.",
    )
    return redirect("household_detail", household_id=household.id)


@login_required
@require_POST
def chore_complete(request, household_id, instance_id):
    membership = get_approved_membership_or_404(request.user, household_id)
    household = membership.household
    with transaction.atomic():
        instance = get_chore_instance_for_user_or_404(
            request.user,
            instance_id,
            for_update=True,
        )
        if (
            instance.household_id != household.id
            or instance.status != ChoreInstance.Status.OPEN
        ):
            raise Http404

        completion_needs_confirmation = (
            instance.assigned_to_id is not None
            and instance.assigned_to_id != request.user.id
            and instance.assignment_status
            in [
                ChoreInstance.AssignmentStatus.PENDING,
                ChoreInstance.AssignmentStatus.ACCEPTED,
            ]
        )
        if completion_needs_confirmation and request.POST.get("confirm") != "yes":
            messages.error(
                request,
                "Confirm completion because this chore belongs to someone else.",
            )
            return redirect("household_detail", household_id=household.id)

        instance.status = ChoreInstance.Status.COMPLETED
        instance.completed_by = request.user
        instance.completed_at = timezone.now()
        instance.save(
            update_fields=["status", "completed_by", "completed_at", "updated_at"]
        )
    messages.success(request, "Chore completed.")
    return redirect("household_detail", household_id=household.id)