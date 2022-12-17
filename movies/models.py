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
from django.db.models import Q
import re
from simple_history.models import HistoricalRecords


MovieMarkStatusTranslation = {
    MarkStatusEnum.DO.value: _("在看"),
    MarkStatusEnum.WISH.value: _("想看"),
    MarkStatusEnum.COLLECT.value: _("看过")
}


def movie_cover_path(instance, filename):
    return GenerateDateUUIDMediaFilePath(instance, filename, settings.MOVIE_MEDIA_PATH_ROOT)


class MovieGenreEnum(models.TextChoices):
    DRAMA = 'Drama', _('剧情')
    KIDS = 'Kids', _('儿童')
    COMEDY = 'Comedy', _('喜剧')
    BIOGRAPHY = 'Biography', _('传记')
    ACTION = 'Action', _('动作')
    HISTORY = 'History', _('历史')
    ROMANCE = 'Romance', _('爱情')
    WAR = 'War', _('战争')
    SCI_FI = 'Sci-Fi', _('科幻')
    CRIME = 'Crime', _('犯罪')
    ANIMATION = 'Animation', _('动画')
    WESTERN = 'Western', _('西部')
    MYSTERY = 'Mystery', _('悬疑')
    FANTASY = 'Fantasy', _('奇幻')
    THRILLER = 'Thriller', _('惊悚')
    ADVENTURE = 'Adventure', _('冒险')
    HORROR = 'Horror', _('恐怖')
    DISASTER = 'Disaster', _('灾难')
    DOCUMENTARY = 'Documentary', _('纪录片')
    MARTIAL_ARTS = 'Martial-Arts', _('武侠')
    SHORT = 'Short', _('短片')
    ANCIENT_COSTUM = 'Ancient-Costum', _('古装')
    EROTICA = 'Erotica', _('情色')
    SPORT = 'Sport', _('运动')
    GAY_LESBIAN = 'Gay/Lesbian', _('同性')
    OPERA = 'Opera', _('戏曲')
    MUSIC = 'Music', _('音乐')
    FILM_NOIR = 'Film-Noir', _('黑色电影')
    MUSICAL = 'Musical', _('歌舞')
    REALITY_TV = 'Reality-TV', _('真人秀')
    FAMILY = 'Family', _('家庭')
    TALK_SHOW = 'Talk-Show', _('脱口秀')
    NEWS = 'News', _('新闻')
    SOAP = 'Soap', _('肥皂剧')
    TV_MOVIE = 'TV Movie', _('电视电影')
    THEATRE = 'Theatre', _('舞台艺术')
    OTHER = 'Other', _('其他')


MovieGenreTranslator = ChoicesDictGenerator(MovieGenreEnum)


class Movie(Entity):
    '''
    Can either be movie or series.
    '''
    # widely recognized name, usually in Chinese
    title = models.CharField(_("title"), max_length=500)
    # original name, for books in foreign language
    orig_title = models.CharField(
        _("original title"), blank=True, default='', max_length=500)
    other_title = postgres.ArrayField(
        models.CharField(_("other title"), blank=True,
                         default='', max_length=500),
        null=True,
        blank=True,
        default=list,
    )
    imdb_code = models.CharField(
        blank=True, max_length=10, null=False, db_index=True, default='')
    director = postgres.ArrayField(
        models.CharField(_("director"), blank=True,
                         default='', max_length=200),
        null=True,
        blank=True,
        default=list,
    )
    playwright = postgres.ArrayField(
        models.CharField(_("playwright"), blank=True,
                         default='', max_length=200),
        null=True,
        blank=True,
        default=list,
    )
    actor = postgres.ArrayField(
        models.CharField(_("actor"), blank=True,
                         default='', max_length=200),
        null=True,
        blank=True,
        default=list,
    )
    genre = postgres.ArrayField(
        models.CharField(
            _("genre"),
            blank=True,
            default='',
            choices=MovieGenreEnum.choices,
            max_length=50
        ),
        null=True,
        blank=True,
        default=list,
    )
    showtime = postgres.ArrayField(
        # HStoreField stores showtime-region pair
        postgres.HStoreField(),
        null=True,
        blank=True,
        default=list,
    )
    site = models.URLField(_('site url'), blank=True, default='', max_length=200)

    # country or region
    area = postgres.ArrayField(
        models.CharField(
            _("country or region"),
            blank=True,
            default='',
            max_length=100,
        ),
        null=True,
        blank=True,
        default=list,
    )

    language = postgres.ArrayField(
        models.CharField(
            blank=True,
            default='',
            max_length=100,
        ),
        null=True,
        blank=True,
        default=list,
    )

    year = models.PositiveIntegerField(null=True, blank=True)
    duration = models.CharField(blank=True, default='', max_length=200)

    cover = models.ImageField(_("poster"), upload_to=movie_cover_path, default=settings.DEFAULT_MOVIE_IMAGE, blank=True)

    ############################################
    # exclusive fields to series
    ############################################
    season = models.PositiveSmallIntegerField(null=True, blank=True)
    # how many episodes in the season
    episodes = models.PositiveIntegerField(null=True, blank=True)
    # deprecated
    # tv_station = models.CharField(blank=True, default='', max_length=200)
    single_episode_length = models.CharField(blank=True, default='', max_length=100)

    ############################################
    # category identifier
    ############################################
    is_series = models.BooleanField(default=False)

    history = HistoricalRecords()

    def __str__(self):
        if self.year:
            return self.title + f"({self.year})"
        else:
            return self.title

    def get_json(self):
        r = {
            'other_title': self.other_title,
            'original_title': self.orig_title,
            'director': self.director,
            'playwright': self.playwright,
            'actor': self.actor,
            'release_year': self.year,
            'genre': self.genre,
            'language': self.language,
            'season': self.season,
            'duration': self.duration,
            'imdb_code': self.imdb_code,
        }
        r.update(super().get_json())
        return r

    def get_absolute_url(self):
        return reverse("movies:retrieve", args=[self.id])

    @property
    def wish_url(self):
        return reverse("movies:wish", args=[self.id])

    def get_tags_manager(self):
        return self.movie_tags

    def get_genre_display(self):
        translated_genre = []
        for g in self.genre:
            translated_genre.append(MovieGenreTranslator[g])
        return translated_genre

    def get_related_movies(self):
        imdb = 'no match' if self.imdb_code is None or self.imdb_code == '' else self.imdb_code
        qs = Q(imdb_code=imdb)
        if self.is_series:
            prefix = re.sub(r'\d+', '', re.sub(r'\s+第.+季', '', self.title))
            if not prefix:
                prefix = self.title
            qs = qs | Q(title__startswith=prefix)
        qs = qs & ~Q(id=self.id)
        return Movie.objects.filter(qs).order_by('season')

    def get_identicals(self):
        qs = Q(orig_title=self.title)
        if self.imdb_code:
            qs = Q(imdb_code=self.imdb_code)
            # qs = qs & ~Q(id=self.id)
            return Movie.objects.filter(qs)
        else:
            return [self]  # Book.objects.filter(id=self.id)

    @property
    def verbose_category_name(self):
        if self.is_series:
            return _("剧集")
        else:
            return _("电影")

    @property
    def mark_class(self):
        return MovieMark

    @property
    def tag_class(self):
        return MovieTag


class MovieMark(Mark):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_marks', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'movie'], name='unique_movie_mark')
        ]

    @property
    def translated_status(self):
        return MovieMarkStatusTranslation[self.status]


class MovieReview(Review):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_reviews', null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'movie'], name='unique_movie_review')
        ]

    @property
    def url(self):
        return reverse("movies:retrieve_review", args=[self.id])

    @property
    def item(self):
        return self.movie


class MovieTag(Tag):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_tags', null=True)
    mark = models.ForeignKey(MovieMark, on_delete=models.CASCADE, related_name='moviemark_tags', null=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['content', 'mark'], name="unique_moviemark_tag")
        ]

    @property
    def item(self):
        return self.movie
