from django.db import models
from common.models import UserOwnedEntity
from movies.models import Movie
from books.models import Book
from music.models import Song, Album
from games.models import Game
from markdownx.models import MarkdownxField
from django.utils.translation import ugettext_lazy as _
from django.conf import settings


def collection_cover_path(instance, filename):
    return GenerateDateUUIDMediaFilePath(instance, filename, settings.COLLECTION_MEDIA_PATH_ROOT)


class Collection(UserOwnedEntity):
    name = models.CharField(max_length=200)
    description = MarkdownxField()
    cover = models.ImageField(_("封面"), upload_to=collection_cover_path, default=settings.DEFAULT_COLLECTION_IMAGE, blank=True)

    def __str__(self):
        return str(self.owner) + ': ' + self.name

    @property
    def item_list(self):
        return list(self.collectionitem_set.objects.all()).sort(lambda i: i.position)

    @property
    def plain_description(self):
        html = markdown(self.description)
        return RE_HTML_TAG.sub(' ', html)


class CollectionItem(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, null=True)
    album = models.ForeignKey(Album, on_delete=models.CASCADE, null=True)
    song = models.ForeignKey(Song, on_delete=models.CASCADE, null=True)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, null=True)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, null=True)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    comment = models.TextField(_("备注"), default='')

    @property
    def item(self):
        items = list(filter(lambda i: i is not None, [self.movie, self.book, self.album, self.song, self.game]))
        return items[0] if len(items) > 0 else None
