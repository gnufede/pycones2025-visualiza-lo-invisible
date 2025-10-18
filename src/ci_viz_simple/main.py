"""
CI Viz Simple - A simple service for tracking test failure patterns across CI.
"""

import contextlib
import json
import sqlite3
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ci_viz_simple.queries import (
    get_failing_tests_across_branches,
    get_flaky_tests,
    get_test_order_correlations,
    get_test_time_regressions,
    get_underlying_issues,
    run_all_queries,
)
from ci_viz_simple.sql_parser import parse_sql_like_query

app = FastAPI(
    title="CI Viz Simple",
    description="Simple CI test visibility system for tracking test failure patterns",
    version="0.1.0",
)

# Database path
DB_PATH = Path(__file__).parent / "ci_viz.db"

# Templates setup
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


class TestResult(BaseModel):
    # Test identification
    test_id: str
    test_name: str
    test_fqn: str
    test_module: str
    test_suite: str | None = None
    test_file_path: str | None = None
    test_line_number: int | None = None

    # Test execution
    test_status: str
    test_message: str | None = None
    test_traceback: str | None = None
    test_total_duration: float
    test_call_duration: float
    test_start_time: str
    was_marked_flaky: bool = False  # Whether CI Viz marked this test as flaky

    # Session information
    session_id: str
    session_start_time: str
    session_end_time: str
    session_total_duration: float

    # Git information
    git_repository_url: str | None = None
    git_branch: str | None = None
    git_commit_hash: str | None = None
    git_commit_message: str | None = None
    git_commit_author: str | None = None
    git_commit_author_email: str | None = None
    git_commit_timestamp: str | None = None

    # Environment information
    env_python_version: str | None = None
    env_platform: str | None = None
    env_architecture: str | None = None
    env_dependencies: str | None = None  # JSON string
    env_vars: str | None = None  # JSON string

    # CI information
    ci_system: str | None = None
    ci_job_url: str | None = None
    ci_pipeline_url: str | None = None
    ci_job_id: str | None = None
    ci_pipeline_id: str | None = None
    ci_trigger: str | None = None
    ci_pull_request_number: int | None = None


def init_database():
    """Initialize the SQLite database with a denormalized schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create a single denormalized table for all test data
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Test identification
            test_id TEXT NOT NULL,
            test_name TEXT NOT NULL,
            test_fqn TEXT NOT NULL,
            test_module TEXT NOT NULL,
            test_suite TEXT,
            test_file_path TEXT,
            test_line_number INTEGER,

            -- Test execution
            test_status TEXT NOT NULL,
            test_message TEXT,
            test_traceback TEXT,
            test_total_duration REAL NOT NULL,
            test_call_duration REAL NOT NULL,
            test_start_time TEXT NOT NULL,
            was_marked_flaky INTEGER DEFAULT 0,  -- Whether CI Viz marked this test as flaky (boolean as INTEGER)

            -- Session information
            session_id TEXT NOT NULL,
            session_start_time TEXT NOT NULL,
            session_end_time TEXT NOT NULL,
            session_total_duration REAL NOT NULL,

            -- Git information
            git_repository_url TEXT,
            git_branch TEXT,
            git_commit_hash TEXT,
            git_commit_message TEXT,
            git_commit_author TEXT,
            git_commit_author_email TEXT,
            git_commit_timestamp TEXT,

            -- Environment information
            env_python_version TEXT,
            env_platform TEXT,
            env_architecture TEXT,
            env_dependencies TEXT,  -- JSON string
            env_vars TEXT,  -- JSON string

            -- CI information
            ci_system TEXT,
            ci_job_url TEXT,
            ci_pipeline_url TEXT,
            ci_job_id TEXT,
            ci_pipeline_id TEXT,
            ci_trigger TEXT,
            ci_pull_request_number INTEGER,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create indexes for common query patterns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_fqn ON test_results(test_fqn)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_git_commit_hash ON test_results(git_commit_hash)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_git_branch ON test_results(git_branch)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_test_status ON test_results(test_status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_id ON test_results(session_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_test_start_time ON test_results(test_start_time)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_test_traceback ON test_results(test_traceback)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_was_marked_flaky ON test_results(was_marked_flaky)"
    )

    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_database()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"message": "CI Viz Simple is running", "version": "0.1.0"}


@app.post("/api/v1/ingest-test-results/")
async def ingest_test_results(test_results: list[TestResult]):
    """Ingest test results directly."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Insert each test result as a separate row (denormalized)
        for test_result in test_results:
            cursor.execute(
                """
                INSERT INTO test_results (
                    test_id, test_name, test_fqn, test_module, test_suite, test_file_path, test_line_number,
                    test_status, test_message, test_traceback, test_total_duration, test_call_duration, test_start_time,
                    was_marked_flaky,
                    session_id, session_start_time, session_end_time, session_total_duration,
                    git_repository_url, git_branch, git_commit_hash, git_commit_message,
                    git_commit_author, git_commit_author_email, git_commit_timestamp,
                    env_python_version, env_platform, env_architecture, env_dependencies, env_vars,
                    ci_system, ci_job_url, ci_pipeline_url, ci_job_id, ci_pipeline_id,
                    ci_trigger, ci_pull_request_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    test_result.test_id,
                    test_result.test_name,
                    test_result.test_fqn,
                    test_result.test_module,
                    test_result.test_suite,
                    test_result.test_file_path,
                    test_result.test_line_number,
                    test_result.test_status,
                    test_result.test_message,
                    test_result.test_traceback,
                    test_result.test_total_duration,
                    test_result.test_call_duration,
                    test_result.test_start_time,
                    (
                        1 if test_result.was_marked_flaky else 0
                    ),  # Convert bool to int for SQLite
                    test_result.session_id,
                    test_result.session_start_time,
                    test_result.session_end_time,
                    test_result.session_total_duration,
                    test_result.git_repository_url,
                    test_result.git_branch,
                    test_result.git_commit_hash,
                    test_result.git_commit_message,
                    test_result.git_commit_author,
                    test_result.git_commit_author_email,
                    test_result.git_commit_timestamp,
                    test_result.env_python_version,
                    test_result.env_platform,
                    test_result.env_architecture,
                    test_result.env_dependencies,
                    test_result.env_vars,
                    test_result.ci_system,
                    test_result.ci_job_url,
                    test_result.ci_pipeline_url,
                    test_result.ci_job_id,
                    test_result.ci_pipeline_id,
                    test_result.ci_trigger,
                    test_result.ci_pull_request_number,
                ),
            )

        conn.commit()
        conn.close()

        return {"message": f"Successfully ingested {len(test_results)} test results"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to ingest test results: {e!s}"
        ) from e


@app.get("/api/v1/stats")
async def get_stats():
    """Get basic statistics about the stored data."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM test_results")
        total_sessions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM test_results")
        total_tests = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM test_results WHERE test_status = 'failed'")
        failed_tests = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT test_fqn) FROM test_results")
        unique_tests = cursor.fetchone()[0]

        conn.close()

        return {
            "total_sessions": total_sessions,
            "total_test_executions": total_tests,
            "failed_test_executions": failed_tests,
            "unique_tests": unique_tests,
            "failure_rate": (
                round(failed_tests / total_tests * 100, 2) if total_tests > 0 else 0
            ),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get stats: {e!s}"
        ) from e


@app.get("/api/v1/analysis/flaky-tests")
async def analyze_flaky_tests(
    days: int = 7,
    min_runs: int = 3,
    git_repository_url: str | None = Query(
        None, description="Filter by repository URL"
    ),
    git_branch: str | None = Query(None, description="Filter by git branch"),
):
    """Get flaky tests - tests that pass and fail for the same commit."""
    try:
        return {
            "results": get_flaky_tests(days, min_runs, git_repository_url, git_branch)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze flaky tests: {e!s}"
        ) from e


@app.get("/api/v1/analysis/failing-across-branches")
async def analyze_failing_across_branches(
    days: int = 7,
    min_occurrences: int = 2,
    git_repository_url: str | None = Query(
        None, description="Filter by repository URL"
    ),
    git_branch: str | None = Query(None, description="Filter by git branch"),
):
    """Get tests failing with same error across different branches."""
    try:
        return {
            "results": get_failing_tests_across_branches(
                days, min_occurrences, git_repository_url, git_branch
            )
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze cross-branch failures: {e!s}"
        ) from e


@app.get("/api/v1/analysis/underlying-issues")
async def analyze_underlying_issues(
    days: int = 7,
    min_tests: int = 2,
    git_repository_url: str | None = Query(
        None, description="Filter by repository URL"
    ),
    git_branch: str | None = Query(None, description="Filter by git branch"),
):
    """Get underlying issues affecting multiple different tests."""
    try:
        return {
            "results": get_underlying_issues(
                days, min_tests, git_repository_url, git_branch
            )
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze underlying issues: {e!s}"
        ) from e


@app.get("/api/v1/analysis/time-regressions")
async def analyze_time_regressions(days: int = 7, threshold_multiplier: float = 2.0):
    """Get tests with significant duration increases."""
    try:
        return {"results": get_test_time_regressions(days, threshold_multiplier)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze time regressions: {e!s}"
        ) from e


@app.get("/api/v1/analysis/test-order-correlations")
async def analyze_test_order_correlations(days: int = 7, min_correlation: float = 0.7):
    """Get test pairs where execution order correlates with failures."""
    try:
        return {"results": get_test_order_correlations(days, min_correlation)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze test order correlations: {e!s}"
        ) from e


@app.get("/api/v1/analysis/all")
async def analyze_all(days: int = 7):
    """Run all analysis queries and return comprehensive results."""
    try:
        return run_all_queries(days)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to run analysis: {e!s}"
        ) from e


@app.get("/api/v1/flaky-tests")
def flaky_tests(git_repository_url: str, git_branch: str):
    tests = get_flaky_tests(
        git_repository_url=git_repository_url, git_branch=git_branch
    )

    # Return dict: test_fqn -> [expected_exception_messages]
    return {
        "flaky_tests": {test["test_fqn"]: test["expected_exceptions"] for test in tests}
    }


@app.get("/api/v1/test-results/")
async def get_test_results(
    test_name: str | None = Query(
        None, description="Filter by test name (partial match)"
    ),
    test_status: str | None = Query(None, description="Filter by test status"),
    git_branch: str | None = Query(None, description="Filter by git branch"),
    git_commit_hash: str | None = Query(None, description="Filter by git commit hash"),
    start_date: str | None = Query(
        None, description="Filter by start date (ISO format)"
    ),
    end_date: str | None = Query(None, description="Filter by end date (ISO format)"),
    sql_query: str | None = Query(None, description="SQL-like query for filtering"),
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Number of results to skip"),
):
    """Get test results with filtering and pagination."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Build WHERE clause dynamically
        where_conditions = []
        params = []

        if sql_query:
            # Parse SQL-like query
            try:
                sql_where, sql_params = parse_sql_like_query(sql_query)
                where_conditions.append(sql_where)
                params.extend(sql_params)
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"SQL query error: {e!s}"
                ) from e
        else:
            # Use individual filters
            if test_name:
                where_conditions.append("test_name LIKE ?")
                params.append(f"%{test_name}%")

            if test_status:
                where_conditions.append("test_status = ?")
                params.append(test_status)

            if git_branch:
                where_conditions.append("git_branch = ?")
                params.append(git_branch)

            if git_commit_hash:
                where_conditions.append("git_commit_hash = ?")
                params.append(git_commit_hash)

            if start_date:
                where_conditions.append("test_start_time >= ?")
                params.append(start_date)

            if end_date:
                where_conditions.append("test_start_time <= ?")
                params.append(end_date)

        where_clause = (
            "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        )

        # Get total count
        count_query = f"SELECT COUNT(*) FROM test_results {where_clause}"  # noqa: S608
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Get results
        query = f"""
            SELECT
                id, test_id, test_name, test_fqn, test_module, test_suite, test_file_path, test_line_number,
                test_status, test_message, test_traceback, test_total_duration, test_call_duration, test_start_time,
                session_id, session_start_time, session_end_time, session_total_duration,
                git_repository_url, git_branch, git_commit_hash, git_commit_message,
                git_commit_author, git_commit_author_email, git_commit_timestamp,
                env_python_version, env_platform, env_architecture, env_dependencies, env_vars,
                ci_system, ci_job_url, ci_pipeline_url, ci_job_id, ci_pipeline_id,
                ci_trigger, ci_pull_request_number, created_at
            FROM test_results
            {where_clause}
            ORDER BY test_start_time DESC
            LIMIT ? OFFSET ?
        """

        cursor.execute(query, [*params, limit, offset])
        results = cursor.fetchall()
        conn.close()

        # Convert to list of dictionaries
        columns = [
            "id",
            "test_id",
            "test_name",
            "test_fqn",
            "test_module",
            "test_suite",
            "test_file_path",
            "test_line_number",
            "test_status",
            "test_message",
            "test_traceback",
            "test_total_duration",
            "test_call_duration",
            "test_start_time",
            "session_id",
            "session_start_time",
            "session_end_time",
            "session_total_duration",
            "git_repository_url",
            "git_branch",
            "git_commit_hash",
            "git_commit_message",
            "git_commit_author",
            "git_commit_author_email",
            "git_commit_timestamp",
            "env_python_version",
            "env_platform",
            "env_architecture",
            "env_dependencies",
            "env_vars",
            "ci_system",
            "ci_job_url",
            "ci_pipeline_url",
            "ci_job_id",
            "ci_pipeline_id",
            "ci_trigger",
            "ci_pull_request_number",
            "created_at",
        ]

        test_results = []
        for row in results:
            test_result = dict(zip(columns, row, strict=False))
            # Convert JSON strings back to objects
            if test_result["env_dependencies"]:
                with contextlib.suppress(Exception):
                    test_result["env_dependencies"] = json.loads(
                        test_result["env_dependencies"]
                    )
            if test_result["env_vars"]:
                with contextlib.suppress(Exception):
                    test_result["env_vars"] = json.loads(test_result["env_vars"])
            test_results.append(test_result)

        return {
            "results": test_results,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(test_results) < total_count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get test results: {e!s}"
        ) from e


def _raise_not_found():
    """Raise HTTPException for not found."""
    raise HTTPException(status_code=404, detail="Test result not found")


@app.get("/api/v1/test-results/{test_result_id}")
async def get_test_result_detail(test_result_id: int):
    """Get detailed information for a specific test result."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        query = """
            SELECT
                id, test_id, test_name, test_fqn, test_module, test_suite, test_file_path, test_line_number,
                test_status, test_message, test_traceback, test_total_duration, test_call_duration, test_start_time,
                session_id, session_start_time, session_end_time, session_total_duration,
                git_repository_url, git_branch, git_commit_hash, git_commit_message,
                git_commit_author, git_commit_author_email, git_commit_timestamp,
                env_python_version, env_platform, env_architecture, env_dependencies, env_vars,
                ci_system, ci_job_url, ci_pipeline_url, ci_job_id, ci_pipeline_id,
                ci_trigger, ci_pull_request_number, created_at
            FROM test_results
            WHERE id = ?
        """

        cursor.execute(query, (test_result_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            _raise_not_found()
        else:
            columns = [
                "id",
                "test_id",
                "test_name",
                "test_fqn",
                "test_module",
                "test_suite",
                "test_file_path",
                "test_line_number",
                "test_status",
                "test_message",
                "test_traceback",
                "test_total_duration",
                "test_call_duration",
                "test_start_time",
                "session_id",
                "session_start_time",
                "session_end_time",
                "session_total_duration",
                "git_repository_url",
                "git_branch",
                "git_commit_hash",
                "git_commit_message",
                "git_commit_author",
                "git_commit_author_email",
                "git_commit_timestamp",
                "env_python_version",
                "env_platform",
                "env_architecture",
                "env_dependencies",
                "env_vars",
                "ci_system",
                "ci_job_url",
                "ci_pipeline_url",
                "ci_job_id",
                "ci_pipeline_id",
                "ci_trigger",
                "ci_pull_request_number",
                "created_at",
            ]

            test_result = dict(zip(columns, result, strict=False))

            # Convert JSON strings back to objects
            if test_result["env_dependencies"]:
                with contextlib.suppress(Exception):
                    test_result["env_dependencies"] = json.loads(
                        test_result["env_dependencies"]
                    )
            if test_result["env_vars"]:
                with contextlib.suppress(Exception):
                    test_result["env_vars"] = json.loads(test_result["env_vars"])

            return test_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get test result detail: {e!s}"
        ) from e


@app.get("/api/v1/test-results/{test_result_id}/related")
async def get_related_test_runs(test_result_id: int):
    """Get related test runs for a specific test result (same test, same branch)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # First get the test result to find test_fqn and git_branch
        cursor.execute(
            "SELECT test_fqn, git_branch FROM test_results WHERE id = ?",
            (test_result_id,),
        )
        result = cursor.fetchone()

        if not result:
            _raise_not_found()
        else:
            test_fqn, git_branch = result

            # Get related test runs (same test, same branch, excluding current one)
            query = """
                SELECT
                    id, test_id, test_name, test_fqn, test_status, test_total_duration, test_start_time,
                    git_commit_hash, git_commit_message, git_commit_author, git_commit_timestamp,
                    ci_job_url, ci_pipeline_url
                FROM test_results
                WHERE test_fqn = ? AND git_branch = ? AND id != ?
                ORDER BY test_start_time DESC
                LIMIT 20
            """

            cursor.execute(query, (test_fqn, git_branch, test_result_id))
            results = cursor.fetchall()
            conn.close()

            columns = [
                "id",
                "test_id",
                "test_name",
                "test_fqn",
                "test_status",
                "test_total_duration",
                "test_start_time",
                "git_commit_hash",
                "git_commit_message",
                "git_commit_author",
                "git_commit_timestamp",
                "ci_job_url",
                "ci_pipeline_url",
            ]

            related_runs = [dict(zip(columns, row, strict=False)) for row in results]

            return {
                "test_fqn": test_fqn,
                "git_branch": git_branch,
                "related_runs": related_runs,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get related test runs: {e!s}"
        ) from e


@app.get("/", response_class=HTMLResponse)
async def serve_interface():
    """Serve the interactive HTML interface."""
    import aiofiles

    async with aiofiles.open(
        Path(__file__).parent / "templates" / "interface.html"
    ) as f:
        html_content = await f.read()
    return HTMLResponse(content=html_content)


def rm_db():
    import os

    os.remove(DB_PATH)


def main():
    """Main entry point for running the service."""
    uvicorn.run("ci_viz_simple.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
