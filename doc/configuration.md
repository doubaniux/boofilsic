Configuration
=============


Settings you may want to change
-------------------------------
most settings resides in `settings.py`, a few critical ones:

 - `SECRET_KEY` back it up well somewhere
 - `SITE_INFO['site_name']` change by you need
 - `CLIENT_NAME` site now show up in Mastodon app page
 - `REDIRECT_URIS` 
 - `APP_WEBSITE` external root url for your side
 - `REDIRECT_URIS` this should be `APP_WEBSITE + "/users/OAuth2_login/"` . It can be multiple urls separated by `\n` , but not all Fediverse software supports it well. Also note changing this later may invalidate app token granted previously
 - `MASTODON_ALLOW_ANY_SITE` set to `True` so that user can login via any Mastodon API compatible sites (e.g. Mastodon/Pleroma)
 - `MASTODON_CLIENT_SCOPE` change it later may invalidate app token granted previously
 - `ADMIN_URL` admin page url, keep it private
 - `SEARCH_BACKEND` should be either `TYPESENSE` or `MEILISEARCH` so that search and index can function. set as `None` will use default database search, which will be for development only and will not work very well in production
 

Settings for Scrapers
---------------------

TBA
