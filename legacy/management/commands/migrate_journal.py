from books.models import Book as Legacy_Book
from movies.models import Movie as Legacy_Movie
from music.models import Album as Legacy_Album
from games.models import Game as Legacy_Game
from common.models import MarkStatusEnum
from books.models import BookMark
from movies.models import MovieMark
from music.models import AlbumMark
from games.models import GameMark
from catalog.common import *
from catalog.models import *
from catalog.sites import *
from journal.models import *
# from social import models as social_models
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
import pprint
from tqdm import tqdm
from django.db.models import Q, Count, Sum
from django.utils import dateparse, timezone
import re
from legacy.models import *
from users.models import User
from django.db import DatabaseError, transaction

BATCH_SIZE = 1000


model_link = {
    BookMark: BookLink,
    MovieMark: MovieLink,
    AlbumMark: AlbumLink,
    GameMark: GameLink,
}

shelf_map = {
    MarkStatusEnum.WISH: ShelfType.WISHLIST,
    MarkStatusEnum.DO: ShelfType.PROGRESS,
    MarkStatusEnum.COLLECT: ShelfType.COMPLETE,
}

tag_map = {
    BookMark: 'bookmark_tags',
    MovieMark: 'moviemark_tags',
    AlbumMark: 'albummark_tags',
    GameMark: 'gamemark_tags',
}


class Command(BaseCommand):
    help = 'Migrate legacy marks to user journal'

    def add_arguments(self, parser):
        parser.add_argument('--book', dest='types', action='append_const', const=BookMark)
        parser.add_argument('--movie', dest='types', action='append_const', const=MovieMark)
        parser.add_argument('--album', dest='types', action='append_const', const=AlbumMark)
        parser.add_argument('--game', dest='types', action='append_const', const=GameMark)
        parser.add_argument('--id', help='id to convert; or, if using with --max-id, the min id')
        parser.add_argument('--maxid', help='max id to convert')
        parser.add_argument('--failstop', help='stop on fail', action='store_true')
        parser.add_argument('--initshelf', help='initialize shelves for users, then exit', action='store_true')
        parser.add_argument('--clear', help='clear all user pieces, then exit', action='store_true')

    def handle(self, *args, **options):
        if options['initshelf']:
            print("Initialize shelves")
            with transaction.atomic():
                for user in tqdm(User.objects.filter(is_active=True)):
                    user.shelf_manager.initialize()
            return

        if options['clear']:
            print("Deleting all migrated user pieces")
            # Piece.objects.all().delete()
            for cls in [Review, Comment, Rating, Tag, ShelfLogEntry, ShelfMember, Shelf]:  # Collection
                print(cls)
                cls.objects.all().delete()
            return

        types = options['types'] or [GameMark, AlbumMark, MovieMark, BookMark]
        for typ in types:
            print(typ)
            LinkModel = model_link[typ]
            tag_field = tag_map[typ]
            qs = typ.objects.all().filter(owner__is_active=True).order_by('id')
            if options['id']:
                if options['maxid']:
                    qs = qs.filter(id__gte=int(options['id']), id__lte=int(options['maxid']))
                else:
                    qs = qs.filter(id=int(options['id']))

            pg = Paginator(qs, BATCH_SIZE)
            for p in tqdm(pg.page_range):
                with transaction.atomic():
                    for entity in pg.get_page(p).object_list:
                        try:
                            item_link = LinkModel.objects.get(old_id=entity.item.id)
                            item = Item.objects.get(uid=item_link.new_uid)
                            mark = Mark(entity.owner, item)
                            mark.update(
                                shelf_type=shelf_map[entity.status],
                                comment_text=entity.text,
                                rating_grade=entity.rating,
                                visibility=entity.visibility,
                                metadata={'shared_link': entity.shared_link},
                                created_time=entity.created_time
                            )
                            tags = [t.content for t in getattr(entity, tag_field).all()]
                            TagManager.tag_item_by_user(item, entity.owner, tags)
                        except Exception as e:
                            print(f'Convert failed for {typ} {entity.id}: {e}')
                            if options['failstop']:
                                raise(e)
        self.stdout.write(self.style.SUCCESS(f'Done.'))
