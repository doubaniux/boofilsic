from django.shortcuts import reverse, redirect, render, get_object_or_404
from django.http import HttpResponseBadRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import auth
from django.contrib.auth import authenticate
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from .models import User, Report, Preference
from .forms import ReportForm
from mastodon.api import *
from mastodon import mastodon_request_included
from common.config import *
from common.models import MarkStatusEnum
from common.utils import PageLinksGenerator
from management.models import Announcement
from books.models import *
from movies.models import *
from music.models import *
from games.models import *
from books.forms import BookMarkStatusTranslator
from movies.forms import MovieMarkStatusTranslator
from music.forms import MusicMarkStatusTranslator
from games.forms import GameMarkStatusTranslator
from mastodon.models import MastodonApplication
from mastodon.api import verify_account
from django.conf import settings
from urllib.parse import quote
import django_rq
from .account import *
from .tasks import *
from datetime import timedelta
from django.utils import timezone
import json
from django.contrib import messages
from books.models import BookMark, BookReview
from movies.models import MovieMark, MovieReview
from games.models import GameMark, GameReview
from music.models import AlbumMark, SongMark, AlbumReview, SongReview
from collection.models import Collection
from common.importers.goodreads import GoodreadsImporter
from common.importers.douban import DoubanImporter


@mastodon_request_included
@login_required
def preferences(request):
    if request.method == 'POST':
        request.user.preference.mastodon_publish_public = bool(request.POST.get('mastodon_publish_public'))
        request.user.preference.mastodon_append_tag = request.POST.get('mastodon_append_tag', '').strip()
        request.user.preference.save()
    return render(request, 'users/preferences.html')


@mastodon_request_included
@login_required
def data(request):
    return render(request, 'users/data.html', {
        'latest_task': request.user.user_synctasks.order_by("-id").first(),
        'import_status': request.user.preference.import_status,
        'export_status': request.user.preference.export_status
    })


@mastodon_request_included
@login_required
def export_reviews(request):
    if request.method != 'POST':
        return redirect(reverse("users:data"))
    return render(request, 'users/data.html')


@mastodon_request_included
@login_required
def export_marks(request):
    if request.method == 'POST':
        if not request.user.preference.export_status.get('marks_pending'):
            django_rq.get_queue('export').enqueue(export_marks_task, request.user)
            request.user.preference.export_status['marks_pending'] = True
            request.user.preference.save()
        messages.add_message(request, messages.INFO, _('导出已开始。'))
        return redirect(reverse("users:data"))
    else:
        try:
            with open(request.user.preference.export_status['marks_file'], 'rb') as fh:
                response = HttpResponse(fh.read(), content_type="application/vnd.ms-excel")
                response['Content-Disposition'] = 'attachment;filename="marks.xlsx"'
                return response
        except Exception:
            messages.add_message(request, messages.ERROR, _('导出文件已过期，请重新导出'))
            return redirect(reverse("users:data"))


@login_required
def sync_mastodon(request):
    if request.method == 'POST':
        django_rq.get_queue('mastodon').enqueue(refresh_mastodon_data_task, request.user)
        messages.add_message(request, messages.INFO, _('同步已开始。'))
    return redirect(reverse("users:data"))


@login_required
def reset_visibility(request):
    if request.method == 'POST':
        visibility = int(request.POST.get('visibility'))
        visibility = visibility if visibility >= 0 and visibility <= 2 else 0
        BookMark.objects.filter(owner=request.user).update(visibility=visibility)
        MovieMark.objects.filter(owner=request.user).update(visibility=visibility)
        GameMark.objects.filter(owner=request.user).update(visibility=visibility)
        AlbumMark.objects.filter(owner=request.user).update(visibility=visibility)
        SongMark.objects.filter(owner=request.user).update(visibility=visibility)
        messages.add_message(request, messages.INFO, _('已重置。'))
    return redirect(reverse("users:data"))


@login_required
def import_goodreads(request):
    if request.method == 'POST':
        raw_url = request.POST.get('url')
        if GoodreadsImporter.import_from_url(raw_url, request.user):
            messages.add_message(request, messages.INFO, _('链接已保存，等待后台导入。'))
        else:
            messages.add_message(request, messages.ERROR, _('无法识别链接。'))
    return redirect(reverse("users:data"))


@login_required
def import_douban(request):
    if request.method == 'POST':
        importer = DoubanImporter(request.user, request.POST.get('visibility'))
        if importer.import_from_file(request.FILES['file']):
            messages.add_message(request, messages.INFO, _('文件上传成功，等待后台导入。'))
        else:
            messages.add_message(request, messages.ERROR, _('无法识别文件。'))
    return redirect(reverse("users:data"))
