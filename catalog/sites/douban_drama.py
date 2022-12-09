from catalog.common import *
from catalog.models import *
from .douban import DoubanDownloader
import logging


_logger = logging.getLogger(__name__)


@SiteList.register
class DoubanDrama(AbstractSite):
    ID_TYPE = IdType.DoubanDrama
    URL_PATTERNS = [r"\w+://www.douban.com/location/drama/(\d+)/"]
    WIKI_PROPERTY_ID = 'P6443'
    DEFAULT_MODEL = Performance

    @classmethod
    def id_to_url(self, id_value):
        return "https://www.douban.com/location/drama/" + id_value + "/"

    def scrape(self):
        h = DoubanDownloader(self.url).download().html()
        data = {}

        title_elem = h.xpath("/html/body//h1/span/text()")
        if title_elem:
            data["title"] = title_elem[0].strip()
        else:
            raise ParseError(self, "title")

        data['other_titles'] = [s.strip() for s in title_elem[1:]]
        other_title_elem = h.xpath("//dl//dt[text()='又名：']/following::dd[@itemprop='name']/text()")
        if len(other_title_elem) > 0:
            data['other_titles'].append(other_title_elem[0].strip())

        plot_elem = h.xpath("//div[@id='link-report']/text()")
        if len(plot_elem) == 0:
            plot_elem = h.xpath("//div[@class='abstract']/text()")
        data['brief'] = '\n'.join(plot_elem) if len(plot_elem) > 0 else ''

        data['genres'] = [s.strip() for s in h.xpath("//dl//dt[text()='类型：']/following-sibling::dd[@itemprop='genre']/text()")]
        data['versions'] = [s.strip() for s in h.xpath("//dl//dt[text()='版本：']/following-sibling::dd[@class='titles']/a//text()")]
        data['directors'] = [s.strip() for s in h.xpath("//div[@class='meta']/dl//dt[text()='导演：']/following-sibling::dd/a[@itemprop='director']//text()")]
        data['playwrights'] = [s.strip() for s in h.xpath("//div[@class='meta']/dl//dt[text()='编剧：']/following-sibling::dd/a[@itemprop='author']//text()")]
        data['actors'] = [s.strip() for s in h.xpath("//div[@class='meta']/dl//dt[text()='主演：']/following-sibling::dd/a[@itemprop='actor']//text()")]

        img_url_elem = h.xpath("//img[@itemprop='image']/@src")
        data['cover_image_url'] = img_url_elem[0].strip() if img_url_elem else None

        pd = ResourceContent(metadata=data)
        if pd.metadata["cover_image_url"]:
            imgdl = BasicImageDownloader(pd.metadata["cover_image_url"], self.url)
            try:
                pd.cover_image = imgdl.download().content
                pd.cover_image_extention = imgdl.extention
            except Exception:
                _logger.debug(f'failed to download cover for {self.url} from {pd.metadata["cover_image_url"]}')
        return pd
