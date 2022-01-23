import logging
import meilisearch
from django.conf import settings
from django.db.models.signals import post_save, post_delete


INDEX_NAME = 'items'
SEARCHABLE_ATTRIBUTES = ['title', 'orig_title', 'other_title', 'subtitle', 'artist', 'author', 'translator', 'developer', 'director', 'actor', 'playwright', 'pub_house', 'company', 'publisher', 'isbn', 'imdb_code']
INDEXABLE_DIRECT_TYPES = ['BigAutoField', 'BooleanField', 'CharField', 'PositiveIntegerField', 'PositiveSmallIntegerField', 'TextField', 'ArrayField']
INDEXABLE_TIME_TYPES = ['DateTimeField']
INDEXABLE_DICT_TYPES = ['JSONField']
INDEXABLE_FLOAT_TYPES = ['DecimalField']
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
            self._instance = meilisearch.Client(settings.MEILISEARCH_SERVER, settings.MEILISEARCH_KEY).index(INDEX_NAME)
        return self._instance

    @classmethod
    def init(self):
        meilisearch.Client(settings.MEILISEARCH_SERVER, settings.MEILISEARCH_KEY).create_index(INDEX_NAME, {'primaryKey': '_id'})
        self.update_settings()

    @classmethod
    def update_settings(self):
        self.instance().update_searchable_attributes(SEARCHABLE_ATTRIBUTES)
        self.instance().update_filterable_attributes(['_class', 'tags', 'source_site'])
        self.instance().update_settings({'displayedAttributes': ['_id', '_class', 'id', 'title', 'tags']})

    @classmethod
    def get_stats(self):
        return self.instance().get_stats()

    @classmethod
    def busy(self):
        return self.instance().get_stats()['isIndexing']

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
            '_id': pk,
            '_class': obj.__class__.__name__,
            # 'id': obj.id
        }
        for field in obj.__class__.indexable_fields:
            item[field] = getattr(obj, field)
        for field in obj.__class__.indexable_fields_time:
            item[field] = getattr(obj, field).timestamp()
        for field in obj.__class__.indexable_fields_float:
            item[field] = float(getattr(obj, field)) if getattr(obj, field) else None
        for field in obj.__class__.indexable_fields_dict:
            d = getattr(obj, field)
            if d.__class__ is dict:
                item.update(d)
        item = {k: v for k, v in item.items() if v}
        return item

    @classmethod
    def replace_item(self, obj):
        try:
            self.instance().add_documents([self.obj_to_dict(obj)])
        except Exception as e:
            logger.error(f"replace item error: \n{e}")

    def replace_batch(self, objects):
        try:
            self.instance().update_documents(documents=objects)
        except Exception as e:
            logger.error(f"replace batch error: \n{e}")

    @classmethod
    def delete_item(self, obj):
        pk = f'{obj.__class__.__name__}-{obj.id}'
        try:
            self.instance().delete_document(pk)
        except Exception as e:
            logger.error(f"delete item error: \n{e}")

    @classmethod
    def patch_item(self, obj, fields):
        pk = f'{obj.__class__.__name__}-{obj.id}'
        data = {}
        for f in fields:
            data[f] = getattr(obj, f)
        try:
            self.instance().update_documents(documents=[data], primary_key=[pk])
        except Exception as e:
            logger.error(f"patch item error: \n{e}")

    @classmethod
    def search(self, q, page=1, category=None, tag=None, sort=None):
        if category or tag:
            f = []
            if category == 'music':
                f.append("(_class = 'Album' OR _class = 'Song')")
            elif category:
                f.append(f"_class = '{category}'")
            if tag:
                f.append(f"tags = '{tag}'")
            filter = ' AND '.join(f)
        else:
            filter = None
        options = {
            'offset': (page - 1) * SEARCH_PAGE_SIZE,
            'limit': SEARCH_PAGE_SIZE,
            'filter': filter,
            'facetsDistribution': ['_class'],
            'sort': None
        }
        r = self.instance().search(q, options)
        # print(r)
        import types
        results = types.SimpleNamespace()
        results.items = list([x for x in map(lambda i: self.item_to_obj(i), r['hits']) if x is not None])
        results.num_pages = (r['nbHits'] + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE
        # print(results)
        return results

    @classmethod
    def item_to_obj(self, item):
        try:
            return self.class_map[item['_class']].objects.get(id=item['id'])
        except Exception as e:
            logger.error(f"unable to load search result item from db:\n{item}")
            return None
