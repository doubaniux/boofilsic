from django.apps import AppConfig

from datetime import datetime

import django_rq

class UsersConfig(AppConfig):
    name = 'users'

    def ready(self) -> None:
        from .tasks import refresh_mastodon_relationships_task

        scheduler = django_rq.get_scheduler('mastodon')

        for job in scheduler.get_jobs():
            job.delete()

        # run every hour
        scheduler.schedule(
            datetime.utcnow(),
            refresh_mastodon_relationships_task,
            interval=60 * 60,
            result_ttl=3600 * 2,
        )