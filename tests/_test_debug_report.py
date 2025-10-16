"""Debug test to see what pytest report contains."""
import pytest


def test_normal_pass():
    """A test that always passes."""
    assert True


@pytest.mark.xfail(reason="Expected to fail", strict=False)
def test_xfail_that_fails():
    """A test marked xfail that actually fails."""
    raise AssertionError


@pytest.mark.xfail(reason="Expected to fail", strict=False)
def test_xfail_that_passes():
    """A test marked xfail that actually passes (xpass)."""
    assert True



