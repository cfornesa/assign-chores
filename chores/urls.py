from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("households/new/", views.household_create, name="household_create"),
    path(
        "households/<int:household_id>/",
        views.household_detail,
        name="household_detail",
    ),
    path(
        "households/<int:household_id>/members/<int:membership_id>/<str:decision>/",
        views.membership_decision,
        name="membership_decision",
    ),
    path("households/invite/<str:token>/", views.invite, name="invite"),
    path(
        "households/<int:household_id>/chores/new/",
        views.chore_create,
        name="chore_create",
    ),
    path(
        "households/<int:household_id>/chores/new/weekly/",
        views.weekly_chore_create,
        name="weekly_chore_create",
    ),
    path(
        "households/<int:household_id>/chores/<int:template_id>/edit/",
        views.chore_edit,
        name="chore_edit",
    ),
    path(
        "households/<int:household_id>/chores/<int:template_id>/delete/",
        views.chore_delete,
        name="chore_delete",
    ),
    path(
        "households/<int:household_id>/instances/<int:instance_id>/assign/",
        views.chore_assign,
        name="chore_assign",
    ),
    path(
        "households/<int:household_id>/instances/<int:instance_id>/complete/",
        views.chore_complete,
        name="chore_complete",
    ),
    path(
        "households/<int:household_id>/instances/<int:instance_id>/<str:action>/",
        views.assignment_action,
        name="assignment_action",
    ),
]