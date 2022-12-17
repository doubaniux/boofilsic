import logging
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseBadRequest, HttpResponseServerError, HttpResponse
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from django.core.paginator import Paginator
from mastodon import mastodon_request_included
from mastodon.models import MastodonApplication
from mastodon.api import share_mark, share_review
from common.utils import PageLinksGenerator
from common.views import PAGE_LINK_NUMBER, jump_or_scrape, go_relogin
from common.models import SourceSiteEnum
from .models import *
from .forms import *
from django.conf import settings
from collection.models import CollectionItem
from common.scraper import get_scraper_by_url, get_normalized_url


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
        form = GameForm()
        return render(
            request,
            'games/create_update.html',
            {
                'form': form,
                'title': _('添加游戏'),
                'submit_url': reverse("games:create"),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        if request.user.is_authenticated:
            # only local user can alter public data
            form = GameForm(request.POST, request.FILES)
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
                return redirect(reverse("games:retrieve", args=[form.instance.id]))
            else:
                return render(
                    request,
                    'games/create_update.html',
                    {
                        'form': form,
                        'title': _('添加游戏'),
                        'submit_url': reverse("games:create"),
                        # provided for frontend js
                        'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
                    }
                )
        else:
            return redirect(reverse("users:login"))
    else:
        return HttpResponseBadRequest()


@login_required
def rescrape(request, id):
    if request.method != 'POST':
        return HttpResponseBadRequest()
    item = get_object_or_404(Game, pk=id)
    url = get_normalized_url(item.source_url)
    scraper = get_scraper_by_url(url)
    scraper.scrape(url)
    form = scraper.save(request_user=request.user, instance=item)
    return redirect(reverse("games:retrieve", args=[form.instance.id]))


@login_required
def update(request, id):
    if request.method == 'GET':
        game = get_object_or_404(Game, pk=id)
        form = GameForm(instance=game)
        page_title = _('修改游戏')
        return render(
            request,
            'games/create_update.html',
            {
                'form': form,
                'is_update': True,
                'title': page_title,
                'submit_url': reverse("games:update", args=[game.id]),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        game = get_object_or_404(Game, pk=id)
        form = GameForm(request.POST, request.FILES, instance=game)
        page_title =  _("修改游戏")
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
                'games/create_update.html',
                {
                    'form': form,
                    'is_update': True,
                    'title': page_title,
                    'submit_url': reverse("games:update", args=[game.id]),
                    # provided for frontend js
                    'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
                }
            )
        return redirect(reverse("games:retrieve", args=[form.instance.id]))

    else:
        return HttpResponseBadRequest()


@mastodon_request_included
# @login_required
def retrieve(request, id):
    if request.method == 'GET':
        game = get_object_or_404(Game, pk=id)
        mark = None
        mark_tags = None
        review = None

        # retreive tags
        game_tag_list = game.game_tags.values('content').annotate(
            tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER]

        # retrieve user mark and initialize mark form
        try:
            if request.user.is_authenticated:
                mark = GameMark.objects.get(owner=request.user, game=game)
        except ObjectDoesNotExist:
            mark = None
        if mark:
            mark_tags = mark.gamemark_tags.all()
            mark.get_status_display = GameMarkStatusTranslator(mark.status)
            mark_form = GameMarkForm(instance=mark, initial={
                'tags': mark_tags
            })
        else:
            mark_form = GameMarkForm(initial={
                'game': game,
                'visibility': request.user.get_preference().default_visibility if request.user.is_authenticated else 0,
                'tags': mark_tags
            })

        # retrieve user review
        try:
            if request.user.is_authenticated:
                review = GameReview.objects.get(
                    owner=request.user, game=game)
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
            mark_list = GameMark.get_available(game, request.user)
            review_list = GameReview.get_available(game, request.user)
            mark_list_more = True if len(mark_list) > MARK_NUMBER else False
            mark_list = mark_list[:MARK_NUMBER]
            for m in mark_list:
                m.get_status_display = GameMarkStatusTranslator(m.status)
            review_list_more = True if len(
                review_list) > REVIEW_NUMBER else False
            review_list = review_list[:REVIEW_NUMBER]
        all_collections = CollectionItem.objects.filter(game=game).annotate(num_marks=Count('collection__collection_marks')).order_by('-num_marks')[:20]
        collection_list = filter(lambda c: c.is_visible_to(request.user), map(lambda i: i.collection, all_collections))

        # def strip_html_tags(text):
        #     import re
        #     regex = re.compile('<.*?>')
        #     return re.sub(regex, '', text)

        # for r in review_list:
        #     r.content = strip_html_tags(r.content)

        return render(
            request,
            'games/detail.html',
            {
                'game': game,
                'mark': mark,
                'review': review,
                'status_enum': MarkStatusEnum,
                'mark_form': mark_form,
                'mark_list': mark_list,
                'mark_list_more': mark_list_more,
                'review_list': review_list,
                'review_list_more': review_list_more,
                'game_tag_list': game_tag_list,
                'mark_tags': mark_tags,
                'collection_list': collection_list,
            }
        )
    else:
        logger.warning('non-GET method at /games/<id>')
        return HttpResponseBadRequest()


@permission_required("games.delete_game")
@login_required
def delete(request, id):
    if request.method == 'GET':
        game = get_object_or_404(Game, pk=id)
        return render(
            request,
            'games/delete.html',
            {
                'game': game,
            }
        )
    elif request.method == 'POST':
        if request.user.is_staff:
            # only staff has right to delete
            game = get_object_or_404(Game, pk=id)
            game.delete()
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
    # transaction on updating game rating
    # owner check(guarantee)
    if request.method == 'POST':
        pk = request.POST.get('id')
        old_rating = None
        old_tags = None
        if not pk:
            game_id = request.POST.get('game')
            mark = GameMark.objects.filter(game_id=game_id, owner=request.user).first()
            if mark:
                pk = mark.id
        if pk:
            mark = get_object_or_404(GameMark, pk=pk)
            if request.user != mark.owner:
                return HttpResponseBadRequest()
            old_rating = mark.rating
            old_tags = mark.gamemark_tags.all()
            if mark.status != request.POST.get('status'):
                mark.created_time = timezone.now()
            # update
            form = GameMarkForm(request.POST, instance=mark)
        else:
            # create
            form = GameMarkForm(request.POST)

        if form.is_valid():
            if form.instance.status == MarkStatusEnum.WISH.value or form.instance.rating == 0:
                form.instance.rating = None
                form.cleaned_data['rating'] = None
            form.instance.owner = request.user
            form.instance.edited_time = timezone.now()
            game = form.instance.game

            try:
                with transaction.atomic():
                    # update game rating
                    game.update_rating(old_rating, form.instance.rating)
                    form.save()
                    # update tags
                    if old_tags:
                        for tag in old_tags:
                            tag.delete()
                    if form.cleaned_data['tags']:
                        for tag in form.cleaned_data['tags']:
                            GameTag.objects.create(
                                content=tag,
                                game=game,
                                mark=form.instance
                            )
            except IntegrityError as e:
                logger.error(e.__str__())
                return HttpResponseServerError("integrity error")

            if form.cleaned_data['share_to_mastodon']:
                if not share_mark(form.instance):
                    return go_relogin(request)
        else:
            return HttpResponseBadRequest(f"invalid form data {form.errors}")

        return redirect(reverse("games:retrieve", args=[form.instance.game.id]))
    else:
        return HttpResponseBadRequest("invalid method")


@mastodon_request_included
@login_required
def wish(request, id):
    if request.method == 'POST':
        game = get_object_or_404(Game, pk=id)
        params = {
            'owner': request.user,
            'status': MarkStatusEnum.WISH,
            'visibility': request.user.preference.default_visibility,
            'game': game,
        }
        try:
            GameMark.objects.create(**params)
        except Exception:
            pass
        return HttpResponse("✔️")
    else:
        return HttpResponseBadRequest("invalid method")


@mastodon_request_included
@login_required
def retrieve_mark_list(request, game_id, following_only=False):
    if request.method == 'GET':
        game = get_object_or_404(Game, pk=game_id)
        queryset = GameMark.get_available(game, request.user, following_only=following_only)
        paginator = Paginator(queryset, MARK_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        marks.pagination = PageLinksGenerator(
            PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        for m in marks:
            m.get_status_display = GameMarkStatusTranslator(m.status)
        return render(
            request,
            'games/mark_list.html',
            {
                'marks': marks,
                'game': game,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def delete_mark(request, id):
    if request.method == 'POST':
        mark = get_object_or_404(GameMark, pk=id)
        if request.user != mark.owner:
            return HttpResponseBadRequest()
        game_id = mark.game.id
        try:
            with transaction.atomic():
                # update game rating
                mark.game.update_rating(mark.rating, None)
                mark.delete()
        except IntegrityError as e:
            return HttpResponseServerError()
        return redirect(reverse("games:retrieve", args=[game_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def create_review(request, game_id):
    if request.method == 'GET':
        form = GameReviewForm(initial={'game': game_id})
        game = get_object_or_404(Game, pk=game_id)
        return render(
            request,
            'games/create_update_review.html',
            {
                'form': form,
                'title': _("添加评论"),
                'game': game,
                'submit_url': reverse("games:create_review", args=[game_id]),
            }
        )
    elif request.method == 'POST':
        form = GameReviewForm(request.POST)
        if form.is_valid():
            form.instance.owner = request.user
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if not share_review(form.instance):
                    return go_relogin(request)
            return redirect(reverse("games:retrieve_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def update_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(GameReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        form = GameReviewForm(instance=review)
        game = review.game
        return render(
            request,
            'games/create_update_review.html',
            {
                'form': form,
                'title': _("编辑评论"),
                'game': game,
                'submit_url': reverse("games:update_review", args=[review.id]),
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(GameReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        form = GameReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.instance.edited_time = timezone.now()
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if not share_review(form.instance):
                    return go_relogin(request)
            return redirect(reverse("games:retrieve_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@login_required
def delete_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(GameReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        review_form = GameReviewForm(instance=review)
        return render(
            request,
            'games/delete_review.html',
            {
                'form': review_form,
                'review': review,
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(GameReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        game_id = review.game.id
        review.delete()
        return redirect(reverse("games:retrieve", args=[game_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
def retrieve_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(GameReview, pk=id)
        if not review.is_visible_to(request.user):
            msg = _("你没有访问这个页面的权限😥")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                }
            )
        review_form = GameReviewForm(instance=review)
        game = review.game
        try:
            mark = GameMark.objects.get(owner=review.owner, game=game)
            mark.get_status_display = GameMarkStatusTranslator(mark.status)
        except ObjectDoesNotExist:
            mark = None
        return render(
            request,
            'games/review_detail.html',
            {
                'form': review_form,
                'review': review,
                'game': game,
                'mark': mark,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_review_list(request, game_id):
    if request.method == 'GET':
        game = get_object_or_404(Game, pk=game_id)
        queryset = GameReview.get_available(game, request.user)
        paginator = Paginator(queryset, REVIEW_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        reviews = paginator.get_page(page_number)
        reviews.pagination = PageLinksGenerator(
            PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        return render(
            request,
            'games/review_list.html',
            {
                'reviews': reviews,
                'game': game,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def scrape(request):
    if request.method == 'GET':
        keywords = request.GET.get('q')
        form = GameForm()
        return render(
            request,
            'games/scrape.html',
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
