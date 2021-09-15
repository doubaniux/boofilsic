import requests
import string
import random
import functools
from django.core.exceptions import ObjectDoesNotExist
from .models import CrossSiteUserInfo
from django.conf import settings

# See https://docs.joinmastodon.org/methods/accounts/

# returns user info
# retruns the same info as verify account credentials
# GET
API_GET_ACCOUNT = '/api/v1/accounts/:id'

# returns user info if valid, 401 if invalid
# GET
API_VERIFY_ACCOUNT = '/api/v1/accounts/verify_credentials'

# obtain token
# GET
API_OBTAIN_TOKEN = '/oauth/token'

# obatin auth code
# GET
API_OAUTH_AUTHORIZE = '/oauth/authorize'

# revoke token
# POST
API_REVOKE_TOKEN = '/oauth/revoke'

# relationships
# GET
API_GET_RELATIONSHIPS = '/api/v1/accounts/relationships'

# toot
# POST
API_PUBLISH_TOOT = '/api/v1/statuses'

# create new app
# POST
API_CREATE_APP = '/api/v1/apps'

# search
# GET
API_SEARCH = '/api/v2/search'


get = functools.partial(requests.get, timeout=settings.MASTODON_TIMEOUT)
post = functools.partial(requests.post, timeout=settings.MASTODON_TIMEOUT)


# low level api below
def get_relationships(site, id_list, token):
    url = 'https://' + site + API_GET_RELATIONSHIPS
    payload = {'id[]': id_list}
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = get(url, headers=headers, params=payload)
    return response.json()


def post_toot(site, content, visibility, token, local_only=False):
    url = 'https://' + site + API_PUBLISH_TOOT
    headers = {
        'Authorization': f'Bearer {token}',
        'Idempotency-Key': random_string_generator(16)
    }
    payload = {
        'status': content,
        'visibility': visibility,
        'local_only': True,
    }
    if not local_only:
        del payload['local_only']
    response = post(url, headers=headers, data=payload)
    return response


def create_app(domain_name):
    # naive protocal strip
    is_http = False
    if domain_name.startswith("https://"):
        domain_name = domain_name.replace("https://", '')
    elif domain_name.startswith("http://"):
        is_http = True
        domain_name = domain_name.replace("http://", '')
    if domain_name.endswith('/'):
        domain_name = domain_name[0:-1]

    if not is_http:
        url = 'https://' + domain_name + API_CREATE_APP
    else:
        url = 'http://' + domain_name + API_CREATE_APP

    payload = {
        'client_name': settings.CLIENT_NAME,
        'scopes': 'read write follow',
        'redirect_uris': settings.REDIRECT_URIS,
        'website': settings.APP_WEBSITE
    }

    if settings.DEBUG:
        payload['redirect_uris'] = 'http://localhost/users/OAuth2_login/\nurn:ietf:wg:oauth:2.0:oob'
        payload['client_name'] = 'test_do_not_authorise'

    response = post(url, data=payload)
    return response


def get_site_id(username, user_site, target_site, token):
    url = 'https://' + target_site + API_SEARCH
    payload = {
        'limit': 1,
        'type': 'accounts',
        'q': f"{username}@{user_site}"
    }
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = get(url, params=payload, headers=headers)
    data = response.json()
    if not data['accounts']: 
        return None
    elif len(data['accounts']) == 0:  # target site may return empty if no cache of this user
        return None
    elif data['accounts'][0]['acct'] != f"{username}@{user_site}":  # or return another user with a similar id which needs to be skipped  
        return None
    else:
        return data['accounts'][0]['id']


# high level api below
def get_relationship(request_user, target_user, token):
    if request_user.mastodon_site == target_user.mastodon_site:
        return get_relationships(request_user.mastodon_site, target_user.mastodon_id, token)
    else:
        cross_site_id = get_cross_site_id(target_user, request_user.mastodon_site, token)
        if cross_site_id is None:
            return [{'blocked_by': True}]  # boldly assume blocked(?!) if no relationship found
            # FIXME should check the reverse direction? but need either cache the target user's oauth token or her blocked list
        else:
            return get_relationships(request_user.mastodon_site, cross_site_id, token)


def get_cross_site_id(target_user, target_site, token):
    """
    Firstly attempt to query local database, if the cross site id
    doesn't exsit then make a query to mastodon site, then save the
    result into database.
    Return target_user at target_site cross site id.
    """
    if target_site == target_user.mastodon_site:
        return target_user.mastodon_id

    try:
        cross_site_info = CrossSiteUserInfo.objects.get(
            uid=f"{target_user.username}@{target_user.mastodon_site}",
            target_site=target_site
        )
    except ObjectDoesNotExist:
        cross_site_id = get_site_id(
            target_user.username, target_user.mastodon_site, target_site, token)
        if not cross_site_id:
            return None
        cross_site_info = CrossSiteUserInfo.objects.create(
            uid=f"{target_user.username}@{target_user.mastodon_site}",
            target_site=target_site,
            site_id=cross_site_id,
            local_id=target_user.id
        )
    return cross_site_info.site_id


def check_visibility(user_owned_entity, token, visitor):
    """
    check if given user can see the user owned entity
    """
    if not visitor == user_owned_entity.owner:
        # mastodon request
        relationship = get_relationship(visitor, user_owned_entity.owner, token)[0]
        if relationship['blocked_by']:
            return False
        if not relationship['following'] and user_owned_entity.is_private:
            return False
        return True
    else:
        return True


# utils below
def random_string_generator(n):
    s = string.ascii_letters + string.punctuation + string.digits
    return ''.join(random.choice(s) for i in range(n))


class TootVisibilityEnum:
    PUBLIC = 'public'
    PRIVATE = 'private'
    DIRECT = 'direct'
    UNLISTED = 'unlisted'
