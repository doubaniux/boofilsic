import logging
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseBadRequest, HttpResponseServerError
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from django.core.paginator import Paginator
from mastodon import mastodon_request_included
from mastodon.api import check_visibility, post_toot, TootVisibilityEnum
from mastodon.utils import rating_to_emoji
from common.utils import PageLinksGenerator
from common.views import PAGE_LINK_NUMBER, jump_or_scrape
from common.models import SourceSiteEnum
from .models import *
from .forms import *
from django.conf import settings


logger = logging.getLogger(__name__)
mastodon_logger = logging.getLogger("django.mastodon")


# how many marks showed on the detail page
MARK_NUMBER = 5
# how many marks at the mark page
MARK_PER_PAGE = 20
# how many reviews showed on the detail page
REVIEW_NUMBER = 5
# how many reviews at the mark page
REVIEW_PER_PAGE = 20
# max tags on detail page
TAG_NUMBER = 10


# public data
###########################
@login_required
def create(request):
    if request.method == 'GET':
        form = MovieForm()
        return render(
            request,
            'movies/create_update.html',
            {
                'form': form,
                'title': _('添加电影/剧集'),
                'submit_url': reverse("movies:create"),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        if request.user.is_authenticated:
            # only local user can alter public data
            form = MovieForm(request.POST, request.FILES)
            if form.is_valid():
                form.instance.last_editor = request.user
                try:
                    with transaction.atomic():
                        form.save()
                        if form.instance.source_site == SourceSiteEnum.IN_SITE.value:
                            real_url = form.instance.get_absolute_url()
                            form.instance.source_url = real_url
                            form.instance.save()
                except IntegrityError as e:
                    logger.error(e.__str__())
                    return HttpResponseServerError("integrity error")
                return redirect(reverse("movies:retrieve", args=[form.instance.id]))
            else:
                return render(
                    request,
                    'movies/create_update.html',
                    {
                        'form': form,
                        'title': _('添加电影/剧集'),
                        'submit_url': reverse("movies:create"),
                        # provided for frontend js
                        'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
                    }
                )
        else:
            return redirect(reverse("users:login"))
    else:
        return HttpResponseBadRequest()


@login_required
def update(request, id):
    if request.method == 'GET':
        movie = get_object_or_404(Movie, pk=id)
        form = MovieForm(instance=movie)
        page_title = _('修改剧集') if movie.is_series else _("修改电影")
        return render(
            request,
            'movies/create_update.html',
            {
                'form': form,
                'title': page_title,
                'submit_url': reverse("movies:update", args=[movie.id]),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        movie = get_object_or_404(Movie, pk=id)
        form = MovieForm(request.POST, request.FILES, instance=movie)
        page_title = _('修改剧集') if movie.is_series else _("修改电影")
        if form.is_valid():
            form.instance.last_editor = request.user
            form.instance.edited_time = timezone.now()
            try:
                with transaction.atomic():
                    form.save()
                    if form.instance.source_site == SourceSiteEnum.IN_SITE.value:
                        real_url = form.instance.get_absolute_url()
                        form.instance.source_url = real_url
                        form.instance.save()
            except IntegrityError as e:
                logger.error(e.__str__())
                return HttpResponseServerError("integrity error")
        else:
            return render(
                request,
                'movies/create_update.html',
                {
                    'form': form,
                    'title': page_title,
                    'submit_url': reverse("movies:update", args=[movie.id]),
                    # provided for frontend js
                    'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
                }
            )
        return redirect(reverse("movies:retrieve", args=[form.instance.id]))

    else:
        return HttpResponseBadRequest()


@mastodon_request_included
# @login_required
def retrieve(request, id):
    if request.method == 'GET':
        movie = get_object_or_404(Movie, pk=id)
        mark = None
        mark_tags = None
        review = None

        # retreive tags
        movie_tag_list = movie.movie_tags.values('content').annotate(
            tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER]

        # retrieve user mark and initialize mark form
        try:
            if request.user.is_authenticated:
                mark = MovieMark.objects.get(owner=request.user, movie=movie)
        except ObjectDoesNotExist:
            mark = None
        if mark:
            mark_tags = mark.moviemark_tags.all()
            mark.get_status_display = MovieMarkStatusTranslator(mark.status)
            mark_form = MovieMarkForm(instance=mark, initial={
                'tags': mark_tags
            })
        else:
            mark_form = MovieMarkForm(initial={
                'movie': movie,
                'tags': mark_tags
            })

        # retrieve user review
        try:
            if request.user.is_authenticated:
                review = MovieReview.objects.get(owner=request.user, movie=movie)
        except ObjectDoesNotExist:
            review = None

        # retrieve other related reviews and marks
        if request.user.is_anonymous:
            # hide all marks and reviews for anonymous user
            mark_list = None
            review_list = None
            mark_list_more = None
            review_list_more = None
        else:
            mark_list = MovieMark.get_available(
                movie, request.user, request.session['oauth_token'])
            review_list = MovieReview.get_available(
                movie, request.user, request.session['oauth_token'])
            mark_list_more = True if len(mark_list) > MARK_NUMBER else False
            mark_list = mark_list[:MARK_NUMBER]
            for m in mark_list:
                m.get_status_display = MovieMarkStatusTranslator(m.status)
            review_list_more = True if len(
                review_list) > REVIEW_NUMBER else False
            review_list = review_list[:REVIEW_NUMBER]

        # def strip_html_tags(text):
        #     import re
        #     regex = re.compile('<.*?>')
        #     return re.sub(regex, '', text)

        # for r in review_list:
        #     r.content = strip_html_tags(r.content)

        return render(
            request,
            'movies/detail.html',
            {
                'movie': movie,
                'mark': mark,
                'review': review,
                'status_enum': MarkStatusEnum,
                'mark_form': mark_form,
                'mark_list': mark_list,
                'mark_list_more': mark_list_more,
                'review_list': review_list,
                'review_list_more': review_list_more,
                'movie_tag_list': movie_tag_list,
                'mark_tags': mark_tags,
            }
        )
    else:
        logger.warning('non-GET method at /movies/<id>')
        return HttpResponseBadRequest()


@permission_required("movies.delete_movie")
@login_required
def delete(request, id):
    if request.method == 'GET':
        movie = get_object_or_404(Movie, pk=id)
        return render(
            request,
            'movies/delete.html',
            {
                'movie': movie,
            }
        )
    elif request.method == 'POST':
        if request.user.is_staff:
            # only staff has right to delete
            movie = get_object_or_404(Movie, pk=id)
            movie.delete()
            return redirect(reverse("common:home"))
        else:
            raise PermissionDenied()
    else:
        return HttpResponseBadRequest()


# user owned entites
###########################
@mastodon_request_included
@login_required
def create_update_mark(request):
    # check list:
    # clean rating if is wish
    # transaction on updating movie rating
    # owner check(guarantee)
    if request.method == 'POST':
        pk = request.POST.get('id')
        old_rating = None
        old_tags = None
        if pk:
            mark = get_object_or_404(MovieMark, pk=pk)
            if request.user != mark.owner:
                return HttpResponseBadRequest()
            old_rating = mark.rating
            old_tags = mark.moviemark_tags.all()
            # update
            form = MovieMarkForm(request.POST, instance=mark)
        else:
            # create
            form = MovieMarkForm(request.POST)

        if form.is_valid():
            if form.instance.status == MarkStatusEnum.WISH.value:
                form.instance.rating = None
                form.cleaned_data['rating'] = None
            form.instance.owner = request.user
            form.instance.edited_time = timezone.now()
            movie = form.instance.movie

            try:
                with transaction.atomic():
                    # update movie rating
                    movie.update_rating(old_rating, form.instance.rating)
                    form.save()
                    # update tags
                    if old_tags:
                        for tag in old_tags:
                            tag.delete()
                    if form.cleaned_data['tags']:
                        for tag in form.cleaned_data['tags']:
                            MovieTag.objects.create(
                                content=tag,
                                movie=movie,
                                mark=form.instance
                            )
            except IntegrityError as e:
                logger.error(e.__str__())
                return HttpResponseServerError("integrity error")

            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.UNLISTED
                url = "https://" + request.get_host() + reverse("movies:retrieve",
                                                                args=[movie.id])
                words = MovieMarkStatusTranslator(form.cleaned_data['status']) +\
                    f"《{movie.title}》" + \
                    rating_to_emoji(form.cleaned_data['rating'])

                # tags = settings.MASTODON_TAGS % {'category': '书', 'type': '标记'}
                tags = ''
                content = words + '\n' + url + '\n' + \
                    form.cleaned_data['text'] + '\n' + tags
                response = post_toot(request.user.mastodon_site, content, visibility,
                                     request.session['oauth_token'])
                if response.status_code != 200:
                    mastodon_logger.error(
                        f"CODE:{response.status_code} {response.text}")
                    return HttpResponseServerError("publishing mastodon status failed")
        else:
            return HttpResponseBadRequest("invalid form data")

        return redirect(reverse("movies:retrieve", args=[form.instance.movie.id]))
    else:
        return HttpResponseBadRequest("invalid method")


@mastodon_request_included
@login_required
def retrieve_mark_list(request, movie_id):
    if request.method == 'GET':
        movie = get_object_or_404(Movie, pk=movie_id)
        queryset = MovieMark.get_available(
            movie, request.user, request.session['oauth_token'])
        paginator = Paginator(queryset, MARK_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        marks.pagination = PageLinksGenerator(
            PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        for m in marks:
            m.get_status_display = MovieMarkStatusTranslator(m.status)
        return render(
            request,
            'movies/mark_list.html',
            {
                'marks': marks,
                'movie': movie,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def delete_mark(request, id):
    if request.method == 'POST':
        mark = get_object_or_404(MovieMark, pk=id)
        if request.user != mark.owner:
            return HttpResponseBadRequest()
        movie_id = mark.movie.id
        try:
            with transaction.atomic():
                # update movie rating
                mark.movie.update_rating(mark.rating, None)
                mark.delete()
        except IntegrityError as e:
            return HttpResponseServerError()
        return redirect(reverse("movies:retrieve", args=[movie_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def create_review(request, movie_id):
    if request.method == 'GET':
        form = MovieReviewForm(initial={'movie': movie_id})
        movie = get_object_or_404(Movie, pk=movie_id)
        return render(
            request,
            'movies/create_update_review.html',
            {
                'form': form,
                'title': _("添加评论"),
                'movie': movie,
                'submit_url': reverse("movies:create_review", args=[movie_id]),
            }
        )
    elif request.method == 'POST':
        form = MovieReviewForm(request.POST)
        if form.is_valid():
            form.instance.owner = request.user
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.UNLISTED
                url = "https://" + request.get_host() + reverse("movies:retrieve_review",
                                                                args=[form.instance.id])
                words = "发布了关于" + f"《{form.instance.movie.title}》" + "的评论"
                # tags = settings.MASTODON_TAGS % {'category': '书', 'type': '评论'}
                tags = ''
                content = words + '\n' + url + \
                    '\n' + form.cleaned_data['title'] + '\n' + tags
                response = post_toot(request.user.mastodon_site, content, visibility,
                                     request.session['oauth_token'])
                if response.status_code != 200:
                    mastodon_logger.error(
                        f"CODE:{response.status_code} {response.text}")
                    return HttpResponseServerError("publishing mastodon status failed")
            return redirect(reverse("movies:retrieve_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def update_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(MovieReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        form = MovieReviewForm(instance=review)
        movie = review.movie
        return render(
            request,
            'movies/create_update_review.html',
            {
                'form': form,
                'title': _("编辑评论"),
                'movie': movie,
                'submit_url': reverse("movies:update_review", args=[review.id]),
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(MovieReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        form = MovieReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.instance.edited_time = timezone.now()
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.UNLISTED
                url = "https://" + request.get_host() + reverse("movies:retrieve_review",
                                                                args=[form.instance.id])
                words = "发布了关于" + f"《{form.instance.movie.title}》" + "的评论"
                # tags = settings.MASTODON_TAGS % {'category': '书', 'type': '评论'}
                tags = ''
                content = words + '\n' + url + \
                    '\n' + form.cleaned_data['title'] + '\n' + tags
                response = post_toot(request.user.mastodon_site, content, visibility,
                                     request.session['oauth_token'])
                if response.status_code != 200:
                    mastodon_logger.error(
                        f"CODE:{response.status_code} {response.text}")
                    return HttpResponseServerError("publishing mastodon status failed")
            return redirect(reverse("movies:retrieve_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@login_required
def delete_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(MovieReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        review_form = MovieReviewForm(instance=review)
        return render(
            request,
            'movies/delete_review.html',
            {
                'form': review_form,
                'review': review,
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(MovieReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        movie_id = review.movie.id
        review.delete()
        return redirect(reverse("movies:retrieve", args=[movie_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(MovieReview, pk=id)
        if not check_visibility(review, request.session['oauth_token'], request.user):
            msg = _("你没有访问这个页面的权限😥")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                }
            )
        review_form = MovieReviewForm(instance=review)
        movie = review.movie
        try:
            mark = MovieMark.objects.get(owner=review.owner, movie=movie)
            mark.get_status_display = MovieMarkStatusTranslator(mark.status)
        except ObjectDoesNotExist:
            mark = None
        return render(
            request,
            'movies/review_detail.html',
            {
                'form': review_form,
                'review': review,
                'movie': movie,
                'mark': mark,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_review_list(request, movie_id):
    if request.method == 'GET':
        movie = get_object_or_404(Movie, pk=movie_id)
        queryset = MovieReview.get_available(
            movie, request.user, request.session['oauth_token'])
        paginator = Paginator(queryset, REVIEW_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        reviews = paginator.get_page(page_number)
        reviews.pagination = PageLinksGenerator(
            PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        return render(
            request,
            'movies/review_list.html',
            {
                'reviews': reviews,
                'movie': movie,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def scrape(request):
    if request.method == 'GET':
        keywords = request.GET.get('q')
        form = MovieForm()
        return render(
            request,
            'movies/scrape.html',
            {
                'q': keywords,
                'form': form,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def click_to_scrape(request):
    if request.method == "POST":
        url = request.POST.get("url")
        if url:
            return jump_or_scrape(request, url)
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()
