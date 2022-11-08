from django.contrib.syndication.views import Feed
from django.urls import reverse
from books.models import BookReview
from .models import User
from markdown import markdown
import operator


MAX_ITEM_PER_TYPE = 10


class ReviewFeed(Feed):
    def get_object(self, request, id):
        return User.get(id)

    def title(self, user):
        return "%s 的评论" % user.display_name

    def link(self, user):
        return user.url

    def description(self, user):
        return "%s 的评论合集 - NeoDB" % user.display_name

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
        target_html = f'<p><a href="{item.item.url}">{item.item.title}</a></p>\n' 
        html = markdown(item.content)
        return target_html + html

    # item_link is only needed if NewsItem has no get_absolute_url method.
    def item_link(self, item):
        return item.url