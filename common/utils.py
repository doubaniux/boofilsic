class PageLinksGenerator:
    # TODO inherit django paginator
    """
    Calculate the pages for multiple links pagination.
    length -- the number of page links in pagination
    """
    def __init__(self, length, current_page, total_pages):
        current_page = int(current_page)
        self.current_page = current_page
        self.start_page = None
        self.end_page = None
        self.page_range = None
        self.has_prev = None
        self.has_next = None

        start_page = current_page - length // 2
        end_page = current_page + length // 2

        # decision is based on the start page and the end page
        # both sides overflow
        if (start_page < 1 and end_page > total_pages)\
            or length >= total_pages:
            self.start_page = 1
            self.end_page = total_pages
            self.has_prev = False
            self.has_next = False
        
        elif start_page < 1 and not end_page > total_pages:
            self.start_page = 1
            # this won't overflow because the total pages are more than the length
            self.end_page = end_page - (start_page - 1)
            self.has_prev = False
            if end_page == total_pages:
                self.has_next = False
            else:
                self.has_next = True
            
        elif not start_page < 1 and end_page > total_pages:
            self.end_page = total_pages
            self.start_page = start_page - (end_page - total_pages)
            self.has_next = False
            if start_page == 1:
                self.has_prev = False
            else:
                self.has_prev = True

        # both sides do not overflow
        elif not start_page < 1 and not end_page > total_pages:
            self.start_page = start_page
            self.end_page = end_page
            self.has_prev = True
            self.has_next = True

        self.first_page = 1
        self.last_page = total_pages
        self.page_range = range(self.start_page, self.end_page + 1)
        # assert self.has_prev is not None and self.has_next is not None


def ChoicesDictGenerator(choices_enum):
    choices_dict = {}
    for attr in dir(choices_enum):
        if not '__' in attr:
            choices_dict[getattr(choices_enum, attr).value] = getattr(choices_enum, attr).label
    return choices_dict