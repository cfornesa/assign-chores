from django import forms

from .models import ChoreTemplate, Household


class HouseholdForm(forms.ModelForm):
    class Meta:
        model = Household
        fields = ["name"]
        labels = {"name": "Household name"}
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Oak Street House",
                    "autocomplete": "organization",
                }
            )
        }


class OneTimeChoreForm(forms.ModelForm):
    class Meta:
        model = ChoreTemplate
        fields = ["title", "description", "one_time_due_at"]
        labels = {"one_time_due_at": "Due date and time (optional)"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "one_time_due_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["one_time_due_at"].input_formats = ["%Y-%m-%dT%H:%M"]


class WeeklyChoreForm(forms.ModelForm):
    class Meta:
        model = ChoreTemplate
        fields = ["title", "description", "weekly_due_weekday"]
        labels = {"weekly_due_weekday": "Due weekday"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }