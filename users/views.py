from django.shortcuts import reverse, redirect, render, get_object_or_404
from django.http import HttpResponseBadRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import auth
from django.contrib.auth import authenticate
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
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
from .export import *
from datetime import timedelta
from django.utils import timezone
import json
from django.contrib import messages
from books.models import BookMark, BookReview
from movies.models import MovieMark, MovieReview
from games.models import GameMark, GameReview
from music.models import AlbumMark, SongMark, AlbumReview, SongReview
from collection.models import Collection


# Views
########################################
def swap_login(request, token, site, refresh_token):
    del request.session['swap_login']
    del request.session['swap_domain']
    code, data = verify_account(site, token)
    current_user = request.user
    if code == 200 and data is not None:
        username = data['username']
        if username == current_user.username and site == current_user.mastodon_site:
            messages.add_message(request, messages.ERROR, _(f'该身份 {username}@{site} 与当前账号相同。'))
        else:
            try:
                existing_user = User.objects.get(username=username, mastodon_site=site)
                messages.add_message(request, messages.ERROR, _(f'该身份 {username}@{site} 已被用于其它账号。'))
            except ObjectDoesNotExist:
                current_user.username = username
                current_user.mastodon_id = data['id']
                current_user.mastodon_site = site
                current_user.mastodon_token = token
                current_user.mastodon_refresh_token = refresh_token
                current_user.mastodon_account = data
                current_user.save(update_fields=['username', 'mastodon_id', 'mastodon_site', 'mastodon_token', 'mastodon_refresh_token', 'mastodon_account'])
                django_rq.get_queue('mastodon').enqueue(refresh_mastodon_data_task, current_user, token)
                messages.add_message(request, messages.INFO, _(f'账号身份已更新为 {username}@{site}。'))
    else:
        messages.add_message(request, messages.ERROR, _('连接联邦网络获取身份信息失败。'))
    return redirect(reverse('users:data'))


# no page rendered
@mastodon_request_included
def OAuth2_login(request):
    """ oauth authentication and logging user into django system """
    if request.method == 'GET':
        code = request.GET.get('code')
        site = request.COOKIES.get('mastodon_domain')

        # Network IO
        try:
            token, refresh_token = obtain_token(site, request, code)
        except ObjectDoesNotExist:
            return HttpResponseBadRequest("Mastodon site not registered")
        if token:
            if request.session.get('swap_login', False) and request.user.is_authenticated: # swap login for existing user
                return swap_login(request, token, site, refresh_token)
            user = authenticate(request, token=token, site=site)
            if user:
                user.mastodon_token = token
                user.mastodon_refresh_token = refresh_token
                user.save(update_fields=['mastodon_token', 'mastodon_refresh_token'])
                auth_login(request, user)
                if request.session.get('next_url') is not None:
                    response = redirect(request.session.get('next_url'))
                    del request.session['next_url']
                else:
                    response = redirect(reverse('common:home'))

                response.delete_cookie('mastodon_domain')
                return response
            else:
                # will be passed to register page
                request.session['new_user_token'] = token
                request.session['new_user_refresh_token'] = refresh_token
                return redirect(reverse('users:register'))
        else:
            return render(
                request,
                'common/error.html',
                {
                    'msg': _("认证失败😫")
                }
            )
    else:
        return HttpResponseBadRequest()


# the 'login' page that user can see
def login(request):
    if request.method == 'GET':
        selected_site = request.GET.get('site', default='')

        sites = MastodonApplication.objects.all().order_by("domain_name")

        # store redirect url in the cookie
        if request.GET.get('next'):
            request.session['next_url'] = request.GET.get('next')

        return render(
            request,
            'users/login.html',
            {
                'sites': sites,
                'scope': quote(settings.MASTODON_CLIENT_SCOPE),
                'selected_site': selected_site,
                'allow_any_site': settings.MASTODON_ALLOW_ANY_SITE,
            }
        )
    else:
        return HttpResponseBadRequest()


def connect(request):
    if not settings.MASTODON_ALLOW_ANY_SITE:
        return redirect(reverse("users:login"))
    login_domain = request.session['swap_domain'] if request.session.get('swap_login') else request.GET.get('domain')
    login_domain = login_domain.strip().lower().split('//')[-1].split('/')[0].split('@')[-1]
    domain, version = get_instance_info(login_domain)
    app, error_msg = get_mastodon_application(domain)
    if app is None:
        return render(request, 'common/error.html', {'msg': error_msg, 'secondary_msg': "", })
    else:
        login_url = get_mastodon_login_url(app, login_domain, version, request)
        resp = redirect(login_url)
        resp.set_cookie("mastodon_domain", domain)
        return resp


@mastodon_request_included
@login_required
def reconnect(request):
    if request.method == 'POST':
        request.session['swap_login'] = True
        request.session['swap_domain'] = request.POST['domain']
        return connect(request)
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def logout(request):
    if request.method == 'GET':
        # revoke_token(request.user.mastodon_site, request.user.mastodon_token)
        auth_logout(request)
        return redirect(reverse("users:login"))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
def register(request):
    """ register confirm page """
    if request.method == 'GET':
        if request.user.is_authenticated:
            return redirect(reverse('common:home'))
        elif request.session.get('new_user_token'):
            return render(
                request,
                'users/register.html'
            )
        else:
            return HttpResponseBadRequest()
    elif request.method == 'POST':
        token = request.session['new_user_token']
        refresh_token = request.session['new_user_refresh_token']
        code, user_data = verify_account(request.COOKIES['mastodon_domain'], token)
        if code != 200 or user_data is None:
            return render(
                request,
                'common/error.html',
                {
                    'msg': _("联邦网络访问失败😫")
                }
            )
        new_user = User(
            username=user_data['username'],
            mastodon_id=user_data['id'],
            mastodon_site=request.COOKIES['mastodon_domain'],
            mastodon_token=token,
            mastodon_refresh_token=refresh_token,
            mastodon_account=user_data,
        )
        new_user.save()
        del request.session['new_user_token']
        del request.session['new_user_refresh_token']
        auth_login(request, new_user)
        response = redirect(reverse('common:home'))
        response.delete_cookie('mastodon_domain')
        return response
    else:
        return HttpResponseBadRequest()


def delete(request):
    raise NotImplementedError


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
        if isinstance(id, str):
            try:
                username = id.split('@')[0]
                site = id.split('@')[1]
            except IndexError as e:
                return HttpResponseBadRequest("Invalid user id")
            query_kwargs = {'username': username, 'mastodon_site': site}
        elif isinstance(id, int):
            query_kwargs = {'pk': id}
        try:
            user = User.objects.get(**query_kwargs)
        except ObjectDoesNotExist:
            msg = _("😖哎呀，这位用户还没有加入本站，快去联邦宇宙呼唤TA来注册吧！")
            sec_msg = _("目前支持来自Mastodon和Pleroma实例的用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )

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

            latest_task = user.user_synctasks.order_by("-id").first()

        # visit other's home page
        else:
            latest_task = None
            # no these value on other's home page
            reports = None
            unread_announcements = None

            # cross site info for visiting other's home page
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.user.mastodon_token)

            # make queries
            relation = get_relationship(request.user, user, request.user.mastodon_token)[0]
            if relation['blocked_by']:
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            book_marks = BookMark.get_available_by_user(user, relation['following'])
            movie_marks = MovieMark.get_available_by_user(user, relation['following'])
            song_marks = SongMark.get_available_by_user(user, relation['following'])
            album_marks = AlbumMark.get_available_by_user(user, relation['following'])
            game_marks = GameMark.get_available_by_user(user, relation['following'])
            book_reviews = BookReview.get_available_by_user(user, relation['following'])
            movie_reviews = MovieReview.get_available_by_user(user, relation['following'])
            song_reviews = SongReview.get_available_by_user(user, relation['following'])
            album_reviews = AlbumReview.get_available_by_user(user, relation['following'])
            game_reviews = GameReview.get_available_by_user(user, relation['following'])

        collections = Collection.objects.filter(owner=user)
        # book marks
        filtered_book_marks = filter_marks(book_marks, BOOKS_PER_SET, 'book')
        book_marks_count = count_marks(book_marks, "book")

        # movie marks
        filtered_movie_marks = filter_marks(movie_marks, MOVIES_PER_SET, 'movie')
        movie_marks_count= count_marks(movie_marks, "movie")

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

        try:
            layout = user.preference.get_serialized_home_layout()
        except ObjectDoesNotExist:
            Preference.objects.create(user=user)
            layout = user.preference.get_serialized_home_layout()

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

                'book_tags': list(map(lambda t: t['content'], BookTag.all_by_user(user)))[:10] if user == request.user else [],
                'movie_tags': list(map(lambda t: t['content'], MovieTag.all_by_user(user)))[:10] if user == request.user else [],
                'music_tags': list(map(lambda t: t['content'], AlbumTag.all_by_user(user)))[:10] if user == request.user else [],
                'game_tags': list(map(lambda t: t['content'], GameTag.all_by_user(user)))[:10] if user == request.user else [],

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

                'layout': layout,
                'reports': reports,
                'unread_announcements': unread_announcements,
                'latest_task': latest_task,
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
            marks += list(queryset.filter(status=MarkStatusEnum[status.upper()]).order_by("-edited_time")[:maximum])
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
        if isinstance(id, str):
            try:
                username = id.split('@')[0]
                site = id.split('@')[1]
            except IndexError as e:
                return HttpResponseBadRequest("Invalid user id")
            query_kwargs = {'username': username, 'mastodon_site': site}
        elif isinstance(id, int):
            query_kwargs = {'pk': id}
        try:
            user = User.objects.get(**query_kwargs)
        except ObjectDoesNotExist:
            msg = _("😖哎呀，这位用户还没有加入本站，快去联邦宇宙呼唤TA来注册吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )
        # mastodon request
        if not user == request.user:
            relation = get_relationship(request.user, user, request.user.mastodon_token)[0]
            if relation['blocked_by']:
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.user.mastodon_token)
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
        if isinstance(id, str):
            try:
                username = id.split('@')[0]
                site = id.split('@')[1]
            except IndexError as e:
                return HttpResponseBadRequest("Invalid user id")
            query_kwargs = {'username': username, 'mastodon_site': site}
        elif isinstance(id, int):
            query_kwargs = {'pk': id}
        try:
            user = User.objects.get(**query_kwargs)
        except ObjectDoesNotExist:
            msg = _("😖哎呀，这位用户还没有加入本站，快去联邦宇宙呼唤TA来注册吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )
        # mastodon request
        if not user == request.user:
            relation = get_relationship(request.user, user, request.user.mastodon_token)[0]
            if relation['blocked_by']:
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.user.mastodon_token)
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

        if isinstance(id, str):
            try:
                username = id.split('@')[0]
                site = id.split('@')[1]
            except IndexError as e:
                return HttpResponseBadRequest("Invalid user id")
            query_kwargs = {'username': username, 'mastodon_site': site}
        elif isinstance(id, int):
            query_kwargs = {'pk': id}
        try:
            user = User.objects.get(**query_kwargs)
        except ObjectDoesNotExist:
            msg = _("😖哎呀，这位用户还没有加入本站，快去联邦宇宙呼唤TA来注册吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )
        tag = request.GET.get('t', default='')
        if user != request.user:
            # mastodon request
            relation = get_relationship(request.user, user, request.user.mastodon_token)[0]
            if relation['blocked_by']:
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            if status == 'reviewed':
                queryset = BookReview.get_available_by_user(user, relation['following']).order_by("-edited_time")
            elif status == 'tagged':
                queryset = BookTag.find_by_user(tag, user, relation['following']).order_by("-mark__edited_time")
            else:
                queryset = BookMark.get_available_by_user(user, relation['following']).filter(
                    status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.user.mastodon_token)
        else:
            if status == 'reviewed':
                queryset = BookReview.objects.filter(owner=user).order_by("-edited_time")
            elif status == 'tagged':
                queryset = BookTag.objects.filter(content=tag, mark__owner=user).order_by("-mark__edited_time")
            else:
                queryset = BookMark.objects.filter(
                    owner=user, status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
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
            'users/book_list.html',
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

        if isinstance(id, str):
            try:
                username = id.split('@')[0]
                site = id.split('@')[1]
            except IndexError as e:
                return HttpResponseBadRequest("Invalid user id")
            query_kwargs = {'username': username, 'mastodon_site': site}
        elif isinstance(id, int):
            query_kwargs = {'pk': id}
        try:
            user = User.objects.get(**query_kwargs)
        except ObjectDoesNotExist:
            msg = _("😖哎呀，这位用户还没有加入本站，快去联邦宇宙呼唤TA来注册吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )
        tag = request.GET.get('t', default='')
        if user != request.user:
            # mastodon request
            relation = get_relationship(request.user, user, request.user.mastodon_token)[0]
            if relation['blocked_by']:
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.user.mastodon_token)
            if status == 'reviewed':
                queryset = MovieReview.get_available_by_user(user, relation['following']).order_by("-edited_time")
            elif status == 'tagged':
                queryset = MovieTag.find_by_user(tag, user, relation['following']).order_by("-mark__edited_time")
            else:
                queryset = MovieMark.get_available_by_user(user, relation['following']).filter(
                    status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
        else:
            if status == 'reviewed':
                queryset = MovieReview.objects.filter(owner=user).order_by("-edited_time")
            elif status == 'tagged':
                queryset = MovieTag.objects.filter(content=tag, mark__owner=user).order_by("-mark__edited_time")
            else:
                queryset = MovieMark.objects.filter(owner=user, status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
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
            'users/movie_list.html',
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

        if isinstance(id, str):
            try:
                username = id.split('@')[0]
                site = id.split('@')[1]
            except IndexError as e:
                return HttpResponseBadRequest("Invalid user id")
            query_kwargs = {'username': username, 'mastodon_site': site}
        elif isinstance(id, int):
            query_kwargs = {'pk': id}
        try:
            user = User.objects.get(**query_kwargs)
        except ObjectDoesNotExist:
            msg = _("😖哎呀，这位用户还没有加入本站，快去联邦宇宙呼唤TA来注册吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )
        tag = request.GET.get('t', default='')
        if user != request.user:
            # mastodon request
            relation = get_relationship(request.user, user, request.user.mastodon_token)[0]
            if relation['blocked_by']:
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.user.mastodon_token)
            if status == 'reviewed':
                queryset = GameReview.get_available_by_user(user, relation['following']).order_by("-edited_time")
            elif status == 'tagged':
                queryset = GameTag.find_by_user(tag, user, relation['following']).order_by("-mark__edited_time")
            else:
                queryset = GameMark.get_available_by_user(user, relation['following']).filter(
                    status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
        else:
            if status == 'reviewed':
                queryset = GameReview.objects.filter(owner=user).order_by("-edited_time")
            elif status == 'tagged':
                queryset = GameTag.objects.filter(content=tag, mark__owner=user).order_by("-mark__edited_time")                
            else:
                queryset = GameMark.objects.filter(
                    owner=user, status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
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
            'users/game_list.html',
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

        if isinstance(id, str):
            try:
                username = id.split('@')[0]
                site = id.split('@')[1]
            except IndexError as e:
                return HttpResponseBadRequest("Invalid user id")
            query_kwargs = {'username': username, 'mastodon_site': site}
        elif isinstance(id, int):
            query_kwargs = {'pk': id}
        try:
            user = User.objects.get(**query_kwargs)
        except ObjectDoesNotExist:
            msg = _("😖哎呀，这位用户还没有加入本站，快去联邦宇宙呼唤TA来注册吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )
        tag = request.GET.get('t', default='')
        if not user == request.user:
            # mastodon request
            relation = get_relationship(request.user, user, request.user.mastodon_token)[0]
            if relation['blocked_by']:
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            if status == 'reviewed':
                queryset = list(AlbumReview.get_available_by_user(user, relation['following']).order_by("-edited_time")) + \
                    list(SongReview.get_available_by_user(user, relation['following']).order_by("-edited_time"))
            elif status == 'tagged':
                queryset = list(AlbumTag.find_by_user(tag, user, relation['following']).order_by("-mark__edited_time"))
            else:
                queryset = list(AlbumMark.get_available_by_user(user, relation['following']).filter(
                    status=MarkStatusEnum[status.upper()])) \
                        + list(SongMark.get_available_by_user(user, relation['following']).filter(
                        status=MarkStatusEnum[status.upper()]))

            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.user.mastodon_token)
        else:
            if status == 'reviewed':
                queryset = list(AlbumReview.objects.filter(owner=user).order_by("-edited_time")) + \
                    list(SongReview.objects.filter(owner=user).order_by("-edited_time"))
            elif status == 'tagged':
                queryset = list(AlbumTag.objects.filter(content=tag, mark__owner=user).order_by("-mark__edited_time"))
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
            'users/music_list.html',
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
            return redirect(reverse("users:home", args=[form.instance.reported_user.id]))
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
    if isinstance(id, str):
        try:
            username = id.split('@')[0]
            site = id.split('@')[1]
        except IndexError as e:
            return HttpResponseBadRequest("Invalid user id")
        query_kwargs = {'username': username, 'mastodon_site': site}
    elif isinstance(id, int):
        query_kwargs = {'pk': id}
    try:
        user = User.objects.get(**query_kwargs)
    except ObjectDoesNotExist:
        msg = _("😖哎呀，这位用户还没有加入本站，快去联邦宇宙呼唤TA来注册吧！")
        sec_msg = _("目前只开放本站用户注册")
        return render(
            request,
            'common/error.html',
            {
                'msg': msg,
                'secondary_msg': sec_msg,
            }
        )
    return list(request, user.id)


# Utils
########################################
def refresh_mastodon_data_task(user, token=None):
    if token:
        user.mastodon_token = token
    if user.refresh_mastodon_data():
        user.save()
        print(f"{user} mastodon data refreshed")
    else:
        print(f"{user} mastodon data refresh failed")


def auth_login(request, user):
    """ Decorates django ``login()``. Attach token to session."""
    auth.login(request, user)
    if user.mastodon_last_refresh < timezone.now() - timedelta(hours=1) or user.mastodon_account == {}:
        django_rq.get_queue('mastodon').enqueue(refresh_mastodon_data_task, user)


def auth_logout(request):
    """ Decorates django ``logout()``. Release token in session."""
    auth.logout(request)


@mastodon_request_included
@login_required
def preferences(request):
    if request.method == 'POST':
        request.user.preference.mastodon_publish_public = bool(request.POST.get('mastodon_publish_public'))
        request.user.preference.save()
    return render(request, 'users/preferences.html', {'mastodon_publish_public': request.user.preference.mastodon_publish_public})


@mastodon_request_included
@login_required
def data(request):
    return render(request, 'users/data.html', {
        'latest_task': request.user.user_synctasks.order_by("-id").first(),
        'export_status': request.user.preference.export_status
    })


@mastodon_request_included
@login_required
def export_reviews(request):
    if request.method != 'POST':
        return redirect(reverse("users:data"))
    return render(request, 'users/data.html')


@mastodon_request_included
@login_required
def export_marks(request):
    if request.method == 'POST':
        if not request.user.preference.export_status.get('marks_pending'):
            django_rq.get_queue('export').enqueue(export_marks_task, request.user)
            request.user.preference.export_status['marks_pending'] = True
            request.user.preference.save()
        messages.add_message(request, messages.INFO, _('导出已开始。'))
        return redirect(reverse("users:data"))
    else:
        with open(request.user.preference.export_status['marks_file'], 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/vnd.ms-excel")
            response['Content-Disposition'] = 'attachment;filename="marks.xlsx"'
            return response


@login_required
def sync_mastodon(request):
    if request.method == 'POST':
        django_rq.get_queue('mastodon').enqueue(refresh_mastodon_data_task, request.user)
        messages.add_message(request, messages.INFO, _('同步已开始。'))
    return redirect(reverse("users:data"))


@login_required
def reset_visibility(request):
    if request.method == 'POST':
        visibility = int(request.POST.get('visibility'))
        visibility = visibility if visibility >= 0 and visibility <= 2 else 0
        BookMark.objects.filter(owner=request.user).update(visibility=visibility)
        MovieMark.objects.filter(owner=request.user).update(visibility=visibility)
        GameMark.objects.filter(owner=request.user).update(visibility=visibility)
        AlbumMark.objects.filter(owner=request.user).update(visibility=visibility)
        SongMark.objects.filter(owner=request.user).update(visibility=visibility)
        messages.add_message(request, messages.INFO, _('已重置。'))
    return redirect(reverse("users:data"))


@login_required
def clear_data(request):
    if request.method == 'POST':
        if request.POST.get('verification') == request.user.mastodon_username:
            BookMark.objects.filter(owner=request.user).delete()
            MovieMark.objects.filter(owner=request.user).delete()
            GameMark.objects.filter(owner=request.user).delete()
            AlbumMark.objects.filter(owner=request.user).delete()
            SongMark.objects.filter(owner=request.user).delete()
            BookReview.objects.filter(owner=request.user).delete()
            MovieReview.objects.filter(owner=request.user).delete()
            GameReview.objects.filter(owner=request.user).delete()
            AlbumReview.objects.filter(owner=request.user).delete()
            SongReview.objects.filter(owner=request.user).delete()
            request.user.first_name = request.user.username
            request.user.last_name = request.user.mastodon_site
            request.user.is_active = False
            request.user.username = 'removed_' + str(request.user.id)
            request.user.mastodon_id = 0
            request.user.mastodon_site = 'removed'
            request.user.mastodon_token = ''
            request.user.mastodon_locked = False
            request.user.mastodon_followers = []
            request.user.mastodon_following = []
            request.user.mastodon_mutes = []
            request.user.mastodon_blocks = []
            request.user.mastodon_domain_blocks = []
            request.user.mastodon_account = {}
            request.user.save()
            auth_logout(request)
            return redirect(reverse("users:login"))
        else:
            messages.add_message(request, messages.ERROR, _('验证信息不符。'))
    return redirect(reverse("users:data"))
