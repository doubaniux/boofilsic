from django.core.management.base import BaseCommand
from common.index import Indexer, INDEX_NAME
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


BATCH_SIZE = 10000


class Command(BaseCommand):
    help = 'Check search index'

    def handle(self, *args, **options):
        print(f'Connecting to search server {settings.MEILISEARCH_SERVER} for index: {INDEX_NAME}')
        stats = Indexer.get_stats()
        print(stats)
        st = Indexer.instance().get_all_update_status() 
        cnt = {"enqueued": [0, 0], "processing": [0, 0], "processed": [0, 0], "failed": [0, 0]}
        lastEnq = {"enqueuedAt": ""}
        lastProc = {"enqueuedAt": ""}
        for s in st:
            n = s["type"].get("number")
            cnt[s["status"]][0] += 1
            cnt[s["status"]][1] += n if n else 0
            if s["status"] == "processing":
                print(s)
            elif s["status"] == "enqueued":
                if s["enqueuedAt"] > lastEnq["enqueuedAt"]:
                    lastEnq = s
            elif s["status"] == "processed":
                if s["enqueuedAt"] > lastProc["enqueuedAt"]:
                    lastProc = s
        print(lastEnq)
        print(lastProc)
        print(cnt)
