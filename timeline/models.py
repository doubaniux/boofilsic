from django.db import models
from common.models import UserOwnedEntity
from books.models import BookMark, BookReview
from movies.models import MovieMark, MovieReview
from games.models import GameMark, GameReview
from music.models import AlbumMark, AlbumReview, SongMark, SongReview
from collection.models import Collection, CollectionMark
from django.db.models.signals import post_save, post_delete


class Activity(UserOwnedEntity):
    bookmark = models.ForeignKey(BookMark, models.CASCADE, null=True)
    bookreview = models.ForeignKey(BookReview, models.CASCADE, null=True)
    moviemark = models.ForeignKey(MovieMark, models.CASCADE, null=True)
    moviereview = models.ForeignKey(MovieReview, models.CASCADE, null=True)
    gamemark = models.ForeignKey(GameMark, models.CASCADE, null=True)
    gamereview = models.ForeignKey(GameReview, models.CASCADE, null=True)
    albummark = models.ForeignKey(AlbumMark, models.CASCADE, null=True)
    albumreview = models.ForeignKey(AlbumReview, models.CASCADE, null=True)
    songmark = models.ForeignKey(SongMark, models.CASCADE, null=True)
    songreview = models.ForeignKey(SongReview, models.CASCADE, null=True)
    collection = models.ForeignKey(Collection, models.CASCADE, null=True)
    collectionmark = models.ForeignKey(CollectionMark, models.CASCADE, null=True)

    @property
    def target(self):
        items = [self.bookmark, self.bookreview, self.moviemark, self.moviereview, self.gamemark, self.gamereview,
                 self.songmark, self.songreview, self.albummark, self.albumreview, self.collection, self.collectionmark]
        return next((x for x in items if x is not None), None)

    @property
    def mark(self):
        items = [self.bookmark, self.moviemark, self.gamemark, self.songmark, self.albummark]
        return next((x for x in items if x is not None), None)

    @property
    def review(self):
        items = [self.bookreview, self.moviereview, self.gamereview, self.songreview, self.albumreview]
        return next((x for x in items if x is not None), None)

    @classmethod
    def upsert_item(self, item):
        attr = item.__class__.__name__.lower()
        f = {'owner': item.owner, attr: item}
        activity = Activity.objects.filter(**f).first()
        if not activity:
            activity = Activity.objects.create(**f)
        activity.created_time = item.created_time
        activity.visibility = item.visibility
        activity.save()


def _post_save_handler(sender, instance, created, **kwargs):
    Activity.upsert_item(instance)


# def activity_post_delete_handler(sender, instance, **kwargs):
#     pass


def init_post_save_handler(model):
    post_save.connect(_post_save_handler, sender=model)
    # post_delete.connect(activity_post_delete_handler, sender=model)  # delete handled by database
