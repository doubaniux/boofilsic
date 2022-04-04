import re
import requests
from lxml import html
# from common.scrapers.goodreads import GoodreadsScraper
from common.scraper import get_scraper_by_url
from books.models import Book, BookMark
from collection.models import Collection
from common.models import MarkStatusEnum
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from user_messages import api as msg
import django_rq


re_shelf = r'^https://www.goodreads.com/review/list/\d+[^?]*\?shelf=[^&]+'
re_profile = r'^https://www.goodreads.com/user/show/(\d+)'
gr_rating = {
    'did not like it': 2,
    'it was ok': 4,
    'liked it': 6,
    'really liked it': 8,
    'it was amazing': 10
}
gr_status = {
}


class GoodreadsImporter:
    @classmethod
    def import_from_url(self, raw_url, user):
        match_shelf = re.match(re_shelf, raw_url)
        match_profile = re.match(re_profile, raw_url)
        if match_profile or match_shelf:
            django_rq.get_queue('doufen').enqueue(self.import_from_url_task, raw_url, user)
            return True
        else:
            return False

    @classmethod
    def import_from_url_task(cls, url, user):
        match_shelf = re.match(re_shelf, url)
        match_profile = re.match(re_profile, url)
        total = 0
        if match_shelf:
            shelf = cls.parse_shelf(match_shelf[0], user)
            if shelf['title'] and shelf['books']:
                collection = Collection.objects.create(title=shelf['title'],
                                                       description='Imported from [Goodreads](' + url + ')',
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
                        # 'created_time': data.time,
                        # 'edited_time': data.time,
                        'rating': book['rating'],
                        'text': book['review'],
                        'status': status,
                        'visibility': 0,
                        'book': book['book'],
                    }
                    try:
                        mark = BookMark.objects.create(**params)
                        mark.book.update_rating(None, mark.rating)
                    except Exception as e:
                        # print(e)
                        pass
                    total += 1
            msg.success(user, f'成功从Goodreads导入{total}个标记。')

    @classmethod
    def parse_shelf(cls, url, user):  # return {'title': 'abc', books: [{'book': obj, 'rating': 10, 'review': 'txt'}, ...]}
        books = []
        url_shelf = url + '&view=table'
        while url_shelf:
            print(url_shelf)
            r = requests.get(url_shelf, timeout=settings.SCRAPING_TIMEOUT)
            url_shelf = None
            if r.status_code == 200:
                content = html.fromstring(r.content.decode('utf-8'))
                try:
                    title = content.xpath(
                        "//span[@class='h1Shelf']/text()")[0].strip()
                except IndexError:
                    raise ValueError("given url contains no book info")
                print(title)
                for cell in content.xpath("//tbody[@id='booksBody']/tr"):
                    url_book = 'https://www.goodreads.com' + \
                        cell.xpath(
                            ".//td[@class='field title']//a/@href")[0].strip()
                    action = cell.xpath(
                        ".//td[@class='field actions']//a/text()")[0].strip()
                    rating_elem = cell.xpath(
                        ".//td[@class='field rating']//span/@title")
                    rating = gr_rating.get(
                        rating_elem[0].strip()) if rating_elem else None
                    url_review = 'https://www.goodreads.com' + \
                        cell.xpath(
                            ".//td[@class='field actions']//a/@href")[0].strip()
                    review = ''
                    try:
                        if action == 'view (with text)':
                            r2 = requests.get(
                                url_review, timeout=settings.SCRAPING_TIMEOUT)
                            if r2.status_code == 200:
                                c2 = html.fromstring(r2.content.decode('utf-8'))
                                review_elem = c2.xpath(
                                    "//div[@itemprop='reviewBody']/text()")
                                review = '\n'.join(
                                    p.strip() for p in review_elem) if review_elem else ''
                            else:
                                print(r2.status_code)
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
                            'review': review
                        })
                    except Exception:
                        print("Error adding " + url_book)
                        pass  # likely just download error
                next_elem = content.xpath("//a[@class='next_page']/@href")
                url_shelf = ('https://www.goodreads.com' + next_elem[0].strip()) if next_elem else None
        return {'title': title, 'books': books}
