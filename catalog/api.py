from ninja import NinjaAPI
from .models import *
from .common import *
from .sites import *
from django.conf import settings
from datetime import date
from ninja import Schema
from typing import List, Optional
from django.utils.baseconv import base62
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import Http404

api = NinjaAPI(
    title=settings.SITE_INFO["site_name"],
    version="1.0.0",
    description=f"{settings.SITE_INFO['site_name']} API <hr/><a href='{settings.APP_WEBSITE}'>Learn more</a>",
)


class ItemIn(Schema):
    title: str
    brief: str


class ItemOut(Schema):
    uuid: str
    title: str
    brief: str
    url: str
    api_url: str
    category: str


class EditionIn(ItemIn):
    subtitle: str = None
    orig_title: str = None
    author: list[str]
    translator: list[str]
    language: str = None
    pub_house: str = None
    pub_year: int = None
    pub_month: int = None
    binding: str = None
    price: str = None
    pages: str = None
    series: str = None
    imprint: str = None


class EditionOut(ItemOut):
    subtitle: str = None
    orig_title: str = None
    author: list[str]
    translator: list[str]
    language: str = None
    pub_house: str = None
    pub_year: int = None
    pub_month: int = None
    binding: str = None
    price: str = None
    pages: str = None
    series: str = None
    imprint: str = None


@api.post("/catalog/fetch", response=ItemOut)
def fetch_item(request, url: str):
    site = SiteManager.get_site_by_url(url)
    if not site:
        return Http404()
    resource = site.get_resource_ready()
    if not resource:
        return Http404()
    return site.get_item()


@api.post("/book/")
def create_edition(request, payload: EditionIn):
    edition = Edition.objects.create(**payload.dict())
    return {"id": edition.uuid}


@api.get("/book/{uuid}/", response=EditionOut)
def get_edition(request, uuid: str):
    edition = get_object_or_404(Edition, uid=base62.decode(uuid))
    return edition


# @api.get("/book", response=List[EditionOut])
# def list_editions(request):
#     qs = Edition.objects.all()
#     return qs


@api.put("/book/{uuid}/")
def update_edition(request, uuid: str, payload: EditionIn):
    edition = get_object_or_404(Item, uid=base62.decode(uuid))
    for attr, value in payload.dict().items():
        setattr(edition, attr, value)
    edition.save()
    return {"success": True}


@api.delete("/book/{uuid}/")
def delete_edition(request, uuid: str):
    edition = get_object_or_404(Edition, uid=base62.decode(uuid))
    edition.delete()
    return {"success": True}
