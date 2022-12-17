from django.db import models
from markdown import markdown
from common.models import UserOwnedEntity
from movies.models import Movie
from books.models import Book
from music.models import Song, Album
from games.models import Game
from markdownx.models import MarkdownxField
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from common.utils import ChoicesDictGenerator, GenerateDateUUIDMediaFilePath
from common.models import RE_HTML_TAG
from django.shortcuts import reverse


def collection_cover_path(instance, filename):
    return GenerateDateUUIDMediaFilePath(instance, filename, settings.COLLECTION_MEDIA_PATH_ROOT)


class Collection(UserOwnedEntity):
    title = models.CharField(max_length=200)
    description = MarkdownxField()
    cover = models.ImageField(_("封面"), upload_to=collection_cover_path, default=settings.DEFAULT_COLLECTION_IMAGE, blank=True)
    collaborative = models.PositiveSmallIntegerField(default=0)  # 0: Editable by owner only / 1: Editable by bi-direction followers

    def __str__(self):
        return f"Collection({self.id} {self.owner} {self.title})"

    @property
    def translated_status(self):
        return '创建了收藏单'

    @property
    def collectionitem_list(self):
        return sorted(list(self.collectionitem_set.all()), key=lambda i: i.position)

    @property
    def item_list(self):
        return map(lambda i: i.item, self.collectionitem_list)

    @property
    def plain_description(self):
        html = markdown(self.description)
        return RE_HTML_TAG.sub(' ', html)

    def has_item(self, item):
        return len(list(filter(lambda i: i.item == item, self.collectionitem_list))) > 0

    def append_item(self, item, comment=""):
        cl = self.collectionitem_list
        if item is None or self.has_item(item):
            return None
        else:
            i = CollectionItem(collection=self, position=cl[-1].position + 1 if len(cl) else 1, comment=comment)
            i.set_item(item)
            i.save()
            return i

    @property
    def item(self):
        return self

    @property
    def mark_class(self):
        return CollectionMark

    @property
    def url(self):
        return reverse("collection:retrieve", args=[self.id])

    @property
    def wish_url(self):
        return reverse("collection:wish", args=[self.id])

    def is_editable_by(self, viewer):
        if viewer.is_staff or viewer.is_superuser or viewer == self.owner:
            return True
        elif self.collaborative == 1 and viewer.is_following(self.owner) and viewer.is_followed_by(self.owner):
            return True
        else:
            return False


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

    # @item.setter
    def set_item(self, new_item):
        old_item = self.item
        if old_item == new_item:
            return
        if old_item is not None:
            self.movie = None
            self.book = None
            self.album = None
            self.song = None
            self.game = None
        setattr(self, new_item.__class__.__name__.lower(), new_item)


class CollectionMark(UserOwnedEntity):
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name='collection_marks', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'collection'], name="unique_collection_mark")
        ]

    def __str__(self):
        return f"CollectionMark({self.id} {self.owner} {self.collection})"

    @property
    def translated_status(self):
        return '关注了收藏单'
