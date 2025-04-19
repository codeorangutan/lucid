import sys
import importlib
import pkg_resources

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

def test_required_packages_installed():
    required = [
        'google-auth',
        'google-auth-oauthlib',
        'google-auth-httplib2',
        'google-api-python-client',
        # add any other core dependencies for your app here
    ]
    for pkg in required:
        try:
            pkg_resources.get_distribution(pkg)
        except pkg_resources.DistributionNotFound:
            assert False, f"{pkg} is not installed!"
