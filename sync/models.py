from django.db import models
from django.utils.translation import ugettext_lazy as _
import django.contrib.postgres.fields as postgres
from users.models import User


class SyncTask(models.Model):
    """A class that records information about douban data synchronization task."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_%(class)ss')
    is_failed = models.BooleanField(default=False)
    # fail_reason = models.TextField(default='')
    is_finished = models.BooleanField(default=False)
    # how many items to synchronize
    total_items = models.PositiveIntegerField(default=0)
    # how many items are handled
    finished_items = models.PositiveIntegerField(default=0)
    # how many imtes have been synchronized successfully
    success_items = models.PositiveIntegerField(default=0)

    failed_urls = postgres.ArrayField(
        models.URLField(blank=True, default='', max_length=200),
        null=True,
        blank=True,
        default=list,
    )

    started_time = models.DateTimeField(auto_now_add=True)
    ended_time = models.DateTimeField(auto_now=True)
    
    # how many items are overwritten
    # overwrite_books = models.PositiveIntegerField(default=0)
    # overwrite_movies = models.PositiveIntegerField(default=0)
    # overwrite_music = models.PositiveIntegerField(default=0)
    # overwrite_games = models.PositiveIntegerField(default=0)

    # options
    # for the same book, if is already marked before sync, overwrite the previous mark or not
    overwrite = models.BooleanField(default=False)
    # sync book marks or not
    sync_book = models.BooleanField()
    # sync movie marks or not
    sync_movie = models.BooleanField()
    # sync music marks or not
    sync_music = models.BooleanField()    
    # sync game marks or not
    sync_game = models.BooleanField()
    # default visibility of marks
    default_public = models.BooleanField()

    # thread pid
    # pid = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        """Meta definition for SyncTask."""

        verbose_name = 'SyncTask'
        verbose_name_plural = 'SyncTasks'

    def __str__(self):
        """Unicode representation of SyncTask."""
        return str(self.user.username) + '@' + str(self.started_time) + self.get_status_emoji()

    def get_status_emoji(self):
        return ("❌" if self.is_failed else "✔") if self.is_finished else "⚡"

    def get_duration(self):
        return self.ended_time - self.started_time
    
    def get_overwritten_items(self):
        if self.overwrite:
            return self.overwrite_books + self.overwrite_games + self.overwrite_movies + self.overwrite_music
        else:
            return 0

    def get_progress(self):
        """
        @return: return percentage
        """
        if self.is_finished:
            return 100
        else:
            if self.total_items > 0:
                return 100 * self.finished_items / self.total_items
            else:
                return 0
