"""
Sample queries for analyzing test failure patterns in CI.
"""
import sqlite3
import typing as t
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent / "ci_viz.db"


def get_flaky_tests(days: int = 7, min_runs: int = 3) -> t.List[t.Dict[str, t.Any]]:
    """
    Query 1: Flaky tests - Different test runs (with same test fqn) for the same git sha 
    pass and fail at different test sessions (in a given time period).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Calculate date threshold
    date_threshold = (datetime.now() - timedelta(days=days)).isoformat()
    
    query = """
        WITH test_runs_by_commit AS (
            SELECT 
                test_fqn,
                git_commit_hash,
                test_status,
                COUNT(*) as run_count,
                COUNT(DISTINCT test_status) as status_count,
                GROUP_CONCAT(DISTINCT test_status) as statuses,
                MIN(test_start_time) as first_run,
                MAX(test_start_time) as last_run,
                COUNT(DISTINCT session_id) as session_count
            FROM test_results 
            WHERE test_start_time >= ? 
                AND git_commit_hash IS NOT NULL 
                AND git_commit_hash != 'unknown'
            GROUP BY test_fqn, git_commit_hash
            HAVING run_count >= ? AND status_count > 1
        )
        SELECT 
            test_fqn,
            git_commit_hash,
            run_count,
            statuses,
            first_run,
            last_run,
            session_count,
            ROUND((run_count * 1.0 / session_count), 2) as avg_runs_per_session
        FROM test_runs_by_commit
        ORDER BY run_count DESC, session_count DESC
    """
    
    cursor.execute(query, (date_threshold, min_runs))
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            "test_fqn": row[0],
            "git_commit_hash": row[1],
            "total_runs": row[2],
            "statuses": row[3],
            "first_run": row[4],
            "last_run": row[5],
            "session_count": row[6],
            "avg_runs_per_session": row[7]
        }
        for row in results
    ]


def get_failing_tests_across_branches(days: int = 7, min_occurrences: int = 2) -> t.List[t.Dict[str, t.Any]]:
    """
    Query 2: Failing tests across branches - Different test runs for different branches 
    fail with the same error traceback (with same test fqn, in a given time period).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    date_threshold = (datetime.now() - timedelta(days=days)).isoformat()
    
    query = """
        WITH failing_tests_by_branch AS (
            SELECT 
                test_fqn,
                test_traceback,
                git_branch,
                COUNT(*) as failure_count,
                COUNT(DISTINCT git_branch) as branch_count,
                GROUP_CONCAT(DISTINCT git_branch) as branches,
                MIN(test_start_time) as first_failure,
                MAX(test_start_time) as last_failure
            FROM test_results 
            WHERE test_start_time >= ? 
                AND test_status = 'failed'
                AND test_traceback IS NOT NULL
                AND git_branch IS NOT NULL 
                AND git_branch != 'unknown'
            GROUP BY test_fqn, test_traceback
            HAVING branch_count > 1 AND failure_count >= ?
        )
        SELECT 
            test_fqn,
            SUBSTR(test_traceback, 1, 200) as traceback_preview,
            branch_count,
            branches,
            failure_count,
            first_failure,
            last_failure
        FROM failing_tests_by_branch
        ORDER BY branch_count DESC, failure_count DESC
    """
    
    cursor.execute(query, (date_threshold, min_occurrences))
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            "test_fqn": row[0],
            "traceback_preview": row[1],
            "affected_branches": row[2],
            "branches": row[3],
            "total_failures": row[4],
            "first_failure": row[5],
            "last_failure": row[6]
        }
        for row in results
    ]


def get_underlying_issues(days: int = 7, min_tests: int = 2) -> t.List[t.Dict[str, t.Any]]:
    """
    Query 3: Underlying issues - Different test runs for different branches fail with 
    the same error traceback (with different test fqn, in a given time period).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    date_threshold = (datetime.now() - timedelta(days=days)).isoformat()
    
    query = """
        WITH similar_failures AS (
            SELECT 
                test_traceback,
                COUNT(DISTINCT test_fqn) as affected_tests,
                COUNT(DISTINCT git_branch) as affected_branches,
                COUNT(*) as total_failures,
                GROUP_CONCAT(DISTINCT test_fqn) as test_list,
                GROUP_CONCAT(DISTINCT git_branch) as branch_list,
                MIN(test_start_time) as first_occurrence,
                MAX(test_start_time) as last_occurrence
            FROM test_results 
            WHERE test_start_time >= ? 
                AND test_status = 'failed'
                AND test_traceback IS NOT NULL
                AND git_branch IS NOT NULL 
                AND git_branch != 'unknown'
            GROUP BY test_traceback
            HAVING affected_tests >= ? AND affected_branches > 1
        )
        SELECT 
            SUBSTR(test_traceback, 1, 200) as traceback_preview,
            affected_tests,
            affected_branches,
            total_failures,
            test_list,
            branch_list,
            first_occurrence,
            last_occurrence
        FROM similar_failures
        ORDER BY affected_tests DESC, affected_branches DESC, total_failures DESC
    """
    
    cursor.execute(query, (date_threshold, min_tests))
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            "traceback_preview": row[0],
            "affected_tests": row[1],
            "affected_branches": row[2],
            "total_failures": row[3],
            "test_list": row[4],
            "branch_list": row[5],
            "first_occurrence": row[6],
            "last_occurrence": row[7]
        }
        for row in results
    ]


def get_test_time_regressions(days: int = 7, threshold_multiplier: float = 2.0) -> t.List[t.Dict[str, t.Any]]:
    """
    Query 4: Test time regression - A test duration (single test fqn) increases 
    above some threshold (in a given time period).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    date_threshold = (datetime.now() - timedelta(days=days)).isoformat()
    
    query = """
        WITH test_durations AS (
            SELECT 
                test_fqn,
                test_total_duration,
                test_start_time,
                git_commit_hash,
                git_branch,
                ROW_NUMBER() OVER (PARTITION BY test_fqn ORDER BY test_start_time) as run_order
            FROM test_results 
            WHERE test_start_time >= ? 
                AND test_status IN ('passed', 'failed')
                AND test_total_duration > 0
        ),
        baseline_durations AS (
            SELECT 
                test_fqn,
                AVG(test_total_duration) as baseline_duration,
                COUNT(*) as baseline_runs
            FROM test_durations 
            WHERE run_order <= 5  -- Use first 5 runs as baseline
            GROUP BY test_fqn
            HAVING baseline_runs >= 3
        ),
        recent_durations AS (
            SELECT 
                td.test_fqn,
                td.test_total_duration,
                td.test_start_time,
                td.git_commit_hash,
                td.git_branch,
                bd.baseline_duration,
                (td.test_total_duration / bd.baseline_duration) as duration_ratio
            FROM test_durations td
            JOIN baseline_durations bd ON td.test_fqn = bd.test_fqn
            WHERE td.run_order > 5  -- Recent runs
        )
        SELECT 
            test_fqn,
            MAX(test_total_duration) as max_duration,
            AVG(baseline_duration) as baseline_duration,
            MAX(duration_ratio) as max_ratio,
            COUNT(*) as regression_count,
            MAX(test_start_time) as latest_occurrence,
            git_commit_hash,
            git_branch
        FROM recent_durations
        WHERE duration_ratio >= ?
        GROUP BY test_fqn, git_commit_hash, git_branch
        ORDER BY max_ratio DESC, max_duration DESC
    """
    
    cursor.execute(query, (date_threshold, threshold_multiplier))
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            "test_fqn": row[0],
            "max_duration": round(row[1], 4),
            "baseline_duration": round(row[2], 4),
            "max_ratio": round(row[3], 2),
            "regression_count": row[4],
            "latest_occurrence": row[5],
            "git_commit_hash": row[6],
            "git_branch": row[7]
        }
        for row in results
    ]


def get_test_order_correlations(days: int = 7, min_correlation: float = 0.7) -> t.List[t.Dict[str, t.Any]]:
    """
    Query 5: Test order correlation - Inspect if there is a correlation for sessions 
    where some tests are run before others, and make the latter fail.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    date_threshold = (datetime.now() - timedelta(days=days)).isoformat()
    
    query = """
        WITH session_test_order AS (
            SELECT 
                session_id,
                test_fqn,
                test_status,
                test_start_time,
                ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY test_start_time) as test_order
            FROM test_results 
            WHERE test_start_time >= ?
        ),
        test_pairs AS (
            SELECT 
                t1.session_id,
                t1.test_fqn as first_test,
                t2.test_fqn as second_test,
                t1.test_status as first_status,
                t2.test_status as second_status,
                t1.test_order as first_order,
                t2.test_order as second_order
            FROM session_test_order t1
            JOIN session_test_order t2 ON t1.session_id = t2.session_id
            WHERE t1.test_order < t2.test_order
                AND t1.test_fqn != t2.test_fqn
        ),
        correlation_analysis AS (
            SELECT 
                first_test,
                second_test,
                COUNT(*) as total_pairs,
                SUM(CASE WHEN first_status = 'passed' AND second_status = 'failed' THEN 1 ELSE 0 END) as failure_after_success,
                SUM(CASE WHEN first_status = 'failed' AND second_status = 'failed' THEN 1 ELSE 0 END) as failure_after_failure,
                SUM(CASE WHEN first_status = 'passed' AND second_status = 'passed' THEN 1 ELSE 0 END) as success_after_success,
                SUM(CASE WHEN second_status = 'failed' THEN 1 ELSE 0 END) as total_second_failures
            FROM test_pairs
            GROUP BY first_test, second_test
            HAVING total_pairs >= 3
        )
        SELECT 
            first_test,
            second_test,
            total_pairs,
            failure_after_success,
            total_second_failures,
            ROUND((failure_after_success * 1.0 / total_pairs), 3) as failure_correlation,
            ROUND((failure_after_success * 1.0 / total_second_failures), 3) as failure_ratio
        FROM correlation_analysis
        WHERE (failure_after_success * 1.0 / total_pairs) >= ?
            AND total_second_failures > 0
        ORDER BY failure_correlation DESC, failure_after_success DESC
    """
    
    cursor.execute(query, (date_threshold, min_correlation))
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            "first_test": row[0],
            "second_test": row[1],
            "total_pairs": row[2],
            "failure_after_success": row[3],
            "total_second_failures": row[4],
            "failure_correlation": row[5],
            "failure_ratio": row[6]
        }
        for row in results
    ]


def run_all_queries(days: int = 7) -> t.Dict[str, t.Any]:
    """Run all analysis queries and return results."""
    return {
        "flaky_tests": get_flaky_tests(days),
        "failing_tests_across_branches": get_failing_tests_across_branches(days),
        "underlying_issues": get_underlying_issues(days),
        "test_time_regressions": get_test_time_regressions(days),
        "test_order_correlations": get_test_order_correlations(days)
    }
