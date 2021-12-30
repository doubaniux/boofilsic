from django.core.management.base import BaseCommand
from common.index import Indexer, INDEX_NAME
from django.conf import settings
from movies.models import Movie
from books.models import Book
from games.models import Game
from music.models import Album, Song


class Command(BaseCommand):
    help = 'Regenerate the search index'

    def handle(self, *args, **options):
        print(f'Connecting to search server {settings.MEILISEARCH_SERVER} for index: {INDEX_NAME}')
        self.stdout.write(self.style.SUCCESS('Index settings updated.'))
        for c in [Movie, Book, Album, Song, Game]:
            print(f'Re-indexing {c}')
            for i in c.objects.all():
                Indexer.replace_item(i)
