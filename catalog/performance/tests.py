from django.test import TestCase
from catalog.common import *


class DoubanDramaTestCase(TestCase):
    def setUp(self):
        pass

    def test_parse(self):
        t_id = '24849279'
        t_url = 'https://www.douban.com/location/drama/24849279/'
        p1 = SiteList.get_site_by_id_type(IdType.DoubanDrama)
        self.assertIsNotNone(p1)
        p1 = SiteList.get_site_by_url(t_url)
        self.assertIsNotNone(p1)
        self.assertEqual(p1.validate_url(t_url), True)
        self.assertEqual(p1.id_to_url(t_id), t_url)
        self.assertEqual(p1.url_to_id(t_url), t_id)

    @use_local_response
    def test_scrape(self):
        t_url = 'https://www.douban.com/location/drama/24849279/'
        site = SiteList.get_site_by_url(t_url)
        self.assertEqual(site.ready, False)
        page = site.get_page_ready()
        self.assertEqual(site.ready, True)
        self.assertEqual(page.metadata['title'], '红花侠')
        item = site.get_item()
        self.assertEqual(item.title, '红花侠')

        # self.assertEqual(i.other_titles, ['スカーレットピンパーネル', 'THE SCARLET PIMPERNEL'])
        # self.assertEqual(len(i.brief), 545)
        # self.assertEqual(i.genres, ['音乐剧'])
        # self.assertEqual(i.versions, ['08星组公演版', '10年月組公演版', '17年星組公演版', 'ュージカル（2017年）版'])
        # self.assertEqual(i.directors, ['小池修一郎', '小池 修一郎', '石丸さち子'])
        # self.assertEqual(i.playwrights, ['小池修一郎', 'Baroness Orczy（原作）', '小池 修一郎'])
        # self.assertEqual(i.actors, ['安蘭けい', '柚希礼音', '遠野あすか', '霧矢大夢', '龍真咲'])
