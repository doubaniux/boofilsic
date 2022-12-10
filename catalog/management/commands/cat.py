from django.core.management.base import BaseCommand
import pprint
from catalog.common import SiteList
from catalog.sites import *


class Command(BaseCommand):
    help = 'Scrape a catalog item from external resource (but not save it)'

    def add_arguments(self, parser):
        parser.add_argument('url', type=str, help='URL to scrape')

    def handle(self, *args, **options):
        url = str(options['url'])
        site = SiteList.get_site_by_url(url)
        if site is None:
            self.stdout.write(self.style.ERROR(f'Unknown site for {url}'))
            return
        self.stdout.write(f'Fetching from {site}')
        resource = site.scrape()
        self.stdout.write(self.style.SUCCESS(f'Done.'))
        pprint.pp(resource.metadata)
        pprint.pp(resource.lookup_ids)
