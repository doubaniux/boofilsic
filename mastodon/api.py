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
        'User-Agent': 'NeoDB/1.0',
        'Authorization': f'Bearer {token}'
    }
    response = get(url, headers=headers, params=payload)
    return response.json()


def post_toot(site, content, visibility, token, local_only=False):
    url = 'https://' + site + API_PUBLISH_TOOT
    headers = {
        'User-Agent': 'NeoDB/1.0',
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


def get_instance_domain(domain_name):
    try:
        response = get(f'https://{domain_name}/api/v1/instance', headers={'User-Agent': 'NeoDB/1.0'})
        return response.json()['uri'].lower().split('//')[-1].split('/')[0]
    except:
        return domain_name

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
        'scopes': settings.MASTODON_CLIENT_SCOPE,
        'redirect_uris': settings.REDIRECT_URIS,
        'website': settings.APP_WEBSITE
    }

    response = post(url, data=payload, headers={'User-Agent': 'NeoDB/1.0'})
    return response


def get_site_id(username, user_site, target_site, token):
    url = 'https://' + target_site + API_SEARCH
    payload = {
        'limit': 1,
        'type': 'accounts',
        'q': f"{username}@{user_site}"
    }
    headers = {
        'User-Agent': 'NeoDB/1.0',
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
def get_relationship(request_user, target_user, useless_token=None):
    return [{
        'blocked_by': target_user.is_blocking(request_user),
        'following': request_user.is_following(target_user),
    }]


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
            print(f'unable to find cross_site_id for {target_user} on {target_site}')
            return None
        cross_site_info = CrossSiteUserInfo.objects.create(
            uid=f"{target_user.username}@{target_user.mastodon_site}",
            target_site=target_site,
            site_id=cross_site_id,
            local_id=target_user.id
        )
    return cross_site_info.site_id


# utils below
def random_string_generator(n):
    s = string.ascii_letters + string.punctuation + string.digits
    return ''.join(random.choice(s) for i in range(n))


def verify_account(site, token):
    url = 'https://' + site + API_VERIFY_ACCOUNT
    try:
        response = get(url, headers={'User-Agent': 'NeoDB/1.0', 'Authorization': f'Bearer {token}'})
        return response.status_code, response.json() if response.status_code == 200 else None
    except Exception:
        return -1, None

def get_related_acct_list(site, token, api):
    url = 'https://' + site + api
    results = []
    while url:
        response = get(url, headers={'User-Agent': 'NeoDB/1.0', 'Authorization': f'Bearer {token}'})
        url = None
        if response.status_code == 200:
            results.extend(map(lambda u: (u['acct'] if u['acct'].find('@') != -1 else u['acct'] + '@' + site) if 'acct' in u else u, response.json()))
            if 'Link' in response.headers:
                for ls in response.headers['Link'].split(','):
                    li = ls.strip().split(';')
                    if li[1].strip() == 'rel="next"':
                        url = li[0].strip().replace('>', '').replace('<', '')
    return results


class TootVisibilityEnum:
    PUBLIC = 'public'
    PRIVATE = 'private'
    DIRECT = 'direct'
    UNLISTED = 'unlisted'
