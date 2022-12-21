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
from .models import *
from django.conf import settings
import re
from users.models import User
from django.http import HttpResponseRedirect
from django.db.models import Q
import time
from management.models import Announcement


PAGE_SIZE = 10


@login_required
def feed(request):
    if request.method != 'GET':
        return
    user = request.user
    unread = Announcement.objects.filter(pk__gt=user.read_announcement_index).order_by('-pk')
    if unread:
        user.read_announcement_index = Announcement.objects.latest('pk').pk
        user.save(update_fields=['read_announcement_index'])
    return render(
        request,
        'feed.html',
        {
            'tags': user.tag_manager.all_tags[:10],
            'unread_announcements': unread,
        }
    )


@login_required
def data(request):
    if request.method != 'GET':
        return
    return render(
        request,
        'feed_data.html',
        {
            'activities': ActivityManager(request.user).get_timeline(before_time=request.GET.get('last'))[:PAGE_SIZE],
        }
    )
