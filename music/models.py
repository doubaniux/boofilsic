import uuid
import django.contrib.postgres.fields as postgres
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import reverse
from common.models import Entity, Mark, Review, Tag, SourceSiteEnum, MarkStatusEnum
from common.utils import ChoicesDictGenerator, GenerateDateUUIDMediaFilePath
from django.utils import timezone
from django.conf import settings


MusicMarkStatusTranslation = {
    MarkStatusEnum.DO.value: _("在听"),
    MarkStatusEnum.WISH.value: _("想听"),
    MarkStatusEnum.COLLECT.value: _("听过")
}


def song_cover_path(instance, filename):
    return GenerateDateUUIDMediaFilePath(instance, filename, settings.SONG_MEDIA_PATH_ROOT)


def album_cover_path(instance, filename):
    return GenerateDateUUIDMediaFilePath(instance, filename, settings.ALBUM_MEDIA_PATH_ROOT)


class Album(Entity):
    title = models.CharField(_("标题"), max_length=500)
    release_date = models.DateField(
        _('发行日期'), auto_now=False, auto_now_add=False, null=True, blank=True)
    cover = models.ImageField(
        _("封面"), upload_to=album_cover_path, default=settings.DEFAULT_ALBUM_IMAGE, blank=True)
    duration = models.PositiveIntegerField(_("时长"), null=True, blank=True)
    artist = postgres.ArrayField(
        models.CharField(_("artist"), blank=True,
                         default='', max_length=200),
        null=True,
        blank=True,
        default=list,
        verbose_name=_("艺术家")
    )
    genre = models.CharField(_("流派"), blank=True,
                             default='', max_length=100)
    company = postgres.ArrayField(
        models.CharField(blank=True,
                         default='', max_length=500),
        null=True,
        blank=True,
        default=list,
        verbose_name=_("发行方")
    )
    track_list = models.TextField(_("曲目"), blank=True, default="")

    def __str__(self):
        return self.title

    def get_json(self):
        r = {
            'artist': self.artist,
            'release_date': self.release_date,
            'genre': self.genre,
            'publisher': self.company,
        }
        r.update(super().get_json())
        return r

    def get_embed_link(self):
        if self.source_site == SourceSiteEnum.SPOTIFY.value:
            return self.source_url.replace("open.spotify.com/", "open.spotify.com/embed/")
        elif self.source_site == SourceSiteEnum.BANDCAMP.value and self.other_info and 'bandcamp_album_id' in self.other_info:
            return f"https://bandcamp.com/EmbeddedPlayer/album={self.other_info['bandcamp_album_id']}/size=large/bgcol=ffffff/linkcol=19A2CA/artwork=small/transparent=true/"
        else:
            return None

    def get_absolute_url(self):
        return reverse("music:retrieve_album", args=[self.id])

    @property
    def wish_url(self):
        return reverse("music:wish_album", args=[self.id])

    def get_tags_manager(self):
        return self.album_tags

    @property
    def verbose_category_name(self):
        return _("专辑")

    @property
    def mark_class(self):
        return AlbumMark

    @property
    def tag_class(self):
        return AlbumTag


class Song(Entity):
    '''
    Song(track) entity, can point to entity Album
    '''
    title = models.CharField(_("标题"), max_length=500)
    release_date = models.DateField(_('发行日期'), auto_now=False, auto_now_add=False, null=True, blank=True)
    isrc = models.CharField(_("ISRC"),
        blank=True, max_length=15, db_index=True, default='')
    # duration in ms
    duration = models.PositiveIntegerField(_("时长"), null=True, blank=True)
    cover = models.ImageField(
        _("封面"), upload_to=song_cover_path, default=settings.DEFAULT_SONG_IMAGE, blank=True)
    artist = postgres.ArrayField(
        models.CharField(blank=True,
                         default='', max_length=100),
        null=True,
        blank=True,
        default=list,
        verbose_name=_("艺术家")
    )
    genre = models.CharField(_("流派"), blank=True, default='', max_length=100)

    album = models.ForeignKey(
        Album, models.SET_NULL, "album_songs", null=True, blank=True, verbose_name=_("所属专辑"))

    def __str__(self):
        return self.title

    def get_json(self):
        r = {
            'artist': self.artist,
            'release_date': self.release_date,
            'genre': self.genre,
        }
        r.update(super().get_json())
        return r

    def get_embed_link(self):
        return self.source_url.replace("open.spotify.com/", "open.spotify.com/embed/") if self.source_site == SourceSiteEnum.SPOTIFY.value else None

    def get_absolute_url(self):
        return reverse("music:retrieve_song", args=[self.id])

    @property
    def wish_url(self):
        return reverse("music:wish_song", args=[self.id])

    def get_tags_manager(self):
        return self.song_tags

    @property
    def verbose_category_name(self):
        return _("单曲")

    @property
    def mark_class(self):
        return SongMark

    @property
    def tag_class(self):
        return SongTag


class SongMark(Mark):
    song = models.ForeignKey(
        Song, on_delete=models.CASCADE, related_name='song_marks', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'song'], name='unique_song_mark')
        ]

    @property
    def translated_status(self):
        return MusicMarkStatusTranslation[self.status]


class SongReview(Review):
    song = models.ForeignKey(
        Song, on_delete=models.CASCADE, related_name='song_reviews', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'song'], name='unique_song_review')
        ]

    @property
    def url(self):
        return settings.APP_WEBSITE + reverse("music:retrieve_song_review", args=[self.id])

    @property
    def item(self):
        return self.song


class SongTag(Tag):
    song = models.ForeignKey(
        Song, on_delete=models.CASCADE, related_name='song_tags', null=True)
    mark = models.ForeignKey(
        SongMark, on_delete=models.CASCADE, related_name='songmark_tags', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['content', 'mark'], name="unique_songmark_tag")
        ]

    @property
    def item(self):
        return self.song


class AlbumMark(Mark):
    album = models.ForeignKey(
        Album, on_delete=models.CASCADE, related_name='album_marks', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'album'], name='unique_album_mark')
        ]

    @property
    def translated_status(self):
        return MusicMarkStatusTranslation[self.status]


class AlbumReview(Review):
    album = models.ForeignKey(
        Album, on_delete=models.CASCADE, related_name='album_reviews', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'album'], name='unique_album_review')
        ]

    @property
    def url(self):
        return settings.APP_WEBSITE + reverse("music:retrieve_album_review", args=[self.id])

    @property
    def item(self):
        return self.album


class AlbumTag(Tag):
    album = models.ForeignKey(
        Album, on_delete=models.CASCADE, related_name='album_tags', null=True)
    mark = models.ForeignKey(
        AlbumMark, on_delete=models.CASCADE, related_name='albummark_tags', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['content', 'mark'], name="unique_albummark_tag")
        ]

    @property
    def item(self):
        return self.album
