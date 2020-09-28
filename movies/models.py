import uuid
import django.contrib.postgres.fields as postgres
from django.utils.translation import ugettext_lazy as _
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from common.models import Resource, Mark, Review, Tag
from boofilsic.settings import BOOK_MEDIA_PATH_ROOT, DEFAULT_BOOK_IMAGE
from django.utils import timezone


def movie_cover_path():
    pass


class GenreEnum(models.TextChoices):
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


class Movie(Resource):
    '''
    Can either be movie or series.
    '''
    # widely recognized name, usually in Chinese
    title = models.CharField(_("title"), max_length=200)
    # original name, for books in foreign language
    orig_title = models.CharField(
        _("original title"), blank=True, default='', max_length=200)
    other_title = postgres.ArrayField(
        models.CharField(_("other title"), blank=True,
                         default='', max_length=100),
        null=True,
        blank=True,
        default=list,
    )
    imbd_code = models.CharField(
        blank=True, max_length=10, null=True, unique=True, db_index=True)
    director = postgres.ArrayField(
        models.CharField(_("director"), blank=True,
                         default='', max_length=100),
        null=True,
        blank=True,
        default=list,
    )
    playwright = postgres.ArrayField(
        models.CharField(_("playwright"), blank=True,
                         default='', max_length=100),
        null=True,
        blank=True,
        default=list,
    )
    actor = postgres.ArrayField(
        models.CharField(_("actor"), blank=True,
                         default='', max_length=100),
        null=True,
        blank=True,
        default=list,
    )
    genre = models.CharField(
        _("genre"),
        blank=True,
        default='',
        choices=GenreEnum.choices
    )
    showtime = postgres.ArrayField(
        # HStoreField stores showtime-region pair
        postgres.HStoreField(),
        null=True,
        blank=True,
        default=list,
    )
    site = models.URLField(_('site url'), max_length=200)
    
    # country or area
    area = postgres.ArrayField(
        models.CharField(
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
    duration = models.CharField(blank=True, default='', max_length=100)

    ############################################
    # exclusive fields to series
    ############################################
    season = models.PositiveSmallIntegerField(null=True, blank=True)
    # how many episodes in the season
    episodes = models.PositiveIntegerField(null=True, blank=True)
    tv_station = models.CharField(blank=True, default='', max_length=200)

    ############################################
    # category identifier
    ############################################
    is_series = models.BooleanField(default=False)


    def __str__(self):
        return self.title


    def get_tags_manager(self):
        raise NotImplementedError


class MovieMark(Mark):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_marks', null=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'movie'], name='unique_movie_mark')
        ]


class MovieReview(Review):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_reviews', null=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'movie'], name='unique_movie_review')
        ]


class MovieTag(Tag):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_tags', null=True)
    mark = models.ForeignKey(MovieMark, on_delete=models.CASCADE, related_name='moviemark_tags', null=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['content', 'mark'], name="unique_moviemark_tag")
        ]
