import re
import requests
from lxml import html
from datetime import datetime
# from common.scrapers.goodreads import GoodreadsScraper
from common.scraper import get_scraper_by_url
from books.models import Book, BookMark
from collection.models import Collection
from common.models import MarkStatusEnum
from django.conf import settings
from user_messages import api as msg
import django_rq
from django.utils.timezone import make_aware


re_list = r'^https://www.goodreads.com/list/show/\d+'
re_shelf = r'^https://www.goodreads.com/review/list/\d+[^?]*\?shelf=[^&]+'
re_profile = r'^https://www.goodreads.com/user/show/(\d+)'
gr_rating = {
    'did not like it': 2,
    'it was ok': 4,
    'liked it': 6,
    'really liked it': 8,
    'it was amazing': 10
}


class GoodreadsImporter:
    @classmethod
    def import_from_url(self, raw_url, user):
        match_list = re.match(re_list, raw_url)
        match_shelf = re.match(re_shelf, raw_url)
        match_profile = re.match(re_profile, raw_url)
        if match_profile or match_shelf or match_list:
            django_rq.get_queue('doufen').enqueue(self.import_from_url_task, raw_url, user)
            return True
        else:
            return False

    @classmethod
    def import_from_url_task(cls, url, user):
        match_list = re.match(re_list, url)
        match_shelf = re.match(re_shelf, url)
        match_profile = re.match(re_profile, url)
        total = 0
        if match_list or match_shelf:
            shelf = cls.parse_shelf(match_shelf[0], user) if match_shelf else cls.parse_list(match_list[0], user)
            if shelf['title'] and shelf['books']:
                collection = Collection.objects.create(title=shelf['title'],
                                                       description=shelf['description'] + '\n\nImported from [Goodreads](' + url + ')',
                                                       owner=user)
                for book in shelf['books']:
                    collection.append_item(book['book'], book['review'])
                    total += 1
                collection.save()
            msg.success(user, f'成功从Goodreads导入包含{total}本书的收藏单{shelf["title"]}。')
        elif match_profile:
            uid = match_profile[1]
            shelves = {
                MarkStatusEnum.WISH: f'https://www.goodreads.com/review/list/{uid}?shelf=to-read',
                MarkStatusEnum.DO: f'https://www.goodreads.com/review/list/{uid}?shelf=currently-reading',
                MarkStatusEnum.COLLECT: f'https://www.goodreads.com/review/list/{uid}?shelf=read',
            }
            for status in shelves:
                shelf_url = shelves.get(status)
                shelf = cls.parse_shelf(shelf_url, user)
                for book in shelf['books']:
                    params = {
                        'owner': user,
                        'rating': book['rating'],
                        'text': book['review'],
                        'status': status,
                        'visibility': 0,
                        'book': book['book'],
                    }
                    if book['last_updated']:
                        params['created_time'] = book['last_updated']
                        params['edited_time'] = book['last_updated']
                    try:
                        mark = BookMark.objects.create(**params)
                        mark.book.update_rating(None, mark.rating)
                    except Exception:
                        print(f'Skip mark for {book["book"]}')
                        pass
                    total += 1
            msg.success(user, f'成功从Goodreads用户主页导入{total}个标记。')

    @classmethod
    def parse_shelf(cls, url, user):  # return {'title': 'abc', books: [{'book': obj, 'rating': 10, 'review': 'txt'}, ...]}
        title = None
        books = []
        url_shelf = url + '&view=table'
        while url_shelf:
            print(f'Shelf loading {url_shelf}')
            r = requests.get(url_shelf, timeout=settings.SCRAPING_TIMEOUT)
            if r.status_code != 200:
                print(f'Shelf loading error {url_shelf}')
                break
            url_shelf = None
            content = html.fromstring(r.content.decode('utf-8'))
            title_elem = content.xpath("//span[@class='h1Shelf']/text()")
            if not title_elem:
                print(f'Shelf parsing error {url_shelf}')
                break
            title = title_elem[0].strip()
            print("Shelf title: " + title)
            for cell in content.xpath("//tbody[@id='booksBody']/tr"):
                url_book = 'https://www.goodreads.com' + \
                    cell.xpath(
                        ".//td[@class='field title']//a/@href")[0].strip()
                # has_review = cell.xpath(
                #     ".//td[@class='field actions']//a/text()")[0].strip() == 'view (with text)'
                rating_elem = cell.xpath(
                    ".//td[@class='field rating']//span/@title")
                rating = gr_rating.get(
                    rating_elem[0].strip()) if rating_elem else None
                url_review = 'https://www.goodreads.com' + \
                    cell.xpath(
                        ".//td[@class='field actions']//a/@href")[0].strip()
                review = ''
                last_updated = None
                try:
                    r2 = requests.get(
                        url_review, timeout=settings.SCRAPING_TIMEOUT)
                    if r2.status_code == 200:
                        c2 = html.fromstring(r2.content.decode('utf-8'))
                        review_elem = c2.xpath(
                            "//div[@itemprop='reviewBody']/text()")
                        review = '\n'.join(
                            p.strip() for p in review_elem) if review_elem else ''
                        date_elem = c2.xpath(
                            "//div[@class='readingTimeline__text']/text()")
                        for d in date_elem:
                            date_matched = re.search(r'(\w+)\s+(\d+),\s+(\d+)', d)
                            if date_matched:
                                last_updated = make_aware(datetime.strptime(date_matched[1] + ' ' + date_matched[2] + ' ' + date_matched[3], '%B %d %Y'))
                    else:
                        print(f"Error loading review{url_review}, ignored")
                    scraper = get_scraper_by_url(url_book)
                    url_book = scraper.get_effective_url(url_book)
                    book = Book.objects.filter(source_url=url_book).first()
                    if not book:
                        print("add new book " + url_book)
                        scraper.scrape(url_book)
                        form = scraper.save(request_user=user)
                        book = form.instance
                    books.append({
                        'url': url_book,
                        'book': book,
                        'rating': rating,
                        'review': review,
                        'last_updated': last_updated
                    })
                except Exception:
                    print("Error adding " + url_book)
                    pass  # likely just download error
            next_elem = content.xpath("//a[@class='next_page']/@href")
            url_shelf = ('https://www.goodreads.com' + next_elem[0].strip()) if next_elem else None
        return {'title': title, 'description': '', 'books': books}

    @classmethod
    def parse_list(cls, url, user):  # return {'title': 'abc', books: [{'book': obj, 'rating': 10, 'review': 'txt'}, ...]}
        title = None
        books = []
        url_shelf = url
        while url_shelf:
            print(f'List loading {url_shelf}')
            r = requests.get(url_shelf, timeout=settings.SCRAPING_TIMEOUT)
            if r.status_code != 200:
                print(f'List loading error {url_shelf}')
                break
            url_shelf = None
            content = html.fromstring(r.content.decode('utf-8'))
            title_elem = content.xpath('//h1[@class="gr-h1 gr-h1--serif"]/text()')
            if not title_elem:
                print(f'List parsing error {url_shelf}')
                break
            title = title_elem[0].strip()
            description = content.xpath('//div[@class="mediumText"]/text()')[0].strip()
            print("List title: " + title)
            for link in content.xpath('//a[@class="bookTitle"]/@href'):
                url_book = 'https://www.goodreads.com' + link
                try:
                    scraper = get_scraper_by_url(url_book)
                    url_book = scraper.get_effective_url(url_book)
                    book = Book.objects.filter(source_url=url_book).first()
                    if not book:
                        print("add new book " + url_book)
                        scraper.scrape(url_book)
                        form = scraper.save(request_user=user)
                        book = form.instance
                    books.append({
                        'url': url_book,
                        'book': book,
                        'review': '',
                    })
                except Exception:
                    print("Error adding " + url_book)
                    pass  # likely just download error
            next_elem = content.xpath("//a[@class='next_page']/@href")
            url_shelf = ('https://www.goodreads.com' + next_elem[0].strip()) if next_elem else None
        return {'title': title, 'description': description, 'books': books}
