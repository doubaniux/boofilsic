from django.test import TestCase
from catalog.common import *
from catalog.models import *


class SpotifyTestCase(TestCase):
    def test_parse(self):
        t_id_type = IdType.Spotify_Album
        t_id_value = '65KwtzkJXw7oT819NFWmEP'
        t_url = 'https://open.spotify.com/album/65KwtzkJXw7oT819NFWmEP'
        site = SiteList.get_site_by_id_type(t_id_type)
        self.assertIsNotNone(site)
        self.assertEqual(site.validate_url(t_url), True)
        site = SiteList.get_site_by_url(t_url)
        self.assertEqual(site.url, t_url)
        self.assertEqual(site.id_value, t_id_value)

    @use_local_response
    def test_scrape(self):
        t_url = 'https://open.spotify.com/album/65KwtzkJXw7oT819NFWmEP'
        site = SiteList.get_site_by_url(t_url)
        self.assertEqual(site.ready, False)
        site.get_page_ready()
        self.assertEqual(site.ready, True)
        self.assertEqual(site.page.metadata['title'], 'The Race For Space')
        self.assertIsInstance(site.page.item, Album)
        self.assertEqual(site.page.item.barcode, '3610159662676')
