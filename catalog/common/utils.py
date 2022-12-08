from pathlib import Path
# import hashlib
import json
from io import StringIO
import logging
import re
from django.utils import timezone
import uuid


logger = logging.getLogger(__name__)


DEFAULT_ITEM_COVER = 'item/default.svg'


def item_cover_path(page, filename):
    fn = timezone.now().strftime('%Y/%m/%d/') + str(uuid.uuid4()) + '.' + filename.split('.')[-1]
    return 'items/' + page.id_type + '/' + fn


TestDataDir = str(Path(__file__).parent.parent.parent.absolute()) + '/test_data/'


class MockResponse:
    def get_mock_file(self, url):
        fn = TestDataDir + re.sub(r'[^\w]', '_', url)
        return re.sub(r'_key_[A-Za-z0-9]+', '_key_19890604', fn)

    def __init__(self, url):
        self.url = url
        fn = self.get_mock_file(url)
        try:
            self.content = Path(fn).read_bytes()
            self.status_code = 200
            logger.debug(f"use local response for {url} from {fn}")
        except Exception:
            self.content = b'Error: response file not found'
            self.status_code = 404
            logger.debug(f"local response not found for {url} at {fn}")

    @property
    def text(self):
        return self.content.decode('utf-8')

    def json(self):
        return json.load(StringIO(self.text))

    @property
    def headers(self):
        return {'Content-Type': 'image/jpeg' if self.url.endswith('jpg') else 'text/html'}
