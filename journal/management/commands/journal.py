from django.core.management.base import BaseCommand
import pprint
from journal.models import *


class Command(BaseCommand):
    help = "Scrape a catalog item from external resource (and save it)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="purge invalid data",
        )

    def handle(self, *args, **options):
        if options["cleanup"]:
            self.stdout.write(f"Cleaning up Rating...")
            Rating.objects.filter(grade=0).delete()
            for cls in ListMember.__subclasses__():
                self.stdout.write(f"Cleaning up {cls}...")
                cls.objects.filter(visibility=99).delete()

        self.stdout.write(self.style.SUCCESS(f"Done."))
