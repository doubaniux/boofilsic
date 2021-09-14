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
from mastodon.auth import *
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
from django.conf import settings

# Views
########################################

# no page rendered
@mastodon_request_included
def OAuth2_login(request):
    """ oauth authentication and logging user into django system """
    if request.method == 'GET':
        code = request.GET.get('code')
        site = request.COOKIES.get('mastodon_domain')

        # Network IO
        try:
            token = obtain_token(site, request, code)
        except ObjectDoesNotExist:
            return HttpResponseBadRequest("Mastodon site not registered")
        if token:
            # oauth is completed when token aquired
            user = authenticate(request, token=token, site=site)
            if user:
                auth_login(request, user, token)
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
                'selected_site': selected_site,
                'allow_any_site': settings.MASTODON_ALLOW_ANY_SITE,
            }
        )
    else:
        return HttpResponseBadRequest()

def connect(request):
    domain = request.GET.get('domain').strip().lower()
    app = MastodonApplication.objects.filter(domain_name=domain).first()
    if app is None:
        try:
            response = create_app(domain)
        except (requests.exceptions.Timeout, ConnectionError):
            error_msg = _("长毛象请求超时。")
        except Exception as e:
            error_msg = str(e)
        else:
            # fill the form with returned data
            data = response.json()
            if response.status_code != 200:
                error_msg = str(data)
            else:
                app = MastodonApplication.objects.create(domain_name=domain, app_id=data['id'], client_id=data['client_id'],
                    client_secret=data['client_secret'], vapid_key=data['vapid_key'])
    if app is None:
        return render(request,
                'common/error.html',
                {
                    'msg': error_msg,
                    'secondary_msg': "",
                }
            )
    else:
        login_url = "https://" + domain + "/oauth/authorize?client_id=" + app.client_id + "&scope=read+write&redirect_uri=" + request.scheme + "://" + request.get_host() + reverse('users:OAuth2_login') + "&response_type=code"
        resp = redirect(login_url)
        resp.set_cookie("mastodon_domain", domain)
        return resp

@mastodon_request_included
@login_required
def logout(request):
    if request.method == 'GET':
        revoke_token(request.user.mastodon_site, request.session['oauth_token'])
        auth_logout(request)
        return redirect(reverse("users:login"))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
def register(request):
    """ register confirm page """
    if request.method == 'GET':
        if request.session.get('oauth_token'):
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
        user_data = get_user_data(request.COOKIES['mastodon_domain'], token)
        if user_data is None:
            return render(
                request,
                'common/error.html',
                {
                    'msg': _("长毛象访问失败😫")
                }
            )
        new_user = User(
            username=user_data['username'],
            mastodon_id=user_data['id'],
            mastodon_site=request.COOKIES['mastodon_domain'],
        )
        new_user.save()
        del request.session['new_user_token']
        auth_login(request, new_user, token)
        response = redirect(reverse('common:home'))
        response.delete_cookie('mastodon_domain')
        return response
    else:
        return HttpResponseBadRequest()


def delete(request):
    raise NotImplementedError


@mastodon_request_included
@login_required
def home(request, id):
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
            msg = _("😖哎呀这位老师还没有注册书影音呢，快去长毛象喊TA来吧！")
            sec_msg = _("目前只开放本站用户注册")
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

            latest_task = user.user_synctasks.order_by("-id").first()

        # visit other's home page
        else:
            latest_task = None
            # no these value on other's home page
            reports = None
            unread_announcements = None

            # cross site info for visiting other's home page
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.session['oauth_token'])
            
            # make queries
            relation = get_relationship(request.user, user, request.session['oauth_token'])[0]
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
            msg = _("😖哎呀这位老师还没有注册书影音呢，快去长毛象喊TA来吧！")
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
            relation = get_relationship(request.user, user, request.session['oauth_token'])[0]
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
                user, request.user.mastodon_site, request.session['oauth_token'])
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
            msg = _("😖哎呀这位老师还没有注册书影音呢，快去长毛象喊TA来吧！")
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
            relation = get_relationship(request.user, user, request.session['oauth_token'])[0]
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
                user, request.user.mastodon_site, request.session['oauth_token'])
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
        if not status.upper() in MarkStatusEnum.names:
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
            msg = _("😖哎呀这位老师还没有注册书影音呢，快去长毛象喊TA来吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )        
        if not user == request.user:
            # mastodon request
            relation = get_relationship(request.user, user, request.session['oauth_token'])[0]
            if relation['blocked_by']:
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            queryset = BookMark.get_available_by_user(user, relation['following']).filter(
                status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.session['oauth_token'])
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
        list_title = str(BookMarkStatusTranslator(MarkStatusEnum[status.upper()])) + str(_("的书"))
        return render(
            request,
            'users/book_list.html',
            {
                'marks': marks,
                'user': user,
                'list_title' : list_title,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def movie_list(request, id, status):
    if request.method == 'GET':
        if not status.upper() in MarkStatusEnum.names:
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
            msg = _("😖哎呀这位老师还没有注册书影音呢，快去长毛象喊TA来吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )
        if not user == request.user:
            # mastodon request
            relation = get_relationship(request.user, user, request.session['oauth_token'])[0]
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
                user, request.user.mastodon_site, request.session['oauth_token'])
        
            queryset = MovieMark.get_available_by_user(user, relation['following']).filter(
                status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
        else:
            queryset = MovieMark.objects.filter(
                owner=user, status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
        paginator = Paginator(queryset, ITEMS_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        for mark in marks:
            mark.movie.tag_list = mark.movie.get_tags_manager().values('content').annotate(
                tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER_ON_LIST]
        marks.pagination = PageLinksGenerator(PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        list_title = str(MovieMarkStatusTranslator(MarkStatusEnum[status.upper()])) + str(_("的电影和剧集"))
        return render(
            request,
            'users/movie_list.html',
            {
                'marks': marks,
                'user': user,
                'list_title' : list_title,
            }
        )
    else:
        return HttpResponseBadRequest()
            

@mastodon_request_included
@login_required
def game_list(request, id, status):
    if request.method == 'GET':
        if not status.upper() in MarkStatusEnum.names:
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
            msg = _("😖哎呀这位老师还没有注册书影音呢，快去长毛象喊TA来吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )
        if not user == request.user:
            # mastodon request
            relation = get_relationship(request.user, user, request.session['oauth_token'])[0]
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
                user, request.user.mastodon_site, request.session['oauth_token'])
        
            queryset = GameMark.get_available_by_user(user, relation['following']).filter(
                status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
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
        list_title = str(GameMarkStatusTranslator(MarkStatusEnum[status.upper()])) + str(_("的游戏"))
        return render(
            request,
            'users/game_list.html',
            {
                'marks': marks,
                'user': user,
                'list_title' : list_title,
            }
        )
    else:
        return HttpResponseBadRequest()
            

@mastodon_request_included
@login_required
def music_list(request, id, status):
    if request.method == 'GET':
        if not status.upper() in MarkStatusEnum.names:
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
            msg = _("😖哎呀这位老师还没有注册书影音呢，快去长毛象喊TA来吧！")
            sec_msg = _("目前只开放本站用户注册")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                    'secondary_msg': sec_msg,
                }
            )        
        if not user == request.user:
            # mastodon request
            relation = get_relationship(request.user, user, request.session['oauth_token'])[0]
            if relation['blocked_by']:
                msg = _("你没有访问TA主页的权限😥")
                return render(
                    request,
                    'common/error.html',
                    {
                        'msg': msg,
                    }
                )
            queryset = list(AlbumMark.get_available_by_user(user, relation['following']).filter(
                status=MarkStatusEnum[status.upper()])) \
                + list(SongMark.get_available_by_user(user, relation['following']).filter(
                    status=MarkStatusEnum[status.upper()]))
            
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.session['oauth_token'])
        else:
            queryset = list(AlbumMark.objects.filter(owner=user, status=MarkStatusEnum[status.upper()])) \
                + list(SongMark.objects.filter(owner=user, status=MarkStatusEnum[status.upper()]))
        queryset = sorted(queryset, key=lambda e: e.edited_time, reverse=True)
        paginator = Paginator(queryset, ITEMS_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        for mark in marks:
            if mark.__class__ == AlbumMark:
                mark.music = mark.album
                mark.music.tag_list = mark.album.get_tags_manager().values('content').annotate(
                    tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER_ON_LIST]
            elif mark.__class__ == SongMark:
                mark.music = mark.song
                mark.music.tag_list = mark.song.get_tags_manager().values('content').annotate(
                    tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER_ON_LIST]

        marks.pagination = PageLinksGenerator(PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        list_title = str(MusicMarkStatusTranslator(MarkStatusEnum[status.upper()])) + str(_("的音乐"))
        return render(
            request,
            'users/music_list.html',
            {
                'marks': marks,
                'user': user,
                'list_title' : list_title,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def set_layout(request):
    if request.method == 'POST':
        # json to python
        raw_layout_data = request.POST.get('layout').replace('false', 'False').replace('true', 'True')
        layout = eval(raw_layout_data)
        request.user.preference.home_layout = eval(raw_layout_data)
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


# Utils
########################################
def auth_login(request, user, token):
    """ Decorates django ``login()``. Attach token to session."""
    request.session['oauth_token'] = token
    auth.login(request, user)


def auth_logout(request):
    """ Decorates django ``logout()``. Release token in session."""
    del request.session['oauth_token']
    auth.logout(request)    
