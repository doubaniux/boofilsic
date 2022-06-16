from django.core.management.base import BaseCommand
from common.scraper import get_scraper_by_url, get_normalized_url
import pprint
from sync.models import SyncTask
from users.models import User
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from tqdm import tqdm
from django.conf import settings
import requests


class Command(BaseCommand):
    help = 'Re-scrape failed urls (via local proxy)'

    def handle(self, *args, **options):
        self.stdout.write(f'Checking local proxy...')
        url = f'{settings.LOCAL_PROXY}?url=https://www.douban.com/doumail/'
        try:
            r = requests.get(url, timeout=settings.SCRAPING_TIMEOUT)
        except Exception as e:
            self.stdout.write(self.style.ERROR(e))
            return
        content = r.content.decode('utf-8')
        if content.find('我的豆邮') == -1:
            self.stdout.write(self.style.ERROR(f'Proxy check failed.'))
            return

        self.stdout.write(f'Loading failed urls...')
        tasks = SyncTask.objects.filter(failed_urls__isnull=False)
        urls = []
        for task in tasks:
            for url in task.failed_urls:
                if url not in urls:
                    urls.append(url)
        with open("/tmp/resync_failed.txt") as file:
            skips = file.readlines()
            skips = [line.strip() for line in skips]
        f_f = open("/tmp/resync_failed.txt", "a")
        f_i = open("/tmp/resync_ignore.txt", "a")
        f_s = open("/tmp/resync_success.txt", "a")
        user = User.objects.get(id=1)

        for url in tqdm(urls):
            url = get_normalized_url(url)
            scraper = get_scraper_by_url(url)
            url = scraper.get_effective_url(url)
            if url in skips:
                self.stdout.write(f'Skip {url}')
            elif scraper is None:
                self.stdout.write(self.style.ERROR(f'Unable to find scraper for {url}'))
                f_i.write(url + '\n')
            else:
                try:
                    entity = scraper.data_class.objects.get(source_url=url)
                    f_i.write(url + '\n')
                except ObjectDoesNotExist:
                    try:
                        # self.stdout.write(f'Fetching {url} via {scraper.__name__}')
                        scraper.scrape(url)
                        form = scraper.save(request_user=user)
                        f_s.write(url + '\n')
                        # self.stdout.write(self.style.SUCCESS(f'Saved.'))
                    except Exception as e:
                        f_f.write(url + '\n')
                        # self.stdout.write(self.style.ERROR(f'Error.'))
