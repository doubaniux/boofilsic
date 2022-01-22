from django.core.management.base import BaseCommand
from common.index import Indexer
from django.conf import settings


class Command(BaseCommand):
    help = 'Initialize the search index'

    def handle(self, *args, **options):
        print(f'Connecting to search server')
        try:
            Indexer.init()
            self.stdout.write(self.style.SUCCESS('Index created.'))
        except Exception:
            Indexer.update_settings()
            self.stdout.write(self.style.SUCCESS('Index settings updated.'))
