class ParseError(Exception):
    def __init__(self, scraper, field):
        msg = f'{type(scraper).__name__}: Error parsing field "{field}" for url {scraper.url}'
        super().__init__(msg)


class ScraperMixin:
    def set_field(self, field, value=None):
        self.data[field] = value

    def parse_str(self, query):
        elem = self.html.xpath(query)
        return elem[0].strip() if elem else None

    def parse_field(self, field, query, error_when_missing=False):
        elem = self.html.xpath(query)
        if elem:
            self.data[field] = elem[0].strip()
        elif error_when_missing:
            raise ParseError(self, field)
        else:
            self.data[field] = None
        return elem
