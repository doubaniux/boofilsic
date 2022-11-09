from django.apps import AppConfig


class BooksConfig(AppConfig):
    name = 'books'

    def ready(self):
        from common.index import Indexer
        from .models import Book
        Indexer.update_model_indexable(Book)
