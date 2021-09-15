from django.apps import AppConfig
from django.conf import settings


class SyncConfig(AppConfig):
    name = 'sync'

    def ready(self):
        from sync.jobs import sync_task_manager
        sync_task_manager.start()