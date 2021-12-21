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
from mastodon.models import MastodonApplication
from mastodon.api import post_toot, TootVisibilityEnum
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


@login_required
def follow(request, id):
    pass


@login_required
def unfollow(request, id):
    pass


@login_required
def list_with(request, type, id):
    pass
