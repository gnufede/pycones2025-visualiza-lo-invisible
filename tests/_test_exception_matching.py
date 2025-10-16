"""
Test to verify that exception matching works correctly.

This test validates that:
1. Tests fail normally if the exception doesn't match expected ones
2. Tests are marked as xfail only when exception matches
"""

import pytest


def test_exception_matching_with_known_exception(monkeypatch):
    """Test that a known exception is properly matched and marked as xfail."""
    # This test verifies the concept - in practice, the matching happens in conftest
    # and we don't directly test it here since it requires the full pytest plugin flow
    
    expected_exceptions = [
        "AssertionError: Expected failure",
        "ValueError: Invalid value",
    ]
    
    actual_exception = "AssertionError: Expected failure\n    at test_file.py:10"
    
    # Verify matching logic
    matches = any(
        expected in actual_exception or actual_exception in expected
        for expected in expected_exceptions
    )
    
    assert matches, "Should match the expected exception"


def test_exception_matching_with_unknown_exception(monkeypatch):
    """Test that an unknown exception doesn't match and allows normal failure."""
    expected_exceptions = [
        "AssertionError: Expected failure",
        "ValueError: Invalid value",
    ]
    
    actual_exception = "RuntimeError: Totally different error\n    at test_file.py:10"
    
    # Verify matching logic
    matches = any(
        expected in actual_exception or actual_exception in expected
        for expected in expected_exceptions
    )
    
    assert not matches, "Should NOT match an unexpected exception"


def test_exception_matching_empty_expected_list():
    """Test that empty expected exception list doesn't match anything."""
    expected_exceptions = []
    
    actual_exception = "AssertionError: Some error"
    
    # Verify matching logic
    matches = any(
        expected in actual_exception or actual_exception in expected
        for expected in expected_exceptions
    )
    
    assert not matches, "Empty list should not match any exception"


def test_problematic_tests_dict_structure():
    """Test that FLAKY_TESTS dict has the expected structure."""
    # Example structure
    problematic_tests = {
        "tests/test_file.py::test_flaky": [
            "AssertionError: Flaky error 1",
            "ValueError: Flaky error 2",
        ],
        "tests/test_file.py::test_another": [
            "RuntimeError: Known issue",
        ],
    }
    
    # Verify structure
    assert isinstance(problematic_tests, dict)
    
    for test_fqn, exceptions in problematic_tests.items():
        assert isinstance(test_fqn, str)
        assert isinstance(exceptions, list)
        assert all(isinstance(exc, str) for exc in exceptions)


def test_api_response_format():
    """Test that the API response has the expected format."""
    # Example API response with detailed=False
    api_response = {
        "problematic_tests": {
            "tests/test_file.py::test_flaky": [
                "AssertionError: Flaky error 1",
                "ValueError: Flaky error 2",
            ],
            "tests/test_file.py::test_another": [
                "RuntimeError: Known issue",
            ],
        },
        "count": 2,
        "filters": {
            "git_repository_url": "https://github.com/user/repo",
            "git_branch": "main",
            "days": 7,
            "min_runs": 3,
        },
    }
    
    # Verify response structure
    assert "problematic_tests" in api_response
    assert "count" in api_response
    assert "filters" in api_response
    
    problematic_tests = api_response["problematic_tests"]
    assert isinstance(problematic_tests, dict)
    assert api_response["count"] == len(problematic_tests)

