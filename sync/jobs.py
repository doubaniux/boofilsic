import logging
import pytz
import signal
import sys
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from openpyxl import load_workbook
from books.models import BookMark, Book, BookTag
from movies.models import MovieMark, Movie, MovieTag
from music.models import AlbumMark, Album, AlbumTag
from games.models import GameMark, Game, GameTag
from common.scraper import DoubanAlbumScraper, DoubanBookScraper, DoubanGameScraper, DoubanMovieScraper
from common.models import MarkStatusEnum
from .models import SyncTask

__all__ = ['sync_task_manager']

logger = logging.getLogger(__name__)


class SyncTaskManger:

    # in seconds
    __CHECK_NEW_TASK_TIME_INTERVAL = 0.05
    MAX_WORKERS = 256

    def __init__(self):
        self.__task_queue = queue.Queue(0)
        self.__stop_event = threading.Event()
        self.__worker_threads = []

    def __listen_for_new_task(self):
        while not self.__stop_event.is_set():
            time.sleep(self.__CHECK_NEW_TASK_TIME_INTERVAL)
            while not self.__task_queue.empty() and not self.is_full():
                task = self.__task_queue.get_nowait()
                self.__start_new_worker(task)

    def __start_new_worker(self, task):
        new_worker = threading.Thread(
            target=sync_doufen_job, args=[task, self.is_stopped], daemon=True
        )
        self.__worker_threads.append(new_worker)
        new_worker.start()

    def __enqueue_existing_tasks(self):
        for task in SyncTask.objects.filter(is_finished=False):
            self.__task_queue.put_nowait(task)

    def is_full(self):
        return len(self.__worker_threads) >= self.MAX_WORKERS

    def add_task(self, task):
        self.__task_queue.put_nowait(task)

    def stop(self, signum, frame):
        print('rceived signal ', signum)
        logger.info(f'rceived signal {signum}')

        self.__stop_event.set()
        # for worker_thread in self.__worker_threads:
        #     worker_thread.join()

        print("stopped")
        logger.info(f'stopped')

    def is_stopped(self):
        return self.__stop_event.is_set()

    def start(self):
        if settings.START_SYNC:
            self.__enqueue_existing_tasks()  # enqueue

        listen_new_task_thread = threading.Thread(
            target=self.__listen_for_new_task, daemon=True)

        self.__worker_threads.append(listen_new_task_thread)

        listen_new_task_thread.start()


class DoufenParser:

    # indices in xlsx
    URL_INDEX = 4
    CONTENT_INDEX = 8
    TAG_INDEX = 7
    TIME_INDEX = 5
    RATING_INDEX = 6

    def __init__(self, task):
        self.__file_path = task.file.path
        self.__progress_sheet, self.__progress_row = task.get_breakpoint()
        self.__is_new_task = True
        if not self.__progress_sheet is None:
            self.__is_new_task = False
        if self.__progress_row is None:
            self.__progress_row = 2
        # data in the excel parse in python types
        self.task = task
        self.items = []

    def __open_file(self):
        self.__fp = open(self.__file_path, 'rb')
        self.__wb = load_workbook(
            self.__fp,
            read_only=True,
            data_only=True,
            keep_links=False
        )

    def __close_file(self):
        if self.__wb is not None:
            self.__wb.close()
        self.__fp.close()

    def __get_item_classes_mapping(self):
        '''
        We assume that the sheets names won't change
        '''
        mappings = []
        if self.task.sync_movie:
            for sheet_name in ['想看', '在看', '看过']:
                mappings.append({'sheet': sheet_name, 'mark_class': MovieMark,
                                 'entity_class': Movie, 'tag_class': MovieTag, 'scraper': DoubanMovieScraper})
        if self.task.sync_music:
            for sheet_name in ['想听', '在听', '听过']:
                mappings.append({'sheet': sheet_name, 'mark_class': AlbumMark,
                                 'entity_class': Album, 'tag_class': AlbumTag, 'scraper': DoubanAlbumScraper})
        if self.task.sync_book:
            for sheet_name in ['想读', '在读', '读过']:
                mappings.append({'sheet': sheet_name, 'mark_class': BookMark,
                                 'entity_class': Book, 'tag_class': BookTag, 'scraper': DoubanBookScraper})
        if self.task.sync_game:
            for sheet_name in ['想玩', '在玩', '玩过']:
                mappings.append({'sheet': sheet_name, 'mark_class': GameMark,
                                 'entity_class': Game, 'tag_class': GameTag, 'scraper': DoubanGameScraper})

        mappings.sort(key=lambda mapping: mapping['sheet'])

        if not self.__is_new_task:
            start_index = [mapping['sheet']
                           for mapping in mappings].index(self.__progress_sheet)
            mappings = mappings[start_index:]

        self.__mappings = mappings
        return mappings

    def __parse_items(self):
        assert self.__wb is not None, 'workbook not found'

        item_classes_mappings = self.__get_item_classes_mapping()

        is_first_sheet = True
        for mapping in item_classes_mappings:
            ws = self.__wb[mapping['sheet']]

            # empty sheet
            if ws.max_row <= 1:
                continue

            # decide starting position
            start_row_index = 2
            if not self.__is_new_task and is_first_sheet:
                start_row_index = self.__progress_row

            # parse data
            for i in range(start_row_index, ws.max_row + 1):
                # url definitely exists
                url = ws.cell(row=i, column=self.URL_INDEX).value

                tags = ws.cell(row=i, column=self.TAG_INDEX).value
                tags = tags.split(',') if tags else None

                time = ws.cell(row=i, column=self.TIME_INDEX).value
                if time:
                    time = datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
                    tz = pytz.timezone('Asia/Shanghai')
                    time = time.replace(tzinfo=tz)
                else:
                    time = None

                content = ws.cell(row=i, column=self.CONTENT_INDEX).value
                if not content:
                    content = ""

                rating = ws.cell(row=i, column=self.RATING_INDEX).value
                rating = int(rating) * 2 if rating else None

                # store result
                self.items.append({
                    'data': DoufenRowData(url, tags, time, content, rating),
                    'entity_class': mapping['entity_class'],
                    'mark_class': mapping['mark_class'],
                    'tag_class': mapping['tag_class'],
                    'scraper': mapping['scraper'],
                    'sheet': mapping['sheet'],
                    'row_index': i,
                })

            # set first sheet flag
            is_first_sheet = False

    def __get_item_number(self):
        assert not self.__wb is None, 'workbook not found'
        assert not self.__mappings is None, 'mappings not found'

        sheets = [mapping['sheet'] for mapping in self.__mappings]
        item_number = 0
        for sheet in sheets:
            item_number += self.__wb[sheet].max_row - 1

        return item_number

    def __update_total_items(self):
        total = self.__get_item_number()
        self.task.total_items = total
        self.task.save(update_fields=["total_items"])

    def parse(self):
        try:
            self.__open_file()
            self.__parse_items()
            if self.__is_new_task:
                self.__update_total_items()
            self.__close_file()
            return self.items

        except Exception as e:
            logger.error(e)
            raise e

        finally:
            self.__close_file()


@dataclass
class DoufenRowData:
    url: str
    tags: list
    time: datetime
    content: str
    rating: int


def add_new_mark(data, user, entity, entity_class, mark_class, tag_class, sheet, is_private):
    params = {
        'owner': user,
        'created_time': data.time,
        'edited_time': data.time,
        'rating': data.rating,
        'text': data.content,
        'status': translate_status(sheet),
        'is_private': not is_private,
        entity_class.__name__.lower(): entity,
    }
    mark = mark_class.objects.create(**params)
    entity.update_rating(None, data.rating)
    if data.tags:
        for tag in data.tags:
            params = {
                'content': tag,
                entity_class.__name__.lower(): entity,
                'mark': mark
            }
            tag_class.objects.create(**params)


def overwrite_mark(entity, entity_class, mark, mark_class, tag_class, data, sheet):
    old_rating = mark.rating
    old_tags = getattr(mark, mark_class.__name__.lower()+'_tags').all()
    # update mark logic
    mark.created_time = data.time
    mark.edited_time = data.time
    mark.text = data.content
    mark.rating = data.rating
    mark.status = translate_status(sheet)
    mark.save()
    entity.update_rating(old_rating, data.rating)
    if old_tags:
        for tag in old_tags:
            tag.delete()
    if data.tags:
        for tag in data.tags:
            params = {
                'content': tag,
                entity_class.__name__.lower(): entity,
                'mark': mark
            }
            tag_class.objects.create(**params)


def sync_doufen_job(task, stop_check_func):
    """
    TODO: Update task status every certain amount of items to reduce IO consumption
    """
    task = SyncTask.objects.get(pk=task.pk)
    if task.is_finished:
        return

    parser = DoufenParser(task)
    items = parser.parse()

    # use pop to reduce memo consumption
    while len(items) > 0 and not stop_check_func():
        item = items.pop(0)
        data = item['data']
        entity_class = item['entity_class']
        mark_class = item['mark_class']
        tag_class = item['tag_class']
        scraper = item['scraper']
        sheet = item['sheet']
        row_index = item['row_index']

        # update progress
        task.set_breakpoint(sheet, row_index, save=True)

        # scrape the entity if not exists
        try:
            entity = entity_class.objects.get(source_url=data.url)
        except ObjectDoesNotExist:
            try:
                scraper.scrape(data.url)
                form = scraper.save(request_user=task.user)
                entity = form.instance
            except Exception as e:
                logger.error(f"Scrape Failed URL: {data.url}")
                logger.error(
                    "Expections during scraping data:", exc_info=e)
                task.failed_urls.append(data.url)
                task.finished_items += 1
                task.save(update_fields=['failed_urls', 'finished_items'])
                continue

        # sync mark
        try:
            # already exists
            params = {
                'owner': task.user,
                entity_class.__name__.lower(): entity
            }
            mark = mark_class.objects.get(**params)

            if task.overwrite:
                overwrite_mark(entity, entity_class, mark,
                               mark_class, tag_class, data, sheet)
            else:
                task.success_items += 1
                task.finished_items += 1
                task.save(update_fields=['success_items', 'finished_items'])
                continue

        except ObjectDoesNotExist:
            add_new_mark(data, task.user, entity, entity_class,
                         mark_class, tag_class, sheet, task.default_public)

        except Exception as e:
            logger.error(
                "Unknown exception when syncing marks", exc_info=e)
            task.failed_urls.append(data.url)
            task.finished_items += 1
            task.save(update_fields=['failed_urls', 'finished_items'])
            continue

        task.success_items += 1
        task.finished_items += 1
        task.save(update_fields=['success_items', 'finished_items'])

    # if task finish
    if len(items) == 0:
        task.is_finished = True
        task.clear_breakpoint()
        task.save(update_fields=['is_finished', 'break_point'])


def translate_status(sheet_name):
    if '想' in sheet_name:
        return MarkStatusEnum.WISH
    elif '在' in sheet_name:
        return MarkStatusEnum.DO
    elif '过' in sheet_name:
        return MarkStatusEnum.COLLECT

    raise ValueError("Not valid status")


sync_task_manager = SyncTaskManger()

# sync_task_manager.start()

signal.signal(signal.SIGTERM, sync_task_manager.stop)
if sys.platform.startswith('linux'):
    signal.signal(signal.SIGHUP, sync_task_manager.stop)
signal.signal(signal.SIGINT, sync_task_manager.stop)
