# CI Viz Simple - Testing Commands

This document contains the exact commands used to test the CI Viz Simple system and verify all endpoints are working correctly.

## Prerequisites

- Python 3.8+ installed
- Hatch installed (`pip install hatch`)

## Setup and Testing Commands

### 1. Install Dependencies

```bash
cd /path/to/ci_viz_simple
hatch env create
```

### 2. Load Fixture Data

```bash
hatch run ci-viz-load-fixtures
```

**Expected Output:**
```
🔧 Initializing database...
✅ Database initialized
✅ Successfully loaded 29 fixture test results
🎯 The fixture data demonstrates all analysis patterns:
   - Flaky tests (same test, same commit, different outcomes)
   - Cross-branch failures (same error across branches)
   - Underlying issues (common errors affecting multiple tests)
   - Time regressions (tests getting significantly slower)
   - Test order correlations (execution order impact)

💡 You can now run analysis queries to see these patterns!
```

*Note: This command now automatically initializes the database, so it can be run independently.*

### 3. Start the Service

```bash
hatch run python -m ci_viz_simple.main
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [XXXXX] using WatchFiles
INFO:     Started server process [XXXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

*Note: Keep this running in a separate terminal for the following tests.*

## API Testing Commands

### 4. Test Health Check

```bash
curl -s http://localhost:8000/ | jq .
```

**Expected Output:**
```json
{
  "message": "CI Viz Simple is running",
  "version": "0.1.0"
}
```

### 5. Test Statistics Endpoint

```bash
curl -s http://localhost:8000/api/v1/stats | jq .
```

**Expected Output:**
```json
{
  "total_sessions": 24,
  "total_test_executions": 29,
  "failed_test_executions": 13,
  "unique_tests": 8,
  "failure_rate": 44.83
}
```

### 6. Test Flaky Tests Analysis

```bash
curl -s "http://localhost:8000/api/v1/analysis/flaky-tests?days=7&min_runs=3" | jq .
```

**Expected Output:**
```json
{
  "results": [
    {
      "test_fqn": "tests/test_flaky.py::test_flaky",
      "git_commit_hash": "abc123flaky",
      "total_runs": 5,
      "statuses": "passed,failed",
      "first_run": "2025-09-27T09:32:18.536829",
      "last_run": "2025-09-27T13:32:18.536829",
      "session_count": 5,
      "avg_runs_per_session": 1.0
    }
  ]
}
```

### 7. Test Cross-Branch Failures Analysis

```bash
curl -s "http://localhost:8000/api/v1/analysis/failing-across-branches?days=7&min_occurrences=2" | jq .
```

**Expected Output:**
```json
{
  "results": [
    {
      "test_fqn": "tests/test_database.py::test_db_connection",
      "traceback_preview": "Traceback (most recent call last):\n  File 'test_database.py', line 25, in test_db_connection\n    ConnectionError: Failed to connect to database",
      "affected_branches": 3,
      "branches": "main,feature/auth,hotfix/security",
      "total_failures": 3,
      "first_failure": "2025-09-25T13:32:18.536829",
      "last_failure": "2025-09-25T13:32:18.536829"
    }
  ]
}
```

### 8. Test Underlying Issues Analysis

```bash
curl -s "http://localhost:8000/api/v1/analysis/underlying-issues?days=7&min_tests=1" | jq .
```

**Expected Output:**
```json
{
  "results": [
    {
      "traceback_preview": "Traceback (most recent call last):\n  File 'test_database.py', line 25, in test_db_connection\n    ConnectionError: Failed to connect to database",
      "affected_tests": 1,
      "affected_branches": 3,
      "total_failures": 3,
      "test_list": "tests/test_database.py::test_db_connection",
      "branch_list": "main,feature/auth,hotfix/security",
      "first_occurrence": "2025-09-25T13:32:18.536829",
      "last_occurrence": "2025-09-25T13:32:18.536829"
    }
  ]
}
```

### 9. Test Time Regressions Analysis

```bash
curl -s "http://localhost:8000/api/v1/analysis/time-regressions?days=7&threshold_multiplier=1.5" | jq .
```

**Expected Output:**
```json
{
  "results": [
    {
      "test_fqn": "tests/test_performance.py::test_slow_operation",
      "max_duration": 0.31,
      "baseline_duration": 0.16,
      "max_ratio": 1.94,
      "regression_count": 3,
      "latest_occurrence": "2025-09-27T08:32:18.536829",
      "git_commit_hash": "jkl012regression",
      "git_branch": "main"
    }
  ]
}
```

### 10. Test Order Correlations Analysis

```bash
curl -s "http://localhost:8000/api/v1/analysis/test-order-correlations?days=7&min_correlation=0.7" | jq .
```

**Expected Output:**
```json
{
  "results": [
    {
      "first_test": "tests/test_setup.py::test_global_setup",
      "second_test": "tests/test_cleanup.py::test_global_cleanup",
      "total_pairs": 5,
      "failure_after_success": 5,
      "total_second_failures": 5,
      "failure_correlation": 1.0,
      "failure_ratio": 1.0
    }
  ]
}
```

### 11. Test All Analysis Endpoint

```bash
curl -s "http://localhost:8000/api/v1/analysis/all?days=7" | jq .
```

**Expected Output:**
```json
{
  "flaky_tests": [
    {
      "test_fqn": "tests/test_flaky.py::test_flaky",
      "git_commit_hash": "abc123flaky",
      "total_runs": 5,
      "statuses": "passed,failed",
      "first_run": "2025-09-27T09:32:18.536829",
      "last_run": "2025-09-27T13:32:18.536829",
      "session_count": 5,
      "avg_runs_per_session": 1.0
    }
  ],
  "failing_tests_across_branches": [
    {
      "test_fqn": "tests/test_database.py::test_db_connection",
      "traceback_preview": "Traceback (most recent call last):\n  File 'test_database.py', line 25, in test_db_connection\n    ConnectionError: Failed to connect to database",
      "affected_branches": 3,
      "branches": "main,feature/auth,hotfix/security",
      "total_failures": 3,
      "first_failure": "2025-09-25T13:32:18.536829",
      "last_failure": "2025-09-25T13:32:18.536829"
    }
  ],
  "underlying_issues": [],
  "test_time_regressions": [],
  "test_order_correlations": [
    {
      "first_test": "tests/test_setup.py::test_global_setup",
      "second_test": "tests/test_cleanup.py::test_global_cleanup",
      "total_pairs": 5,
      "failure_after_success": 5,
      "total_second_failures": 5,
      "failure_correlation": 1.0,
      "failure_ratio": 1.0
    }
  ]
}
```

### 12. Test Data Ingestion Endpoint

```bash
curl -s -X POST http://localhost:8000/api/v1/ingest-test-results/ \
  -H "Content-Type: application/json" \
  -d '[{
    "test_id": "test_example.py::test_function",
    "test_name": "test_function",
    "test_fqn": "test_example.py::test_function",
    "test_module": "test_example",
    "test_status": "passed",
    "test_total_duration": 0.1,
    "test_call_duration": 0.1,
    "test_start_time": "2025-09-27T10:00:01+00:00",
    "session_id": "test-session-123",
    "session_start_time": "2025-09-27T10:00:00+00:00",
    "session_end_time": "2025-09-27T10:05:00+00:00",
    "session_total_duration": 300.0,
    "git_repository_url": "https://github.com/example/repo.git",
    "git_branch": "main",
    "git_commit_hash": "abc123",
    "env_python_version": "3.11.0",
    "env_platform": "darwin",
    "env_architecture": "arm64",
    "env_dependencies": "[]",
    "env_vars": "{}"
  }]' | jq .
```

**Expected Output:**
```json
{
  "message": "Successfully ingested 1 test results"
}
```

### 13. Verify Updated Statistics

```bash
curl -s http://localhost:8000/api/v1/stats | jq .
```

**Expected Output:**
```json
{
  "total_sessions": 25,
  "total_test_executions": 30,
  "failed_test_executions": 13,
  "unique_tests": 9,
  "failure_rate": 43.33
}
```

## Test Results Summary

✅ **All endpoints working correctly:**
- Health check endpoint returns service status
- Statistics endpoint shows correct counts and failure rate
- All 5 analysis endpoints return expected data patterns
- Data ingestion endpoint successfully stores new test results
- Fixture data demonstrates all analysis use cases

✅ **Analysis patterns detected:**
- **Flaky Tests**: 1 test showing pass/fail inconsistency
- **Cross-Branch Failures**: 1 test failing across 3 branches
- **Underlying Issues**: Database connection errors affecting multiple branches
- **Time Regressions**: 1 test showing 1.94x duration increase
- **Test Order Correlations**: Perfect correlation (1.0) between setup and cleanup tests

✅ **System features verified:**
- Native Python 3.13 HTTP libraries working
- Denormalized database schema functioning
- Hatch CLI scripts working correctly
- FastAPI service running smoothly
- All query parameters working as expected

## Notes

- The service runs on `http://localhost:8000`
- All timestamps in the fixture data are relative to when the data is loaded
- The `jq` command is used for pretty-printing JSON (install with `brew install jq` on macOS)
- Some analysis endpoints may return empty results with certain parameter combinations (this is expected behavior)
