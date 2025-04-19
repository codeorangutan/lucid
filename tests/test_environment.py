import sys

def test_python_version():
    assert sys.version_info >= (3, 11), f"Python 3.11+ required, found {sys.version}"  # Ensures correct Python version

def test_playwright_installed():
    try:
        import playwright
    except ImportError:
        assert False, "Playwright is not installed!"

def test_pandas_installed():
    try:
        import pandas
    except ImportError:
        assert False, "Pandas is not installed!"

def test_sqlalchemy_installed():
    try:
        import sqlalchemy
    except ImportError:
        assert False, "SQLAlchemy is not installed!"

def test_pycryptodome_installed():
    try:
        import Crypto
    except ImportError:
        assert False, "PyCryptodome is not installed!"
