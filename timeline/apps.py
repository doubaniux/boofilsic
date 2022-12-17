from django.apps import AppConfig


class TimelineConfig(AppConfig):
    name = 'timeline'

    def ready(self):
        from .models import init_post_save_handler
        from books.models import BookMark, BookReview
        from movies.models import MovieMark, MovieReview
        from games.models import GameMark, GameReview
        from music.models import AlbumMark, AlbumReview, SongMark, SongReview
        from collection.models import Collection, CollectionMark
        for m in [BookMark, BookReview, MovieMark, MovieReview, GameMark, GameReview, AlbumMark, AlbumReview, SongMark, SongReview, Collection, CollectionMark]:
            init_post_save_handler(m)
