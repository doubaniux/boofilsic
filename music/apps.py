from django.apps import AppConfig


class MusicConfig(AppConfig):
    name = 'music'

    def ready(self):
        from common.index import Indexer
        from .models import Album, Song
        Indexer.update_model_indexable(Album)
        Indexer.update_model_indexable(Song)
