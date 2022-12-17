from django.core.management.base import BaseCommand
from common.index import Indexer
from django.conf import settings
from movies.models import Movie
from books.models import Book
from games.models import Game
from music.models import Album, Song
from django.core.paginator import Paginator
from tqdm import tqdm
from time import sleep
from datetime import timedelta
from django.utils import timezone


BATCH_SIZE = 1000


class Command(BaseCommand):
    help = 'Regenerate the search index'

    # def add_arguments(self, parser):
    #     parser.add_argument('hours', type=int, help='Re-index items modified in last N hours, 0 to reindex all')

    def handle(self, *args, **options):
        # h = int(options['hours'])
        print(f'Connecting to search server')
        if Indexer.busy():
            print('Please wait for previous updates')
        # Indexer.update_settings()
        # self.stdout.write(self.style.SUCCESS('Index settings updated.'))
        for c in [Book, Song, Album, Game, Movie]:
            print(f'Re-indexing {c}')
            qs = c.objects.all()  # if h == 0 else c.objects.filter(edited_time__gt=timezone.now() - timedelta(hours=h))
            pg = Paginator(qs.order_by('id'), BATCH_SIZE)
            for p in tqdm(pg.page_range):
                items = list(map(lambda o: Indexer.obj_to_dict(o), pg.get_page(p).object_list))
                if items:
                    Indexer.replace_batch(items)
                    while Indexer.busy():
                        sleep(0.5)
