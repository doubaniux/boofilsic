from django.core.management.base import BaseCommand
import pprint
from catalog.models import *


class Command(BaseCommand):
    help = "catalog app utilities"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="purge invalid data (is_deleted=true)",
        )

    def handle(self, *args, **options):
        if options["cleanup"]:
            for cls in Item.__subclasses__():
                self.stdout.write(f"Cleaning up {cls}...")
                cls.objects.filter(is_deleted=True).delete()

        self.stdout.write(self.style.SUCCESS(f"Done."))
