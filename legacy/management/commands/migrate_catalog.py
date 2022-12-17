from books.models import Book as Legacy_Book
from movies.models import Movie as Legacy_Movie
from music.models import Album as Legacy_Album
from games.models import Game as Legacy_Game
from catalog.common import *
from catalog.models import *
from catalog.sites import *
from catalog.book.utils import detect_isbn_asin
from journal import models as journal_models
from social import models as social_models
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
import pprint
from tqdm import tqdm
from django.db.models import Q, Count, Sum
from django.utils import dateparse, timezone
import re
from legacy.models import *


BATCH_SIZE = 1000


def _book_convert(entity):
    content = ResourceContent(metadata={
        'title': entity.title,
        'brief': entity.brief,
        'cover_image_path': str(entity.cover),

        'subtitle': entity.subtitle,
        'orig_title': entity.orig_title,
        'author': entity.author,
        'translator': entity.translator,
        'language': entity.language,
        'pub_house': entity.pub_house,
        'pub_year': entity.pub_year,
        'pub_month': entity.pub_month,
        'binding': entity.binding,
        'price': entity.price,
        'pages': entity.pages,
        'contents': entity.contents,
        'series': entity.other_info.get('丛书') if entity.other_info else None,
        'imprint': entity.other_info.get('出品方') if entity.other_info else None,
    })
    if entity.isbn:
        t, v = detect_isbn_asin(entity.isbn)
        if t:
            content.lookup_ids[t] = v
    if entity.other_info and entity.other_info.get('统一书号'):
        content.lookup_ids[IdType.CUBN] = entity.other_info.get('统一书号')
    return content


def _album_convert(entity):
    content = ResourceContent(metadata={
        'title': entity.title,
        'brief': entity.brief,
        'cover_image_path': str(entity.cover),

        'other_title': entity.other_info.get('又名') if entity.other_info else None,
        'album_type': entity.other_info.get('专辑类型') if entity.other_info else None,
        'media': entity.other_info.get('介质') if entity.other_info else None,
        'disc_count': entity.other_info.get('碟片数') if entity.other_info else None,
        'artist': entity.artist,
        'genre': entity.genre,
        'release_date': entity.release_date.strftime('%Y-%m-%d') if entity.release_date else None,
        'duration': entity.duration,
        'company': entity.company,
        'track_list': entity.track_list,
        'bandcamp_album_id': entity.other_info.get('bandcamp_album_id') if entity.other_info else None,
    })
    if entity.other_info and entity.other_info.get('ISRC'):
        content.lookup_ids[IdType.ISRC] = entity.other_info.get('ISRC')
    if entity.other_info and entity.other_info.get('条形码'):
        content.lookup_ids[IdType.GTIN] = entity.other_info.get('条形码')
    if entity.other_info and entity.other_info.get('UPC'):
        content.lookup_ids[IdType.GTIN] = entity.other_info.get('UPC')
    return content


def _game_convert(entity):
    content = ResourceContent(metadata={
        'title': entity.title,
        'brief': entity.brief,
        'cover_image_path': str(entity.cover),

        'other_title': entity.other_title,
        'developer': entity.developer,
        'publisher': entity.publisher,
        'release_date': entity.release_date.strftime('%Y-%m-%d') if entity.release_date else None,
        'genre': entity.genre,
        'platform': entity.platform,
        'official_site': entity.other_info.get('official_site') if entity.other_info else None,
    })
    if entity.other_info and entity.other_info.get('steam_url'):
        content.lookup_ids[IdType.Steam] = re.search(r'store\.steampowered\.com/app/(\d+)', entity.other_info.get('steam_url'))[1]
    return content


def _movie_tv_convert(entity):
    content = ResourceContent(metadata={
        'title': entity.title,
        'brief': entity.brief,
        'cover_image_path': str(entity.cover),

        'orig_title': entity.orig_title,
        'other_title': entity.other_title,
        'director': entity.director,
        'playwright': entity.playwright,
        'actor': entity.actor,
        'genre': entity.genre,
        'showtime': entity.showtime,
        'site': entity.site,
        'area': entity.area,
        'language': entity.language,
        'year': entity.year,
        'duration': entity.duration,
        'season_count': entity.other_info.get('Seasons') if entity.other_info else None,
        'season_number': entity.season,
        'episode_count': entity.episodes,
        'single_episode_length': entity.single_episode_length,
        'is_series': entity.is_series,
    })
    if entity.imdb_code:
        content.lookup_ids[IdType.IMDB] = entity.imdb_code
    if entity.other_info and entity.other_info.get('TMDB_ID'):
        content.lookup_ids[IdType.TMDB_TV] = entity.other_info.get('TMDB_ID')
    return content


Legacy_Book.convert = _book_convert
Legacy_Movie.convert = _movie_tv_convert
Legacy_Game.convert = _game_convert
Legacy_Album.convert = _album_convert
model_map = {
    Legacy_Book: Edition,
    Legacy_Movie: Movie,
    Legacy_Game: Game,
    Legacy_Album: Album,
}
model_link = {
    Legacy_Book: BookLink,
    Legacy_Movie: MovieLink,
    Legacy_Game: GameLink,
    Legacy_Album: AlbumLink,
}


class Command(BaseCommand):
    help = 'Migrate legacy books'

    def add_arguments(self, parser):
        parser.add_argument('--book', dest='types', action='append_const', const=Legacy_Book)
        parser.add_argument('--movie', dest='types', action='append_const', const=Legacy_Movie)
        parser.add_argument('--album', dest='types', action='append_const', const=Legacy_Album)
        parser.add_argument('--game', dest='types', action='append_const', const=Legacy_Game)
        parser.add_argument('--id', help='id to convert; or, if using with --max-id, the min id')
        parser.add_argument('--maxid', help='max id to convert')
        parser.add_argument('--failstop', help='stop on fail', action='store_true')
        parser.add_argument('--clearlink', help='clear legacy link table', action='store_true')
        parser.add_argument('--reload', help='reload and ignore existing ExternalResource', action='store_true')

    def handle(self, *args, **options):
        types = options['types'] or [Legacy_Game, Legacy_Album, Legacy_Movie, Legacy_Book]
        reload = options['reload']
        for typ in types:
            print(typ)
            LinkModel = model_link[typ]
            if options['clearlink']:
                LinkModel.objects.all().delete()
            qs = typ.objects.all().order_by('id')  # if h == 0 else c.objects.filter(edited_time__gt=timezone.now() - timedelta(hours=h))
            if options['id']:
                if options['maxid']:
                    qs = qs.filter(id__gte=int(options['id']), id__lte=int(options['maxid']))
                else:
                    qs = qs.filter(id=int(options['id']))

            pg = Paginator(qs, BATCH_SIZE)
            for p in tqdm(pg.page_range):
                links = []
                for entity in pg.get_page(p).object_list:
                    try:
                        content = entity.convert()
                        site = SiteManager.get_site_by_url(entity.source_url)
                        item = None
                        if site:
                            if not site.DEFAULT_MODEL and not content.metadata.get('preferred_model'):
                                if model_map[typ] == Movie and entity.is_series:
                                    content.metadata['preferred_model'] = 'TVSeason' if entity.season else 'TVShow'
                                else:
                                    content.metadata['preferred_model'] = model_map[typ].__name__
                            item = site.get_resource_ready(preloaded_content=content, ignore_existing_content=reload).item
                        else:
                            # not known site, try save item without external resource
                            item = None
                            model = Edition
                            t, v = None, None
                            if content.lookup_ids:
                                t, v = Item.get_best_lookup_id(content.lookup_ids)
                                item = model.objects.filter(primary_lookup_id_type=t, primary_lookup_id_value=v).first()
                            if not item:
                                obj = model.copy_metadata(content.metadata)
                                obj['primary_lookup_id_type'] = t
                                obj['primary_lookup_id_value'] = v
                                item = model.objects.create(**obj)
                            item.cover = content.metadata['cover_image_path']
                            item.save()
                        links.append(LinkModel(old_id=entity.id, new_uid=item.uid))
                        # pprint.pp(site.get_item())
                    except Exception as e:
                        print(f'Convert failed for {entity}: {e}')
                        if options['failstop']:
                            raise(e)
                    # return
                LinkModel.objects.bulk_create(links)
        self.stdout.write(self.style.SUCCESS(f'Done.'))
