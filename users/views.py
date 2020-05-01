from django.shortcuts import reverse, redirect, render
from django.http import HttpResponseBadRequest, HttpResponse
from django.contrib import auth
from django.contrib.auth import authenticate
from .models import User
from .auth import *
from boofilsic.settings import MASTODON_DOMAIN_NAME, CLIENT_ID, CLIENT_SECRET
from common.mastodon.api import *


# Views
########################################

# no page rendered
def OAuth2_login(request):
    """ oauth authentication and logging user into django system """
    if request.method == 'GET':
        code = request.GET.get('code')
        # Network IO
        token = obtain_token(request, code)
        if token:
            # oauth is completed when token aquired
            user = authenticate(request, token=token)
            if user:
                auth_login(request, user, token)
                return redirect(reverse('common:home'))
            else:
                # will be passed to register page
                request.session['new_user_token'] = token
                return redirect(reverse('users:register'))
        else:
            # TODO better fail result page
            return HttpResponse(content="Authentication failed.")
    else:
        return HttpResponseBadRequest()


# the 'login' page that user can see
def login(request):
    if request.method == 'GET':
        # TODO NOTE replace http with https!!!!
        auth_url = f"https://{MASTODON_DOMAIN_NAME}{OAUTH_AUTHORIZE}?" +\
        f"client_id={CLIENT_ID}&scope=read+write&" +\
        f"redirect_uri=http://{request.get_host()}{reverse('users:OAuth2_login')}" +\
        "&response_type=code"

        return render(
            request,
            'users/login.html',
            {
                'oauth_auth_url': auth_url
            }
        )
    else:
        return HttpResponseBadRequest()


def logout(request):
    if request.method == 'GET':
        revoke_token(request.session['oauth_token'])
        auth_logout(request)
        return redirect(reverse("users:login"))
    else:
        return HttpResponseBadRequest()


def register(request):
    """ register confirm page """
    if request.method == 'GET':
        if request.session.get('oauth_token'):
            return redirect(reverse('common:home'))
        elif request.session.get('new_user_token'):
            return render(
                request,
                'users/register.html'
            )
        else:
            return HttpResponseBadRequest()
    elif request.method == 'POST':
        token = request.session['new_user_token']
        user_data = get_user_data(token)
        new_user = User(
            username=user_data['username'],
            mastodon_id=user_data['id']
        )
        new_user.save()
        del request.session['new_user_token']
        auth_login(request, new_user, token)
        return redirect(reverse('common:home'))
    else:
        return HttpResponseBadRequest()


def delete(request):
    raise NotImplementedError


# Utils
########################################

def auth_login(request, user, token):
    """ Decorates django ``login()``. Attach token to session."""
    request.session['oauth_token'] = token
    auth.login(request, user)


def auth_logout(request):
    """ Decorates django ``logout()``. Release token in session."""
    del request.session['oauth_token']
    auth.logout(request)    