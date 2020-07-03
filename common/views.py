from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from books.models import Book
from common.models import MarkStatusEnum
from common.utils import PageLinksGenerator
from users.models import Report, User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseBadRequest


# how many books have in each set at the home page
BOOKS_PER_SET = 5

# how many items are showed in one search result page
ITEMS_PER_PAGE = 20

# how many pages links in the pagination
PAGE_LINK_NUMBER = 7


@login_required
def home(request):
    if request.method == 'GET':

        do_book_marks = request.user.user_bookmarks.filter(status=MarkStatusEnum.DO)
        do_books_more = True if do_book_marks.count() > BOOKS_PER_SET else False

        wish_book_marks = request.user.user_bookmarks.filter(status=MarkStatusEnum.WISH)
        wish_books_more = True if wish_book_marks.count() > BOOKS_PER_SET else False
        
        collect_book_marks = request.user.user_bookmarks.filter(status=MarkStatusEnum.COLLECT)
        collect_books_more = True if collect_book_marks.count() > BOOKS_PER_SET else False

        reports = Report.objects.order_by('-submitted_time').filter(is_read=False)
        # reports = Report.objects.latest('submitted_time').filter(is_read=False)

        return render(
            request,
            'common/home.html',
            {
                'do_book_marks': do_book_marks[:BOOKS_PER_SET],
                'wish_book_marks': wish_book_marks[:BOOKS_PER_SET],
                'collect_book_marks': collect_book_marks[:BOOKS_PER_SET],
                'do_books_more': do_books_more,
                'wish_books_more': wish_books_more,
                'collect_books_more': collect_books_more,
                'reports': reports,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def search(request):
    if request.method == 'GET':
        # in the future when more modules are added...
        # category = request.GET.get("category")
        q = Q()
        keywords = request.GET.get("q", default='').split()
        query_args = []
        for keyword in keywords:
            q = q | Q(title__icontains=keyword)
            q = q | Q(subtitle__istartswith=keyword)
            q = q | Q(orig_title__icontains=keyword)
        query_args.append(q)
        queryset = Book.objects.filter(*query_args)

        paginator = Paginator(queryset, ITEMS_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        items = paginator.get_page(page_number)
        items.pagination = PageLinksGenerator(PAGE_LINK_NUMBER, page_number, paginator.num_pages)

        return render(
            request,
            "common/search_result.html",
            {
                "items": items,
            }
        )

    else:
        return HttpResponseBadRequest()