import requests
import random
from lxml import html
import re
from boofilsic.settings import LUMINATI_USERNAME, LUMINATI_PASSWORD, DEBUG

RE_NUMBERS = re.compile(r"\d+\d*")
RE_WHITESPACES = re.compile(r"\s+")

DEFAULT_REQUEST_HEADERS = {
    'Host': 'book.douban.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:70.0) Gecko/20100101 Firefox/70.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    # well, since brotli lib is so bothering, remove `br`
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0',
}

# in seconds
TIMEOUT = 10

# luminati account credentials
PORT = 22225


def scrape_douban_book(url):
    session_id = random.random()
    proxy_url = ('http://%s-country-cn-session-%s:%s@zproxy.lum-superproxy.io:%d' %
        (LUMINATI_USERNAME, session_id, LUMINATI_PASSWORD, PORT))
    proxies = {
        'http': proxy_url,
        'https': proxy_url,    
    }
    if DEBUG:
        proxies = None
    r = requests.get(url, proxies=proxies, headers=DEFAULT_REQUEST_HEADERS, timeout=TIMEOUT)
    # r = requests.get(url, headers=DEFAULT_REQUEST_HEADERS, timeout=TIMEOUT)
    
    content = html.fromstring(r.content.decode('utf-8'))

    title = content.xpath("/html/body/div[3]/h1/span/text()")[0].strip()

    subtitle_elem = content.xpath("//div[@id='info']//span[text()='副标题:']/following::text()")
    subtitle = subtitle_elem[0].strip() if subtitle_elem else None

    orig_title_elem = content.xpath("//div[@id='info']//span[text()='原作名:']/following::text()")
    orig_title = orig_title_elem[0].strip() if orig_title_elem else None

    language_elem = content.xpath("//div[@id='info']//span[text()='语言:']/following::text()")
    language = language_elem[0].strip() if language_elem else None

    pub_house_elem = content.xpath("//div[@id='info']//span[text()='出版社:']/following::text()")
    pub_house = pub_house_elem[0].strip() if pub_house_elem else None

    pub_date_elem = content.xpath("//div[@id='info']//span[text()='出版年:']/following::text()")
    pub_date = pub_date_elem[0].strip() if pub_date_elem else None
    year_month_day = RE_NUMBERS.findall(pub_date)
    if len(year_month_day) in (2, 3):
        pub_year = int(year_month_day[0])
        pub_month = int(year_month_day[1])
    elif len(year_month_day) == 1:
        pub_year = int(year_month_day[0])
        pub_month = None
    else:
        pub_year = None
        pub_month = None
    if pub_year and pub_month and pub_year < pub_month:
        pub_year, pub_month = pub_month, pub_year
    pub_year = None if pub_year is not None and not pub_year in range(0, 3000) else pub_year
    pub_month = None if pub_month is not None and not pub_month in range(1, 12) else pub_month

    binding_elem = content.xpath("//div[@id='info']//span[text()='装帧:']/following::text()")
    binding = binding_elem[0].strip() if binding_elem else None

    price_elem = content.xpath("//div[@id='info']//span[text()='定价:']/following::text()")
    price = price_elem[0].strip() if price_elem else None

    pages_elem = content.xpath("//div[@id='info']//span[text()='页数:']/following::text()")
    pages = pages_elem[0].strip() if pages_elem else None 
    if pages is not None:
        pages = int(RE_NUMBERS.findall(pages)[0]) if RE_NUMBERS.findall(pages) else None

    isbn_elem = content.xpath("//div[@id='info']//span[text()='ISBN:']/following::text()")
    isbn = isbn_elem[0].strip() if isbn_elem else None

    brief_elem = content.xpath("//h2/span[text()='内容简介']/../following-sibling::div[1]//div[@class='intro'][not(ancestor::span[@class='short'])]/p/text()")
    brief = '\n'.join(p.strip() for p in brief_elem) if brief_elem else None

    img_url_elem = content.xpath("//*[@id='mainpic']/a/img/@src")
    img_url = img_url_elem[0].strip() if img_url_elem else None
    raw_img = None
    if img_url:
        img_response = requests.get(
            img_url, 
            headers={
                'accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'accept-encoding': 'gzip, deflate',
                'accept-language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,fr-FR;q=0.6,fr;q=0.5,zh-TW;q=0.4',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 Edg/81.0.416.72',
                'cache-control': 'no-cache',
                'dnt': '1'  ,
            }, 
            proxies=proxies,
            timeout=TIMEOUT, 
        )
        if img_response.status_code == 200:
            raw_img = img_response.content

    # there are two html formats for authors and translators
    authors_elem = content.xpath("""//div[@id='info']//span[text()='作者:']/following-sibling::br[1]/
        preceding-sibling::a[preceding-sibling::span[text()='作者:']]/text()""")
    if not authors_elem:
        authors_elem = content.xpath("""//div[@id='info']//span[text()=' 作者']/following-sibling::a/text()""")
    if authors_elem:
        authors = []
        for author in authors_elem:
            authors.append(RE_WHITESPACES.sub(' ', author.strip()))
    else:
        authors = None

    translators_elem = content.xpath("""//div[@id='info']//span[text()='译者:']/following-sibling::br[1]/
        preceding-sibling::a[preceding-sibling::span[text()='译者:']]/text()""")
    if not translators_elem:
        translators_elem = content.xpath("""//div[@id='info']//span[text()=' 译者']/following-sibling::a/text()""")
    if translators_elem:
        translators = []
        for translator in translators_elem:
            translators.append(RE_WHITESPACES.sub(' ', translator.strip()))
    else:
        translators = None

    other = {}
    cncode_elem = content.xpath("//div[@id='info']//span[text()='统一书号:']/following::text()")
    if cncode_elem:
        other['统一书号'] = cncode_elem[0].strip()
    series_elem = content.xpath("//div[@id='info']//span[text()='丛书:']/following-sibling::a[1]/text()")
    if series_elem:
        other['丛书'] = series_elem[0].strip()            
    imprint_elem = content.xpath("//div[@id='info']//span[text()='出品方:']/following-sibling::a[1]/text()")
    if imprint_elem:
        other['出品方'] = imprint_elem[0].strip()

    data = {
        'title' : title,
        'subtitle' : subtitle,
        'orig_title' : orig_title,
        'author' : authors,
        'translator' : translators,
        'language' : language,
        'pub_house' : pub_house,
        'pub_year' : pub_year,
        'pub_month' : pub_month,
        'binding' : binding,
        'price' : price,
        'pages' : pages,
        'isbn' : isbn,
        'brief' : brief,
        'other_info' : other
    }
    return data, raw_img
