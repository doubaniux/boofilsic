import requests
from django.shortcuts import reverse
from django.contrib.auth.backends import ModelBackend, UserModel
from boofilsic.settings import MASTODON_DOMAIN_NAME, CLIENT_ID, CLIENT_SECRET
from common.mastodon.api import *


class OAuth2Backend(ModelBackend):
    """ Used to glue OAuth2 and Django User model """
    # "authenticate() should check the credentials it gets and returns
    #  a user object that matches those credentials."
    # arg request is an interface specification, not used in this implementation
    def authenticate(self, request, token=None, username=None, **kwargs):
        """ when username is provided, assume that token is newly obtained and valid """
        if token is None:
            return

        if username is None:
            user_data = get_user_data(token)
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
        

def obtain_token(request, code):
    """ Returns token if success else None. """
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': f"http://{request.get_host()}{reverse('users:OAuth2_login')}",
        'grant_type': 'authorization_code',
        'code': code,
        'scope': 'read write'
    }
    url = 'https://' + MASTODON_DOMAIN_NAME + OAUTH_TOKEN
    response = requests.post(url, data=payload)
    if response.status_code != 200:
        return
    data = response.json()
    return data.get('access_token')


def get_user_data(token):
    url = 'https://' + MASTODON_DOMAIN_NAME + VERIFY_ACCOUNT_CREDENTIALS
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    return response.json()


def revoke_token(token):
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scope': token
    }
    url = 'https://' + MASTODON_DOMAIN_NAME + REVOKE_TOKEN
    response = requests.post(url, data=payload)


def verify_token(token):
    """ Check if the token is valid and is of local instance. """
    url = 'https://' + MASTODON_DOMAIN_NAME + VERIFY_ACCOUNT_CREDENTIALS
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        res_data = response.json()
        # check if is local instance user
        if res_data['acct'] == res_data['username']:
            return True
    return False