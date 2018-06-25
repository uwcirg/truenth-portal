# test plugin
# https://docs.pytest.org/en/latest/writing_plugins.html#conftest-py-plugins
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--include-ui-testing",
        action="store_true",
        default=False,
        help="run selenium ui tests",
    )
