import logging
from django.utils import timezone
import uuid


_logger = logging.getLogger(__name__)


DEFAULT_ITEM_COVER = "item/default.svg"


def resource_cover_path(resource, filename):
    fn = (
        timezone.now().strftime("%Y/%m/%d/")
        + str(uuid.uuid4())
        + "."
        + filename.split(".")[-1]
    )
    return "item/" + resource.id_type + "/" + fn


def item_cover_path(item, filename):
    fn = (
        timezone.now().strftime("%Y/%m/%d/")
        + str(uuid.uuid4())
        + "."
        + filename.split(".")[-1]
    )
    return "item/" + item.category + "/" + fn
