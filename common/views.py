import operator
from difflib import SequenceMatcher
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from books.models import Book
from movies.models import Movie
from common.models import MarkStatusEnum
from common.utils import PageLinksGenerator
from users.models import Report, User
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponseBadRequest


# how many books have in each set at the home page
BOOKS_PER_SET = 5

# how many movies have in each set at the home page
MOVIES_PER_SET = 5

# how many items are showed in one search result page
ITEMS_PER_PAGE = 20

# how many pages links in the pagination
PAGE_LINK_NUMBER = 7

# max tags on list page
TAG_NUMBER_ON_LIST = 5


@login_required
def home(request):
    if request.method == 'GET':

        do_book_marks = request.user.user_bookmarks.filter(
            status=MarkStatusEnum.DO).order_by("-edited_time")
        do_books_more = True if do_book_marks.count() > BOOKS_PER_SET else False

        wish_book_marks = request.user.user_bookmarks.filter(
            status=MarkStatusEnum.WISH).order_by("-edited_time")
        wish_books_more = True if wish_book_marks.count() > BOOKS_PER_SET else False
        
        collect_book_marks = request.user.user_bookmarks.filter(
            status=MarkStatusEnum.COLLECT).order_by("-edited_time")
        collect_books_more = True if collect_book_marks.count() > BOOKS_PER_SET else False


        do_movie_marks = request.user.user_moviemarks.filter(
            status=MarkStatusEnum.DO).order_by("-edited_time")
        do_movies_more = True if do_movie_marks.count() > MOVIES_PER_SET else False

        wish_movie_marks = request.user.user_moviemarks.filter(
            status=MarkStatusEnum.WISH).order_by("-edited_time")
        wish_movies_more = True if wish_movie_marks.count() > MOVIES_PER_SET else False
        
        collect_movie_marks = request.user.user_moviemarks.filter(
            status=MarkStatusEnum.COLLECT).order_by("-edited_time")
        collect_movies_more = True if collect_movie_marks.count() > MOVIES_PER_SET else False

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
                'do_movie_marks': do_movie_marks[:MOVIES_PER_SET],
                'wish_movie_marks': wish_movie_marks[:MOVIES_PER_SET],
                'collect_movie_marks': collect_movie_marks[:MOVIES_PER_SET],
                'do_movies_more': do_movies_more,
                'wish_movies_more': wish_movies_more,
                'collect_movies_more': collect_movies_more,
                'reports': reports,
            }
        )
    else:
        return HttpResponseBadRequest()


@login_required
def search(request):
    if request.method == 'GET':

        if not request.GET.get("q"):
            return HttpResponseBadRequest()

        # category, book/movie/record etc
        category = request.GET.get("c", default='').strip().lower()

        def book_param_handler():
            q = Q()
            query_args = []
            # keywords
            keywords = request.GET.get("q", default='').strip()

            for keyword in [keywords]:
                q = q | Q(title__icontains=keyword)
                q = q | Q(subtitle__icontains=keyword)
                q = q | Q(orig_title__icontains=keyword)

            # tag
            tag = request.GET.get("tag", default='')
            if tag:
                q = q & Q(book_tags__content__iexact=tag)

            query_args.append(q)
            queryset = Book.objects.filter(*query_args).distinct()

            def calculate_similarity(book):
                similarity, n = 0, 0
                for keyword in keywords:
                    similarity += 1/2 * SequenceMatcher(None, keyword, book.title).quick_ratio() 
                    + 1/3 * SequenceMatcher(None, keyword, book.orig_title).quick_ratio()
                    + 1/6 * SequenceMatcher(None, keyword, book.subtitle).quick_ratio()
                    n += 1
                book.similarity = similarity / n
                return book.similarity
            if len(queryset) > 0:
                ordered_queryset = sorted(queryset, key=calculate_similarity, reverse=True)
            else:
                ordered_queryset = queryset
            return ordered_queryset
            
        def movie_param_handler():
            q = Q()
            query_args = []
            # keywords
            keywords = request.GET.get("q", default='').strip()

            for keyword in [keywords]:
                q = q | Q(title__icontains=keyword)
                q = q | Q(other_title__icontains=keyword)
                q = q | Q(orig_title__icontains=keyword)

            # tag
            tag = request.GET.get("tag", default='')
            if tag:
                q = q & Q(movie_tags__content__iexact=tag)

            query_args.append(q)
            queryset = Movie.objects.filter(*query_args).distinct()

            def calculate_similarity(movie):
                similarity, n = 0, 0
                for keyword in keywords:
                    similarity += 1/2 * SequenceMatcher(None, keyword, movie.title).quick_ratio()
                    + 1/4 * SequenceMatcher(None, keyword, movie.orig_title).quick_ratio()
                    + 1/4 * SequenceMatcher(None, keyword, movie.other_title).quick_ratio()
                    n += 1
                movie.similarity = similarity / n
                return movie.similarity
            if len(queryset) > 0:
                ordered_queryset = sorted(queryset, key=calculate_similarity, reverse=True)
            else:
                ordered_queryset = queryset
            return ordered_queryset

        def all_param_handler():
            book_queryset = book_param_handler()
            movie_queryset = movie_param_handler()
            ordered_queryset = sorted(
                book_queryset + movie_queryset, 
                key=operator.attrgetter('similarity'), 
                reverse=True
            )
            return ordered_queryset

        param_handler = {
            'book': book_param_handler,
            'movie': movie_param_handler,
            'all': all_param_handler,
            '': all_param_handler
        }

        try:
            queryset = param_handler[category]()
        except KeyError as e:
            queryset = param_handler['all']()
        paginator = Paginator(queryset, ITEMS_PER_PAGE)
        page_number = request.GET.get('page', default=1)
        items = paginator.get_page(page_number)
        items.pagination = PageLinksGenerator(PAGE_LINK_NUMBER, page_number, paginator.num_pages)
        for item in items:
            item.tag_list = item.get_tags_manager().values('content').annotate(
                tag_frequency=Count('content')).order_by('-tag_frequency')[:TAG_NUMBER_ON_LIST]

        return render(
            request,
            "common/search_result.html",
            {
                "items": items,
            }
        )

    else:
        return HttpResponseBadRequest()
