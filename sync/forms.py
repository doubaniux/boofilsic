from django import forms
from .models import SyncTask

class SyncTaskForm(forms.ModelForm):
    """Form definition for SyncTask."""

    class Meta:
        """Meta definition for SyncTaskform."""

        model = SyncTask
        fields = [
            "user",
            "overwrite",
            "sync_book",
            "sync_movie",
            "sync_music",
            "sync_game",
            "default_public",
        ]

