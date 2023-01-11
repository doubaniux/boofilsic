from rq.utils import first
from catalog.common import *
from catalog.models import *
from catalog.sites import *
from catalog.sites.tmdb import *
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
import pprint
from tqdm import tqdm
import logging
import csv

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    load imdb episode -> show mapping - https://www.imdb.com/interfaces/
    """

    help = "Refetch Douban TV Shows"

    def add_arguments(self, parser):
        parser.add_argument("--minid", help="min id to start")

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Loading imdb data.tsv"))
        catalog = {}
        episodes = {}
        seasons = {}
        shows = {}
        c = {
            "fix-show": 0,
            "fix-season": 0,
            "missing-tmdb": 0,
            "missing-imdb": 0,
        }
        with open("../data.tsv", newline="") as csvfile:
            reader = csv.reader(csvfile, delimiter="\t")
            next(reader)
            for row in reader:
                episodes[row[0]] = {
                    "parent": row[1],
                    "season": int(row[2]) if row[2] != "\\N" else 0,
                    "episode": int(row[3]) if row[3] != "\\N" else 0,
                }
                shows[row[1]] = True
                if row[3] == "1":
                    seasons[f"{row[1]}-{row[2]}"] = row[0]

        self.stdout.write(self.style.SUCCESS(f"Refreshing catalog tv seasons"))
        qs = (
            TVSeason.objects.all()
            .order_by("id")
            .filter(primary_lookup_id_type=IdType.IMDB, show__isnull=True)
        )
        if options["minid"]:
            qs = qs.filter(id__gte=int(options["minid"]))

        for item in tqdm(qs):
            imdb = item.primary_lookup_id_value
            show_imdb = None
            ep1_imdb = None
            season = None
            if imdb in episodes:
                show_imdb = episodes[imdb]["parent"]
                season = episodes[imdb]["season"]
            elif imdb in shows:
                show_imdb = imdb
            if show_imdb:
                show = catalog.get(show_imdb)
                if not show:
                    show = (
                        TVShow.objects.all()
                        .filter(
                            primary_lookup_id_type=IdType.IMDB,
                            primary_lookup_id_value=show_imdb,
                        )
                        .first()
                    )
                if not show:
                    res = None
                    try:
                        res_data = search_tmdb_by_imdb_id(show_imdb)
                        if "tv_results" in res_data and len(res_data["tv_results"]) > 0:
                            url = f"https://www.themoviedb.org/tv/{res_data['tv_results'][0]['id']}"
                            site = SiteManager.get_site_by_url(url)
                            res = site.get_resource_ready()
                    except Exception as e:
                        _logger.warn(e)
                    show = res.item if res else None
                    if show and show.__class__ != TVShow:
                        _logger.warn(f"error {show} is not show")
                        show = None
                if show:
                    catalog[show_imdb] = show
                    item.show = show
                    _logger.info(f"linked {item} with {show}")
                    if season and season != item.season_number:
                        _logger.warn(
                            f"fix season number for {item} from {item.season_number} to {season}"
                        )
                        item.season_number = season
                        c["fix-season"] += 1
                    item.save()
                    c["fix-show"] += 1
                else:
                    _logger.warn(f"Can't find {show_imdb} in TMDB for {item}")
                    c["missing-tmdb"] += 1
            else:
                c["missing-imdb"] += 1

        self.stdout.write(self.style.SUCCESS(f"Done"))
        pprint.pp(c)
