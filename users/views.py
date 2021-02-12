from django.shortcuts import reverse, redirect, render, get_object_or_404
from django.http import HttpResponseBadRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import auth
from django.contrib.auth import authenticate
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from .models import User, Report
from .forms import ReportForm
from mastodon.auth import *
from mastodon.api import *
from mastodon import mastodon_request_included
from common.views import BOOKS_PER_SET, ITEMS_PER_PAGE, PAGE_LINK_NUMBER, TAG_NUMBER_ON_LIST, MOVIES_PER_SET
from common.models import MarkStatusEnum
from common.utils import PageLinksGenerator
from books.models import *
from movies.models import *
from books.forms import BookMarkStatusTranslator
from movies.forms import MovieMarkStatusTranslator
from mastodon.models import MastodonApplication


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

        return render(
            request,
            'users/login.html',
            {
                'sites': sites,
                'selected_site': selected_site,
            }
        )
    else:
        return HttpResponseBadRequest()


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
        if user == request.user:
            return redirect("common:home")
        else:
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
            book_marks = BookMark.get_available_by_user(user, relation['following'])
            do_book_marks = book_marks.filter(status=MarkStatusEnum.DO)
            do_books_more = True if do_book_marks.count() > BOOKS_PER_SET else False

            wish_book_marks = book_marks.filter(status=MarkStatusEnum.WISH)
            wish_books_more = True if wish_book_marks.count() > BOOKS_PER_SET else False
            
            collect_book_marks = book_marks.filter(status=MarkStatusEnum.COLLECT)
            collect_books_more = True if collect_book_marks.count() > BOOKS_PER_SET else False            

            movie_marks = MovieMark.get_available_by_user(user, relation['following'])
            do_movie_marks = movie_marks.filter(status=MarkStatusEnum.DO)
            do_movies_more = True if do_movie_marks.count() > BOOKS_PER_SET else False

            wish_movie_marks = movie_marks.filter(status=MarkStatusEnum.WISH)
            wish_movies_more = True if wish_movie_marks.count() > BOOKS_PER_SET else False
            
            collect_movie_marks = movie_marks.filter(status=MarkStatusEnum.COLLECT)
            collect_movies_more = True if collect_movie_marks.count() > BOOKS_PER_SET else False            

            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.session['oauth_token'])

            return render(
                request,
                'common/home.html',
                {
                    'user': user,
                    'do_book_marks': do_book_marks[:BOOKS_PER_SET],
                    'wish_book_marks': wish_book_marks[:BOOKS_PER_SET],
                    'collect_book_marks': collect_book_marks[:BOOKS_PER_SET],
                    'do_books_more': do_books_more,
                    'wish_books_more': wish_books_more,
                    'collect_books_more': collect_books_more,                    
                    'do_movie_marks': do_movie_marks[:MOVIES_PER_SET],
                    'wish_movie_marks': wish_movie_marks[:MOVIES_PER_SET],
                    'collect_movie_marks': collect_movie_marks[:MOVIES_PER_SET],
                    'do_movies_more': do_movies_more,
                    'wish_movies_more': wish_movies_more,
                    'collect_movies_more': collect_movies_more,
                }
            )
    else:
        return HttpResponseBadRequest()


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
            queryset = MovieMark.get_available_by_user(user, relation['following']).filter(
                status=MarkStatusEnum[status.upper()]).order_by("-edited_time")
            user.target_site_id = get_cross_site_id(
                user, request.user.mastodon_site, request.session['oauth_token'])
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
