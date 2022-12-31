import uuid
import logging
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.translation import gettext_lazy as _
from django.http import (
    HttpResponseBadRequest,
    HttpResponseServerError,
    HttpResponse,
    HttpResponseRedirect,
)
from django.core.exceptions import BadRequest, ObjectDoesNotExist, PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from django.core.paginator import Paginator
from polymorphic.base import django
from catalog.common.sites import AbstractSite, SiteManager
from mastodon import mastodon_request_included
from mastodon.models import MastodonApplication
from mastodon.api import share_mark, share_review
from .models import *
from django.conf import settings
from common.scraper import get_scraper_by_url, get_normalized_url
from django.utils.baseconv import base62
from journal.models import Mark, ShelfMember, Review
from journal.models import query_visible, query_following
from common.utils import PageLinksGenerator
from common.views import PAGE_LINK_NUMBER
from journal.models import ShelfTypeNames
import django_rq
from rq.job import Job

_logger = logging.getLogger(__name__)


NUM_REVIEWS_ON_ITEM_PAGE = 5
NUM_REVIEWS_ON_LIST_PAGE = 20


class HTTPResponseHXRedirect(HttpResponseRedirect):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self["HX-Redirect"] = self["Location"]

    status_code = 200


def retrieve_by_uuid(request, item_uid):
    item = get_object_or_404(Item, uid=item_uid)
    return redirect(item.url)


def retrieve(request, item_path, item_uuid):
    if request.method == "GET":
        item = get_object_or_404(Item, uid=base62.decode(item_uuid))
        item_url = f"/{item_path}/{item_uuid}"
        if item.url != item_url:
            return redirect(item.url)
        mark = None
        review = None
        mark_list = None
        review_list = None
        collection_list = []
        shelf_types = [
            (n[1], n[2]) for n in iter(ShelfTypeNames) if n[0] == item.category
        ]
        if request.user.is_authenticated:
            visible = query_visible(request.user)
            mark = Mark(request.user, item)
            _logger.info(mark.rating)
            review = mark.review
            collection_list = (
                item.collections.all()
                .filter(visible)
                .annotate(like_counts=Count("likes"))
                .order_by("-like_counts")
            )
            mark_query = (
                ShelfMember.objects.filter(item=item)
                .filter(visible)
                .order_by("-created_time")
            )
            mark_list = [
                member.mark for member in mark_query[:NUM_REVIEWS_ON_ITEM_PAGE]
            ]
            review_list = (
                Review.objects.filter(item=item)
                .filter(visible)
                .order_by("-created_time")[:NUM_REVIEWS_ON_ITEM_PAGE]
            )

        return render(
            request,
            item.class_name + ".html",
            {
                "item": item,
                "mark": mark,
                "review": review,
                "mark_list": mark_list,
                "review_list": review_list,
                "collection_list": collection_list,
                "shelf_types": shelf_types,
            },
        )
    else:
        return HttpResponseBadRequest()


def mark_list(request, item_path, item_uuid, following_only=False):
    item = get_object_or_404(Item, uid=base62.decode(item_uuid))
    if not item:
        return HttpResponseNotFound("item not found")
    queryset = ShelfMember.objects.filter(item=item).order_by("-created_time")
    if following_only:
        queryset = queryset.filter(query_following(request.user))
    else:
        queryset = queryset.filter(query_visible(request.user))
    paginator = Paginator(queryset, NUM_REVIEWS_ON_LIST_PAGE)
    page_number = request.GET.get("page", default=1)
    marks = paginator.get_page(page_number)
    marks.pagination = PageLinksGenerator(
        PAGE_LINK_NUMBER, page_number, paginator.num_pages
    )
    return render(
        request,
        "item_mark_list.html",
        {
            "marks": marks,
            "item": item,
        },
    )


def review_list(request, item_path, item_uuid):
    item = get_object_or_404(Item, uid=base62.decode(item_uuid))
    if not item:
        return HttpResponseNotFound("item not found")
    queryset = Review.objects.filter(item=item).order_by("-created_time")
    queryset = queryset.filter(query_visible(request.user))
    paginator = Paginator(queryset, NUM_REVIEWS_ON_LIST_PAGE)
    page_number = request.GET.get("page", default=1)
    reviews = paginator.get_page(page_number)
    reviews.pagination = PageLinksGenerator(
        PAGE_LINK_NUMBER, page_number, paginator.num_pages
    )
    return render(
        request,
        "item_review_list.html",
        {
            "reviews": reviews,
            "item": item,
        },
    )


def fetch_task(url):
    try:
        site = SiteManager.get_site_by_url(url)
        site.get_resource_ready()
        item = site.get_item()
        return item.url if item else "-"
    except Exception:
        return "-"


def fetch_refresh(request, job_id):
    retry = request.GET
    job = Job.fetch(id=job_id, connection=django_rq.get_connection("fetch"))
    item_url = job.result if job else "-"  # FIXME job.return_value() in rq 1.12
    if item_url:
        if item_url == "-":
            return render(request, "fetch_failed.html")
        else:
            return HTTPResponseHXRedirect(item_url)
    else:
        retry = int(request.GET.get("retry", 0)) + 1
        if retry > 10:
            return render(request, "fetch_failed.html")
        else:
            return render(
                request,
                "fetch_refresh.html",
                {"job_id": job_id, "retry": retry, "delay": retry * 2},
            )


def fetch(request, url, site: AbstractSite = None):
    if not site:
        site = SiteManager.get_site_by_url(keywords)
        if not site:
            return HttpResponseBadRequest()
    item = site.get_item()
    if item:
        return redirect(item.url)
    job_id = uuid.uuid4().hex
    django_rq.get_queue("fetch").enqueue(fetch_task, url, job_id=job_id)
    return render(
        request,
        "fetch_pending.html",
        {
            "site": site,
            "job_id": job_id,
        },
    )


def search(request):
    category = request.GET.get("c", default="all").strip().lower()
    if category == "all":
        category = None
    keywords = request.GET.get("q", default="").strip()
    tag = request.GET.get("tag", default="").strip()
    p = request.GET.get("page", default="1")
    page_number = int(p) if p.isdigit() else 1
    if not (keywords or tag):
        return render(
            request,
            "common/search_result.html",
            {
                "items": None,
            },
        )

    if request.user.is_authenticated and keywords.find("://") > 0:
        site = SiteManager.get_site_by_url(keywords)
        if site:
            return fetch(request, keywords, site)
    if settings.SEARCH_BACKEND is None:
        # return limited results if no SEARCH_BACKEND
        result = {
            "items": Items.objects.filter(title__like=f"%{keywords}%")[:10],
            "num_pages": 1,
        }
    else:
        result = Indexer.search(keywords, page=page_number, category=category, tag=tag)
    keys = []
    items = []
    urls = []
    for i in result.items:
        key = (
            i.isbn
            if hasattr(i, "isbn")
            else (i.imdb_code if hasattr(i, "imdb_code") else None)
        )
        if key is None:
            items.append(i)
        elif key not in keys:
            keys.append(key)
            items.append(i)
        for res in i.external_resources.all():
            urls.append(res.url)
    if request.path.endswith(".json/"):
        return JsonResponse(
            {
                "num_pages": result.num_pages,
                "items": list(map(lambda i: i.get_json(), items)),
            }
        )
    request.session["search_dedupe_urls"] = urls
    return render(
        request,
        "search_results.html",
        {
            "items": items,
            "pagination": PageLinksGenerator(
                PAGE_LINK_NUMBER, page_number, result.num_pages
            ),
            "categories": ["book", "movie", "music", "game"],
        },
    )
