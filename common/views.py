import operator
import logging
from difflib import SequenceMatcher
from urllib.parse import urlparse
from django.shortcuts import render, redirect, reverse
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db.models import Q, Count
from django.http import HttpResponseBadRequest
from books.models import Book
from movies.models import Movie
from games.models import Game
from music.models import Album, Song, AlbumMark, SongMark
from users.models import Report, User, Preference
from mastodon.decorators import mastodon_request_included
from users.views import home as user_home
from common.models import MarkStatusEnum
from common.utils import PageLinksGenerator
from common.scraper import scraper_registry
from common.config import *
from common.searcher import ExternalSources
from management.models import Announcement
from django.conf import settings
from common.index import Indexer


logger = logging.getLogger(__name__)


@login_required
def home(request):
    return user_home(request, request.user.id)



@login_required
def search(request):
    category = request.GET.get("c", default='all').strip().lower()
    if category == 'all':
        category = None
    keywords = request.GET.get("q", default='').strip()
    tag = request.GET.get("tag", default='').strip()
    page_number = int(request.GET.get('page', default=1))
    if not (keywords or tag):
        return render(
            request,
            "common/search_result.html",
            {
                "items": None,
            }
        )
    url_validator = URLValidator()
    try:
        url_validator(keywords)
        # validation success
        return jump_or_scrape(request, keywords)
    except ValidationError as e:
        pass
    #
    result = Indexer.search(keywords, page=page_number, category=category, tag=tag)
    for item in result.items:
        item.tag_list = item.all_tag_list[:TAG_NUMBER_ON_LIST]
    return render(
        request,
        "common/search_result.html",
        {
            "items": result.items,
            "pagination": PageLinksGenerator(PAGE_LINK_NUMBER, page_number, result.num_pages),
            "external_items": ExternalSources.search(category, keywords, page_number),
            "categories": ['book', 'movie', 'music', 'game'],
        }
    )


@login_required
def search2(request):
    if request.method == 'GET':

        # test if input serach string is empty or not excluding param ?c=
        empty_querystring_criteria = {k: v for k, v in request.GET.items() if k != 'c'}
        if not len(empty_querystring_criteria):
            return HttpResponseBadRequest()

        # test if user input an URL, if so jump to URL handling function
        url_validator = URLValidator()
        input_string = request.GET.get('q', default='').strip()
        try:
            url_validator(input_string)
            # validation success
            return jump_or_scrape(request, input_string)
        except ValidationError as e:
            pass

        # category, book/movie/music etc
        category = request.GET.get("c", default='').strip().lower()
        # keywords, seperated by blank space
        # it is better not to split the keywords
        keywords = request.GET.get("q", default='').strip()
        keywords = [keywords] if keywords else ''
        # tag, when tag is provided there should be no keywords , for now
        tag = request.GET.get("tag", default='')

        # white space string, empty query
        if not (keywords or tag):
            return render(
                request,
                "common/search_result.html",
                {
                    "items": None,
                }
            )

        def book_param_handler(**kwargs):
            # keywords
            keywords = kwargs.get('keywords')
            # tag
            tag = kwargs.get('tag')

            query_args = []
            q = Q()

            for keyword in keywords:
                q = q | Q(title__icontains=keyword)
                q = q | Q(subtitle__icontains=keyword)
                q = q | Q(orig_title__icontains=keyword)
            if tag:
                q = q & Q(book_tags__content__iexact=tag)

            query_args.append(q)
            queryset = Book.objects.filter(*query_args).distinct()

            def calculate_similarity(book):
                if keywords:
                    # search by keywords
                    similarity, n = 0, 0
                    for keyword in keywords:
                        similarity += 1/2 * SequenceMatcher(None, keyword, book.title).quick_ratio() 
                        + 1/3 * SequenceMatcher(None, keyword, book.orig_title).quick_ratio()
                        + 1/6 * SequenceMatcher(None, keyword, book.subtitle).quick_ratio()
                        n += 1
                    book.similarity = similarity / n

                elif tag:
                    # search by single tag
                    book.similarity = 0 if book.rating_number is None else book.rating_number
                else:
                    book.similarity = 0
                return book.similarity
            if len(queryset) > 0:
                ordered_queryset = sorted(queryset, key=calculate_similarity, reverse=True)
            else:
                ordered_queryset = list(queryset)
            return ordered_queryset
            
        def movie_param_handler(**kwargs):
            # keywords
            keywords = kwargs.get('keywords')
            # tag
            tag = kwargs.get('tag')

            query_args = []
            q = Q()

            for keyword in keywords:
                q = q | Q(title__icontains=keyword)
                q = q | Q(other_title__icontains=keyword)
                q = q | Q(orig_title__icontains=keyword)
            if tag:
                q = q & Q(movie_tags__content__iexact=tag)

            query_args.append(q)
            queryset = Movie.objects.filter(*query_args).distinct()

            def calculate_similarity(movie):
                if keywords:
                    # search by name
                    similarity, n = 0, 0
                    for keyword in keywords:
                        similarity += 1/2 * SequenceMatcher(None, keyword, movie.title).quick_ratio()
                        + 1/4 * SequenceMatcher(None, keyword, movie.orig_title).quick_ratio()
                        + 1/4 * SequenceMatcher(None, keyword, movie.other_title).quick_ratio()
                        n += 1
                    movie.similarity = similarity / n
                elif tag:
                    # search by single tag
                    movie.similarity = 0 if movie.rating_number is None else movie.rating_number
                else:
                    movie.similarity = 0
                return movie.similarity
            if len(queryset) > 0:
                ordered_queryset = sorted(queryset, key=calculate_similarity, reverse=True)
            else:
                ordered_queryset = list(queryset)
            return ordered_queryset

        def game_param_handler(**kwargs):
            # keywords
            keywords = kwargs.get('keywords')
            # tag
            tag = kwargs.get('tag')

            query_args = []
            q = Q()

            for keyword in keywords:
                q = q | Q(title__icontains=keyword)
                q = q | Q(other_title__icontains=keyword)
                q = q | Q(developer__icontains=keyword)
                q = q | Q(publisher__icontains=keyword)
            if tag:
                q = q & Q(game_tags__content__iexact=tag)

            query_args.append(q)
            queryset = Game.objects.filter(*query_args).distinct()

            def calculate_similarity(game):
                if keywords:
                    # search by name
                    developer_dump = ' '.join(game.developer)
                    publisher_dump = ' '.join(game.publisher)
                    similarity, n = 0, 0
                    for keyword in keywords:
                        similarity += 1/2 * SequenceMatcher(None, keyword, game.title).quick_ratio()
                        + 1/4 * SequenceMatcher(None, keyword, game.other_title).quick_ratio()
                        + 1/16 * SequenceMatcher(None, keyword, developer_dump).quick_ratio()
                        + 1/16 * SequenceMatcher(None, keyword, publisher_dump).quick_ratio()
                        n += 1
                    game.similarity = similarity / n
                elif tag:
                    # search by single tag
                    game.similarity = 0 if game.rating_number is None else game.rating_number
                else:
                    game.similarity = 0
                return game.similarity
            if len(queryset) > 0:
                ordered_queryset = sorted(queryset, key=calculate_similarity, reverse=True)
            else:
                ordered_queryset = list(queryset)
            return ordered_queryset

        def music_param_handler(**kwargs):
            # keywords
            keywords = kwargs.get('keywords')
            # tag
            tag = kwargs.get('tag')

            query_args = []
            q = Q()

            # search albums
            for keyword in keywords:
                q = q | Q(title__icontains=keyword)
                q = q | Q(artist__icontains=keyword)
            if tag:
                q = q & Q(album_tags__content__iexact=tag)

            query_args.append(q)
            album_queryset = Album.objects.filter(*query_args).distinct()

            # extra query args for songs
            q = Q()
            for keyword in keywords:
                q = q | Q(album__title__icontains=keyword)
                q = q | Q(title__icontains=keyword)
                q = q | Q(artist__icontains=keyword)
            if tag:
                q = q & Q(song_tags__content__iexact=tag)
            query_args.clear()
            query_args.append(q)
            song_queryset = Song.objects.filter(*query_args).distinct()
            queryset = list(album_queryset) + list(song_queryset)

            def calculate_similarity(music):
                if keywords:
                    # search by name
                    similarity, n = 0, 0
                    artist_dump = ' '.join(music.artist)
                    for keyword in keywords:
                        if music.__class__ == Album:
                            similarity += 1/2 * SequenceMatcher(None, keyword, music.title).quick_ratio() \
                                + 1/2 * SequenceMatcher(None, keyword, artist_dump).quick_ratio()
                        elif music.__class__ == Song:
                            similarity += 1/2 * SequenceMatcher(None, keyword, music.title).quick_ratio() \
                                + 1/6 * SequenceMatcher(None, keyword, artist_dump).quick_ratio() \
                                + 1/6 * (SequenceMatcher(None, keyword, music.album.title).quick_ratio() if music.album is not None else 0)
                        n += 1
                    music.similarity = similarity / n
                elif tag:
                    # search by single tag
                    music.similarity = 0 if music.rating_number is None else music.rating_number
                else:
                    music.similarity = 0
                return music.similarity
            if len(queryset) > 0:
                ordered_queryset = sorted(queryset, key=calculate_similarity, reverse=True)
            else:
                ordered_queryset = list(queryset)
            return ordered_queryset

        def all_param_handler(**kwargs):
            book_queryset = book_param_handler(**kwargs)
            movie_queryset = movie_param_handler(**kwargs)
            music_queryset = music_param_handler(**kwargs)
            game_queryset = game_param_handler(**kwargs)
            ordered_queryset = sorted(
                book_queryset + movie_queryset + music_queryset + game_queryset, 
                key=operator.attrgetter('similarity'), 
                reverse=True
            )
            return ordered_queryset

        param_handler = {
            'book': book_param_handler,
            'movie': movie_param_handler,
            'music': music_param_handler,
            'game': game_param_handler,
            'all': all_param_handler,
            '': all_param_handler
        }

        categories = [k for k in param_handler.keys() if not k in ['all', '']]

        try:
            queryset = param_handler[category](
                keywords=keywords,
                tag=tag
            )
        except KeyError as e:
            queryset = param_handler['all'](
                keywords=keywords,
                tag=tag
            )
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
                "external_items": ExternalSources.search(category, input_string, page_number),
                "categories": categories,
            }
        )

    else:
        return HttpResponseBadRequest()


@login_required
@mastodon_request_included
def jump_or_scrape(request, url):
    """
    1. match url to registered scrapers
    2. try to find the url in the db, if exits then jump, else scrape and jump
    """

    # redirect to this site
    this_site = request.get_host()
    if this_site in url:
        return redirect(url)

    # match url to registerd sites
    matched_host = None
    for host in scraper_registry:
        if host in url:
            matched_host = host
            break

    if matched_host is None:
        # invalid url
        return render(request, 'common/error.html', {'msg': _("链接非法，查询失败")})
    else:
        scraper = scraper_registry[matched_host]
        try:
            # raise ObjectDoesNotExist
            effective_url = scraper.get_effective_url(url)
            entity = scraper.data_class.objects.get(source_url=effective_url)
            # if exists then jump to detail page
            return redirect(entity)
        except ObjectDoesNotExist:
            # scrape if not exists
            try:
                scraper.scrape(url)
                form = scraper.save(request_user=request.user)
            except Exception as e:
                logger.error(f"Scrape Failed URL: {url}\n{e}")
                if settings.DEBUG:
                    logger.error("Expections during saving scraped data:", exc_info=e)
                return render(request, 'common/error.html', {'msg': _("爬取数据失败😫")})
            return redirect(form.instance)

