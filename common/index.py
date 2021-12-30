import meilisearch
from django.conf import settings
from django.db.models.signals import post_save, post_delete


# TODO
# use post_save, post_delete
# search result translate back to model
INDEX_NAME = 'items'
INDEX_SEARCHABLE_ATTRIBUTES = ['title', 'orig_title', 'other_title', 'subtitle', 'artist', 'author', 'translator', 'developer', 'brief', 'contents', 'track_list', 'pub_house', 'company', 'publisher', 'isbn', 'imdb_code', 'UPC', 'TMDB_ID', 'BANDCAMP_ALBUM_ID']
INDEXABLE_DIRECT_TYPES = ['BigAutoField', 'BooleanField', 'CharField', 'PositiveIntegerField', 'PositiveSmallIntegerField', 'TextField', 'ArrayField']
INDEXABLE_TIME_TYPES = ['DateTimeField']
INDEXABLE_DICT_TYPES = ['JSONField']
INDEXABLE_FLOAT_TYPES = ['DecimalField']
# NONINDEXABLE_TYPES = ['ForeignKey', 'FileField',]


def item_post_save_handler(sender, instance, **kwargs):
    Indexer.replace_item(instance)


def item_post_delete_handler(sender, instance, **kwargs):
    Indexer.delete_item(instance)


def tag_post_save_handler(sender, instance, **kwargs):
    pass


def tag_post_delete_handler(sender, instance, **kwargs):
    pass


class Indexer:
    @classmethod
    def instance(self):
        return meilisearch.Client(settings.MEILISEARCH_SERVER, settings.MEILISEARCH_KEY).index(INDEX_NAME)
        # TODO cache per process/request

    @classmethod
    def init(self):
        meilisearch.Client(settings.MEILISEARCH_SERVER, settings.MEILISEARCH_KEY).create_index(INDEX_NAME, {'primaryKey': '_id'})
        self.update_settings()

    @classmethod
    def update_settings(self):
        self.instance().update_searchable_attributes(INDEX_SEARCHABLE_ATTRIBUTES)
        self.instance().update_filterable_attributes(['_class', 'tags', 'genre', 'source_site'])
        self.instance().update_settings({'displayedAttributes': ['_id', '_class', 'id', 'title', 'tags']})

    @classmethod
    def update_model_indexable(self, model):
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
    def replace_item(self, obj):
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
        # print(item)
        self.instance().add_documents([item])

    @classmethod
    def delete_item(self, obj):
        pk = f'{obj.__class__.__name__}-{obj.id}'
        self.instance().delete_document(pk)

    @classmethod
    def patch_item(self, obj, fields):
        pk = f'{obj.__class__.__name__}-{obj.id}'
        data = {}
        for f in fields:
            data[f] = getattr(obj, f)
        self.instance().update_documents(documents=[data], primary_key=[pk])
