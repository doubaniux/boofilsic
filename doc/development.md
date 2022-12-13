Development
===========

*this doc is based on new data models work which is a work in progress*

First, a working version of local NeoDB instance has to be established, see [install guide](GUIDE.md).

Since new data model is still under development, most pieces are off by default, add `new_data_model=1` to your shell env and run migrations before start working on these new models

```
export new_data_model=1
python3 manage.py makemigrations 
python3 manage.py migrate
```

It's recommended to create the test database from freshly created database:
```
CREATE DATABASE test_neodb WITH TEMPLATE neodb;
```
Alternatively `python3 manage.py test` can create test databases every time test runs, but it's slow and buggy bc test run initial migration scripts slightly differently.

Run Test
--------
Now to verify everything works, run tests with `python3 manage.py test --keepdb`
```
$ python3 manage.py test --keepdb

Using existing test database for alias 'default'...
System check identified no issues (2 silenced).
........................................................
----------------------------------------------------------------------
Ran 56 tests in 1.100s

OK
Preserving test database for alias 'default'...
```


Data Models
-----------
main django apps for NeoDB:
 - `users` manages user in typical django fashion
 - `mastodon` this leverages [Mastodon API](https://docs.joinmastodon.org/client/intro/) and [Twitter API](https://developer.twitter.com/en/docs/twitter-api) for user login and data sync
 - `catalog` manages different types of items user may review, and scrapers to fetch from external resources, see [catalog.md](catalog.md) for more details
 - `journal` manages user created content(review/ratings) and lists(collection/shelf/tag), see [journal.md](journal.md) for more details
 - `social` manages timeline for local users and ActivityStreams for remote servers, see [social.md](social.md) for more details

These apps are legacy: books, music, movies, games, collections, they will be removed soon.


ActivityPub
-----------

TBA

References:
 - https://www.w3.org/TR/activitypub/
 - https://www.w3.org/TR/activitystreams-core/
 - https://www.w3.org/TR/activitystreams-vocabulary/
 - https://www.w3.org/TR/json-ld/
 - https://codeberg.org/fediverse/fep/src/branch/main/feps/fep-e232.md
 - https://socialhub.activitypub.rocks/t/guide-for-new-activitypub-implementers/479
 - https://blog.joinmastodon.org/2018/06/how-to-implement-a-basic-activitypub-server/
 - https://docs.joinmastodon.org/spec/activitypub/
