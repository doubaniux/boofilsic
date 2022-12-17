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
# from .forms import *
# from .forms import BookMarkStatusTranslator
from django.conf import settings
from collection.models import CollectionItem
from common.scraper import get_scraper_by_url, get_normalized_url
from django.utils.baseconv import base62
from journal.models import Mark


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
            review = mark.review

        # # retreive tags
        # book_tag_list = book.book_tags.values('content').annotate(
        #     tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER]

        # # retrieve user mark and initialize mark form
        # try:
        #     if request.user.is_authenticated:
        #         mark = BookMark.objects.get(owner=request.user, book=book)
        # except ObjectDoesNotExist:
        #     mark = None
        # if mark:
        #     mark_tags = mark.bookmark_tags.all()
        #     mark.get_status_display = BookMarkStatusTranslator(mark.status)
        #     mark_form = BookMarkForm(instance=mark, initial={
        #         'tags': mark_tags
        #     })
        # else:
        #     mark_form = BookMarkForm(initial={
        #         'book': book,
        #         'visibility': request.user.get_preference().default_visibility if request.user.is_authenticated else 0,
        #         'tags': mark_tags
        #     })

        # # retrieve user review
        # try:
        #     if request.user.is_authenticated:
        #         review = BookReview.objects.get(owner=request.user, book=book)
        # except ObjectDoesNotExist:
        #     review = None

        # # retrieve other related reviews and marks
        # if request.user.is_anonymous:
        #     # hide all marks and reviews for anonymous user
        #     mark_list = None
        #     review_list = None
        #     mark_list_more = None
        #     review_list_more = None
        # else:
        #     mark_list = BookMark.get_available_for_identicals(book, request.user)
        #     review_list = BookReview.get_available_for_identicals(book, request.user)
        #     mark_list_more = True if len(mark_list) > MARK_NUMBER else False
        #     mark_list = mark_list[:MARK_NUMBER]
        #     for m in mark_list:
        #         m.get_status_display = BookMarkStatusTranslator(m.status)
        #     review_list_more = True if len(
        #         review_list) > REVIEW_NUMBER else False
        #     review_list = review_list[:REVIEW_NUMBER]
        # all_collections = CollectionItem.objects.filter(book=book).annotate(num_marks=Count('collection__collection_marks')).order_by('-num_marks')[:20]
        # collection_list = filter(lambda c: c.is_visible_to(request.user), map(lambda i: i.collection, all_collections))

        # def strip_html_tags(text):
        #     import re
        #     regex = re.compile('<.*?>')
        #     return re.sub(regex, '', text)

        # for r in review_list:
        #     r.content = strip_html_tags(r.content)

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
