from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseBadRequest
from .models import *
from .forms import *


@login_required
def create(request):
    if request.method == 'GET':
        form = BookForm()
        return render(
            request,
            'books/create_update.html',
            {
                'form': form,
                'title': _('添加书籍')
            }
        )
    elif request.method == 'POST':
        # check user credential in post data, must be the login user
        pass
        form = BookForm(request.POST)
        if form.is_valid():
            form.instance.last_editor = request.user
            form.save()
        
        return redirect(reverse("books:retrieve", args=[form.instance.id]))
    else:
        return HttpResponseBadRequest()


@login_required
def retrieve(request, id):
    if request.method == 'GET':
        book = get_object_or_404(Book, pk=id)
        return render(
            request,
            'books/detail.html',
            {
                'book': book,
            }
        )
    else:
        return HttpResponseBadRequest()