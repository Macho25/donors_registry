# -*- coding: utf-8 -*-
"""Defines fixtures available to all tests."""

import logging
from itertools import cycle
from pathlib import Path
from random import sample, shuffle
from shutil import copy
from tempfile import NamedTemporaryFile
from typing import Iterator
from unittest.mock import MagicMock, NonCallableMagicMock, patch

import webtest.app
from flask.app import Flask
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy.extension import SQLAlchemy
from pandas import DataFrame
from pytest import fixture
from sqlalchemy.exc import IntegrityError
from webtest import TestApp

from registry.app import create_app
from registry.donor.models import DonorsOverview, IgnoredDonors, Note
from registry.extensions import db as _db
from registry.user.models import User
from tests.utils import (
    get_test_data_df,
    test_data_ignored,
    test_data_medals,
    test_data_notes,
    test_data_overrides,
    test_data_records,
)

TEST_RECORDS = 1000  # Number of test imports to use in test database
BACKUP_DB_PATH = Path("instance") / "backup.sqlite"
TEST_DB_PATH = Path("instance") / "test.sqlite"


@fixture(scope="session")
def app() -> Iterator[Flask]:
    """Create application for the tests."""
    _app = create_app("tests.settings")
    _app.logger.setLevel(logging.CRITICAL)
    ctx = _app.test_request_context()
    ctx.push()

    yield _app

    ctx.pop()


@fixture
def testapp(app: Flask) -> webtest.app.TestApp:
    """Create Webtest app."""
    return TestApp(app)


@fixture(scope="function", autouse=True)
def db(app: Flask) -> Iterator[SQLAlchemy]:
    """Create database for the tests."""
    _db.app = app

    # If the backup db exists, use it
    # if not, create it from scratch and save it for other tests
    if BACKUP_DB_PATH.is_file():
        copy(BACKUP_DB_PATH, TEST_DB_PATH)
    else:
        with app.app_context():
            migrate = Migrate()
            migrate.init_app(app, _db)
            upgrade()

        test_data_records(_db, limit=TEST_RECORDS)
        test_data_medals(_db)
        test_data_overrides(_db)
        test_data_ignored(_db, limit=3)
        test_data_notes(_db)

        DonorsOverview.refresh_overview()

        copy(TEST_DB_PATH, BACKUP_DB_PATH)

    yield _db

    # Explicitly close DB connection
    _db.session.close()


@fixture(scope="function")
def user(db: SQLAlchemy) -> User:
    """Create user for the tests."""
    user = User("test@example.com", "test123")
    user.test_password = "test123"
    user.active = True
    db.session.add(user)
    # The user might already exists in the db and we cannot
    # combine session-scoped and function-scoped fixtures
    # so we have to be ready for that situation.
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return user


@fixture(scope="session")
def test_data_df() -> DataFrame:
    """The same data we have in test database but in form of Pandas DataFrame"""
    return get_test_data_df(TEST_RECORDS)


def sample_of_rc(amount: int = 100) -> Iterator[str]:
    """Yields random sample of RC from test data"""
    test_data = get_test_data_df(TEST_RECORDS)
    dcs = test_data.MISTO_ODBERU.unique()
    shuffle(dcs)
    dcs = cycle(dcs)

    for _ in range(amount):
        dc = next(dcs)
        yield sample(list(test_data[test_data.MISTO_ODBERU == dc].RC.unique()), 1)[0]


def new_rc_if_ignored(rodne_cislo: str) -> str:
    while True:
        if _db.session.get(IgnoredDonors, rodne_cislo):
            rodne_cislo = next(sample_of_rc(1))
            continue
        return rodne_cislo


@fixture(scope="session", autouse=True)
def empty_stamp_png() -> Iterator[None]:
    with NamedTemporaryFile(
        dir="registry/static/stamps", suffix=".png"
    ), NamedTemporaryFile(dir="registry/static/signatures", suffix=".png"):
        yield


@fixture
def mock_smtp() -> Iterator[NonCallableMagicMock]:
    with patch("smtplib.SMTP", autospec=True) as mock_smtp_class:
        mock_instance = mock_smtp_class.return_value
        mock_instance.send_message = MagicMock()
        yield mock_instance


def delete_note_if_exists(rodne_cislo: str) -> None:
    if (note := _db.session.get(Note, rodne_cislo)) is not None:
        _db.session.delete(note)
        _db.session.commit()
