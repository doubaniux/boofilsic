import logging
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _

_logger = logging.getLogger(__name__)


@login_required
def home(request):
    if request.user.get_preference().classic_homepage:
        return redirect(reverse("journal:home", args=[request.user.mastodon_username]))
    else:
        return redirect(reverse("social:feed"))
