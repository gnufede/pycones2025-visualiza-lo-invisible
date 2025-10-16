# test_problematic_integration.py

"""
Demo test to show the problematic tests integration feature.

This test will be detected as problematic if it has a history of failures
and will be automatically marked as xfail by the pytest plugin.
"""

import random


def test_flaky_example():
    """A flaky test that sometimes fails to demonstrate the integration."""
    # This test will fail ~30% of the time to simulate flakiness
    # In a real scenario, this would be replaced by actual problematic tests
    if random.random() < 0.3:
        msg = "Simulated flaky test failure"
        raise AssertionError(msg)
    assert True


def test_stable_example():
    """A stable test that should always pass."""
    assert True

