from django.http import Http404

from .models import ChoreInstance, ChoreTemplate, Membership


def get_approved_membership_or_404(user, household_id):
    try:
        return Membership.objects.select_related("household").get(
            household_id=household_id,
            user=user,
            status=Membership.Status.APPROVED,
        )
    except Membership.DoesNotExist as exc:
        raise Http404 from exc


def get_chore_template_for_user_or_404(user, template_id):
    try:
        return ChoreTemplate.objects.select_related("household").get(
            id=template_id,
            household__memberships__user=user,
            household__memberships__status=Membership.Status.APPROVED,
        )
    except ChoreTemplate.DoesNotExist as exc:
        raise Http404 from exc


def get_chore_instance_for_user_or_404(user, instance_id, *, for_update=False):
    queryset = ChoreInstance.objects.select_related(
        "household",
        "template",
        "assigned_to",
        "completed_by",
    )
    if for_update:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(
            id=instance_id,
            household__memberships__user=user,
            household__memberships__status=Membership.Status.APPROVED,
        )
    except ChoreInstance.DoesNotExist as exc:
        raise Http404 from exc