from django.core.management.base import BaseCommand
from users.models import User
from datetime import timedelta
from django.utils import timezone
from timeline.models import Activity
from books.models import BookMark, BookReview
from movies.models import MovieMark, MovieReview
from games.models import GameMark, GameReview
from music.models import AlbumMark, AlbumReview, SongMark, SongReview
from collection.models import Collection, CollectionMark
from tqdm import tqdm


class Command(BaseCommand):
    help = 'Re-populating activity for timeline'

    def handle(self, *args, **options):
        for cl in [BookMark, BookReview, MovieMark, MovieReview, GameMark, GameReview, AlbumMark, AlbumReview, SongMark, SongReview, Collection, CollectionMark]:
            for a in tqdm(cl.objects.filter(created_time__gt='2022-1-1 00:00+0800'), desc=f'Populating {cl.__name__}'):
                Activity.upsert_item(a)
