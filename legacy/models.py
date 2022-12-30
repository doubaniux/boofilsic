from django.db import models


class BookLink(models.Model):
    old_id = models.IntegerField(db_index=True)
    new_uid = models.UUIDField()


class MovieLink(models.Model):
    old_id = models.IntegerField(db_index=True)
    new_uid = models.UUIDField()


class AlbumLink(models.Model):
    old_id = models.IntegerField(db_index=True)
    new_uid = models.UUIDField()


class SongLink(models.Model):
    old_id = models.IntegerField(db_index=True)
    new_uid = models.UUIDField()


class GameLink(models.Model):
    old_id = models.IntegerField(db_index=True)
    new_uid = models.UUIDField()
