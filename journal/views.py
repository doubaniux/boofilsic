import logging
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError, HttpResponseNotFound
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from django.core.paginator import Paginator
from .models import *
from django.conf import settings
import re
from users.models import User
from django.http import HttpResponseRedirect
from django.db.models import Q
import time
from management.models import Announcement
from django.utils.baseconv import base62
from .forms import *
from mastodon.api import share_review


_logger = logging.getLogger(__name__)
PAGE_SIZE = 10


@login_required
def wish(request, item_uuid):
    if request.method == 'POST':
        item = get_object_or_404(Item, uid=base62.decode(item_uuid))
        if not item:
            return HttpResponseNotFound("item not found")
        request.user.shelf_manager.move_item(item, ShelfType.WISHLIST)
        return HttpResponse("✔️")
    else:
        return HttpResponseBadRequest("invalid request")


@login_required
def like(request, piece_uuid):
    if request.method == 'POST':
        piece = get_object_or_404(Collection, uid=base62.decode(piece_uuid))
        if not piece:
            return HttpResponseNotFound("piece not found")
        Like.user_like_piece(request.user, piece)
        return HttpResponse("✔️")
    else:
        return HttpResponseBadRequest("invalid request")


@login_required
def add_to_collection(request, item_uuid):
    item = get_object_or_404(Item, uid=base62.decode(item_uuid))
    if request.method == 'GET':
        collections = Collection.objects.filter(owner=request.user)
        return render(
            request,
            'add_to_collection.html',
            {
                'item': item,
                'collections': collections,
            }
        )
    else:
        cid = int(request.POST.get('collection_id', default=0))
        if not cid:
            cid = Collection.objects.create(owner=request.user, title=f'{request.user.username}的收藏单').id
        collection = Collection.objects.get(owner=request.user, id=cid)
        collection.append_item(item, metadata={'comment': request.POST.get('comment')})
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def go_relogin(request):
    return render(request, 'common/error.html', {
        'url': reverse("users:connect") + '?domain=' + request.user.mastodon_site,
        'msg': _("信息已保存，但是未能分享到联邦网络"),
        'secondary_msg': _("可能是你在联邦网络(Mastodon/Pleroma/...)的登录状态过期了，正在跳转到联邦网络重新登录😼")})


@login_required
def mark(request, item_uuid):
    item = get_object_or_404(Item, uid=base62.decode(item_uuid))
    mark = Mark(request.user, item)
    if request.method == 'GET':
        tags = TagManager.get_item_tags_by_user(item, request.user)
        shelf_types = [(n[1], n[2]) for n in iter(ShelfTypeNames) if n[0] == item.category]
        shelf_type = request.GET.get('shelf_type', mark.shelf_type)
        return render(request, 'mark.html', {
            'item': item,
            'mark': mark,
            'shelf_type': shelf_type,
            'tags': ','.join(tags),
            'shelf_types': shelf_types,
        })
    elif request.method == 'POST':
        if request.POST.get('delete', default=False):
            mark.delete()
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        else:
            visibility = int(request.POST.get('visibility', default=0))
            rating = request.POST.get('rating', default=0)
            rating = int(rating) if rating else None
            status = ShelfType(request.POST.get('status'))
            text = request.POST.get('text')
            tags = request.POST.get('tags')
            tags = tags.split(',') if tags else []
            share_to_mastodon = bool(request.POST.get('share_to_mastodon', default=False))
            TagManager.tag_item_by_user(item, request.user, tags, visibility)
            try:
                mark.update(status, text, rating, visibility, share_to_mastodon=share_to_mastodon)
            except Exception:
                go_relogin(request)
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def review_retrieve(request, review_uuid):
    piece = get_object_or_404(Review, uid=base62.decode(review_uuid))
    if not piece.is_visible_to(request.user):
        raise PermissionDenied()
    return render(request, 'review.html', {'review': piece})


@login_required
def review_edit(request, item_uuid, review_uuid=None):
    item = get_object_or_404(Item, uid=base62.decode(item_uuid))
    review = get_object_or_404(Review, uid=base62.decode(review_uuid)) if review_uuid else None
    if review and not review.is_editable_by(request.user):
        raise PermissionDenied()
    if request.method == 'GET':
        form = ReviewForm(instance=review) if review else ReviewForm(initial={'item': item.id})
        return render(request, 'review_edit.html', {'form': form, 'item': item})
    elif request.method == 'POST':
        form = ReviewForm(request.POST, instance=review) if review else ReviewForm(request.POST)
        if form.is_valid():
            if not review:
                form.instance.owner = request.user
            form.instance.edited_time = timezone.now()
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                form.instance.save = lambda **args: None
                form.instance.shared_link = None
                if not share_review(form.instance):
                    return go_relogin(request)
            return redirect(reverse("journal:review_retrieve", args=[form.instance.uuid]))
        else:
            return HttpResponseBadRequest(form.errors)
    else:
        return HttpResponseBadRequest()


@login_required
def review_delete(request, review_uuid):
    review = get_object_or_404(Review, uid=base62.decode(review_uuid))
    if not review.is_editable_by(request.user):
        raise PermissionDenied()
    if request.method == 'GET':
        review_form = ReviewForm(instance=review)
        return render(request, 'review_delete.html', {'form': review_form, 'review': review})
    elif request.method == 'POST':
        item = review.item
        review.delete()
        return redirect(item.url)
    else:
        return HttpResponseBadRequest()


def mark_list(request, shelf_type, item_category):
    pass


def review_list(request):
    pass


def collection_list(request):
    pass


@login_required
def liked_list(request):
    pass
