from django.apps import AppConfig


class MoviesConfig(AppConfig):
    name = 'movies'

    def ready(self):
        from common.index import Indexer
        from .models import Movie
        Indexer.update_model_indexable(Movie)
