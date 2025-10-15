"""
Integration test for CI Viz problematic test detection.

This test validates the complete feedback loop:
1. Tests run and send data to CI Viz
2. CI Viz identifies problematic tests
3. Pytest plugin marks problematic tests as xfail
4. Tests are tracked with xfailed/xpassed statuses
"""

import contextlib
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def backup_database():
    """Backup the existing database."""
    db_path = Path(__file__).parent.parent / "src" / "ci_viz_simple" / "ci_viz.db"
    backup_path = db_path.with_suffix(".db.backup")

    if db_path.exists():
        shutil.copy2(db_path, backup_path)
        db_path.unlink()
    else:
        pass

    return backup_path


def restore_database(backup_path):
    """Restore the backed up database."""
    db_path = Path(__file__).parent.parent / "src" / "ci_viz_simple" / "ci_viz.db"

    # Remove the test database
    if db_path.exists():
        db_path.unlink()

    # Restore backup if it exists
    if backup_path and backup_path.exists():
        shutil.copy2(backup_path, db_path)
        backup_path.unlink()
    else:
        pass


def is_server_running():
    """Check if the CI Viz server is running."""
    try:
        req = urllib.request.Request("http://localhost:8000/health")
        with urllib.request.urlopen(req, timeout=2):
            return True
    except (urllib.error.URLError, urllib.error.HTTPError):
        return False


def start_server():
    """Start the CI Viz server."""

    # Start server in background
    process = subprocess.Popen(
        [sys.executable, "-m", "ci_viz_simple.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent,
    )

    # Wait for server to be ready (max 1 seconds)
    for _i in range(50):
        time.sleep(0.02)
        if is_server_running():
            return process

    # Server didn't start
    stdout, stderr = process.communicate(timeout=1)
    msg = "Failed to start CI Viz server"
    raise RuntimeError(msg)


def stop_server(process):
    """Stop the CI Viz server."""
    if process:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run_tests():
    """Run the test suite."""

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_demo.py",
            "tests/test_problematic_integration.py",
            "-vv",
            "--tb=short",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    # Count outcomes
    passed = result.stdout.count(" PASSED")
    failed = result.stdout.count(" FAILED")
    xfailed = result.stdout.count(" XFAIL")
    xpassed = result.stdout.count(" XPASS")

    return {
        "passed": passed,
        "failed": failed,
        "xfailed": xfailed,
        "xpassed": xpassed,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def query_test_results():
    """Query the CI Viz API for test results."""
    try:
        # Get all test results
        req = urllib.request.Request(
            "http://localhost:8000/api/v1/test-results/?limit=1000"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("results", [])
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        ValueError,
    ):
        return []


def query_stats():
    """Query the CI Viz API for statistics."""
    try:
        req = urllib.request.Request("http://localhost:8000/api/v1/stats")
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        ValueError,
    ):
        return {}


def analyze_results(results):
    """Analyze the test results."""

    # Count statuses
    status_counts = {}
    marked_problematic_count = 0

    for result in results:
        status = result.get("test_status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

        if result.get("was_marked_problematic"):
            marked_problematic_count += 1

    # for status, _count in sorted(status_counts.items()):
    #     pass

    # Find xfailed and xpassed tests
    xfailed_tests = [r for r in results if r.get("test_status") == "xfailed"]
    xpassed_tests = [r for r in results if r.get("test_status") == "xpassed"]

    # if xfailed_tests:
    #     for _test in xfailed_tests[:5]:  # Show first 5
    #         pass

    # if xpassed_tests:
    #     for _test in xpassed_tests[:5]:  # Show first 5
    #         pass

    return {
        "status_counts": status_counts,
        "marked_problematic_count": marked_problematic_count,
        "xfailed_count": len(xfailed_tests),
        "xpassed_count": len(xpassed_tests),
    }


def verify_integration():
    """
    Verify the integration by checking that:
    1. Tests were marked as problematic
    2. xfailed/xpassed statuses were recorded
    """

    results = query_test_results()
    if not results:
        return False

    analysis = analyze_results(results)

    # Verify we have xfailed or xpassed tests
    has_xfailed = analysis["xfailed_count"] > 0
    has_xpassed = analysis["xpassed_count"] > 0

    # At least one of xfailed or xpassed should be present
    success = has_xfailed or has_xpassed

    print(f"  → xfailed tests: {analysis['xfailed_count']}", flush=True)
    print(f"  → xpassed tests: {analysis['xpassed_count']}", flush=True)
    print(f"  → Marked problematic: {analysis['marked_problematic_count']}", flush=True)
    print(f"  → Total passed: {analysis['status_counts'].get('passed', 0)}", flush=True)
    print(f"  → Total failed: {analysis['status_counts'].get('failed', 0)}", flush=True)

    if success:
        print("  ✓ Found xfailed or xpassed tests\n", flush=True)
    else:
        print("  ✗ No xfailed or xpassed tests found\n", flush=True)

    return success


def main():
    """Main integration test."""
    print("\n" + "=" * 80, flush=True)
    print("CI Viz Integration Test", flush=True)
    print("=" * 80 + "\n", flush=True)

    backup_path = None
    server_process = None

    try:
        # Step 0: Backup database and start fresh
        print("Step 0: Backing up database...", flush=True)
        backup_path = backup_database()
        print(f"  ✓ Backed up to: {backup_path}\n", flush=True)

        # Step 1: Start server if not running
        print("Step 1: Checking server status...", flush=True)
        server_was_running = is_server_running()

        if server_was_running:
            print("  ✓ Server already running\n", flush=True)
        else:
            print("  → Starting server...", flush=True)
            server_process = start_server()
            print("  ✓ Server started\n", flush=True)

        # Verify server is responding
        stats = query_stats()
        print(
            f"  → Server responding with {stats.get('total_tests', 0)} tests\n",
            flush=True,
        )

        # Step 2: Run tests multiple times
        num_iterations = 12
        print(f"Step 2: Running tests {num_iterations} times...", flush=True)

        for i in range(1, num_iterations + 1):
            print(f"\n  → Iteration {i}/{num_iterations}", flush=True)
            print("  " + "-" * 76, flush=True)
            test_result = run_tests()

            # Print pytest output
            if test_result["stdout"]:
                # Print each line with indentation
                for line in test_result["stdout"].split("\n"):
                    if line.strip():  # Skip empty lines
                        print(f"    {line}", flush=True)

            # Print summary
            print(
                f"    Summary: {test_result['passed']} passed, "
                f"{test_result['failed']} failed, "
                f"{test_result['xfailed']} xfailed, "
                f"{test_result['xpassed']} xpassed",
                flush=True,
            )

        print("\n  ✓ All test runs completed\n", flush=True)

        # Step 3: Verify results
        print("Step 3: Verifying results...", flush=True)

        # Get updated stats
        stats = query_stats()
        print(f"  → Total tests in DB: {stats.get('total_tests', 0)}", flush=True)

        # Verify the integration
        success = verify_integration()

        # Step 4: Cleanup
        print("\nStep 4: Cleaning up...", flush=True)
        if server_process:
            print("  → Stopping server...", flush=True)
            stop_server(server_process)
            print("  ✓ Server stopped", flush=True)

        print("  → Restoring database...", flush=True)
        restore_database(backup_path)
        print("  ✓ Database restored\n", flush=True)

        if success:
            print("=" * 80, flush=True)
            print("✓ Integration test PASSED", flush=True)
            print("=" * 80 + "\n", flush=True)
        else:
            print("=" * 80, flush=True)
            print("✗ Integration test FAILED", flush=True)
            print("=" * 80 + "\n", flush=True)

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        ValueError,
        OSError,
    ):
        import traceback

        print("\n" + "=" * 80, flush=True)
        print("✗ Integration test FAILED with exception", flush=True)
        print("=" * 80, flush=True)
        traceback.print_exc()

        # Cleanup on error
        print("\nCleaning up after error...", flush=True)
        if server_process:
            with contextlib.suppress(Exception):
                stop_server(server_process)

        if backup_path:
            with contextlib.suppress(Exception):
                restore_database(backup_path)

        return 1
    else:
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
