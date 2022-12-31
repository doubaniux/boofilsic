from django.core.management.base import BaseCommand
from django.conf import settings
from catalog.models import *
import pprint


class Command(BaseCommand):
    help = "Manage the search index"

    def add_arguments(self, parser):
        parser.add_argument(
            "--init",
            help="initialize index",
            action="store_true",
        )
        parser.add_argument(
            "--stat",
            action="store_true",
        )

    def init_index(self):
        self.stdout.write(f"Connecting to search server")
        Indexer.init()
        self.stdout.write(self.style.SUCCESS("Index created."))

    def stat(self, *args, **options):
        self.stdout.write(f"Connecting to search server")
        stats = Indexer.get_stats()
        pprint.pp(stats)

    def handle(self, *args, **options):
        if options["init"]:
            self.init_index()
        elif options["stat"]:
            self.stat()
        # else:

        # try:
        #     Indexer.init()
        #     self.stdout.write(self.style.SUCCESS('Index created.'))
        # except Exception:
        #     Indexer.update_settings()
        #     self.stdout.write(self.style.SUCCESS('Index settings updated.'))
