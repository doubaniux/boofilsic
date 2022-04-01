from django.contrib.auth.backends import ModelBackend, UserModel
from django.shortcuts import reverse
from .api import *
from .models import MastodonApplication
from django.conf import settings
from urllib.parse import quote


def get_mastodon_application(domain):
    app = MastodonApplication.objects.filter(domain_name=domain).first()
    if app is not None:
        return app, ''
    if domain == TWITTER_DOMAIN:
        return None, 'Twitter未配置'
    error_msg = None
    try:
        response = create_app(domain)
    except (requests.exceptions.Timeout, ConnectionError):
        error_msg = _("联邦网络请求超时。")
    except Exception as e:
        error_msg = str(e)
    else:
        # fill the form with returned data
        if response.status_code != 200:
            error_msg = "实例连接错误，代码: " + str(response.status_code)
            print(f'Error connecting {domain}: {response.status_code} {response.content.decode("utf-8")}')
        else:
            try:
                data = response.json()
            except Exception as e:
                error_msg = "实例返回内容无法识别"
                print(f'Error connecting {domain}: {response.status_code} {response.content.decode("utf-8")} {e}')
            else:
                app = MastodonApplication.objects.create(domain_name=domain, app_id=data['id'], client_id=data['client_id'],
                    client_secret=data['client_secret'], vapid_key=data['vapid_key'] if 'vapid_key' in data else '')
    return app, error_msg


def get_mastodon_login_url(app, login_domain, version, request):
    url = request.scheme + "://" + request.get_host() + reverse('users:OAuth2_login')
    if login_domain == TWITTER_DOMAIN:
        return f"https://twitter.com/i/oauth2/authorize?response_type=code&client_id={app.client_id}&redirect_uri={quote(url)}&scope={quote(settings.TWITTER_CLIENT_SCOPE)}&state=state&code_challenge=challenge&code_challenge_method=plain"
    scope = 'read' if 'Pixelfed' in version else settings.MASTODON_CLIENT_SCOPE
    return "https://" + login_domain + "/oauth/authorize?client_id=" + app.client_id + "&scope=" + quote(scope) + "&redirect_uri=" + url + "&response_type=code"


def obtain_token(site, request, code):
    """ Returns token if success else None. """
    mast_app = MastodonApplication.objects.get(domain_name=site)
    redirect_uri = request.scheme + "://" + request.get_host() + reverse('users:OAuth2_login')
    payload = {
        'client_id': mast_app.client_id,
        'client_secret': mast_app.client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
        'code': code,
        'code_verifier': 'challenge'
    }
    headers = {'User-Agent': 'NeoDB/1.0'}
    auth = None
    if mast_app.is_proxy:
        url = 'https://' + mast_app.proxy_to + API_OBTAIN_TOKEN
    elif site == TWITTER_DOMAIN:
        url = 'https://api.twitter.com/2/oauth2/token'
        auth = (mast_app.client_id, mast_app.client_secret)
        del payload['client_secret']
    else:
        url = 'https://' + mast_app.domain_name + API_OBTAIN_TOKEN
    response = post(url, data=payload, headers=headers, auth=auth)
    # {"token_type":"bearer","expires_in":7200,"access_token":"VGpkOEZGR3FQRDJ5NkZ0dmYyYWIwS0dqeHpvTnk4eXp0NV9nWDJ2TEpmM1ZTOjE2NDg3ODMxNTU4Mzc6MToxOmF0OjE","scope":"block.read follows.read offline.access tweet.write users.read mute.read","refresh_token":"b1pXbGEzeUF1WE5yZHJOWmxTeWpvMTBrQmZPd0czLU0tQndZQTUyU3FwRDVIOjE2NDg3ODMxNTU4Mzg6MToxOnJ0OjE"}
    if response.status_code != 200:
        print(url)
        print(response.status_code)
        print(response.text)
        return None, None
    data = response.json()
    return data.get('access_token'), data.get('refresh_token', '')


def refresh_access_token(site, refresh_token):
    if site != TWITTER_DOMAIN:
        return None
    mast_app = MastodonApplication.objects.get(domain_name=site)
    url = 'https://api.twitter.com/2/oauth2/token'
    payload = {
        'client_id': mast_app.client_id,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }
    headers = {'User-Agent': 'NeoDB/1.0'}
    auth = (mast_app.client_id, mast_app.client_secret)
    response = post(url, data=payload, headers=headers, auth=auth)
    if response.status_code != 200:
        print(url)
        print(response.status_code)
        print(response.text)
        return None
    data = response.json()
    return data.get('access_token')


def revoke_token(site, token):
    mast_app = MastodonApplication.objects.get(domain_name=site)

    payload = {
        'client_id': mast_app.client_id,
        'client_secret': mast_app.client_secret,
        'token': token
    }

    if mast_app.is_proxy:
        url = 'https://' + mast_app.proxy_to + API_REVOKE_TOKEN
    else:
        url = 'https://' + site + API_REVOKE_TOKEN
    post(url, data=payload, headers={'User-Agent': 'NeoDB/1.0'})


class OAuth2Backend(ModelBackend):
    """ Used to glue OAuth2 and Django User model """
    # "authenticate() should check the credentials it gets and returns
    #  a user object that matches those credentials."
    # arg request is an interface specification, not used in this implementation

    def authenticate(self, request, token=None, username=None, site=None, **kwargs):
        """ when username is provided, assume that token is newly obtained and valid """
        if token is None or site is None:
            return

        if username is None:
            code, user_data = verify_account(site, token)
            if code == 200:
                userid = user_data['id']
            else:
                # aquiring user data fail means token is invalid thus auth fail
                return None

        # when username is provided, assume that token is newly obtained and valid
        try:
            user = UserModel._default_manager.get(mastodon_id=userid, mastodon_site=site)
        except UserModel.DoesNotExist:
            return None
        else:
            if self.user_can_authenticate(user):
                return user
            return None
