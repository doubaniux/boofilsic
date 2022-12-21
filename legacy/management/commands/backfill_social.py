from books.models import Book as Legacy_Book
from movies.models import Movie as Legacy_Movie
from music.models import Album as Legacy_Album
from music.models import Song as Legacy_Song
from games.models import Game as Legacy_Game
from common.models import MarkStatusEnum
from books.models import BookMark, BookReview
from movies.models import MovieMark, MovieReview
from music.models import AlbumMark, AlbumReview
from games.models import GameMark, GameReview
from collection.models import Collection as Legacy_Collection
from collection.models import CollectionMark as Legacy_CollectionMark
from catalog.common import *
from catalog.models import *
from catalog.sites import *
from journal.models import *
from social.models import *
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


template_map = {
    ShelfMember: ActivityTemplate.MarkItem,
    Collection: ActivityTemplate.CreateCollection,
    Like: ActivityTemplate.LikeCollection,
    Review: ActivityTemplate.ReviewItem,
}


class Command(BaseCommand):
    help = 'Backfill user activities'

    def add_arguments(self, parser):
        parser.add_argument('--since', help='start date to backfill')
        parser.add_argument('--clear', help='clear all user pieces, then exit', action='store_true')

    def clear(self):
        print("Deleting migrated user activities")
        LocalActivity.objects.all().delete()

    def backfill(self, options):
        types = [Collection, Like, Review, ShelfMember]
        for typ in types:
            print(typ)
            template = template_map[typ]
            qs = typ.objects.all().filter(owner__is_active=True).order_by('id')
            if options['since']:
                qs = qs.filter(created_time__gte=options['since'])
            else:
                qs = qs.filter(created_time__gte='2022-12-01')
            with transaction.atomic():
                for piece in tqdm(qs):
                    params = {
                        'owner': piece.owner,
                        'visibility': piece.visibility,
                        'template': template,
                        'action_object': piece,
                        'created_time': piece.created_time
                    }
                    LocalActivity.objects.create(**params)

    def handle(self, *args, **options):
        if options['clear']:
            self.clear()
        else:
            self.backfill(options)
        self.stdout.write(self.style.SUCCESS(f'Done.'))
