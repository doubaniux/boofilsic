from django.shortcuts import reverse, redirect, render, get_object_or_404
from django.http import HttpResponseBadRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import auth
from django.contrib.auth import authenticate
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db.models import Count
from .models import User, Report, Preference
from .forms import ReportForm
from mastodon.api import *
from mastodon import mastodon_request_included
from common.config import *
from common.models import MarkStatusEnum
from common.utils import PageLinksGenerator
from management.models import Announcement
from books.models import *
from movies.models import *
from music.models import *
from games.models import *
from books.forms import BookMarkStatusTranslator
from movies.forms import MovieMarkStatusTranslator
from music.forms import MusicMarkStatusTranslator
from games.forms import GameMarkStatusTranslator
from mastodon.models import MastodonApplication
from mastodon.api import verify_account
from django.conf import settings
from urllib.parse import quote
import django_rq
from .account import *
from .data import *
from datetime import timedelta
from django.utils import timezone
import json
from django.contrib import messages
from books.models import BookMark, BookReview
from movies.models import MovieMark, MovieReview
from games.models import GameMark, GameReview
from music.models import AlbumMark, SongMark, AlbumReview, SongReview
from collection.models import Collection
from common.importers.goodreads import GoodreadsImporter
from common.importers.douban import DoubanImporter


def render_user_not_found(request):
    msg = _("😖哎呀，这位用户还没有加入本站，快去联邦宇宙呼唤TA来注册吧！")
    sec_msg = _("")
    return render(
        request,
        'common/error.html',
        {
            'msg': msg,
            'secondary_msg': sec_msg,
        }
    )


def home_redirect(request, id):
    try:
        query_kwargs = {'pk': id}
        user = User.objects.get(**query_kwargs)
        return redirect(reverse("users:home", args=[user.mastodon_username]))
    except Exception:
        return redirect(settings.LOGIN_URL)


def home_anonymous(request, id):
    login_url = settings.LOGIN_URL + "?next=" + request.get_full_path()
    try:
        username = id.split('@')[0]
        site = id.split('@')[1]
        return render(request, 'users/home_anonymous.html', {
                      'login_url': login_url,
                      'username': username,
                      'site': site,
                      })
    except Exception:
        return redirect(login_url)


@mastodon_request_included
def home(request, id):
    if not request.user.is_authenticated:
        return home_anonymous(request, id)
    if request.method == 'GET':
        user = User.get(id)
        if user is None:
            return render_user_not_found(request)

        # access one's own home page
        if user == request.user:
            reports = Report.objects.order_by(
                '-submitted_time').filter(is_read=False)
            unread_announcements = Announcement.objects.filter(
                    pk__gt=request.user.read_announcement_index).order_by('-pk')
            try:
                request.user.read_announcement_index = Announcement.objects.latest(
                    'pk').pk
                request.user.save(update_fields=['read_announcement_index'])
            except ObjectDoesNotExist as e:
                # when there is no annoucenment
                pass
            book_marks = request.user.user_bookmarks.all()
            movie_marks = request.user.user_moviemarks.all()
            album_marks = request.user.user_albummarks.all()
            song_marks = request.user.user_songmarks.all()
            game_marks = request.user.user_gamemarks.all()
            book_reviews = request.user.user_bookreviews.all()
            movie_reviews = request.user.user_moviereviews.all()
            album_reviews = request.user.user_albumreviews.all()
            song_reviews = request.user.user_songreviews.all()
            game_reviews = request.user.user_gamereviews.all()

        # visit other's home page
        else:
            # no these value on other's home page
            reports = None
            unread_announcements = None

            if request.user.is_blocked_by(user) or request.user.is_blocking(user):
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            is_following = request.user.is_following(user)
            book_marks = BookMark.get_available_by_user(user, is_following)
            movie_marks = MovieMark.get_available_by_user(user, is_following)
            song_marks = SongMark.get_available_by_user(user, is_following)
            album_marks = AlbumMark.get_available_by_user(user, is_following)
            game_marks = GameMark.get_available_by_user(user, is_following)
            book_reviews = BookReview.get_available_by_user(user, is_following)
            movie_reviews = MovieReview.get_available_by_user(user, is_following)
            song_reviews = SongReview.get_available_by_user(user, is_following)
            album_reviews = AlbumReview.get_available_by_user(user, is_following)
            game_reviews = GameReview.get_available_by_user(user, is_following)

        collections = Collection.objects.filter(owner=user)
        marked_collections = Collection.objects.filter(pk__in=CollectionMark.objects.filter(owner=user).values_list('collection', flat=True))

        # book marks
        filtered_book_marks = filter_marks(book_marks, BOOKS_PER_SET, 'book')
        book_marks_count = count_marks(book_marks, "book")

        # movie marks
        filtered_movie_marks = filter_marks(movie_marks, MOVIES_PER_SET, 'movie')
        movie_marks_count = count_marks(movie_marks, "movie")

        # game marks
        filtered_game_marks = filter_marks(game_marks, GAMES_PER_SET, 'game')
        game_marks_count = count_marks(game_marks, "game")

        # music marks
        filtered_music_marks = filter_marks([song_marks, album_marks], MUSIC_PER_SET, 'music')
        music_marks_count = count_marks([song_marks, album_marks], "music")

        for mark in filtered_music_marks["do_music_marks"] +\
            filtered_music_marks["wish_music_marks"] +\
                filtered_music_marks["collect_music_marks"]:
            # for template convenience
            if mark.__class__ == AlbumMark:
                mark.type = "album"
            else:
                mark.type = "song"

        music_reviews = list(album_reviews.order_by("-edited_time")) + list(song_reviews.order_by("-edited_time"))
        for review in music_reviews:
            review.type = 'album' if review.__class__ == AlbumReview else 'song'

        layout = user.get_preference().get_serialized_home_layout()

        return render(
            request,
            'users/home.html',
            {
                'user': user,
                **filtered_book_marks,
                **filtered_movie_marks,
                **filtered_game_marks,
                **filtered_music_marks,
                **book_marks_count,
                **movie_marks_count,
                **music_marks_count,
                **game_marks_count,

                'book_tags': BookTag.all_by_user(user)[:10] if user == request.user else [],
                'movie_tags': MovieTag.all_by_user(user)[:10] if user == request.user else [],
                'music_tags': AlbumTag.all_by_user(user)[:10] if user == request.user else [],
                'game_tags': GameTag.all_by_user(user)[:10] if user == request.user else [],

                'book_reviews': book_reviews.order_by("-edited_time")[:BOOKS_PER_SET],
                'movie_reviews': movie_reviews.order_by("-edited_time")[:MOVIES_PER_SET],
                'music_reviews': music_reviews[:MUSIC_PER_SET],
                'game_reviews': game_reviews[:GAMES_PER_SET],
                'book_reviews_more': book_reviews.count() > BOOKS_PER_SET,
                'movie_reviews_more': movie_reviews.count() > MOVIES_PER_SET,
                'music_reviews_more': len(music_reviews) > MUSIC_PER_SET,
                'game_reviews_more': game_reviews.count() > GAMES_PER_SET,
                'book_reviews_count': book_reviews.count(),
                'movie_reviews_count': movie_reviews.count(),
                'music_reviews_count': len(music_reviews),
                'game_reviews_count': game_reviews.count(),

                'collections': collections.order_by("-edited_time")[:BOOKS_PER_SET],
                'collections_count': collections.count(),
                'collections_more': collections.count() > BOOKS_PER_SET,

                'marked_collections': marked_collections.order_by("-edited_time")[:BOOKS_PER_SET],
                'marked_collections_count': marked_collections.count(),
                'marked_collections_more': marked_collections.count() > BOOKS_PER_SET,

                'layout': layout,
                'reports': reports,
                'unread_announcements': unread_announcements,
            }
        )
    else:
        return HttpResponseBadRequest()


def filter_marks(querysets, maximum, type_name):
    """
    Filter marks by amount limits and order them edited time, store results in a dict,
    which could be directly used in template.
    @param querysets: one queryset or multiple querysets as a list
    """
    result = {}
    if not isinstance(querysets, list):
        querysets = [querysets]

    for status in MarkStatusEnum.values:
        marks = []
        count = 0
        for queryset in querysets:
            marks += list(queryset.filter(status=MarkStatusEnum[status.upper()]).order_by("-created_time")[:maximum])
            count += queryset.filter(status=MarkStatusEnum[status.upper()]).count()

        # marks
        marks = sorted(marks, key=lambda e: e.edited_time, reverse=True)[:maximum]
        result[f"{status}_{type_name}_marks"] = marks
        # flag indicates if marks are more than `maximun`
        if count > maximum:
            result[f"{status}_{type_name}_more"] = True
        else:
            result[f"{status}_{type_name}_more"] = False

    return result


def count_marks(querysets, type_name):
    """
    Count all available marks, then assembly a dict to be used in template
    @param querysets: one queryset or multiple querysets as a list
    """
    result = {}
    if not isinstance(querysets, list):
        querysets = [querysets]
    for status in MarkStatusEnum.values:
        count = 0
        for queryset in querysets:
            count += queryset.filter(status=MarkStatusEnum[status.upper()]).count()
        result[f"{status}_{type_name}_count"] = count
    return result


@mastodon_request_included
@login_required
def followers(request, id):
    if request.method == 'GET':
        user = User.get(id)
        if user is None or user != request.user:
            return render_user_not_found(request)
        return render(
            request,
            'users/relation_list.html',
            {
                'user': user,
                'is_followers_page': True,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def following(request, id):
    if request.method == 'GET':
        user = User.get(id)
        if user is None or user != request.user:
            return render_user_not_found(request)
        return render(
            request,
            'users/relation_list.html',
            {
                'user': user,
                'page_type': 'followers',
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def book_list(request, id, status):
    if request.method == 'GET':
        if status.upper() not in MarkStatusEnum.names and status not in ['reviewed', 'tagged']:
            return HttpResponseBadRequest()

        user = User.get(id)
        if user is None:
            return render_user_not_found(request)
        tag = request.GET.get('t', default='')
        if user != request.user:
            if request.user.is_blocked_by(user) or request.user.is_blocking(user):
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            is_following = request.user.is_following(user)
            if status == 'reviewed':
                queryset = BookReview.get_available_by_user(user, is_following).order_by("-edited_time")
            elif status == 'tagged':
                queryset = BookTag.find_by_user(tag, user, request.user).order_by("-mark__created_time")
            else:
                queryset = BookMark.get_available_by_user(user, is_following).filter(
                    status=MarkStatusEnum[status.upper()]).order_by("-created_time")
        else:
            if status == 'reviewed':
                queryset = BookReview.objects.filter(owner=user).order_by("-edited_time")
            elif status == 'tagged':
                queryset = BookTag.objects.filter(content=tag, mark__owner=user).order_by("-mark__created_time")
            else:
                queryset = BookMark.objects.filter(
                    owner=user, status=MarkStatusEnum[status.upper()]).order_by("-created_time")
        paginator = Paginator(queryset, ITEMS_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        for mark in marks:
            mark.book.tag_list = mark.book.get_tags_manager().values('content').annotate(
                tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER_ON_LIST]
        marks.pagination = PageLinksGenerator(PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        if status == 'reviewed':
            list_title = str(_("评论过的书"))
        elif status == 'tagged':
            list_title = str(_(f"标记为「{tag}」的书"))
        else:
            list_title = str(BookMarkStatusTranslator(MarkStatusEnum[status.upper()])) + str(_("的书"))
        return render(
            request,
            'users/item_list.html',
            {
                'marks': marks,
                'user': user,
                'status': status,
                'list_title': list_title,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def movie_list(request, id, status):
    if request.method == 'GET':
        if status.upper() not in MarkStatusEnum.names and status not in ['reviewed', 'tagged']:
            return HttpResponseBadRequest()

        user = User.get(id)
        if user is None:
            return render_user_not_found(request)
        tag = request.GET.get('t', default='')
        if user != request.user:
            if request.user.is_blocked_by(user) or request.user.is_blocking(user):
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            is_following = request.user.is_following(user)
            if status == 'reviewed':
                queryset = MovieReview.get_available_by_user(user, is_following).order_by("-edited_time")
            elif status == 'tagged':
                queryset = MovieTag.find_by_user(tag, user, request.user).order_by("-mark__created_time")
            else:
                queryset = MovieMark.get_available_by_user(user, is_following).filter(
                    status=MarkStatusEnum[status.upper()]).order_by("-created_time")
        else:
            if status == 'reviewed':
                queryset = MovieReview.objects.filter(owner=user).order_by("-edited_time")
            elif status == 'tagged':
                queryset = MovieTag.objects.filter(content=tag, mark__owner=user).order_by("-mark__created_time")
            else:
                queryset = MovieMark.objects.filter(owner=user, status=MarkStatusEnum[status.upper()]).order_by("-created_time")
        paginator = Paginator(queryset, ITEMS_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        for mark in marks:
            mark.movie.tag_list = mark.movie.get_tags_manager().values('content').annotate(
                tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER_ON_LIST]
        marks.pagination = PageLinksGenerator(PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        if status == 'reviewed':
            list_title = str(_("评论过的电影和剧集"))
        elif status == 'tagged':
            list_title = str(_(f"标记为「{tag}」的电影和剧集"))
        else:
            list_title = str(MovieMarkStatusTranslator(MarkStatusEnum[status.upper()])) + str(_("的电影和剧集"))

        return render(
            request,
            'users/item_list.html',
            {
                'marks': marks,
                'user': user,
                'status': status,
                'list_title': list_title,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def game_list(request, id, status):
    if request.method == 'GET':
        if status.upper() not in MarkStatusEnum.names and status not in ['reviewed', 'tagged']:
            return HttpResponseBadRequest()

        user = User.get(id)
        if user is None:
            return render_user_not_found(request)
        tag = request.GET.get('t', default='')
        if user != request.user:
            if request.user.is_blocked_by(user) or request.user.is_blocking(user):
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            is_following = request.user.is_following(user)
            if status == 'reviewed':
                queryset = GameReview.get_available_by_user(user, is_following).order_by("-edited_time")
            elif status == 'tagged':
                queryset = GameTag.find_by_user(tag, user, request.user).order_by("-mark__created_time")
            else:
                queryset = GameMark.get_available_by_user(user, is_following).filter(
                    status=MarkStatusEnum[status.upper()]).order_by("-created_time")
        else:
            if status == 'reviewed':
                queryset = GameReview.objects.filter(owner=user).order_by("-edited_time")
            elif status == 'tagged':
                queryset = GameTag.objects.filter(content=tag, mark__owner=user).order_by("-mark__created_time")
            else:
                queryset = GameMark.objects.filter(
                    owner=user, status=MarkStatusEnum[status.upper()]).order_by("-created_time")
        paginator = Paginator(queryset, ITEMS_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        for mark in marks:
            mark.game.tag_list = mark.game.get_tags_manager().values('content').annotate(
                tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER_ON_LIST]
        marks.pagination = PageLinksGenerator(PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        if status == 'reviewed':
            list_title = str(_("评论过的游戏"))
        elif status == 'tagged':
            list_title = str(_(f"标记为「{tag}」的游戏"))
        else:
            list_title = str(GameMarkStatusTranslator(MarkStatusEnum[status.upper()])) + str(_("的游戏"))
        return render(
            request,
            'users/item_list.html',
            {
                'marks': marks,
                'user': user,
                'status': status,
                'list_title': list_title,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def music_list(request, id, status):
    if request.method == 'GET':
        if status.upper() not in MarkStatusEnum.names and status not in ['reviewed', 'tagged']:
            return HttpResponseBadRequest()

        user = User.get(id)
        if user is None:
            return render_user_not_found(request)
        tag = request.GET.get('t', default='')
        if not user == request.user:
            if request.user.is_blocked_by(user) or request.user.is_blocking(user):
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            is_following = request.user.is_following(user)
            if status == 'reviewed':
                queryset = list(AlbumReview.get_available_by_user(user, is_following).order_by("-edited_time")) + \
                    list(SongReview.get_available_by_user(user, is_following).order_by("-edited_time"))
            elif status == 'tagged':
                queryset = list(AlbumTag.find_by_user(tag, user, request.user).order_by("-mark__created_time"))
            else:
                queryset = list(AlbumMark.get_available_by_user(user, is_following).filter(
                    status=MarkStatusEnum[status.upper()])) \
                        + list(SongMark.get_available_by_user(user, is_following).filter(
                        status=MarkStatusEnum[status.upper()]))
        else:
            if status == 'reviewed':
                queryset = list(AlbumReview.objects.filter(owner=user).order_by("-edited_time")) + \
                    list(SongReview.objects.filter(owner=user).order_by("-edited_time"))
            elif status == 'tagged':
                queryset = list(AlbumTag.objects.filter(content=tag, mark__owner=user).order_by("-mark__created_time"))
            else:
                queryset = list(AlbumMark.objects.filter(owner=user, status=MarkStatusEnum[status.upper()])) \
                    + list(SongMark.objects.filter(owner=user, status=MarkStatusEnum[status.upper()]))
        queryset = sorted(queryset, key=lambda e: e.edited_time, reverse=True)
        paginator = Paginator(queryset, ITEMS_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        for mark in marks:
            if mark.__class__ in [AlbumMark, AlbumReview, AlbumTag]:
                mark.music = mark.album
                mark.music.tag_list = mark.album.get_tags_manager().values('content').annotate(
                    tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER_ON_LIST]
            elif mark.__class__ == SongMark or mark.__class__ == SongReview:
                mark.music = mark.song
                mark.music.tag_list = mark.song.get_tags_manager().values('content').annotate(
                    tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER_ON_LIST]

        marks.pagination = PageLinksGenerator(PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        if status == 'reviewed':
            list_title = str(_("评论过的音乐"))
        elif status == 'tagged':
            list_title = str(_(f"标记为「{tag}」的音乐"))
        else:
            list_title = str(MusicMarkStatusTranslator(MarkStatusEnum[status.upper()])) + str(_("的音乐"))
        return render(
            request,
            'users/item_list.html',
            {
                'marks': marks,
                'user': user,
                'status': status,
                'list_title': list_title,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def set_layout(request):
    if request.method == 'POST':
        layout = json.loads(request.POST.get('layout'))
        request.user.preference.home_layout = layout
        request.user.preference.save()
        return redirect(reverse("common:home"))
    else:
        return HttpResponseBadRequest()


@login_required
def report(request):
    if request.method == 'GET':
        user_id = request.GET.get('user_id')
        if user_id:
            user = get_object_or_404(User, pk=user_id)
            form = ReportForm(initial={'reported_user': user})
        else:
            form = ReportForm()
        return render(
            request,
            'users/report.html',
            {
                'form': form,
            }
        )
    elif request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            form.instance.is_read = False
            form.instance.submit_user = request.user
            form.save()
            return redirect(reverse("users:home", args=[form.instance.reported_user.mastodon_username]))
        else:
            return render(
                request,
                'users/report.html',
                {
                    'form': form,
                }
            )
    else:
        return HttpResponseBadRequest()


@login_required
def manage_report(request):
    if request.method == 'GET':
        reports = Report.objects.all()
        for r in reports.filter(is_read=False):
            r.is_read = True
            r.save()
        return render(
            request,
            'users/manage_report.html',
            {
                'reports': reports,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def collection_list(request, id):
    from collection.views import list
    user = User.get(id)
    if user is None:
        return render_user_not_found(request)
    return list(request, user.id)


@login_required
def marked_collection_list(request, id):
    from collection.views import list
    user = User.get(id)
    if user is None:
        return render_user_not_found(request)
    return list(request, user.id, True)


@login_required
def tag_list(request, id):
    user = User.get(id)
    if user is None:
        return render_user_not_found(request)
    if user != request.user:
        raise PermissionDenied()  # tag list is for user's own view only, for now
    return render(
        request,
        'users/tags.html', {
            'book_tags': BookTag.all_by_user(user),
            'movie_tags': MovieTag.all_by_user(user),
            'music_tags': AlbumTag.all_by_user(user),
            'game_tags': GameTag.all_by_user(user),
        }
    )
