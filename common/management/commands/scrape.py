from django.core.management.base import BaseCommand
from common.scraper import scraper_registry
import pprint


class Command(BaseCommand):
    help = 'Scrape an item from URL (but not save it)'

    def add_arguments(self, parser):
        parser.add_argument('url', type=str, help='URL to scrape')

    def handle(self, *args, **options):
        url = str(options['url'])
        matched_host = None
        for host in scraper_registry:
            if host in url:
                matched_host = host
                break

        if matched_host is None:
            self.stdout.write(self.style.ERROR(f'Unable to match a scraper for {url}'))
            return

        scraper = scraper_registry[matched_host]
        effective_url = scraper.get_effective_url(url)
        self.stdout.write(f'Fetching {effective_url} via {scraper.__name__}')
        data, img = scraper.scrape(effective_url)
        self.stdout.write(self.style.SUCCESS(f'Done.'))
        pprint.pp(data)
