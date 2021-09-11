from .forms import *
from .models import *
from common.models import SourceSiteEnum
from common.views import PAGE_LINK_NUMBER, jump_or_scrape
from common.utils import PageLinksGenerator
from mastodon.utils import rating_to_emoji
from mastodon.api import check_visibility, post_toot, TootVisibilityEnum
from mastodon import mastodon_request_included
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Count
from django.db import IntegrityError, transaction
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import HttpResponseBadRequest, HttpResponseServerError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404, redirect, reverse
import logging
from django.shortcuts import render


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
def create_song(request):
    if request.method == 'GET':
        form = SongForm()
        return render(
            request,
            'music/create_update_song.html',
            {
                'form': form,
                'title': _('添加音乐'),
                'submit_url': reverse("music:create_song"),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        if request.user.is_authenticated:
            # only local user can alter public data
            form = SongForm(request.POST, request.FILES)
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
                return redirect(reverse("music:retrieve_song", args=[form.instance.id]))
            else:
                return render(
                    request,
                    'music/create_update_song.html',
                    {
                        'form': form,
                        'title': _('添加音乐'),
                        'submit_url': reverse("music:create_song"),
                        # provided for frontend js
                        'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
                    }
                )
        else:
            return redirect(reverse("users:login"))
    else:
        return HttpResponseBadRequest()


@login_required
def update_song(request, id):
    if request.method == 'GET':
        song = get_object_or_404(Song, pk=id)
        form = SongForm(instance=song)
        page_title = _('修改音乐')
        return render(
            request,
            'music/create_update_song.html',
            {
                'form': form,
                'title': page_title,
                'submit_url': reverse("music:update_song", args=[song.id]),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        song = get_object_or_404(Song, pk=id)
        form = SongForm(request.POST, request.FILES, instance=song)
        page_title = _('修改音乐')
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
                'music/create_update_song.html',
                {
                    'form': form,
                    'title': page_title,
                    'submit_url': reverse("music:update_song", args=[song.id]),
                    # provided for frontend js
                    'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
                }
            )
        return redirect(reverse("music:retrieve_song", args=[form.instance.id]))

    else:
        return HttpResponseBadRequest()


@mastodon_request_included
# @login_required
def retrieve_song(request, id):
    if request.method == 'GET':
        song = get_object_or_404(Song, pk=id)
        mark = None
        mark_tags = None
        review = None

        def ms_to_readable(ms):
            if not ms:
                return
            x = ms // 1000
            seconds = x % 60
            x //= 60
            if x == 0:
                return f"{seconds}秒"
            minutes = x % 60
            x //= 60
            if x == 0:
                return f"{minutes}分{seconds}秒"
            hours = x % 24
            return f"{hours}时{minutes}分{seconds}秒"

        song.get_duration_display = ms_to_readable(song.duration)
            

        # retrieve tags
        song_tag_list = song.song_tags.values('content').annotate(
            tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER]

        # retrieve user mark and initialize mark form
        try:
            if request.user.is_authenticated:
                mark = SongMark.objects.get(owner=request.user, song=song)
        except ObjectDoesNotExist:
            mark = None
        if mark:
            mark_tags = mark.songmark_tags.all()
            mark.get_status_display = MusicMarkStatusTranslator(mark.status)
            mark_form = SongMarkForm(instance=mark, initial={
                'tags': mark_tags
            })
        else:
            mark_form = SongMarkForm(initial={
                'song': song,
                'tags': mark_tags
            })

        # retrieve user review
        try:
            if request.user.is_authenticated:
                review = SongReview.objects.get(
                    owner=request.user, song=song)
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
            mark_list = SongMark.get_available(
                song, request.user, request.session['oauth_token'])
            review_list = SongReview.get_available(
                song, request.user, request.session['oauth_token'])
            mark_list_more = True if len(mark_list) > MARK_NUMBER else False
            mark_list = mark_list[:MARK_NUMBER]
            for m in mark_list:
                m.get_status_display = MusicMarkStatusTranslator(m.status)
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
            'music/song_detail.html',
            {
                'song': song,
                'mark': mark,
                'review': review,
                'status_enum': MarkStatusEnum,
                'mark_form': mark_form,
                'mark_list': mark_list,
                'mark_list_more': mark_list_more,
                'review_list': review_list,
                'review_list_more': review_list_more,
                'song_tag_list': song_tag_list,
                'mark_tags': mark_tags,
            }
        )
    else:
        logger.warning('non-GET method at /song/<id>')
        return HttpResponseBadRequest()


@permission_required("music.delete_song")
@login_required
def delete_song(request, id):
    if request.method == 'GET':
        song = get_object_or_404(Song, pk=id)
        return render(
            request,
            'music/delete_song.html',
            {
                'song': song,
            }
        )
    elif request.method == 'POST':
        if request.user.is_staff:
            # only staff has right to delete
            song = get_object_or_404(Song, pk=id)
            song.delete()
            return redirect(reverse("common:home"))
        else:
            raise PermissionDenied()
    else:
        return HttpResponseBadRequest()


# user owned entites
###########################
@mastodon_request_included
@login_required
def create_update_song_mark(request):
    # check list:
    # clean rating if is wish
    # transaction on updating song rating
    # owner check(guarantee)
    if request.method == 'POST':
        pk = request.POST.get('id')
        old_rating = None
        old_tags = None
        if pk:
            mark = get_object_or_404(SongMark, pk=pk)
            if request.user != mark.owner:
                return HttpResponseBadRequest()
            old_rating = mark.rating
            old_tags = mark.songmark_tags.all()
            # update
            form = SongMarkForm(request.POST, instance=mark)
        else:
            # create
            form = SongMarkForm(request.POST)

        if form.is_valid():
            if form.instance.status == MarkStatusEnum.WISH.value:
                form.instance.rating = None
                form.cleaned_data['rating'] = None
            form.instance.owner = request.user
            form.instance.edited_time = timezone.now()
            song = form.instance.song

            try:
                with transaction.atomic():
                    # update song rating
                    song.update_rating(old_rating, form.instance.rating)
                    form.save()
                    # update tags
                    if old_tags:
                        for tag in old_tags:
                            tag.delete()
                    if form.cleaned_data['tags']:
                        for tag in form.cleaned_data['tags']:
                            SongTag.objects.create(
                                content=tag,
                                song=song,
                                mark=form.instance
                            )
            except IntegrityError as e:
                logger.error(e.__str__())
                return HttpResponseServerError("integrity error")

            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.UNLISTED
                url = "https://" + request.get_host() + reverse("music:retrieve_song",
                                                                args=[song.id])
                words = MusicMarkStatusTranslator(form.cleaned_data['status']) +\
                    f"《{song.title}》" + \
                    rating_to_emoji(form.cleaned_data['rating'])

                # tags = MASTODON_TAGS % {'category': '书', 'type': '标记'}
                tags = ''
                content = words + '\n' + url + '\n' + \
                    form.cleaned_data['text'] + '\n' + tags
                response = post_toot(request.user.mastodon_site, content, visibility,
                                     request.session['oauth_token'])
                if response.status_code != 200:
                    mastodon_logger.error(
                        f"CODE:{response.status_code} {response.text}")
                    return HttpResponseServerError("publishing mastodon status failed")
        else:
            return HttpResponseBadRequest("invalid form data")

        return redirect(reverse("music:retrieve_song", args=[form.instance.song.id]))
    else:
        return HttpResponseBadRequest("invalid method")


@mastodon_request_included
@login_required
def retrieve_song_mark_list(request, song_id):
    if request.method == 'GET':
        song = get_object_or_404(Song, pk=song_id)
        queryset = SongMark.get_available(
            song, request.user, request.session['oauth_token'])
        paginator = Paginator(queryset, MARK_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        marks.pagination = PageLinksGenerator(
            PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        for m in marks:
            m.get_status_display = MusicMarkStatusTranslator(m.status)
        return render(
            request,
            'music/song_mark_list.html',
            {
                'marks': marks,
                'song': song,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def delete_song_mark(request, id):
    if request.method == 'POST':
        mark = get_object_or_404(SongMark, pk=id)
        if request.user != mark.owner:
            return HttpResponseBadRequest()
        song_id = mark.song.id
        try:
            with transaction.atomic():
                # update song rating
                mark.song.update_rating(mark.rating, None)
                mark.delete()
        except IntegrityError as e:
            return HttpResponseServerError()
        return redirect(reverse("music:retrieve_song", args=[song_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def create_song_review(request, song_id):
    if request.method == 'GET':
        form = SongReviewForm(initial={'song': song_id})
        song = get_object_or_404(Song, pk=song_id)
        return render(
            request,
            'music/create_update_song_review.html',
            {
                'form': form,
                'title': _("添加评论"),
                'song': song,
                'submit_url': reverse("music:create_song_review", args=[song_id]),
            }
        )
    elif request.method == 'POST':
        form = SongReviewForm(request.POST)
        if form.is_valid():
            form.instance.owner = request.user
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.UNLISTED
                url = "https://" + request.get_host() + reverse("music:retrieve_song_review",
                                                                args=[form.instance.id])
                words = "发布了关于" + f"《{form.instance.song.title}》" + "的评论"
                # tags = MASTODON_TAGS % {'category': '书', 'type': '评论'}
                tags = ''
                content = words + '\n' + url + \
                    '\n' + form.cleaned_data['title'] + '\n' + tags
                response = post_toot(request.user.mastodon_site, content, visibility,
                                     request.session['oauth_token'])
                if response.status_code != 200:
                    mastodon_logger.error(
                        f"CODE:{response.status_code} {response.text}")
                    return HttpResponseServerError("publishing mastodon status failed")
            return redirect(reverse("music:retrieve_song_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def update_song_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(SongReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        form = SongReviewForm(instance=review)
        song = review.song
        return render(
            request,
            'music/create_update_song_review.html',
            {
                'form': form,
                'title': _("编辑评论"),
                'song': song,
                'submit_url': reverse("music:update_song_review", args=[review.id]),
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(SongReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        form = SongReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.instance.edited_time = timezone.now()
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.UNLISTED
                url = "https://" + request.get_host() + reverse("music:retrieve_song_review",
                                                                args=[form.instance.id])
                words = "发布了关于" + f"《{form.instance.song.title}》" + "的评论"
                # tags = MASTODON_TAGS % {'category': '书', 'type': '评论'}
                tags = ''
                content = words + '\n' + url + \
                    '\n' + form.cleaned_data['title'] + '\n' + tags
                response = post_toot(request.user.mastodon_site, content, visibility,
                                     request.session['oauth_token'])
                if response.status_code != 200:
                    mastodon_logger.error(
                        f"CODE:{response.status_code} {response.text}")
                    return HttpResponseServerError("publishing mastodon status failed")
            return redirect(reverse("music:retrieve_song_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@login_required
def delete_song_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(SongReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        review_form = SongReviewForm(instance=review)
        return render(
            request,
            'music/delete_song_review.html',
            {
                'form': review_form,
                'review': review,
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(SongReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        song_id = review.song.id
        review.delete()
        return redirect(reverse("music:retrieve_song", args=[song_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_song_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(SongReview, pk=id)
        if not check_visibility(review, request.session['oauth_token'], request.user):
            msg = _("你没有访问这个页面的权限😥")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                }
            )
        review_form = SongReviewForm(instance=review)
        song = review.song
        try:
            mark = SongMark.objects.get(owner=review.owner, song=song)
            mark.get_status_display = MusicMarkStatusTranslator(mark.status)
        except ObjectDoesNotExist:
            mark = None
        return render(
            request,
            'music/song_review_detail.html',
            {
                'form': review_form,
                'review': review,
                'song': song,
                'mark': mark,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_song_review_list(request, song_id):
    if request.method == 'GET':
        song = get_object_or_404(Song, pk=song_id)
        queryset = SongReview.get_available(
            song, request.user, request.session['oauth_token'])
        paginator = Paginator(queryset, REVIEW_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        reviews = paginator.get_page(page_number)
        reviews.pagination = PageLinksGenerator(
            PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        return render(
            request,
            'music/song_review_list.html',
            {
                'reviews': reviews,
                'song': song,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def scrape_song(request):
    if request.method == 'GET':
        keywords = request.GET.get('q')
        form = SongForm()
        return render(
            request,
            'music/scrape_song.html',
            {
                'q': keywords,
                'form': form,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def click_to_scrape_song(request):
    if request.method == "POST":
        url = request.POST.get("url")
        if url:
            return jump_or_scrape(request, url)
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@login_required
def create_album(request):
    if request.method == 'GET':
        form = AlbumForm()
        return render(
            request,
            'music/create_update_album.html',
            {
                'form': form,
                'title': _('添加音乐'),
                'submit_url': reverse("music:create_album"),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        if request.user.is_authenticated:
            # only local user can alter public data
            form = AlbumForm(request.POST, request.FILES)
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
                return redirect(reverse("music:retrieve_album", args=[form.instance.id]))
            else:
                return render(
                    request,
                    'music/create_update_album.html',
                    {
                        'form': form,
                        'title': _('添加音乐'),
                        'submit_url': reverse("music:create_album"),
                        # provided for frontend js
                        'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
                    }
                )
        else:
            return redirect(reverse("users:login"))
    else:
        return HttpResponseBadRequest()


@login_required
def update_album(request, id):
    if request.method == 'GET':
        album = get_object_or_404(Album, pk=id)
        form = AlbumForm(instance=album)
        page_title = _('修改音乐')
        return render(
            request,
            'music/create_update_album.html',
            {
                'form': form,
                'title': page_title,
                'submit_url': reverse("music:update_album", args=[album.id]),
                # provided for frontend js
                'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
            }
        )
    elif request.method == 'POST':
        album = get_object_or_404(Album, pk=id)
        form = AlbumForm(request.POST, request.FILES, instance=album)
        page_title = _('修改音乐')
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
                'music/create_update_album.html',
                {
                    'form': form,
                    'title': page_title,
                    'submit_url': reverse("music:update_album", args=[album.id]),
                    # provided for frontend js
                    'this_site_enum_value': SourceSiteEnum.IN_SITE.value,
                }
            )
        return redirect(reverse("music:retrieve_album", args=[form.instance.id]))

    else:
        return HttpResponseBadRequest()


@mastodon_request_included
# @login_required
def retrieve_album(request, id):
    if request.method == 'GET':
        album = get_object_or_404(Album, pk=id)
        mark = None
        mark_tags = None
        review = None

        def ms_to_readable(ms):
            if not ms:
                return
            x = ms // 1000
            seconds = x % 60
            x //= 60
            if x == 0:
                return f"{seconds}秒"
            minutes = x % 60
            x //= 60
            if x == 0:
                return f"{minutes}分{seconds}秒"
            hours = x % 24
            return f"{hours}时{minutes}分{seconds}秒"

        album.get_duration_display = ms_to_readable(album.duration)

        # retrieve tags
        album_tag_list = album.album_tags.values('content').annotate(
            tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER]

        # retrieve user mark and initialize mark form
        try:
            if request.user.is_authenticated:
                mark = AlbumMark.objects.get(owner=request.user, album=album)
        except ObjectDoesNotExist:
            mark = None
        if mark:
            mark_tags = mark.albummark_tags.all()
            mark.get_status_display = MusicMarkStatusTranslator(mark.status)
            mark_form = AlbumMarkForm(instance=mark, initial={
                'tags': mark_tags
            })
        else:
            mark_form = AlbumMarkForm(initial={
                'album': album,
                'tags': mark_tags
            })

        # retrieve user review
        try:
            if request.user.is_authenticated:
                review = AlbumReview.objects.get(
                    owner=request.user, album=album)
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
            mark_list = AlbumMark.get_available(
                album, request.user, request.session['oauth_token'])
            review_list = AlbumReview.get_available(
                album, request.user, request.session['oauth_token'])
            mark_list_more = True if len(mark_list) > MARK_NUMBER else False
            mark_list = mark_list[:MARK_NUMBER]
            for m in mark_list:
                m.get_status_display = MusicMarkStatusTranslator(m.status)
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
            'music/album_detail.html',
            {
                'album': album,
                'mark': mark,
                'review': review,
                'status_enum': MarkStatusEnum,
                'mark_form': mark_form,
                'mark_list': mark_list,
                'mark_list_more': mark_list_more,
                'review_list': review_list,
                'review_list_more': review_list_more,
                'album_tag_list': album_tag_list,
                'mark_tags': mark_tags,
            }
        )
    else:
        logger.warning('non-GET method at /album/<id>')
        return HttpResponseBadRequest()


@permission_required("music.delete_album")
@login_required
def delete_album(request, id):
    if request.method == 'GET':
        album = get_object_or_404(Album, pk=id)
        return render(
            request,
            'music/delete_album.html',
            {
                'album': album,
            }
        )
    elif request.method == 'POST':
        if request.user.is_staff:
            # only staff has right to delete
            album = get_object_or_404(Album, pk=id)
            album.delete()
            return redirect(reverse("common:home"))
        else:
            raise PermissionDenied()
    else:
        return HttpResponseBadRequest()


# user owned entites
###########################
@mastodon_request_included
@login_required
def create_update_album_mark(request):
    # check list:
    # clean rating if is wish
    # transaction on updating album rating
    # owner check(guarantee)
    if request.method == 'POST':
        pk = request.POST.get('id')
        old_rating = None
        old_tags = None
        if pk:
            mark = get_object_or_404(AlbumMark, pk=pk)
            if request.user != mark.owner:
                return HttpResponseBadRequest()
            old_rating = mark.rating
            old_tags = mark.albummark_tags.all()
            # update
            form = AlbumMarkForm(request.POST, instance=mark)
        else:
            # create
            form = AlbumMarkForm(request.POST)

        if form.is_valid():
            if form.instance.status == MarkStatusEnum.WISH.value:
                form.instance.rating = None
                form.cleaned_data['rating'] = None
            form.instance.owner = request.user
            form.instance.edited_time = timezone.now()
            album = form.instance.album

            try:
                with transaction.atomic():
                    # update album rating
                    album.update_rating(old_rating, form.instance.rating)
                    form.save()
                    # update tags
                    if old_tags:
                        for tag in old_tags:
                            tag.delete()
                    if form.cleaned_data['tags']:
                        for tag in form.cleaned_data['tags']:
                            AlbumTag.objects.create(
                                content=tag,
                                album=album,
                                mark=form.instance
                            )
            except IntegrityError as e:
                logger.error(e.__str__())
                return HttpResponseServerError("integrity error")

            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.UNLISTED
                url = "https://" + request.get_host() + reverse("music:retrieve_album",
                                                                args=[album.id])
                words = MusicMarkStatusTranslator(form.cleaned_data['status']) +\
                    f"《{album.title}》" + \
                    rating_to_emoji(form.cleaned_data['rating'])

                # tags = MASTODON_TAGS % {'category': '书', 'type': '标记'}
                tags = ''
                content = words + '\n' + url + '\n' + \
                    form.cleaned_data['text'] + '\n' + tags
                response = post_toot(request.user.mastodon_site, content, visibility,
                                     request.session['oauth_token'])
                if response.status_code != 200:
                    mastodon_logger.error(
                        f"CODE:{response.status_code} {response.text}")
                    return HttpResponseServerError("publishing mastodon status failed")
        else:
            return HttpResponseBadRequest("invalid form data")

        return redirect(reverse("music:retrieve_album", args=[form.instance.album.id]))
    else:
        return HttpResponseBadRequest("invalid method")


@mastodon_request_included
@login_required
def retrieve_album_mark_list(request, album_id):
    if request.method == 'GET':
        album = get_object_or_404(Album, pk=album_id)
        queryset = AlbumMark.get_available(
            album, request.user, request.session['oauth_token'])
        paginator = Paginator(queryset, MARK_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        marks.pagination = PageLinksGenerator(
            PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        for m in marks:
            m.get_status_display = MusicMarkStatusTranslator(m.status)
        return render(
            request,
            'music/album_mark_list.html',
            {
                'marks': marks,
                'album': album,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def delete_album_mark(request, id):
    if request.method == 'POST':
        mark = get_object_or_404(AlbumMark, pk=id)
        if request.user != mark.owner:
            return HttpResponseBadRequest()
        album_id = mark.album.id
        try:
            with transaction.atomic():
                # update album rating
                mark.album.update_rating(mark.rating, None)
                mark.delete()
        except IntegrityError as e:
            return HttpResponseServerError()
        return redirect(reverse("music:retrieve_album", args=[album_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def create_album_review(request, album_id):
    if request.method == 'GET':
        form = AlbumReviewForm(initial={'album': album_id})
        album = get_object_or_404(Album, pk=album_id)
        return render(
            request,
            'music/create_update_album_review.html',
            {
                'form': form,
                'title': _("添加评论"),
                'album': album,
                'submit_url': reverse("music:create_album_review", args=[album_id]),
            }
        )
    elif request.method == 'POST':
        form = AlbumReviewForm(request.POST)
        if form.is_valid():
            form.instance.owner = request.user
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.UNLISTED
                url = "https://" + request.get_host() + reverse("music:retrieve_album_review",
                                                                args=[form.instance.id])
                words = "发布了关于" + f"《{form.instance.album.title}》" + "的评论"
                # tags = MASTODON_TAGS % {'category': '书', 'type': '评论'}
                tags = ''
                content = words + '\n' + url + \
                    '\n' + form.cleaned_data['title'] + '\n' + tags
                response = post_toot(request.user.mastodon_site, content, visibility,
                                     request.session['oauth_token'])
                if response.status_code != 200:
                    mastodon_logger.error(
                        f"CODE:{response.status_code} {response.text}")
                    return HttpResponseServerError("publishing mastodon status failed")
            return redirect(reverse("music:retrieve_album_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def update_album_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(AlbumReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        form = AlbumReviewForm(instance=review)
        album = review.album
        return render(
            request,
            'music/create_update_album_review.html',
            {
                'form': form,
                'title': _("编辑评论"),
                'album': album,
                'submit_url': reverse("music:update_album_review", args=[review.id]),
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(AlbumReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        form = AlbumReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.instance.edited_time = timezone.now()
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.UNLISTED
                url = "https://" + request.get_host() + reverse("music:retrieve_album_review",
                                                                args=[form.instance.id])
                words = "发布了关于" + f"《{form.instance.album.title}》" + "的评论"
                # tags = MASTODON_TAGS % {'category': '书', 'type': '评论'}
                tags = ''
                content = words + '\n' + url + \
                    '\n' + form.cleaned_data['title'] + '\n' + tags
                response = post_toot(request.user.mastodon_site, content, visibility,
                                     request.session['oauth_token'])
                if response.status_code != 200:
                    mastodon_logger.error(
                        f"CODE:{response.status_code} {response.text}")
                    return HttpResponseServerError("publishing mastodon status failed")
            return redirect(reverse("music:retrieve_album_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@login_required
def delete_album_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(AlbumReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        review_form = AlbumReviewForm(instance=review)
        return render(
            request,
            'music/delete_album_review.html',
            {
                'form': review_form,
                'review': review,
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(AlbumReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        album_id = review.album.id
        review.delete()
        return redirect(reverse("music:retrieve_album", args=[album_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_album_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(AlbumReview, pk=id)
        if not check_visibility(review, request.session['oauth_token'], request.user):
            msg = _("你没有访问这个页面的权限😥")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                }
            )
        review_form = AlbumReviewForm(instance=review)
        album = review.album
        try:
            mark = AlbumMark.objects.get(owner=review.owner, album=album)
            mark.get_status_display = MusicMarkStatusTranslator(mark.status)
        except ObjectDoesNotExist:
            mark = None
        return render(
            request,
            'music/album_review_detail.html',
            {
                'form': review_form,
                'review': review,
                'album': album,
                'mark': mark,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_album_review_list(request, album_id):
    if request.method == 'GET':
        album = get_object_or_404(Album, pk=album_id)
        queryset = AlbumReview.get_available(
            album, request.user, request.session['oauth_token'])
        paginator = Paginator(queryset, REVIEW_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        reviews = paginator.get_page(page_number)
        reviews.pagination = PageLinksGenerator(
            PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        return render(
            request,
            'music/album_review_list.html',
            {
                'reviews': reviews,
                'album': album,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def scrape_album(request):
    if request.method == 'GET':
        keywords = request.GET.get('q')
        form = AlbumForm()
        return render(
            request,
            'music/scrape_album.html',
            {
                'q': keywords,
                'form': form,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def click_to_scrape_album(request):
    if request.method == "POST":
        url = request.POST.get("url")
        if url:
            return jump_or_scrape(request, url)
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()
