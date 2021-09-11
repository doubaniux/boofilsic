from django.contrib.auth.backends import ModelBackend, UserModel
from django.shortcuts import reverse
from .api import *
from .models import MastodonApplication
from django.conf import settings


def obtain_token(site, request, code):
    """ Returns token if success else None. """
    mast_app = MastodonApplication.objects.get(domain_name=site)
    payload = {
        'client_id': mast_app.client_id,
        'client_secret': mast_app.client_secret,
        'redirect_uri': f"https://{request.get_host()}{reverse('users:OAuth2_login')}",
        'grant_type': 'authorization_code',
        'code': code,
        'scope': 'read write'
    }
    if settings.DEBUG:
        payload['redirect_uri']= f"http://{request.get_host()}{reverse('users:OAuth2_login')}",
    if mast_app.is_proxy:
        url = 'https://' + mast_app.proxy_to + API_OBTAIN_TOKEN
    else:
        url = 'https://' + mast_app.domain_name + API_OBTAIN_TOKEN
    response = post(url, data=payload)
    if response.status_code != 200:
        return
    data = response.json()
    return data.get('access_token')


def get_user_data(site, token):
    url = 'https://' + site + API_VERIFY_ACCOUNT
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = get(url, headers=headers)
    if response.status_code != 200:
        return None
    return response.json()


def revoke_token(site, token):
    mast_app = MastodonApplication.objects.get(domain_name=site)

    payload = {
        'client_id': mast_app.client_id,
        'client_secret': mast_app.client_secret,
        'scope': token
    }

    if mast_app.is_proxy:
        url = 'https://' + mast_app.proxy_to + API_REVOKE_TOKEN
    else:
        url = 'https://' + site + API_REVOKE_TOKEN
    response = post(url, data=payload)


def verify_token(site, token):
    """ Check if the token is valid and is of local instance. """
    url = 'https://' + site + API_VERIFY_ACCOUNT
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = get(url, headers=headers)
    if response.status_code == 200:
        res_data = response.json()
        # check if is local instance user
        if res_data['acct'] == res_data['username']:
            return True
    return False


class OAuth2Backend(ModelBackend):
    """ Used to glue OAuth2 and Django User model """
    # "authenticate() should check the credentials it gets and returns
    #  a user object that matches those credentials."
    # arg request is an interface specification, not used in this implementation
    def authenticate(self, request, token=None, username=None, site=None,  **kwargs):
        """ when username is provided, assume that token is newly obtained and valid """
        if token is None or site is None:
            return

        if username is None:
            user_data = get_user_data(site, token)
            if user_data:
                username = user_data['username']
            else:
                # aquiring user data fail means token is invalid thus auth fail
                return None

        # when username is provided, assume that token is newly obtained and valid
        try:
            user = UserModel._default_manager.get_by_natural_key(user_data['username'])
        except UserModel.DoesNotExist:
            return None
        else:
            if self.user_can_authenticate(user):
                return user
            return None
