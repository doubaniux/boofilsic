from django.apps import AppConfig


class GamesConfig(AppConfig):
    name = 'games'

    def ready(self):
        from common.index import Indexer
        from .models import Game
        Indexer.update_model_indexable(Game)
