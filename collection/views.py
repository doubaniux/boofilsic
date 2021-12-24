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
        form = CollectionForm()
        return render(
            request,
            'create_update.html',
            {
                'form': form,
                'title': _('添加收藏单'),
                'submit_url': reverse("collection:create"),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        if request.user.is_authenticated:
            # only local user can alter public data
            form = CollectionForm(request.POST, request.FILES)
            form.instance.owner = request.user
            if form.is_valid():
                form.instance.last_editor = request.user
                try:
                    with transaction.atomic():
                        form.save()
                except IntegrityError as e:
                    logger.error(e.__str__())
                    return HttpResponseServerError("integrity error")
                return redirect(reverse("collection:retrieve", args=[form.instance.id]))
            else:
                return render(
                    request,
                    'create_update.html',
                    {
                        'form': form,
                        'title': _('添加收藏單'),
                        'submit_url': reverse("collection:create"),
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
    page_title = _("修改游戏")
    collection = get_object_or_404(Collection, pk=id)
    if not collection.is_visible_to(request.user):
        raise PermissionDenied()
    if request.method == 'GET':
        form = CollectionForm(instance=collection)
        return render(
            request,
            'create_update.html',
            {
                'form': form,
                'title': page_title,
                'submit_url': reverse("collection:update", args=[collection.id]),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        form = CollectionForm(request.POST, request.FILES, instance=collection)
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
                'create_update.html',
                {
                    'form': form,
                    'title': page_title,
                    'submit_url': reverse("collection:update", args=[collection.id]),
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
        collection = get_object_or_404(Collection, pk=id)
        if not collection.is_visible_to(request.user):
            raise PermissionDenied()
        form = CollectionForm(instance=collection)

        followers = []
        if request.user.is_authenticated:
            followers = []

        return render(
            request,
            'detail.html',
            {
                'collection': collection,
                'form': form,
                'followers': followers,

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
