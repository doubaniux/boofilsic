from catalog.common import *
from catalog.models import *
from catalog.sites import *
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
import pprint
from tqdm import tqdm
import logging

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refetch TMDB TV Shows"

    def add_arguments(self, parser):

        parser.add_argument("--minid", help="min id to start")

    def handle(self, *args, **options):
        qs = ExternalResource.objects.all().filter(id_type="tmdb_tv").order_by("id")
        if options["minid"]:
            qs = qs.filter(id__gte=int(options["minid"]))
        for res in tqdm(qs):
            if res:
                try:
                    site = SiteManager.get_site_by_url(res.url)
                    site.get_resource_ready(ignore_existing_content=True)
                    _logger.info(f"fetch {res.url} success {site.get_item().title}")
                except Exception as e:
                    _logger.error(f"fetch {res.url} error {e}")
