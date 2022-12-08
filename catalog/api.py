from ninja import NinjaAPI
from .models import Podcast
from django.conf import settings


api = NinjaAPI(title=settings.SITE_INFO['site_name'], version="1.0.0", description=settings.SITE_INFO['site_name'])

        
@api.get("/podcasts/{item_id}")
def get_item(request, item_id: int):
    return Podcast.objects.filter(pk=item_id).first()
