# conftest.py

import json
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, UTC
import subprocess
import os
import sys
import platform
import pprint

TEST_DATA = {}


def pytest_sessionstart(session):
    """Capture session start info."""
    global TEST_DATA
    TEST_DATA = {
        "session_id": str(uuid.uuid4()),
        "session_start_time": datetime.now(UTC).isoformat(),
        "git_info": get_git_info(),
        "environment": get_environment_info(),
        "ci_info": get_ci_info(),
        "test_results": [],
    }


def pytest_runtest_logreport(report):
    """Capture individual test results."""
    if report.when == "call":  # Only capture the main test execution
        test_result = {
            "test_id": report.nodeid,
            "test_name": report.nodeid.split("::")[-1],
            "test_fqn": report.nodeid,
            "test_module": report.nodeid.split("::")[0].replace("/", ".").replace(".py", ""),
            "test_suite": report.nodeid.split("::")[1] if "::" in report.nodeid else None,
            "test_status": map_pytest_outcome(report.outcome),
            "test_message": str(report.longrepr) if report.failed else None,
            "test_traceback": str(report.longrepr) if report.failed else None,
            "test_total_duration": report.duration,
            "test_call_duration": report.duration,
            "test_start_time": datetime.now(UTC).isoformat(),
            "test_file_path": str(report.fspath) if hasattr(report, "fspath") else None,
            "test_line_number": report.location[1] if report.location else None,
        }
        TEST_DATA["test_results"].append(test_result)


def pytest_sessionfinish(session):
    """Send data to CI Viz at session end."""
    end = datetime.now(UTC)
    TEST_DATA["session_end_time"] = end.isoformat()

    # Calculate total duration
    start = datetime.fromisoformat(TEST_DATA["session_start_time"])
    TEST_DATA["session_total_duration"] = (end - start).total_seconds()

    send_to_ci_viz(TEST_DATA)


def get_git_info():
    """Extract git information."""
    try:
        return {
            "git_repository_url": subprocess.check_output(["git", "config", "--get", "remote.origin.url"])
            .decode()
            .strip(),
            "git_branch": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip(),
            "git_commit_hash": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
            "git_commit_message": subprocess.check_output(["git", "log", "-1", "--pretty=%B"]).decode().strip(),
            "git_commit_author": subprocess.check_output(["git", "log", "-1", "--pretty=%an"]).decode().strip(),
            "git_commit_author_email": subprocess.check_output(["git", "log", "-1", "--pretty=%ae"]).decode().strip(),
            "git_commit_timestamp": subprocess.check_output(["git", "log", "-1", "--pretty=%aI"]).decode().strip(),
        }
    except Exception:
        return {"git_repository_url": "unknown", "git_branch": "unknown", "git_commit_hash": "unknown"}


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
            "ci_pull_request_number": int(os.environ.get("GITHUB_PR_NUMBER", 0)) or None,
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
    mapping = {"passed": "passed", "failed": "failed", "skipped": "skipped", "error": "error"}
    return mapping.get(outcome, "error")


def send_to_ci_viz(data):
    """Send test session data to CI Viz."""
    ci_viz_url = os.environ.get('CI_VIZ_URL', 'http://localhost:8000')
    
    # Print data for debugging (can be disabled with env var)
    if os.environ.get('CI_VIZ_DEBUG', 'true').lower() == 'true':
        print("📊 Test session data:")
        pprint.pprint(data)

    try:
        # Convert session data to individual test results
        test_results = []
        for test_result in data["test_results"]:
            test_results.append({
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
                "git_commit_author_email": data["git_info"].get("git_commit_author_email"),
                "git_commit_timestamp": data["git_info"].get("git_commit_timestamp"),
                
                # Environment information
                "env_python_version": data["environment"].get("env_python_version"),
                "env_platform": data["environment"].get("env_platform"),
                "env_architecture": data["environment"].get("env_architecture"),
                "env_dependencies": json.dumps(data["environment"].get("env_dependencies", [])),
                "env_vars": json.dumps(data["environment"].get("env_vars", {})),
                
                # CI information
                "ci_system": data["ci_info"].get("ci_system"),
                "ci_job_url": data["ci_info"].get("ci_job_url"),
                "ci_pipeline_url": data["ci_info"].get("ci_pipeline_url"),
                "ci_job_id": data["ci_info"].get("ci_job_id"),
                "ci_pipeline_id": data["ci_info"].get("ci_pipeline_id"),
                "ci_trigger": data["ci_info"].get("ci_trigger"),
                "ci_pull_request_number": data["ci_info"].get("ci_pull_request_number"),
            })

        # Prepare request
        url = f"{ci_viz_url}/api/v1/ingest-test-results/"
        json_data = json.dumps(test_results).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=json_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status == 200:
                print(f"✅ Test results sent to CI Viz: {response.status}")
            else:
                print(f"⚠️ CI Viz returned status: {response.status}")
                
    except urllib.error.URLError as e:
        if isinstance(e, urllib.error.ConnectionRefusedError):
            print(f"⚠️ CI Viz service not available at {ci_viz_url}")
            print("💡 Start the service with: hatch run python -m ci_viz_simple.main")
        else:
            print(f"⚠️ Failed to connect to CI Viz: {e}")
        # Don't fail the test run if CI Viz is unavailable
    except Exception as e:
        print(f"⚠️ Failed to send results to CI Viz: {e}")
        # Don't fail the test run if CI Viz is unavailable
