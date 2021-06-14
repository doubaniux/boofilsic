import logging
import pytz
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from openpyxl import load_workbook
from books.models import BookMark, Book, BookTag
from movies.models import MovieMark, Movie, MovieTag
from music.models import AlbumMark, Album, AlbumTag
from games.models import GameMark, Game, GameTag
from common.scraper import DoubanAlbumScraper, DoubanBookScraper, DoubanGameScraper, DoubanMovieScraper
from common.models import MarkStatusEnum

logger = logging.getLogger(__name__)


def sync_douban_job(task, user, filename, temp_dir):
    try:
        # NOTE use python IO since bug occurs using openpyxl
        fp = open(filename, 'rb')
        wb = load_workbook(
            fp,
            read_only=True,
            data_only=True,
            keep_links=False
        )

        # count items
        items_count = 0
        # sheet names
        categories = []
        # substract headers
        if task.sync_book:
            categories.append({'sheets': ['想读', '在读', '读过'], 'mark': BookMark, 'entity': Book, 'tag': BookTag, 'scraper': DoubanBookScraper})
            items_count += wb['想读'].max_row + wb['在读'].max_row + wb['读过'].max_row - 3
        if task.sync_movie:
            categories.append({'sheets': ['想看', '在看', '看过'], 'mark': MovieMark, 'entity': Movie, 'tag': MovieTag, 'scraper': DoubanMovieScraper})
            items_count += wb['想看'].max_row + wb['在看'].max_row + wb['看过'].max_row - 3
        if task.sync_music:
            categories.append({'sheets': ['想听', '在听', '听过'], 'mark': AlbumMark, 'entity': Album, 'tag': AlbumTag, 'scraper': DoubanAlbumScraper})
            items_count += wb['想听'].max_row + wb['在听'].max_row + wb['听过'].max_row - 3
        if task.sync_game:
            categories.append({'sheets': ['想玩', '在玩', '玩过'], 'mark': GameMark, 'entity': Game, 'tag': GameTag, 'scraper': DoubanGameScraper})
            items_count += wb['想玩'].max_row + wb['在玩'].max_row + wb['玩过'].max_row - 3
        
        if items_count == 0:
            task.is_finished = True
            task.ended_time = timezone.now()
            task.save()
            wb.close()
            temp_dir.cleanup()
            return
        else:
            task.total_items = items_count
            task.save(update_fields=["total_items"])
        
        # add marks
        # indices in xlsx
        URL_INDEX = 4
        CONTENT_INDEX = 8
        TAG_INDEX = 7
        TIME_INDEX = 5
        RATING_INDEX = 6

        for category in categories:
            for sheet in category['sheets']:
                ws = wb[sheet]
                if ws.max_row <= 1:
                    continue
                for i in range(2, ws.max_row + 1):
                    task.finished_items += 1
                    task.save(update_fields=["finished_items"])
                    # collect info
                    # url definitely exists
                    url = ws.cell(row=i, column=URL_INDEX).value
                    tags = ws.cell(row=i, column=TAG_INDEX).value
                    if tags:
                        tags = tags.split(',')
                    else:
                        tags = None
                    time = ws.cell(row=i, column=TIME_INDEX).value
                    if time:
                        time = datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
                        tz = pytz.timezone('Asia/Shanghai')
                        time = time.replace(tzinfo=tz)
                    else:
                        time = None
                    content = ws.cell(row=i, column=CONTENT_INDEX).value
                    if not content:
                        content = ""
                    rating = ws.cell(row=i, column=RATING_INDEX).value
                    if rating:
                        rating = int(rating) * 2
                    else:
                        rating = None

                    # scrape the entity if not exists
                    try:
                        item = category['entity'].objects.get(source_url=url)
                    except ObjectDoesNotExist:
                        try:
                            scraper = category['scraper']
                            scraper.scrape(url)
                            form = scraper.save(request_user=user)
                            item = form.instance
                        except Exception as e:
                            logger.error(f"Scrape Failed URL: {url}")
                            logger.error("Expections during saving scraped data:", exc_info=e)
                            task.failed_urls.append(url)
                            task.save(update_fields=['failed_urls'])
                            continue
                    
                    # sync mark
                    try:
                        # already exists
                        params = {
                            'owner': user,
                            category['entity'].__name__.lower(): item
                        }
                        mark = category['mark'].objects.get(**params)
                        old_rating = mark.rating
                        old_tags = getattr(
                            mark, category['mark'].__name__.lower()+'_tags').all()
                        if task.overwrite:
                            # update mark logic
                            mark.created_time = time
                            mark.edited_time = time
                            mark.text = content
                            mark.rating = rating
                            mark.status = translate_status(sheet)
                            mark.save()
                            item.update_rating(old_rating, rating)
                            if old_tags:
                                for tag in old_tags:
                                    tag.delete()
                            if tags:
                                for tag in tags:
                                    params = {
                                        'content': tag,
                                        category['entity'].__name__.lower(): item,
                                        'mark': mark
                                    }
                                    category['tag'].objects.create(**params)
                        else:
                            continue

                    except ObjectDoesNotExist:
                        # add new mark
                        params = {
                            'owner': user,
                            'created_time': time,
                            'edited_time': time,
                            'rating': rating,
                            'text': content,
                            'status': translate_status(sheet),
                            'is_private': not task.default_public,
                            category['entity'].__name__.lower(): item,
                        }
                        mark = category['mark'].objects.create(**params)
                        item.update_rating(None, rating)
                        if tags:
                            for tag in tags:
                                params = {
                                    'content': tag,
                                    category['entity'].__name__.lower(): item,
                                    'mark': mark
                                }
                                category['tag'].objects.create(**params)
                    except Exception as e:
                        logger.error("Unknown exception when syncing marks", exc_info=e)
                        task.failed_urls.append(url)
                        task.save(update_fields=['failed_urls'])
                        continue
                    task.success_items += 1
                    task.save(update_fields=["success_items"])

        task.is_finished = True
        task.ended_time = timezone.now()
        task.save()
        wb.close()

    except Exception as e:
        task.is_failed = True
        task.is_finished = True
        task.ended_time = timezone.now()
        task.save()
        logger.error("Sync task failed", exc_info=e)
        raise e

    finally:
        if wb is not None:
            wb.close()
        fp.close()
        temp_dir.cleanup()


def translate_status(sheet_name):
    if '想' in sheet_name:
        return MarkStatusEnum.WISH
    elif '在' in sheet_name:
        return MarkStatusEnum.DO
    elif '过' in sheet_name:
        return MarkStatusEnum.COLLECT
    
    raise ValueError("Not valid status")
