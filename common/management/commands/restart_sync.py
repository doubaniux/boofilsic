from django.core.management.base import BaseCommand
from redis import Redis
from rq.job import Job
from sync.models import SyncTask
from sync.jobs import import_doufen_task
from django.utils import timezone
import django_rq


class Command(BaseCommand):
    help = 'Restart a sync task'

    def add_arguments(self, parser):
        parser.add_argument('synctask_id', type=int, help='Sync Task ID')

    def handle(self, *args, **options):
        task = SyncTask.objects.get(id=options['synctask_id'])
        task.finished_items = 0
        task.failed_urls = []
        task.success_items = 0
        task.total_items = 0
        task.is_finished = False
        task.is_failed = False
        task.break_point = ''
        task.started_time = timezone.now()
        task.save()
        django_rq.get_queue('doufen').enqueue(import_doufen_task, task, job_id=f'SyncTask_{task.id}')
        self.stdout.write(self.style.SUCCESS(f'Queued {task}'))
