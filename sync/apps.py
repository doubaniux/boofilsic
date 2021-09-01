from django.apps import AppConfig


class SyncConfig(AppConfig):
    name = 'sync'

    def ready(self):
        from sync.jobs import sync_task_manager
        sync_task_manager.start()