from django.contrib.syndication.views import Feed
from django.conf import settings
from .models import User
from markdown import markdown
import operator
import mimetypes


MAX_ITEM_PER_TYPE = 10


class ReviewFeed(Feed):
    def get_object(self, request, id):
        return User.get(id)

    def title(self, user):
        return "%s的评论" % user.display_name

    def link(self, user):
        return settings.APP_WEBSITE + user.url

    def description(self, user):
        return "%s的评论合集 - NiceDB" % user.display_name

    def items(self, user):
        if user is None:
            return None
        book_reviews = list(user.user_bookreviews.filter(visibility=0)[:MAX_ITEM_PER_TYPE])
        movie_reviews = list(user.user_moviereviews.filter(visibility=0)[:MAX_ITEM_PER_TYPE])
        album_reviews = list(user.user_albumreviews.filter(visibility=0)[:MAX_ITEM_PER_TYPE])
        game_reviews = list(user.user_gamereviews.filter(visibility=0)[:MAX_ITEM_PER_TYPE])
        all_reviews = sorted(
                book_reviews + movie_reviews + album_reviews + game_reviews, 
                key=operator.attrgetter('created_time'), 
                reverse=True
            )
        return all_reviews

    def item_title(self, item):
        return f"{item.title} - 评论《{item.item.title}》"

    def item_description(self, item):
        target_html = f'<p><a href="{item.item.absolute_url}">{item.item.title}</a></p>\n' 
        html = markdown(item.content)
        return target_html + html

    # item_link is only needed if NewsItem has no get_absolute_url method.
    def item_link(self, item):
        return item.absolute_url

    def item_categories(self, item):
        return [item.item.verbose_category_name]

    def item_pubdate(self, item):
        return item.created_time

    def item_updateddate(self, item):
        return item.edited_time

    def item_enclosure_url(self, item):
        return settings.APP_WEBSITE + item.item.cover.url

    def item_enclosure_mime_type(self, item):
        t, _ = mimetypes.guess_type(item.item.cover.url)
        return t

    def item_enclosure_length(self, item):
        return item.item.cover.file.size

    def item_comments(self, item):
        return item.shared_link
