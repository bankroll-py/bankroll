from enum import unique
from peewee import Model, SqliteDatabase, BlobField, CharField, DateField, DecimalField, ForeignKeyField, TextField
from playhouse.fields import PickleField
from typing import Mapping

import bankroll.configuration as configuration


@unique
class Settings(configuration.Settings):
    DATABASE = 'database'

    @property
    def help(self) -> str:
        if self == self.DATABASE:
            return "A local path to a SQLite database to use for the trade journal. If a database does not already exist at this location, one will be created."
        else:
            return ""

    @classmethod
    def sectionName(cls) -> str:
        return 'Journal'


_database = SqliteDatabase(None)


class _BaseModel(Model):  # type: ignore
    class Meta:
        database = _database


class Entry(_BaseModel):
    underlying = CharField()
    text = TextField()
    maxProfit = DecimalField()
    maxLoss = DecimalField()
    realizedProfit = DecimalField()


# Represents a serialized bankroll.model.Activity, so we can link trades and journal entries.
class Activity(_BaseModel):
    pickled = PickleField(null=False)
    journalEntry = ForeignKeyField(Entry, backref='activities')


def openDatabase(settings: Mapping[Settings, str]) -> None:
    _database.init(settings[Settings.DATABASE])
    _database.connect()
    _database.create_tables([Entry, Activity])