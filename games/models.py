import uuid
import django.contrib.postgres.fields as postgres
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import reverse
from common.models import Entity, Mark, Review, Tag, MarkStatusEnum
from common.utils import ChoicesDictGenerator, GenerateDateUUIDMediaFilePath
from django.utils import timezone
from django.conf import settings
from simple_history.models import HistoricalRecords


GameMarkStatusTranslation = {
    MarkStatusEnum.DO.value: _("在玩"),
    MarkStatusEnum.WISH.value: _("想玩"),
    MarkStatusEnum.COLLECT.value: _("玩过")
}


def game_cover_path(instance, filename):
    return GenerateDateUUIDMediaFilePath(instance, filename, settings.GAME_MEDIA_PATH_ROOT)


class Game(Entity):
    """
    """

    title = models.CharField(_("名称"), max_length=500)

    other_title = postgres.ArrayField(
        models.CharField(blank=True,default='', max_length=500),
        null=True,
        blank=True,
        default=list,
        verbose_name=_("别名")
    )

    developer = postgres.ArrayField(
        models.CharField(blank=True, default='', max_length=500),
        null=True,
        blank=True,
        default=list,
        verbose_name=_("开发商")
    )

    publisher = postgres.ArrayField(
        models.CharField(blank=True, default='', max_length=500),
        null=True,
        blank=True,
        default=list,
        verbose_name=_("发行商")
    )

    release_date = models.DateField(
        _('发行日期'),
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True
    )

    genre = postgres.ArrayField(
        models.CharField(blank=True, default='', max_length=200),
        null=True,
        blank=True,
        default=list,
        verbose_name=_("类型")
    )

    platform = postgres.ArrayField(
        models.CharField(blank=True, default='', max_length=200),
        null=True,
        blank=True,
        default=list,
        verbose_name=_("平台")
    )

    cover = models.ImageField(_("封面"), upload_to=game_cover_path, default=settings.DEFAULT_GAME_IMAGE, blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return self.title

    def get_json(self):
        r = {
            'developer': self.developer,
            'other_title': self.other_title,
            'publisher': self.publisher,
            'release_date': self.release_date,
            'platform': self.platform,
            'genre': self.genre,
        }
        r.update(super().get_json())
        return r

    def get_absolute_url(self):
        return reverse("games:retrieve", args=[self.id])

    @property
    def year(self):
        return self.release_date.year if self.release_date else None

    @property
    def wish_url(self):
        return reverse("games:wish", args=[self.id])

    def get_tags_manager(self):
        return self.game_tags

    @property
    def verbose_category_name(self):
        return _("游戏")

    @property
    def mark_class(self):
        return GameMark

    @property
    def tag_class(self):
        return GameTag


class GameMark(Mark):
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='game_marks', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'game'], name='unique_game_mark')
        ]

    @property
    def translated_status(self):
        return GameMarkStatusTranslation[self.status]


class GameReview(Review):
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='game_reviews', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'game'], name='unique_game_review')
        ]

    @property
    def url(self):
        return reverse("games:retrieve_review", args=[self.id])

    @property
    def item(self):
        return self.game


class GameTag(Tag):
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='game_tags', null=True)
    mark = models.ForeignKey(
        GameMark, on_delete=models.CASCADE, related_name='gamemark_tags', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['content', 'mark'], name="unique_gamemark_tag")
        ]

    @property
    def item(self):
        return self.game
