from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseBadRequest, HttpResponseServerError
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.core.paginator import Paginator
from common.mastodon import mastodon_request_included
from common.mastodon.api import check_visibility, post_toot, TootVisibilityEnum
from common.mastodon.utils import rating_to_emoji
from .models import *
from .forms import *
from .forms import BookMarkStatusTranslator


# how many marks showed on the detail page
MARK_NUMBER = 5
# how many marks at the mark page
MARK_PER_PAGE = 20
# how many reviews showed on the detail page
REVIEW_NUMBER = 5
# how many reviews at the mark page
REVIEW_PER_PAGE = 20


# public data
###########################
@login_required
def create(request):
    if request.method == 'GET':
        form = BookForm()
        return render(
            request,
            'books/create_update.html',
            {
                'form': form,
                'title': _('添加书籍'),
                'submit_url': reverse("books:create")
            }
        )
    elif request.method == 'POST':
        if request.user.is_authenticated:
            # only local user can alter public data
            form = BookForm(request.POST, request.FILES)
            if form.is_valid():
                form.instance.last_editor = request.user
                form.save()
                return redirect(reverse("books:retrieve", args=[form.instance.id]))
            else:
                return render(
                    request,
                    'books/create_update.html',
                    {
                        'form': form,
                        'title': _('添加书籍'),
                        'submit_url': reverse("books:create")
                    }
                )
        else:
            return redirect(reverse("users:login"))
    else:
        return HttpResponseBadRequest()


@login_required
def update(request, id):
    if request.method == 'GET':
        book = get_object_or_404(Book, pk=id)
        form = BookForm(instance=book)
        return render(
            request,
            'books/create_update.html',
            {
                'form': form,
                'title': _('修改书籍'),
                'submit_url': reverse("books:update", args=[book.id])
            }
        )
    elif request.method == 'POST':
        book = get_object_or_404(Book, pk=id)
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.instance.last_editor = request.user
            form.instance.edited_time = timezone.now()
            form.save()
        else:
            return render(
            request,
            'books/create_update.html',
            {
                'form': form,
                'title': _('修改书籍'),
                'submit_url': reverse("books:update", args=[book.id])
            }
        )
        return redirect(reverse("books:retrieve", args=[form.instance.id]))

    else:
        return HttpResponseBadRequest()    


@mastodon_request_included
@login_required
def retrieve(request, id):
    if request.method == 'GET':
        book = get_object_or_404(Book, pk=id)
        mark = None
        review = None
        try:
            mark = BookMark.objects.get(owner=request.user, book=book)
        except ObjectDoesNotExist:
            mark = None
        if mark:
            mark.get_status_display = BookMarkStatusTranslator(mark.status)
            mark_form = BookMarkForm(instance=mark)
        else:
            mark_form = BookMarkForm(initial={
                'book': book
            })

        try:
            review = BookReview.objects.get(owner=request.user, book=book)
        except ObjectDoesNotExist:
            review = None
        
        mark_list = BookMark.get_available(book, request.user, request.session['oauth_token'])
        mark_list_more = True if len(mark_list) > MARK_NUMBER else False
        mark_list = mark_list[:MARK_NUMBER]
        for m in mark_list:
            m.get_status_display = BookMarkStatusTranslator(m.status)
        review_list = BookReview.get_available(book, request.user, request.session['oauth_token'])
        review_list_more = True if len(review_list) > REVIEW_NUMBER else False
        review_list = review_list[:REVIEW_NUMBER]

        # def strip_html_tags(text):
        #     import re
        #     regex = re.compile('<.*?>')
        #     return re.sub(regex, '', text)

        # for r in review_list:
        #     r.content = strip_html_tags(r.content)

        return render(
            request,
            'books/detail.html',
            {
                'book': book,
                'mark': mark,
                'review': review,
                'status_enum': MarkStatusEnum,
                'mark_form': mark_form,
                'mark_list': mark_list,
                'mark_list_more': mark_list_more,
                'review_list': review_list,
                'review_list_more': review_list_more,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def delete(request, id):
    if request.method == 'GET':
        book = get_object_or_404(Book, pk=id)
        return render(
            request,
            'books/delete.html',
            {
                'book': book,
            }
        )
    elif request.method == 'POST':
        if request.user.is_staff:
            # only staff has right to delete
            book = get_object_or_404(Book, pk=id)
            book.delete()
            return redirect(reverse("common:search"))
        else:
            raise PermissionDenied()
    else:
        return HttpResponseBadRequest()    


# user owned entites
###########################
@mastodon_request_included
@login_required
def create_update_mark(request):
    # check list:
    # clean rating if is wish
    # transaction on updating book rating
    # owner check(guarantee)
    if request.method == 'POST':
        pk = request.POST.get('id')
        old_rating = None
        if pk:
            mark = get_object_or_404(BookMark, pk=pk)
            old_rating = mark.rating
            # update
            form = BookMarkForm(request.POST, instance=mark)
        else:
            # create
            form = BookMarkForm(request.POST)

        if form.is_valid():
            if form.instance.status == MarkStatusEnum.WISH.value:
                form.instance.rating = None
            form.instance.owner = request.user
            form.instance.edited_time = timezone.now()
            book = form.instance.book
            try:
                with transaction.atomic():
                    # update book rating
                    book.update_rating(old_rating, form.instance.rating)
                    form.save()
            except IntegrityError as e:
                return HttpResponseServerError()

            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.PUBLIC
                url = "https://" + request.get_host() + reverse("books:retrieve", args=[book.id])
                words = BookMarkStatusTranslator(int(form.cleaned_data['status'])) +\
                     f"《{book.title}》" + rating_to_emoji(form.cleaned_data['rating'])
                content = words + '\n' + url + '\n' + form.cleaned_data['text']
                post_toot(content, visibility, request.session['oauth_token'], local_only=True)
        else:
            return HttpResponseBadRequest()

        return redirect(reverse("books:retrieve", args=[form.instance.book.id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_mark_list(request, book_id):
    if request.method == 'GET':
        book = get_object_or_404(Book, pk=book_id)
        queryset = BookMark.get_available(book, request.user, request.session['oauth_token'])
        paginator = Paginator(queryset, MARK_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        marks = paginator.get_page(page_number)
        for m in marks:
            m.get_status_display = BookMarkStatusTranslator(m.status)
        return render(
            request,
            'books/mark_list.html',
            {
                'marks': marks,
                'book': book,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def delete_mark(request, id):
    if request.method == 'POST':
        mark = get_object_or_404(BookMark, pk=id)
        book_id = mark.book.id
        try:
            with transaction.atomic():
                # update book rating
                mark.book.update_rating(mark.rating, None)
                mark.delete()
        except IntegrityError as e:
            return HttpResponseServerError()
        return redirect(reverse("books:retrieve", args=[book_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def create_review(request, book_id):
    if request.method == 'GET':
        form = BookReviewForm(initial={'book': book_id})
        book = get_object_or_404(Book, pk=book_id)
        return render(
            request,
            'books/create_update_review.html',
            {
                'form': form,
                'title': _("添加评论"),
                'book': book,
                'submit_url': reverse("books:create_review", args=[book_id]),
            }
        )
    elif request.method == 'POST':
        form = BookReviewForm(request.POST)
        if form.is_valid():
            form.instance.owner = request.user
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.PUBLIC
                url = "https://" + request.get_host() + reverse("books:retrieve_review", args=[form.instance.id])
                words = "发布了关于" + f"《{form.instance.book.title}》" + "的评论"
                content = words + '\n' + url + '\n' + form.cleaned_data['title']
                post_toot(content, visibility, request.session['oauth_token'])
            return redirect(reverse("books:retrieve_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def update_review(request, id):
    # owner check
    # edited time
    if request.method == 'GET':
        review = get_object_or_404(BookReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()        
        form = BookReviewForm(instance=review)
        book = review.book
        return render(
            request,
            'books/create_update_review.html',
            {
                'form': form,
                'title': _("编辑评论"),
                'book': book,
                'submit_url': reverse("books:update_review", args=[review.id]),
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(BookReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        form = BookReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.instance.edited_time = timezone.now()
            form.save()
            if form.cleaned_data['share_to_mastodon']:
                if form.cleaned_data['is_private']:
                    visibility = TootVisibilityEnum.PRIVATE
                else:
                    visibility = TootVisibilityEnum.PUBLIC
                url = "https://" + request.get_host() + reverse("books:retrieve_review", args=[form.instance.id])
                words = "发布了关于" + f"《{form.instance.book.title}》" + "的评论"
                content = words + '\n' + url + '\n' + form.cleaned_data['title']
                post_toot(content, visibility, request.session['oauth_token'])
            return redirect(reverse("books:retrieve_review", args=[form.instance.id]))
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()    


@login_required
def delete_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(BookReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        review_form = BookReviewForm(instance=review)
        return render(
            request,
            'books/delete_review.html',
            {
                'form': review_form,
                'review': review,
            }
        )
    elif request.method == 'POST':
        review = get_object_or_404(BookReview, pk=id)
        if request.user != review.owner:
            return HttpResponseBadRequest()
        book_id = review.book.id
        review.delete()
        return redirect(reverse("books:retrieve", args=[book_id]))
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_review(request, id):
    if request.method == 'GET':
        review = get_object_or_404(BookReview, pk=id)
        if not check_visibility(review, request.session['oauth_token'], request.user):
            msg = _("你没有访问这个页面的权限😥")
            return render(
                request,
                'common/error.html',
                {
                    'msg': msg,
                }
            )
        review_form = BookReviewForm(instance=review)
        book = review.book
        try:
            mark = BookMark.objects.get(owner=review.owner, book=book)
            mark.get_status_display = BookMarkStatusTranslator(mark.status)
        except ObjectDoesNotExist:
            mark = None
        return render(
            request,
            'books/review_detail.html',
            {
                'form': review_form,
                'review': review,
                'book': book,
                'mark': mark,
            }
        )
    else:
        return HttpResponseBadRequest()


@mastodon_request_included
@login_required
def retrieve_review_list(request, book_id):
    if request.method == 'GET':
        book = get_object_or_404(Book, pk=book_id)
        queryset = BookReview.get_available(book, request.user, request.session['oauth_token'])
        paginator = Paginator(queryset, REVIEW_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        reviews = paginator.get_page(page_number)
        return render(
            request,
            'books/review_list.html',
            {
                'reviews': reviews,
                'book': book,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def scrape(request):
    if request.method == 'GET':
        keywords = request.GET.get('q')
        form = BookForm()
        return render(
            request,
            'books/scrape.html',
            {
                'q': keywords,
                'form': form,
            }
        )
    else:
        return HttpResponseBadRequest()