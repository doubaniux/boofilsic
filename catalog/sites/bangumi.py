from catalog.common import *
from catalog.models import *
import logging


_logger = logging.getLogger(__name__)


@SiteList.register
class Bangumi(AbstractSite):
    ID_TYPE = IdType.Bangumi
    URL_PATTERNS = [
        r"https://bgm\.tv/subject/(\d+)",
    ]
    WIKI_PROPERTY_ID = ''
    DEFAULT_MODEL = None

    @classmethod
    def id_to_url(self, id_value):
        return f"https://bgm.tv/subject/{id_value}"

    def scrape(self):
        # TODO rewrite with bangumi api https://bangumi.github.io/api/
        pass
