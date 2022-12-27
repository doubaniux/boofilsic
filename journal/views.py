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
from users.views import render_user_blocked, render_user_not_found


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


def render_relogin(request):
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
                return render_relogin(request)
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
                    return render_relogin(request)
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


def render_list_not_fount(request):
    msg = _("相关列表不存在")
    return render(
        request,
        'common/error.html',
        {
            'msg': msg,
        }
    )


def _render_list(request, user_name, type, shelf_type=None, item_category=None, tag_title=None):
    user = User.get(user_name)
    if user is None:
        return render_user_not_found(request)
    if user != request.user and (request.user.is_blocked_by(user) or request.user.is_blocking(user)):
        return render_user_blocked(request)
    if type == 'mark':
        shelf = user.shelf_manager.get_shelf(item_category, shelf_type)
        queryset = ShelfMember.objects.filter(owner=user, parent=shelf)
    elif type == 'tagmember':
        tag = Tag.objects.filter(owner=user, title=tag_title).first()
        if not tag:
            return render_list_not_fount(request)
        if tag.visibility != 0 and user != request.user:
            return render_list_not_fount(request)
        queryset = TagMember.objects.filter(parent=tag)
    elif type == 'review':
        queryset = Review.objects.filter(owner=user)
        queryset = queryset.filter(query_item_category(item_category))
    else:
        return HttpResponseBadRequest()
    if user != request.user:
        if request.user.is_following(user):
            queryset = queryset.filter(visibility__ne=2)
        else:
            queryset = queryset.filter(visibility=0)
    paginator = Paginator(queryset, PAGE_SIZE)
    page_number = request.GET.get('page', default=1)
    members = paginator.get_page(page_number)
    return render(request, f'user_{type}_list.html', {
        'user': user,
        'members': members,
    })


@login_required
def user_mark_list(request, user_name, shelf_type, item_category):
    return _render_list(request, user_name, 'mark', shelf_type=shelf_type, item_category=item_category)


@login_required
def user_tag_member_list(request, user_name, tag_title):
    return _render_list(request, user_name, 'tagmember', tag_title=tag_title)


@login_required
def user_review_list(request, user_name, item_category):
    return _render_list(request, user_name, 'review', item_category=item_category)


@login_required
def user_tag_list(request, user_name):
    user = User.get(user_name)
    if user is None:
        return render_user_not_found(request)
    if user != request.user and (request.user.is_blocked_by(user) or request.user.is_blocking(user)):
        return render_user_blocked(request)
    tags = Tag.objects.filter(owner=user)
    tags = user.tag_set.all()
    if user != request.user:
        tags = tags.filter(visibility=0)
    tags = tags.values('title').annotate(total=Count('members')).order_by('-total')
    return render(request, f'user_tag_list.html', {
        'user': user,
        'tags': tags,
    })


@login_required
def user_collection_list(request, user_name):
    user = User.get(user_name)
    if user is None:
        return render_user_not_found(request)
    if user != request.user and (request.user.is_blocked_by(user) or request.user.is_blocking(user)):
        return render_user_blocked(request)
    collections = Tag.objects.filter(owner=user)
    if user != request.user:
        if request.user.is_following(user):
            collections = collections.filter(visibility__ne=2)
        else:
            collections = collections.filter(visibility=0)
    return render(request, f'user_collection_list.html', {
        'user': user,
        'collections': collections,
    })


@login_required
def user_liked_collection_list(request, user_name):
    user = User.get(user_name)
    if user is None:
        return render_user_not_found(request)
    if user != request.user and (request.user.is_blocked_by(user) or request.user.is_blocking(user)):
        return render_user_blocked(request)
    collections = Collection.objects.filter(likes__owner=user)
    if user != request.user:
        collections = collections.filter(query_visible(request.user))
    return render(request, f'user_collection_list.html', {
        'user': user,
        'collections': collections,
    })
