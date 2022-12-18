import os
from django.core.management.base import BaseCommand
from users.models import User
from users.tasks import export_marks_task


class Command(BaseCommand):
    help = 'Backfill Mastodon data if missing'

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('user_id', type=int, help='User ID in the DB')
        parser.add_argument('output', type=str, help='Full path of output')

    def handle(self, *args, **options):
        user_id = options['user_id']
        path = options['output']
        if not os.path.exists(path) and not os.access(os.path.dirname(path), os.W_OK):
            raise ValueError("Invalid path")

        user = User.objects.get(id=user_id)
        export_marks_task(user, file=path)
