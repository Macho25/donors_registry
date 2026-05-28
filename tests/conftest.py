from _pytest.main import Session
from pytest import ExitCode

from tests.fixtures import (  # noqa: F401
    BACKUP_DB_PATH,
    TEST_DB_PATH,
    app,
    db,
    empty_stamp_png,
    mock_smtp,
    test_data_df,
    testapp,
    user,
)


def pytest_sessionfinish(session: Session, exitstatus: ExitCode) -> None:
    try:
        BACKUP_DB_PATH.unlink()
    except FileNotFoundError:
        pass

    try:
        TEST_DB_PATH.unlink()
    except FileNotFoundError:
        pass
