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
