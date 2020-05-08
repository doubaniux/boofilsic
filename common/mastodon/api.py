import requests
import string
import random
import functools
from boofilsic.settings import MASTODON_TIMEOUT, MASTODON_DOMAIN_NAME

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


get = functools.partial(requests.get, timeout=MASTODON_TIMEOUT)
post = functools.partial(requests.post, timeout=MASTODON_TIMEOUT)


def get_relationships(id_list, token):
    url = 'https://' + MASTODON_DOMAIN_NAME + API_GET_RELATIONSHIPS
    payload = {'id[]': id_list}
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = get(url, headers=headers, data=payload)
    return response.json()


def check_visibility(user_owned_entity, token, visitor):
    """
    check if given user can see the user owned entity
    """
    if not visitor == user_owned_entity.owner:
        # mastodon request
        relationship = get_relationships([visitor.mastodon_id], token)[0]
        if relationship['blocked_by']:
            return False
        if not relationship['following'] and user_owned_entity.is_private:
            return False
        return True
    else:
        return True


def post_toot(content, visibility, token, local_only=False):
    url = 'https://' + MASTODON_DOMAIN_NAME + API_PUBLISH_TOOT
    headers = {
        'Authorization': f'Bearer {token}',
        'Idempotency-Key': random_string_generator(16)
    }
    payload = {
        'status': content,
        'visibility': visibility,
        'local_only': local_only,
    }
    response = post(url, headers=headers, data=payload)
    return response

def random_string_generator(n):
    s = string.ascii_letters + string.punctuation + string.digits
    return ''.join(random.choice(s) for i in range(n))


class TootVisibilityEnum:
    PUBLIC = 'public'
    PRIVATE = 'private'
    DIRECT = 'direct'
    UNLISTED = 'unlisted'