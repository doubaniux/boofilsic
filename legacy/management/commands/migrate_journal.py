from books.models import Book as Legacy_Book
from movies.models import Movie as Legacy_Movie
from music.models import Album as Legacy_Album
from games.models import Game as Legacy_Game
from common.models import MarkStatusEnum
from books.models import BookMark, BookReview
from movies.models import MovieMark, MovieReview
from music.models import AlbumMark, AlbumReview
from games.models import GameMark, GameReview
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
    BookReview: BookLink,
    MovieReview: MovieLink,
    AlbumReview: AlbumLink,
    GameReview: GameLink,
}

shelf_map = {
    ShelfType.WISHLIST: MarkStatusEnum.WISH,
    ShelfType.PROGRESS: MarkStatusEnum.DO,
    ShelfType.COMPLETE: MarkStatusEnum.COLLECT,
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
        parser.add_argument('--mark', help='migrate shelves/tags/ratings, then exit', action='store_true')
        parser.add_argument('--review', help='migrate reviews, then exit', action='store_true')
        parser.add_argument('--collection', help='migrate collections, then exit', action='store_true')
        parser.add_argument('--id', help='id to convert; or, if using with --max-id, the min id')
        parser.add_argument('--maxid', help='max id to convert')
        parser.add_argument('--failstop', help='stop on fail', action='store_true')
        parser.add_argument('--initshelf', help='initialize shelves for users, then exit', action='store_true')
        parser.add_argument('--clear', help='clear all user pieces, then exit', action='store_true')

    def initshelf(self):
        print("Initialize shelves")
        with transaction.atomic():
            for user in tqdm(User.objects.filter(is_active=True)):
                user.shelf_manager.initialize()

    def clear(self):
        print("Deleting all migrated user pieces")
        # Piece.objects.all().delete()
        for cls in [Review, Comment, Rating, TagMember, Tag, ShelfLogEntry, ShelfMember]:  # Collection
            print(cls)
            cls.objects.all().delete()

    def collection(self, options):
        pass

    def review(self, options):
        for typ in [GameReview, AlbumReview, BookReview, MovieReview]:
            print(typ)
            LinkModel = model_link[typ]
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
                            Review.review_item_by_user(item, entity.owner, entity.title, entity.content, {'shared_link': entity.shared_link}, entity.visibility)
                        except Exception as e:
                            print(f'Convert failed for {typ} {entity.id}: {e}')
                            if options['failstop']:
                                raise(e)

    def mark(self, options):
        types = options['types'] or [GameMark, AlbumMark, MovieMark, BookMark]
        print('Preparing cache')
        tag_cache = {f'{t.owner_id}_{t.title}': t.id for t in Tag.objects.all()}
        shelf_cache = {f'{s.owner_id}_{s.item_category}_{shelf_map[s.shelf_type]}': s.id for s in Shelf.objects.all()}

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
                            tags = [t.content for t in getattr(entity, tag_field).all()]
                            """
                            mark = Mark(entity.owner, item)
                            mark.update(
                                shelf_type=shelf_map[entity.status],
                                comment_text=entity.text,
                                rating_grade=entity.rating,
                                visibility=entity.visibility,
                                metadata={'shared_link': entity.shared_link},
                                created_time=entity.created_time
                            )
                            TagManager.tag_item_by_user(item, entity.owner, tags)
                            """  # rewrote above with direct create to speed up
                            user_id = entity.owner_id
                            item_id = item.id
                            visibility = entity.visibility
                            created_time = entity.created_time
                            if entity.rating:
                                Rating.objects.create(owner_id=user_id, item_id=item_id, grade=entity.rating, visibility=visibility)
                            if entity.text:
                                Comment.objects.create(owner_id=user_id, item_id=item_id, text=entity.text, visibility=visibility)
                            shelf = shelf_cache[f'{user_id}_{item.category}_{entity.status}']
                            ShelfMember.objects.create(
                                _shelf_id=shelf,
                                owner_id=user_id,
                                position=0,
                                item_id=item_id,
                                metadata={'shared_link': entity.shared_link},
                                created_time=created_time)
                            ShelfLogEntry.objects.create(owner_id=user_id, shelf_id=shelf, item_id=item_id, timestamp=created_time)
                            for title in tags:
                                tag_key = f'{user_id}_{title}'
                                if tag_key not in tag_cache:
                                    tag = Tag.objects.create(owner_id=user_id, title=title, visibility=0).id
                                    tag_cache[tag_key] = tag
                                else:
                                    tag = tag_cache[tag_key]
                                TagMember.objects.create(
                                    _tag_id=tag,
                                    owner_id=user_id,
                                    position=0,
                                    item_id=item_id,
                                    created_time=created_time)
                        except Exception as e:
                            print(f'Convert failed for {typ} {entity.id}: {e}')
                            if options['failstop']:
                                raise(e)

    def handle(self, *args, **options):
        if options['initshelf']:
            self.initshelf()
        elif options['clear']:
            self.clear()
        elif options['collection']:
            self.collection(options)
        elif options['review']:
            self.review(options)
        elif options['mark']:
            self.mark(options)
        self.stdout.write(self.style.SUCCESS(f'Done.'))
