import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
from unittest.mock import MagicMock
from request_cns_test import request_cns_remote_test

@pytest.mark.unit
def test_request_cns_remote_test_does_not_ping_real_site():
    # Patch Playwright and all browser/page methods with MagicMock
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()

    # Set up the mock object hierarchy
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    # Call the function with dummy data
    request_cns_remote_test(mock_playwright, "testsubject", "1990", "test@example.com")

    # Assert that the page.goto was called with the expected URL (but not actually executed)
    mock_page.goto.assert_any_call("https://www.cnsvs.com/")
    # Optionally, check other calls for coverage
    assert mock_page.locator.call_count > 0
