"""
Demo tests to showcase the CI visibility system.
"""
import time
import random


def test_always_pass():
    """A test that always passes."""
    assert 1 + 1 == 2


def test_sometimes_flaky():
    """A test that sometimes fails to demonstrate flaky test detection."""
    # Simulate flakiness - fails ~30% of the time
    if random.random() < 0.3:
        assert False, "Simulated flaky failure"
    assert True


def test_slow_operation():
    """A test that takes some time to complete."""
    # Simulate some work
    time.sleep(0.1)
    assert "hello" in "hello world"


def test_with_traceback():
    """A test that fails with a specific traceback."""
    try:
        result = 10 / 0
        assert result > 0
    except ZeroDivisionError as e:
        # Re-raise to create a consistent traceback pattern
        raise AssertionError("Division by zero error in calculation") from e


class TestSuite:
    """A test suite to demonstrate test organization."""
    
    def test_suite_method_1(self):
        """First test in the suite."""
        assert len("test") == 4
    
    def test_suite_method_2(self):
        """Second test in the suite."""
        assert "python" != "java"
    
    def test_potentially_dependent(self):
        """A test that might be affected by test execution order."""
        # This could fail if some global state is modified
        assert hasattr(self, '__class__')
