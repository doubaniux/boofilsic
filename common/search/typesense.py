import types
import logging
import typesense
from typesense.exceptions import ObjectNotFound
from django.conf import settings
from django.db.models.signals import post_save, post_delete


INDEX_NAME = 'items'
SEARCHABLE_ATTRIBUTES = ['title', 'orig_title', 'other_title', 'subtitle', 'artist', 'author', 'translator',
                         'developer', 'director', 'actor', 'playwright', 'pub_house', 'company', 'publisher', 'isbn', 'imdb_code']
FILTERABLE_ATTRIBUTES = ['_class', 'tags', 'source_site']
INDEXABLE_DIRECT_TYPES = ['BigAutoField', 'BooleanField', 'CharField',
                          'PositiveIntegerField', 'PositiveSmallIntegerField', 'TextField', 'ArrayField']
INDEXABLE_TIME_TYPES = ['DateTimeField']
INDEXABLE_DICT_TYPES = ['JSONField']
INDEXABLE_FLOAT_TYPES = ['DecimalField']
SORTING_ATTRIBUTE = None
# NONINDEXABLE_TYPES = ['ForeignKey', 'FileField',]
SEARCH_PAGE_SIZE = 20


logger = logging.getLogger(__name__)


def item_post_save_handler(sender, instance, created, **kwargs):
    if not created and settings.SEARCH_INDEX_NEW_ONLY:
        return
    Indexer.replace_item(instance)


def item_post_delete_handler(sender, instance, **kwargs):
    Indexer.delete_item(instance)


def tag_post_save_handler(sender, instance, **kwargs):
    pass


def tag_post_delete_handler(sender, instance, **kwargs):
    pass


class Indexer:
    class_map = {}
    _instance = None

    @classmethod
    def instance(self):
        if self._instance is None:
            self._instance = typesense.Client(settings.TYPESENSE_CONNECTION)
        return self._instance

    @classmethod
    def init(self):
        # self.instance().collections[INDEX_NAME].delete()
        # fields = [
        #     {"name": "_class", "type": "string", "facet": True},
        #     {"name": "source_site", "type": "string", "facet": True},
        #     {"name": ".*", "type": "auto", "locale": "zh"},
        # ]
        # use dumb schema below before typesense fix a bug
        fields = [
            {'name': 'id', 'type': 'string'},
            {'name': '_id', 'type': 'int64'},
            {'name': '_class', 'type': 'string', "facet": True},
            {'name': 'source_site', 'type': 'string', "facet": True},
            {'name': 'isbn', 'optional': True, 'type': 'string'},
            {'name': 'imdb_code', 'optional': True, 'type': 'string'},
            {'name': 'author', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'orig_title', 'optional': True, 'locale': 'zh', 'type': 'string'},
            {'name': 'pub_house', 'optional': True, 'locale': 'zh', 'type': 'string'},
            {'name': 'title', 'optional': True, 'locale': 'zh', 'type': 'string'},
            {'name': 'translator', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'subtitle', 'optional': True, 'locale': 'zh', 'type': 'string'},
            {'name': 'artist', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'company', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'developer', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'other_title', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'publisher', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'actor', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'director', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'playwright', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': 'tags', 'optional': True, 'locale': 'zh', 'type': 'string[]'},
            {'name': '.*', 'optional': True, 'locale': 'zh', 'type': 'auto'},
        ]

        self.instance().collections.create({
            "name": INDEX_NAME,
            "fields": fields
        })

    @classmethod
    def update_settings(self):
        # https://github.com/typesense/typesense/issues/96
        print('not supported by typesense yet')
        pass

    @classmethod
    def get_stats(self):
        return self.instance().collections[INDEX_NAME].retrieve()

    @classmethod
    def busy(self):
        return False

    @classmethod
    def update_model_indexable(self, model):
        if settings.SEARCH_BACKEND is None:
            return
        self.class_map[model.__name__] = model
        model.indexable_fields = ['tags']
        model.indexable_fields_time = []
        model.indexable_fields_dict = []
        model.indexable_fields_float = []
        for field in model._meta.get_fields():
            type = field.get_internal_type()
            if type in INDEXABLE_DIRECT_TYPES:
                model.indexable_fields.append(field.name)
            elif type in INDEXABLE_TIME_TYPES:
                model.indexable_fields_time.append(field.name)
            elif type in INDEXABLE_DICT_TYPES:
                model.indexable_fields_dict.append(field.name)
            elif type in INDEXABLE_FLOAT_TYPES:
                model.indexable_fields_float.append(field.name)
        post_save.connect(item_post_save_handler, sender=model)
        post_delete.connect(item_post_delete_handler, sender=model)

    @classmethod
    def obj_to_dict(self, obj):
        pk = f'{obj.__class__.__name__}-{obj.id}'
        item = {
            '_class': obj.__class__.__name__,
        }
        for field in obj.__class__.indexable_fields:
            item[field] = getattr(obj, field)
        for field in obj.__class__.indexable_fields_time:
            item[field] = getattr(obj, field).timestamp()
        for field in obj.__class__.indexable_fields_float:
            item[field] = float(getattr(obj, field)) if getattr(
                obj, field) else None
        for field in obj.__class__.indexable_fields_dict:
            d = getattr(obj, field)
            if d.__class__ is dict:
                item.update(d)
        item = {k: v for k, v in item.items() if v and (
            k in SEARCHABLE_ATTRIBUTES or k in FILTERABLE_ATTRIBUTES or k == 'id')}
        item['_id'] = item['id']
        # typesense requires primary key to be named 'id', type string
        item['id'] = pk
        return item

    @classmethod
    def replace_item(self, obj):
        try:
            self.instance().collections[INDEX_NAME].documents.upsert(self.obj_to_dict(obj), {
                'dirty_values': 'coerce_or_drop'
            })
        except Exception as e:
            logger.error(f"replace item error: \n{e}")

    @classmethod
    def replace_batch(self, objects):
        try:
            self.instance().collections[INDEX_NAME].documents.import_(
                objects, {'action': 'upsert'})
        except Exception as e:
            logger.error(f"replace batch error: \n{e}")

    @classmethod
    def delete_item(self, obj):
        pk = f'{obj.__class__.__name__}-{obj.id}'
        try:
            self.instance().collections[INDEX_NAME].documents[pk].delete()
        except Exception as e:
            logger.error(f"delete item error: \n{e}")

    @classmethod
    def search(self, q, page=1, category=None, tag=None, sort=None):
        f = []
        if category == 'music':
            f.append('_class:= [Album, Song]')
        elif category:
            f.append('_class:= ' + category)
        else:
            f.append('')
        if tag:
            f.append(f"tags:= '{tag}'")
        filter = ' && '.join(f)
        options = {
            'q': q,
            'page': page,
            'per_page': SEARCH_PAGE_SIZE,
            'query_by': ','.join(SEARCHABLE_ATTRIBUTES),
            'filter_by': filter,
            # 'facetsDistribution': ['_class'],
            # 'sort_by': None,
        }
        results = types.SimpleNamespace()

        try:
            r = self.instance().collections[INDEX_NAME].documents.search(options)
            results.items = list([x for x in map(lambda i: self.item_to_obj(i['document']), r['hits']) if x is not None])
            results.num_pages = (r['found'] + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE
        except ObjectNotFound:
            results.items = []
            results.num_pages = 1

        return results

    @classmethod
    def item_to_obj(self, item):
        try:
            return self.class_map[item['_class']].objects.get(id=item['_id'])
        except Exception as e:
            logger.error(f"unable to load search result item from db:\n{item}")
            return None
