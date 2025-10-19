"""
CI Test Analysis Queries

This module provides optimized SQL queries for analyzing test failure patterns in CI systems.
The queries are designed to identify common issues like flaky tests, cross-branch failures,
underlying systemic problems, performance regressions, and test order dependencies.

All queries include proper status filtering to handle all test statuses:
- 'passed', 'failed', 'error', 'skipped' - standard pytest outcomes
- 'xfailed', 'xpassed' - expected failure outcomes (tests marked as problematic)
"""

import sqlite3
import typing as t
from datetime import UTC, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "ci_viz.db"

# Valid test statuses for filtering
VALID_STATUSES = ("passed", "failed", "error", "skipped", "xfailed", "xpassed")
FAILURE_STATUSES = (
    "failed",
    "error",
    "xfailed",
)  # xfailed is also a failure (expected)

# Default thresholds for analysis queries
DEFAULT_DAYS_LOOKBACK = 7
DEFAULT_MIN_RUNS = 3
DEFAULT_MIN_OCCURRENCES = 2
DEFAULT_MIN_TESTS = 2
DEFAULT_THRESHOLD_MULTIPLIER = 2.0
DEFAULT_MIN_CORRELATION = 0.7

# Thresholds for confidence scoring
HIGH_CONFIDENCE_MIN_RUNS = 10
HIGH_CONFIDENCE_MIN_SESSIONS = 3
MEDIUM_CONFIDENCE_MIN_RUNS = 5
MEDIUM_CONFIDENCE_MIN_SESSIONS = 2

# Query-specific constants
BASELINE_RUN_COUNT = 5  # Number of runs to use for baseline in time regressions
MIN_BASELINE_RUNS = 3  # Minimum baseline runs required for regression analysis
MIN_TEST_PAIRS = 3  # Minimum observations needed for test order correlation

# Display limits
TRACEBACK_PREVIEW_LENGTH = 200  # Characters to show in traceback previews


def _execute_query(query: str, params: tuple) -> list[tuple]:
    """Execute a query and return results, handling connection lifecycle."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()


def get_flaky_tests(
    git_repository_url: str | None = None,
    git_branch: str | None = None,
) -> list[dict[str, t.Any]]:

    params = list()
    if git_repository_url:
        params.append(git_repository_url)

    if git_branch:
        params.append(git_branch)

    query = """
        SELECT test_fqn,
            GROUP_CONCAT(DISTINCT test_traceback) as expected_exceptions
        FROM test_results
        WHERE git_repository_url = ? AND git_branch = ?
        GROUP BY test_fqn, git_commit_hash
        HAVING SUM(test_status = 'passed') > 0
        AND SUM(test_status = 'failed') > 0
    """
    results = _execute_query(query, tuple(params))

    parsed = []
    for test_fqn, concat in results:
        if not concat:
            exceptions = []
        else:
            # Split on commas (added by GROUP_CONCAT)
            # and restore any commas that were replaced before insert
            exceptions = [t.replace("⸴", ",") for t in concat.split(",")]

        parsed.append(
            {
                "test_fqn": test_fqn,
                "expected_exceptions": exceptions,
            }
        )

    return parsed


def get_failing_tests_across_branches(
    days: int = DEFAULT_DAYS_LOOKBACK,
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
    git_repository_url: str | None = None,
    git_branch: str | None = None,
) -> list[dict[str, t.Any]]:
    """
    Query 2: Failing tests across branches - Tests that fail with the same error
    across multiple branches, indicating a systemic issue.

    This query identifies tests that:
    - Fail with identical tracebacks across different git branches
    - Meet the minimum occurrence threshold
    - Have non-null tracebacks for meaningful error analysis

    Args:
        days: Number of days to look back for test runs
        min_occurrences: Minimum number of failures required to include a test
        git_repository_url: Filter by specific repository (optional)
        git_branch: Filter by specific branch (optional) - Note: for cross-branch analysis, this limits the branches considered

    Returns:
        List of dictionaries containing cross-branch failure information
    """
    date_threshold = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    # Build WHERE clause dynamically based on provided filters
    where_conditions = [
        "test_start_time >= ?",
        "test_status IN ('failed', 'error', 'xfailed')",  # Include xfailed as failures
        "test_traceback IS NOT NULL",
        "test_traceback != ''",
        "git_branch IS NOT NULL",
        "git_branch != 'unknown'",
    ]
    params = [date_threshold]

    if git_repository_url:
        where_conditions.append("git_repository_url = ?")
        params.append(git_repository_url)

    if git_branch:
        where_conditions.append("git_branch = ?")
        params.append(git_branch)

    where_clause = " AND ".join(where_conditions)

    query = f"""
        -- CTE to find tests that fail with the same error across multiple branches
        WITH failing_tests_by_traceback AS (
            SELECT
                test_fqn,                           -- The test that's failing
                test_traceback,                     -- The exact error traceback

                -- Count how many different branches this error affects
                COUNT(DISTINCT git_branch) as affected_branches,

                -- Count total number of failures with this exact traceback
                COUNT(*) as total_failures,

                -- Find when this error first and last occurred
                MIN(test_start_time) as first_failure,
                MAX(test_start_time) as last_failure,

                -- Create a comma-separated list of all affected branches
                GROUP_CONCAT(DISTINCT git_branch) as branch_list

            FROM test_results
            WHERE {where_clause}

            -- GROUP BY test_fqn AND test_traceback means we're grouping by:
            -- "same test failing with identical error message"
            GROUP BY test_fqn, test_traceback

            -- HAVING filters the grouped results
            HAVING affected_branches > 1            -- Must affect more than 1 branch (cross-branch issue)
                AND total_failures >= ?             -- Must meet minimum failure count
        )
        -- Main SELECT: return cross-branch failure information
        SELECT
            test_fqn,
            -- Show only first N characters of traceback for readability (TRACEBACK_PREVIEW_LENGTH)
            SUBSTR(test_traceback, 1, 200) as traceback_preview,
            affected_branches,
            branch_list,
            total_failures,
            first_failure,
            last_failure
        FROM failing_tests_by_traceback
        -- Order by most branches affected first, then by most failures
        ORDER BY affected_branches DESC, total_failures DESC
    """

    # Add min_occurrences to params
    params.append(min_occurrences)

    results = _execute_query(query, tuple(params))

    return [
        {
            "test_fqn": row[0],
            "traceback_preview": row[1],
            "affected_branches": row[2],
            "branch_list": row[3],
            "total_failures": row[4],
            "first_failure": row[5],
            "last_failure": row[6],
        }
        for row in results
    ]


def get_underlying_issues(
    days: int = DEFAULT_DAYS_LOOKBACK,
    min_tests: int = DEFAULT_MIN_TESTS,
    git_repository_url: str | None = None,
    git_branch: str | None = None,
) -> list[dict[str, t.Any]]:
    """
    Query 3: Underlying issues - Common error patterns affecting multiple tests across branches.

    This query identifies systemic issues by finding identical error tracebacks that:
    - Affect multiple different tests (different test_fqn)
    - Occur across multiple git branches
    - Meet the minimum test count threshold

    Such patterns often indicate:
    - Infrastructure problems (database, network, environment)
    - Missing dependencies or configuration issues
    - Shared code defects affecting multiple test modules

    Args:
        days: Number of days to look back for test runs
        min_tests: Minimum number of different tests that must be affected
        git_repository_url: Filter by specific repository (optional)
        git_branch: Filter by specific branch (optional)

    Returns:
        List of dictionaries containing underlying issue information
    """
    date_threshold = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    # Build WHERE clause dynamically based on provided filters
    where_conditions = [
        "test_start_time >= ?",
        "test_status IN ('failed', 'error', 'xfailed')",  # Include xfailed as failures
        "test_traceback IS NOT NULL",
        "test_traceback != ''",
        "git_branch IS NOT NULL",
        "git_branch != 'unknown'",
    ]
    params = [date_threshold]

    if git_repository_url:
        where_conditions.append("git_repository_url = ?")
        params.append(git_repository_url)

    if git_branch:
        where_conditions.append("git_branch = ?")
        params.append(git_branch)

    where_clause = " AND ".join(where_conditions)

    query = f"""
        -- CTE to find common error patterns affecting multiple different tests
        WITH common_failures AS (
            SELECT
                test_traceback,                     -- The error traceback (this is our grouping key)

                -- Count how many DIFFERENT tests are affected by this same error
                COUNT(DISTINCT test_fqn) as affected_tests,

                -- Count how many different branches are affected
                COUNT(DISTINCT git_branch) as affected_branches,

                -- Count total number of failures with this exact traceback
                COUNT(*) as total_failures,

                -- Find when this error pattern first and last occurred
                MIN(test_start_time) as first_occurrence,
                MAX(test_start_time) as last_occurrence,

                -- Create lists of all affected tests and branches
                GROUP_CONCAT(DISTINCT test_fqn) as test_list,
                GROUP_CONCAT(DISTINCT git_branch) as branch_list

            FROM test_results
            WHERE {where_clause}

            -- GROUP BY test_traceback means we're grouping by:
            -- "identical error traceback" (regardless of which test it came from)
            -- This finds systemic issues that affect multiple different tests
            GROUP BY test_traceback

            -- HAVING filters the grouped results
            HAVING affected_tests >= ?              -- Must affect at least min_tests different tests
                AND affected_branches > 1           -- Must affect multiple branches
        )
        -- Main SELECT: return systemic issue information
        SELECT
            -- Show only first N characters of traceback for readability (TRACEBACK_PREVIEW_LENGTH)
            SUBSTR(test_traceback, 1, 200) as traceback_preview,
            affected_tests,                         -- How many different tests are affected
            affected_branches,                      -- How many different branches are affected
            total_failures,                         -- Total number of failures with this error
            test_list,                              -- Comma-separated list of affected tests
            branch_list,                            -- Comma-separated list of affected branches
            first_occurrence,                       -- When this error pattern first appeared
            last_occurrence                         -- When this error pattern last appeared
        FROM common_failures
        -- Order by most tests affected first, then most branches, then most failures
        ORDER BY affected_tests DESC, affected_branches DESC, total_failures DESC
    """

    # Add min_tests to params
    params.append(min_tests)

    results = _execute_query(query, tuple(params))

    return [
        {
            "traceback_preview": row[0],
            "affected_tests": row[1],
            "affected_branches": row[2],
            "total_failures": row[3],
            "test_list": row[4],
            "branch_list": row[5],
            "first_occurrence": row[6],
            "last_occurrence": row[7],
        }
        for row in results
    ]


def get_test_time_regressions(
    days: int = DEFAULT_DAYS_LOOKBACK,
    threshold_multiplier: float = DEFAULT_THRESHOLD_MULTIPLIER,
) -> list[dict[str, t.Any]]:
    """
    Query 4: Test time regression - Tests that have significantly increased in duration.

    This query identifies performance regressions by:
    - Establishing a baseline duration from early test runs
    - Comparing recent runs against this baseline
    - Flagging tests that exceed the threshold multiplier

    The analysis uses the first 5 runs as baseline and compares against subsequent runs.
    Only tests with sufficient baseline data (3+ runs) are analyzed.

    Args:
        days: Number of days to look back for test runs
        threshold_multiplier: Factor by which duration must increase to be considered a regression

    Returns:
        List of dictionaries containing test performance regression information
    """
    date_threshold = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    query = """
        -- Step 1: Get all test runs with their execution order
        WITH test_durations AS (
            SELECT
                test_fqn,                           -- The test name
                test_total_duration,                -- How long the test took
                test_start_time,                    -- When the test ran
                git_commit_hash,                    -- Which commit this was
                git_branch,                         -- Which branch this was

                -- ROW_NUMBER() creates a sequence number for each test run
                -- PARTITION BY test_fqn means we restart counting for each different test
                -- ORDER BY test_start_time means we number them chronologically
                -- So run_order = 1 is the first time this test ran, 2 is second time, etc.
                ROW_NUMBER() OVER (PARTITION BY test_fqn ORDER BY test_start_time) as run_order

            FROM test_results
            WHERE test_start_time >= ?              -- Only recent runs
                AND test_status IN ('passed', 'failed', 'xpassed', 'xfailed')  -- Only completed runs (not skipped)
                AND test_total_duration > 0         -- Must have valid duration
        ),

        -- Step 2: Calculate baseline duration from early runs
        baseline_durations AS (
            SELECT
                test_fqn,
                -- Average duration of the first 5 runs (this is our "normal" speed)
                AVG(test_total_duration) as baseline_duration,
                COUNT(*) as baseline_runs
            FROM test_durations
            WHERE run_order <= ?                    -- Only use first N runs as baseline
            GROUP BY test_fqn
            HAVING baseline_runs >= ?               -- Must have at least N baseline runs
        ),

        -- Step 3: Compare recent runs against baseline
        recent_durations AS (
            SELECT
                td.test_fqn,
                td.test_total_duration,             -- Current run duration
                td.test_start_time,
                td.git_commit_hash,
                td.git_branch,
                bd.baseline_duration,               -- What this test "normally" takes

                -- Calculate how much slower this run is compared to baseline
                -- 1.0 = same speed, 2.0 = twice as slow, 0.5 = twice as fast
                (td.test_total_duration / bd.baseline_duration) as duration_ratio

            FROM test_durations td
            JOIN baseline_durations bd ON td.test_fqn = bd.test_fqn  -- Match test to its baseline
            WHERE td.run_order > ?                  -- Only look at recent runs (after baseline)
        )

        -- Step 4: Find regressions and aggregate by test/commit/branch
        SELECT
            test_fqn,
            MAX(test_total_duration) as max_duration,        -- Slowest run we found
            AVG(baseline_duration) as baseline_duration,     -- Average baseline speed
            MAX(duration_ratio) as max_ratio,                -- Worst slowdown ratio
            COUNT(*) as regression_count,                    -- How many slow runs we found
            MAX(test_start_time) as latest_occurrence,       -- When this regression last happened
            git_commit_hash,                                 -- Which commit had the regression
            git_branch                                       -- Which branch had the regression
        FROM recent_durations
        WHERE duration_ratio >= ?                    -- Only include runs that are significantly slower
        GROUP BY test_fqn, git_commit_hash, git_branch  -- Group by test and context
        ORDER BY max_ratio DESC, max_duration DESC    -- Show worst regressions first
    """

    results = _execute_query(
        query,
        (
            date_threshold,
            BASELINE_RUN_COUNT,
            MIN_BASELINE_RUNS,
            BASELINE_RUN_COUNT,
            threshold_multiplier,
        ),
    )

    return [
        {
            "test_fqn": row[0],
            "max_duration": round(row[1], 4),
            "baseline_duration": round(row[2], 4),
            "max_ratio": round(row[3], 2),
            "regression_count": row[4],
            "latest_occurrence": row[5],
            "git_commit_hash": row[6],
            "git_branch": row[7],
        }
        for row in results
    ]


def get_test_order_correlations(
    days: int = DEFAULT_DAYS_LOOKBACK,
    min_correlation: float = DEFAULT_MIN_CORRELATION,
) -> list[dict[str, t.Any]]:
    """
    Query 5: Test order correlation - Identifies tests that may be causing other tests to fail.

    This query analyzes test execution order within sessions to find patterns where:
    - A test runs before another test in the same session
    - The second test fails more often when the first test passes
    - This suggests the first test may be leaving the system in a bad state

    The correlation is measured as the ratio of "second test fails after first test passes"
    to "total times the tests run in sequence".

    Args:
        days: Number of days to look back for test runs
        min_correlation: Minimum correlation threshold (0.0 to 1.0) to include a pair

    Returns:
        List of dictionaries containing test order correlation information
    """
    date_threshold = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    query = """
        -- Step 1: Order all tests within each session by execution time
        WITH session_test_order AS (
            SELECT
                session_id,                         -- Which test session this was
                test_fqn,                           -- Which test this was
                test_status,                        -- Whether it passed or failed
                test_start_time,                    -- When it started running

                -- ROW_NUMBER() creates execution order within each session
                -- PARTITION BY session_id means we restart counting for each session
                -- ORDER BY test_start_time means we number them by start time
                -- So test_order = 1 is the first test in the session, 2 is second, etc.
                ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY test_start_time) as test_order

            FROM test_results
            WHERE test_start_time >= ?              -- Only recent runs
                AND test_status IN ('passed', 'failed', 'error', 'xpassed', 'xfailed')  -- Only completed tests
        ),

        -- Step 2: Create all possible pairs of tests that ran in the same session
        test_pairs AS (
            SELECT
                t1.session_id,                      -- The session where both tests ran
                t1.test_fqn as first_test,          -- The test that ran first
                t2.test_fqn as second_test,         -- The test that ran second
                t1.test_status as first_status,     -- Whether the first test passed/failed
                t2.test_status as second_status,    -- Whether the second test passed/failed
                t1.test_order as first_order,       -- Execution order of first test
                t2.test_order as second_order       -- Execution order of second test

            FROM session_test_order t1
            JOIN session_test_order t2 ON t1.session_id = t2.session_id  -- Same session
            WHERE t1.test_order < t2.test_order     -- First test must run before second test
                AND t1.test_fqn != t2.test_fqn      -- Must be different tests
        ),

        -- Step 3: Analyze the correlation between test pairs
        correlation_analysis AS (
            SELECT
                first_test,                         -- The test that runs first
                second_test,                        -- The test that runs second

                -- Count total number of times these tests ran in sequence
                COUNT(*) as total_pairs,

                -- Count specific scenarios using conditional aggregation
                -- How many times did the second test fail AFTER the first test passed?
                -- This suggests the first test might be causing the second to fail
                SUM(CASE WHEN first_status IN ('passed', 'xpassed') AND second_status IN ('failed', 'error', 'xfailed') THEN 1 ELSE 0 END) as failure_after_success,

                -- How many times did both tests fail?
                SUM(CASE WHEN first_status IN ('failed', 'error', 'xfailed') AND second_status IN ('failed', 'error', 'xfailed') THEN 1 ELSE 0 END) as failure_after_failure,

                -- How many times did both tests pass?
                SUM(CASE WHEN first_status IN ('passed', 'xpassed') AND second_status IN ('passed', 'xpassed') THEN 1 ELSE 0 END) as success_after_success,

                -- How many times did the second test fail (regardless of first test)?
                SUM(CASE WHEN second_status IN ('failed', 'error', 'xfailed') THEN 1 ELSE 0 END) as total_second_failures

            FROM test_pairs
            GROUP BY first_test, second_test         -- Group by test pair
            HAVING total_pairs >= ?                  -- Must have at least N observations
        )

        -- Step 4: Calculate correlation metrics and filter for significant correlations
        SELECT
            first_test,
            second_test,
            total_pairs,                            -- How many times we observed this pair
            failure_after_success,                  -- Times second failed after first passed
            total_second_failures,                  -- Total times second test failed

            -- Correlation: (failures after success) / (total pairs)
            -- 1.0 = second test ALWAYS fails when first test passes
            -- 0.0 = second test NEVER fails when first test passes
            ROUND((failure_after_success * 1.0 / total_pairs), 3) as failure_correlation,

            -- Ratio: (failures after success) / (total second failures)
            -- How much of the second test's failures happen after the first test passes?
            ROUND((failure_after_success * 1.0 / total_second_failures), 3) as failure_ratio

        FROM correlation_analysis
        WHERE (failure_after_success * 1.0 / total_pairs) >= ?  -- Only high correlations
            AND total_second_failures > 0                       -- Second test must actually fail sometimes
        ORDER BY failure_correlation DESC, failure_after_success DESC  -- Show strongest correlations first
    """

    results = _execute_query(query, (date_threshold, MIN_TEST_PAIRS, min_correlation))

    return [
        {
            "first_test": row[0],
            "second_test": row[1],
            "total_pairs": row[2],
            "failure_after_success": row[3],
            "total_second_failures": row[4],
            "failure_correlation": row[5],
            "failure_ratio": row[6],
        }
        for row in results
    ]


def get_problematic_tests(
    git_repository_url: str | None = None,
    git_branch: str | None = None,
    days: int = DEFAULT_DAYS_LOOKBACK,
    min_runs: int = DEFAULT_MIN_RUNS,
) -> list[dict[str, t.Any]]:
    """
    Identify problematic tests by combining results from existing analysis queries.

    This function leverages the existing well-tested queries to identify tests that should
    be marked as expected failures in CI:
    - Flaky tests (from get_flaky_tests)
    - Cross-branch failing tests (from get_failing_tests_across_branches)
    - Tests affected by underlying issues (from get_underlying_issues)

    Args:
        git_repository_url: Filter by specific repository (optional)
        git_branch: Filter by specific branch (optional)
        days: Number of days to look back for analysis
        min_runs: Minimum number of runs required to analyze a test

    Returns:
        List of dictionaries containing problematic test information with expected exception messages
    """
    problematic_tests = {}  # Use dict to deduplicate by test_fqn

    # Helper to fetch exception messages for a test
    def get_exception_messages_for_test(test_fqn: str) -> list[str]:
        """Fetch unique exception messages for a specific test."""
        date_threshold = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        where_conditions = [
            "test_fqn = ?",
            "test_start_time >= ?",
            "test_status IN ('failed', 'error', 'xfailed')",
            "test_traceback IS NOT NULL",
            "test_traceback != ''",
        ]
        params = [test_fqn, date_threshold]

        if git_repository_url:
            where_conditions.append("git_repository_url = ?")
            params.append(git_repository_url)

        if git_branch:
            where_conditions.append("git_branch = ?")
            params.append(git_branch)

        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT DISTINCT test_traceback
            FROM test_results
            WHERE {where_clause}
            LIMIT 10
        """

        results = _execute_query(query, tuple(params))
        return [row[0] for row in results if row[0]]

    # 1. Get flaky tests - these are definitely problematic
    flaky_tests = get_flaky_tests(
        days=days,
        min_runs=min_runs,
        git_repository_url=git_repository_url,
        git_branch=git_branch,
    )
    for test in flaky_tests:
        test_fqn = test["test_fqn"]
        problematic_tests[test_fqn] = {
            "test_fqn": test_fqn,
            "problem_type": "flaky",
            "confidence": (
                "high" if test["total_runs"] >= HIGH_CONFIDENCE_MIN_RUNS else "medium"
            ),
            "total_runs": test["total_runs"],
            "passed_count": test["passed_count"],
            "failed_count": test["failed_count"],
            "failure_rate": round(100 - test["pass_rate"], 1),
            "first_run": test["first_run"],
            "last_run": test["last_run"],
            "session_count": test["session_count"],
            "git_commit_hash": test["git_commit_hash"],
            "source_analysis": "flaky_tests",
            "expected_exceptions": get_exception_messages_for_test(test_fqn),
        }

    # 2. Get tests failing across branches - these indicate systemic issues
    cross_branch_tests = get_failing_tests_across_branches(
        days=days,
        min_occurrences=2,
        git_repository_url=git_repository_url,
        git_branch=git_branch,
    )
    for test in cross_branch_tests:
        test_fqn = test["test_fqn"]

        # If already identified as flaky, upgrade to flaky_and_failing
        if test_fqn in problematic_tests:
            problematic_tests[test_fqn]["problem_type"] = "flaky_and_failing"
            problematic_tests[test_fqn]["source_analysis"] += ", cross_branch_failures"
            # Merge exception messages
            existing_exceptions = set(
                problematic_tests[test_fqn].get("expected_exceptions", [])
            )
            new_exceptions = get_exception_messages_for_test(test_fqn)
            problematic_tests[test_fqn]["expected_exceptions"] = list(
                existing_exceptions | set(new_exceptions)
            )
        else:
            problematic_tests[test_fqn] = {
                "test_fqn": test_fqn,
                "problem_type": "cross_branch_failing",
                "confidence": (
                    "high"
                    if test["total_failures"] >= MEDIUM_CONFIDENCE_MIN_RUNS
                    else "medium"
                ),
                "total_runs": test["total_failures"],  # Only failures recorded here
                "passed_count": 0,  # Not available from this query
                "failed_count": test["total_failures"],
                "failure_rate": 100.0,  # All recorded runs are failures
                "first_run": test["first_failure"],
                "last_run": test["last_failure"],
                "affected_branches": test["affected_branches"],
                "branch_list": test["branch_list"],
                "sample_error_preview": test["traceback_preview"],
                "source_analysis": "cross_branch_failures",
                "expected_exceptions": get_exception_messages_for_test(test_fqn),
            }

    # 3. Get tests affected by underlying issues - these are systematically problematic
    underlying_issues = get_underlying_issues(
        days=days,
        min_tests=2,
        git_repository_url=git_repository_url,
        git_branch=git_branch,
    )
    for issue in underlying_issues:
        # Parse the test_list to get individual test FQNs
        test_fqns = issue["test_list"].split(",") if issue["test_list"] else []

        for test_fqn_raw in test_fqns:
            test_fqn = test_fqn_raw.strip()
            if not test_fqn:
                continue

            # If already identified, add this as additional context
            if test_fqn in problematic_tests:
                problematic_tests[test_fqn]["source_analysis"] += ", underlying_issues"
                # Upgrade confidence if this test is affected by systemic issues
                if problematic_tests[test_fqn]["confidence"] != "high":
                    problematic_tests[test_fqn]["confidence"] = "high"
                # Merge exception messages
                existing_exceptions = set(
                    problematic_tests[test_fqn].get("expected_exceptions", [])
                )
                new_exceptions = get_exception_messages_for_test(test_fqn)
                problematic_tests[test_fqn]["expected_exceptions"] = list(
                    existing_exceptions | set(new_exceptions)
                )
            else:
                problematic_tests[test_fqn] = {
                    "test_fqn": test_fqn,
                    "problem_type": "systemic_issue",
                    "confidence": "high",  # Systemic issues are high confidence
                    "total_runs": issue["total_failures"],  # Only failures recorded
                    "passed_count": 0,  # Not available from this query
                    "failed_count": issue["total_failures"],
                    "failure_rate": 100.0,  # All recorded runs are failures
                    "first_run": issue["first_occurrence"],
                    "last_run": issue["last_occurrence"],
                    "affected_tests": issue["affected_tests"],
                    "affected_branches": issue["affected_branches"],
                    "sample_error_preview": issue["traceback_preview"],
                    "source_analysis": "underlying_issues",
                    "expected_exceptions": get_exception_messages_for_test(test_fqn),
                }

    # Convert dict back to list and sort by priority
    result_list = list(problematic_tests.values())

    # Sort by problem type priority, then by failure rate, then by total runs
    priority_order = {
        "flaky_and_failing": 1,
        "systemic_issue": 2,
        "cross_branch_failing": 3,
        "flaky": 4,
    }

    result_list.sort(
        key=lambda x: (
            priority_order.get(x["problem_type"], 5),
            -x["failure_rate"],
            -x["total_runs"],
        )
    )

    return result_list


def run_all_queries(days: int = DEFAULT_DAYS_LOOKBACK) -> dict[str, t.Any]:
    """Run all analysis queries and return results."""
    return {
        "flaky_tests": get_flaky_tests(days),
        "failing_tests_across_branches": get_failing_tests_across_branches(days),
        "underlying_issues": get_underlying_issues(days),
        "test_time_regressions": get_test_time_regressions(days),
        "test_order_correlations": get_test_order_correlations(days),
    }
