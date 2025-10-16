# conftest.py

import json
import os
import platform
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
import pprint

import pytest

TEST_DATA = {}
PROBLEMATIC_TESTS = {}  # Cache for problematic tests: {test_fqn: [exception_messages]}


def fetch_problematic_tests():
    """Fetch list of problematic tests with their expected exceptions from CI Viz service."""
    global PROBLEMATIC_TESTS  # noqa: PLW0602

    ci_viz_url = os.environ.get("CI_VIZ_URL", "http://localhost:8000")

    # Get git info to filter problematic tests by repo and branch
    git_info = get_git_info()
    git_repository_url = git_info.get("git_repository_url")
    git_branch = git_info.get("git_branch")

    # Skip if we don't have git info or if it's unknown
    if not git_repository_url or git_repository_url == "unknown":
        return  # No repository info available, can't filter problematic tests

    if not git_branch or git_branch == "unknown":
        return  # No branch info available, can't filter problematic tests

    try:
        # Build URL with query parameters
        params = {
            "git_repository_url": git_repository_url,
            "git_branch": git_branch,
            "detailed": "false",  # We need test FQNs with expected exceptions
            "days": os.environ.get("CI_VIZ_PROBLEMATIC_DAYS", "7"),
            "min_runs": os.environ.get("CI_VIZ_MIN_RUNS", "3"),
        }

        query_string = urllib.parse.urlencode(params)
        url = f"{ci_viz_url}/api/v1/problematic-tests?{query_string}"

        req = urllib.request.Request(url, method="GET")

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                # Now we get a dict mapping test_fqn to list of expected exceptions
                problematic_tests_dict = data.get("problematic_tests", {})
                PROBLEMATIC_TESTS.update(problematic_tests_dict)
            # Non-200 responses are silently ignored

    except urllib.error.URLError:
        # Don't fail the test run if CI Viz is unavailable
        pass
    except (urllib.error.HTTPError, json.JSONDecodeError, ValueError):
        # Don't fail the test run if CI Viz has issues
        pass


def pytest_sessionstart(session):  # noqa: ARG001
    """Capture session start info and fetch problematic tests."""
    global TEST_DATA  # noqa: PLW0603

    # Fetch problematic tests first
    fetch_problematic_tests()

    TEST_DATA = {
        "session_id": str(uuid.uuid4()),
        "session_start_time": datetime.now(UTC).isoformat(),
        "git_info": get_git_info(),
        "environment": get_environment_info(),
        "ci_info": get_ci_info(),
        "test_results": [],
    }


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Mark test as xfail if it fails with an expected exception.
    
    This hook is called after the test runs, so we can inspect the actual exception.
    Only mark as xfail if the exception matches one of the expected exceptions for this test.
    """
    # Let pytest generate the report first
    outcome = yield
    report = outcome.get_result()
    
    # Only process test call phase (not setup or teardown)
    if report.when != "call":
        return
    
    # Only process if test failed
    if not report.failed:
        return
    
    test_fqn = item.nodeid
    
    # Check if this test is in our problematic tests list
    expected_exceptions = PROBLEMATIC_TESTS.get(test_fqn, [])
    if not expected_exceptions:
        return  # Not a problematic test, let it fail normally
    
    # Get the actual exception traceback as a string
    actual_exception = str(report.longrepr) if report.longrepr else ""
    
    # Check if the actual exception matches any of the expected exceptions
    for expected_exception in expected_exceptions:
        if expected_exception in actual_exception or actual_exception in expected_exception:
            # This is an expected failure! Mark it as xfail
            report.outcome = "skipped"
            report.wasxfail = f"Test failed with expected exception (known flaky/problematic test tracked by CI Viz)"
            return
    
    # If we get here, the test failed with a DIFFERENT exception than expected
    # This is a REAL failure that should fail the build!
    # Do nothing and let pytest report it as a normal failure


def pytest_runtest_logreport(report):
    """Capture individual test results."""
    if report.when == "call":  # Only capture the main test execution
        # Check if this test was marked as problematic by CI Viz
        was_marked_problematic = report.nodeid in PROBLEMATIC_TESTS

        # Determine the actual test status
        # pytest reports xfailed tests as "skipped" with wasxfail attribute
        # and xpassed tests as "passed" with wasxfail attribute
        if hasattr(report, "wasxfail"):
            if report.outcome == "skipped":
                test_status = "xfailed"  # Expected to fail and did fail
            elif report.outcome == "passed":
                test_status = "xpassed"  # Expected to fail but passed!
            else:
                test_status = map_pytest_outcome(report.outcome)
        else:
            test_status = map_pytest_outcome(report.outcome)

        test_result = {
            "test_id": report.nodeid,
            "test_name": report.nodeid.split("::")[-1],
            "test_fqn": report.nodeid,
            "test_module": report.nodeid.split("::")[0]
            .replace("/", ".")
            .replace(".py", ""),
            "test_suite": (
                report.nodeid.split("::")[1] if "::" in report.nodeid else None
            ),
            "test_status": test_status,
            "test_message": str(report.longrepr) if report.failed else None,
            "test_traceback": str(report.longrepr) if report.failed else None,
            "test_total_duration": report.duration,
            "test_call_duration": report.duration,
            "test_start_time": datetime.now(UTC).isoformat(),
            "test_file_path": str(report.fspath) if hasattr(report, "fspath") else None,
            "test_line_number": report.location[1] if report.location else None,
            "was_marked_problematic": was_marked_problematic,  # Track if CI Viz marked this as problematic
        }
        TEST_DATA["test_results"].append(test_result)


def pytest_sessionfinish(session):  # noqa: ARG001
    """Send data to CI Viz at session end."""
    end = datetime.now(UTC)
    TEST_DATA["session_end_time"] = end.isoformat()

    # Calculate total duration
    start = datetime.fromisoformat(TEST_DATA["session_start_time"])
    TEST_DATA["session_total_duration"] = (end - start).total_seconds()

    # pprint.pprint(TEST_DATA)
    send_to_ci_viz(TEST_DATA)


def get_git_info():
    """Extract git information."""
    try:
        return {
            "git_repository_url": subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"]
            )
            .decode()
            .strip(),
            "git_branch": subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"]
            )
            .decode()
            .strip(),
            "git_commit_hash": subprocess.check_output(["git", "rev-parse", "HEAD"])
            .decode()
            .strip(),
            "git_commit_message": subprocess.check_output(
                ["git", "log", "-1", "--pretty=%B"]
            )
            .decode()
            .strip(),
            "git_commit_author": subprocess.check_output(
                ["git", "log", "-1", "--pretty=%an"]
            )
            .decode()
            .strip(),
            "git_commit_author_email": subprocess.check_output(
                ["git", "log", "-1", "--pretty=%ae"]
            )
            .decode()
            .strip(),
            "git_commit_timestamp": subprocess.check_output(
                ["git", "log", "-1", "--pretty=%aI"]
            )
            .decode()
            .strip(),
        }
    except (subprocess.CalledProcessError, FileNotFoundError, UnicodeDecodeError):
        return {
            "git_repository_url": "unknown",
            "git_branch": "unknown",
            "git_commit_hash": "unknown",
        }


def get_environment_info():
    """Extract environment information."""
    return {
        "env_python_version": sys.version.split()[0],
        "env_platform": platform.system().lower(),
        "env_architecture": platform.machine(),
        "env_dependencies": [],  # Could be enhanced to read requirements
        "env_vars": {
            "CI": os.environ.get("CI", "false"),
            "CI_PROVIDER": os.environ.get("GITHUB_ACTIONS", "unknown"),
        },
    }


def get_ci_info():
    """Extract CI system information."""
    ci_info = {}

    # GitHub Actions
    if os.environ.get("GITHUB_ACTIONS"):
        ci_info = {
            "ci_system": "GitHub Actions",
            "ci_job_url": f"https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}",
            "ci_pipeline_url": f"https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions",
            "ci_job_id": os.environ.get("GITHUB_RUN_ID"),
            "ci_pipeline_id": os.environ.get("GITHUB_RUN_NUMBER"),
            "ci_trigger": os.environ.get("GITHUB_EVENT_NAME"),
            "ci_pull_request_number": int(os.environ.get("GITHUB_PR_NUMBER", 0))
            or None,
        }

    # Jenkins
    elif os.environ.get("JENKINS_URL"):
        ci_info = {
            "ci_system": "Jenkins",
            "ci_job_url": os.environ.get("BUILD_URL"),
            "ci_pipeline_url": os.environ.get("JOB_URL"),
            "ci_job_id": os.environ.get("BUILD_ID"),
            "ci_pipeline_id": os.environ.get("BUILD_NUMBER"),
            "ci_trigger": "unknown",
        }

    # CircleCI
    elif os.environ.get("CIRCLECI"):
        ci_info = {
            "ci_system": "CircleCI",
            "ci_job_url": os.environ.get("CIRCLE_BUILD_URL"),
            "ci_job_id": os.environ.get("CIRCLE_BUILD_NUM"),
            "ci_trigger": "unknown",
        }

    return ci_info


def map_pytest_outcome(outcome):
    """Map pytest outcomes to CI Viz status."""
    mapping = {
        "passed": "passed",
        "failed": "failed",
        "skipped": "skipped",
        "error": "error",
        "xfailed": "xfailed",  # Expected failure that failed (marked as problematic)
        "xpassed": "xpassed",  # Expected failure that passed (test improved!)
    }
    return mapping.get(outcome, "error")


def send_to_ci_viz(data):
    """Send test session data to CI Viz."""
    ci_viz_url = os.environ.get("CI_VIZ_URL", "http://localhost:8000")

    try:
        # Convert session data to individual test results
        test_results = [
            {
                # Test identification
                "test_id": test_result["test_id"],
                "test_name": test_result["test_name"],
                "test_fqn": test_result["test_fqn"],
                "test_module": test_result["test_module"],
                "test_suite": test_result.get("test_suite"),
                "test_file_path": test_result.get("test_file_path"),
                "test_line_number": test_result.get("test_line_number"),
                # Test execution
                "test_status": test_result["test_status"],
                "test_message": test_result.get("test_message"),
                "test_traceback": test_result.get("test_traceback"),
                "test_total_duration": test_result["test_total_duration"],
                "test_call_duration": test_result["test_call_duration"],
                "test_start_time": test_result["test_start_time"],
                "was_marked_problematic": test_result.get(
                    "was_marked_problematic", False
                ),
                # Session information
                "session_id": data["session_id"],
                "session_start_time": data["session_start_time"],
                "session_end_time": data["session_end_time"],
                "session_total_duration": data["session_total_duration"],
                # Git information
                "git_repository_url": data["git_info"].get("git_repository_url"),
                "git_branch": data["git_info"].get("git_branch"),
                "git_commit_hash": data["git_info"].get("git_commit_hash"),
                "git_commit_message": data["git_info"].get("git_commit_message"),
                "git_commit_author": data["git_info"].get("git_commit_author"),
                "git_commit_author_email": data["git_info"].get(
                    "git_commit_author_email"
                ),
                "git_commit_timestamp": data["git_info"].get("git_commit_timestamp"),
                # Environment information
                "env_python_version": data["environment"].get("env_python_version"),
                "env_platform": data["environment"].get("env_platform"),
                "env_architecture": data["environment"].get("env_architecture"),
                "env_dependencies": json.dumps(
                    data["environment"].get("env_dependencies", [])
                ),
                "env_vars": json.dumps(data["environment"].get("env_vars", {})),
                # CI information
                "ci_system": data["ci_info"].get("ci_system"),
                "ci_job_url": data["ci_info"].get("ci_job_url"),
                "ci_pipeline_url": data["ci_info"].get("ci_pipeline_url"),
                "ci_job_id": data["ci_info"].get("ci_job_id"),
                "ci_pipeline_id": data["ci_info"].get("ci_pipeline_id"),
                "ci_trigger": data["ci_info"].get("ci_trigger"),
                "ci_pull_request_number": data["ci_info"].get("ci_pull_request_number"),
            }
            for test_result in data["test_results"]
        ]

        # Prepare request
        url = f"{ci_viz_url}/api/v1/ingest-test-results/"
        json_data = json.dumps(test_results).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=json_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        urllib.request.urlopen(req, timeout=30).close()

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        ValueError,
    ):
        # Don't fail the test run if CI Viz is unavailable
        pass

