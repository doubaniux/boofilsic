from django.conf import settings


if settings.SEARCH_BACKEND == 'MEILISEARCH':
    from .search.meilisearch import Indexer
elif settings.SEARCH_BACKEND == 'TYPESENSE':
    from .search.typesense import Indexer
else:
    class Indexer:
        @classmethod
        def update_model_indexable(self, cls):
            pass
