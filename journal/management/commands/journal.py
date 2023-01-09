from django.core.management.base import BaseCommand
import pprint
from journal.models import *


class Command(BaseCommand):
    help = "journal app utilities"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="purge invalid data (visibility=99)",
        )

    def handle(self, *args, **options):
        if options["cleanup"]:
            for pcls in [Content, ListMember]:
                for cls in pcls.__subclasses__():
                    self.stdout.write(f"Cleaning up {cls}...")
                    cls.objects.filter(visibility=99).delete()

        self.stdout.write(self.style.SUCCESS(f"Done."))
