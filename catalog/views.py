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
from .models import *
# from .forms import *
# from .forms import BookMarkStatusTranslator
from django.conf import settings
from collection.models import CollectionItem
from common.scraper import get_scraper_by_url, get_normalized_url
from django.utils.baseconv import base62
from journal.models import Mark
from journal.models import query_visible


_logger = logging.getLogger(__name__)


def retrieve_by_uuid(request, item_uuid):
    item = get_object_or_404(Item, uid=item_uuid)
    return redirect(item.url)


def retrieve(request, item_path, item_uid):
    if request.method == 'GET':
        item = get_object_or_404(Item, uid=base62.decode(item_uid))
        item_url = f'/{item_path}/{item_uid}/'
        if item.url != item_url:
            return redirect(item.url)
        mark = None
        review = None
        mark_list = None
        review_list = None
        mark_list_more = None
        review_list_more = None
        collection_list = []
        mark_form = None
        if request.user.is_authenticated:
            mark = Mark(request.user, item)
            _logger.info(mark.rating)
            review = mark.review
            collection_list = item.collections.all().filter(query_visible(request.user)).annotate(like_counts=Count('likes')).order_by('-like_counts')

        return render(request, item.class_name + '.html', {
            'item': item,
            'mark': mark,
            'review': review,
            'mark_form': mark_form,
            'mark_list': mark_list,
            'mark_list_more': mark_list_more,
            'review_list': review_list,
            'review_list_more': review_list_more,
            'collection_list': collection_list,
        }
        )
    else:
        logger.warning('non-GET method at /book/<id>')
        return HttpResponseBadRequest()
