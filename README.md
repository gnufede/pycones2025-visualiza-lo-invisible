# CI Viz Simple

A simple demonstration system for tracking test failure patterns across CI environments. Built for a PyCon talk about test and CI visibility.

## Overview

This project demonstrates how to build a system that:
1. Captures comprehensive test execution data during pytest runs
2. Ingests this data into a FastAPI service with SQLite storage
3. Provides analysis endpoints to identify common test failure patterns

## Architecture

- **Test Data Collection**: `conftest.py` captures test execution metadata using native Python 3.13 HTTP
- **Data Ingestion**: FastAPI service receives and stores denormalized test results
- **Storage**: SQLite database with fully denormalized schema for fast queries
- **Analysis**: Pre-built queries for common failure pattern detection
- **CLI Tools**: Hatch scripts for service management and data loading

## Quick Start

### 1. Install Dependencies

```bash
hatch env create
```

### 2. Start the CI Viz Service

```bash
hatch run python -m ci_viz_simple.main
```

The service will start on `http://localhost:8000`. You can view the API documentation at `http://localhost:8000/docs`.

### 3. Load Demo Data (Optional)

```bash
hatch run ci-viz-load-fixtures
```

This loads comprehensive fixture data that demonstrates all analysis patterns.

### 4. Run Tests

```bash
hatch run pytest tests/
```

The `conftest.py` will automatically capture test data and send it to the running service using native Python 3.13 HTTP libraries.

### 5. Run Integration Test (Optional)

To verify the complete problematic test detection feedback loop:

```bash
python run_integration_test.py
```

This will:
1. Backup and reset the database
2. Start the server (if not running)
3. Run tests multiple times to generate data
4. Verify that problematic tests are detected and marked as xfail
5. Confirm xfailed/xpassed statuses are tracked
6. Restore the original database

## CLI Commands

The project includes several hatch scripts for easy management:

- `hatch run python -m ci_viz_simple.main` - Start the FastAPI service
- `hatch run ci-viz-load-fixtures` - Load demo data for all analysis patterns
- `hatch run pytest tests/` - Run tests with automatic data collection

## API Endpoints

### Data Ingestion
- `POST /api/v1/ingest-test-results/` - Ingest test results (denormalized)
- `GET /api/v1/stats` - Get basic statistics

### Analysis Endpoints
- `GET /api/v1/analysis/flaky-tests` - Find flaky tests (same test, same commit, different outcomes)
- `GET /api/v1/analysis/failing-across-branches` - Tests failing with same error across branches
- `GET /api/v1/analysis/underlying-issues` - Common error patterns affecting multiple tests
- `GET /api/v1/analysis/time-regressions` - Tests with significant duration increases
- `GET /api/v1/analysis/test-order-correlations` - Test execution order impact on failures
- `GET /api/v1/analysis/all` - Run all analyses

### CI Integration Endpoints
- `GET /api/v1/problematic-tests` - Get tests currently having issues (for pytest plugin integration)

## Sample Queries Explained

### 1. Flaky Tests
Identifies tests that pass and fail for the same git commit hash, indicating non-deterministic behavior.

**Use case**: Find tests that are unreliable and need investigation.

### 2. Failing Tests Across Branches
Finds tests with the same name failing with identical error messages across different branches.

**Use case**: Identify systematic issues that affect multiple development streams.

### 3. Underlying Issues
Discovers common error patterns affecting different tests across branches.

**Use case**: Find root causes that manifest in multiple test failures.

### 4. Test Time Regressions
Detects tests whose execution time has increased significantly compared to baseline.

**Use case**: Identify performance regressions in test code or application code.

### 5. Test Order Correlations
Analyzes whether certain test execution orders correlate with failures.

**Use case**: Find tests that have hidden dependencies or side effects.

### 6. Problematic Tests Integration
Combines results from flaky tests, cross-branch failures, and underlying issues analyses to identify tests that should be marked as expected failures in CI.

**Use case**: Prevent known problematic tests from failing CI builds while they're being fixed.

## Configuration

### Environment Variables

- `CI_VIZ_URL`: URL of the CI Viz service (default: `http://localhost:8000`)
- `CI_VIZ_DEBUG`: Enable debug output (default: `true`)

#### Problematic Tests Integration
- `CI_VIZ_PROBLEMATIC_DAYS`: Days to look back for problematic test analysis (default: `7`)
- `CI_VIZ_MIN_RUNS`: Minimum runs required to analyze a test (default: `3`)

### Query Parameters

All analysis endpoints support these parameters:
- `days`: Time window for analysis (default: 7)
- Additional parameters specific to each analysis type

## Data Schema

The system uses a fully denormalized SQLite schema (`test_results` table) that stores all data in a single table:

- **Test Identification**: Test ID, name, FQN, module, suite, file path, line number
- **Test Execution**: Status, message, traceback, durations, start time, problematic marker
- **Session Information**: Unique session ID, timestamps, duration
- **Git Information**: Repository, branch, commit hash, author, message, timestamp
- **Environment**: Python version, platform, architecture, dependencies, environment variables
- **CI Information**: CI system details, job URLs, pipeline information, trigger, PR number

### Test Statuses

The system recognizes the following test statuses:
- `passed` - Test succeeded
- `failed` - Test failed
- `error` - Test encountered an error
- `skipped` - Test was skipped
- `xfailed` - Test was expected to fail (marked as problematic) and did fail
- `xpassed` - Test was expected to fail (marked as problematic) but passed (improvement detected!)

This denormalized approach enables fast queries across all dimensions without complex joins.

## Example Usage

### Running Analysis

```bash
# Load demo data first
hatch run ci-viz-load-fixtures

# Get flaky tests from the last 14 days
curl "http://localhost:8000/api/v1/analysis/flaky-tests?days=14&min_runs=5"

# Find time regressions with 3x threshold
curl "http://localhost:8000/api/v1/analysis/time-regressions?threshold_multiplier=3.0"

# Get comprehensive analysis
curl "http://localhost:8000/api/v1/analysis/all?days=30"

# Get problematic tests for CI integration (just test FQNs)
curl "http://localhost:8000/api/v1/problematic-tests?git_branch=main&detailed=false"
```

### Custom Test Data

You can also send custom test data directly as denormalized test results:

```python
import urllib.request
import json

test_results = [
    {
        "test_id": "test_example.py::test_function",
        "test_name": "test_function",
        "test_fqn": "test_example.py::test_function",
        "test_module": "test_example",
        "test_status": "passed",
        "test_total_duration": 0.1,
        "test_call_duration": 0.1,
        "test_start_time": "2025-09-27T10:00:01+00:00",
        "session_id": "custom-session-123",
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
        "env_vars": "{}",
        # ... other fields
    }
]

url = "http://localhost:8000/api/v1/ingest-test-results/"
data = json.dumps(test_results).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
response = urllib.request.urlopen(req)
```

## CI Integration: Problematic Tests Auto-Detection

The CI Viz system includes an advanced feature that automatically identifies problematic tests and marks them as expected failures during pytest runs. This prevents known flaky or consistently failing tests from breaking your CI pipeline while they're being investigated and fixed.

### How It Works

1. **At Session Start**: The pytest plugin calls the `/api/v1/problematic-tests` endpoint
2. **Analysis**: The system combines results from existing analysis queries to identify:
   - **Flaky tests**: From the flaky tests analysis (same test, same commit, different outcomes)
   - **Cross-branch failures**: From the cross-branch analysis (same error across branches)
   - **Systemic issues**: From the underlying issues analysis (common errors affecting multiple tests)
3. **Auto-marking**: Problematic tests are automatically marked with `pytest.mark.xfail`
4. **CI Protection**: These tests won't fail your CI build, but you'll still see their results

### Configuration

The integration is controlled by environment variables:

```bash
# Basic configuration
export CI_VIZ_URL="http://localhost:8000"
export CI_VIZ_DEBUG="true"

# Problematic test detection tuning
export CI_VIZ_PROBLEMATIC_DAYS="7"        # Days of history to analyze
export CI_VIZ_MIN_RUNS="3"                # Minimum runs to consider a test
```

### Example Usage

```bash
# Start the CI Viz service
hatch run python -m ci_viz_simple.main

# Load some demo data to see the feature in action
hatch run ci-viz-load-fixtures

# Run tests - problematic tests will be auto-detected and marked as xfail
hatch run pytest tests/ -v

# Check what tests were marked as problematic
curl "http://localhost:8000/api/v1/problematic-tests?git_branch=main&detailed=false"

# Query for xfailed tests (tests that were marked problematic and failed as expected)
curl "http://localhost:8000/api/v1/test-results/?test_status=xfailed&limit=10"

# Query for xpassed tests (tests that were marked problematic but passed - improvement!)
curl "http://localhost:8000/api/v1/test-results/?test_status=xpassed&limit=10"
```

### Benefits

- **Stable CI**: Known problematic tests won't break your builds
- **Visibility**: You still see test results and can track improvements
- **Automatic**: No manual maintenance of xfail markers
- **Data-driven**: Based on actual test execution history
- **Flexible**: Configurable thresholds for different project needs

### API Endpoint Details

The `/api/v1/problematic-tests` endpoint supports:

- **Repository filtering**: `git_repository_url` parameter
- **Branch filtering**: `git_branch` parameter  
- **Time window**: `days` parameter (default: 7)
- **Minimum runs**: `min_runs` parameter (default: 3)
- **Output format**: `detailed=false` for just test FQNs, `detailed=true` for full analysis

## Development

### Project Structure

```
src/ci_viz_simple/
├── __init__.py
├── main.py          # FastAPI application with denormalized TestResult model
├── queries.py       # Analysis query implementations
└── fixtures.py      # Demo fixture data + CLI script for loading

tests/
├── conftest.py                    # pytest plugin using native Python 3.13 HTTP
├── test_demo.py                   # Demo tests
├── test_problematic_integration.py # Flaky tests for integration testing
├── test_integration.py            # Integration test module
└── ...

run_integration_test.py  # Standalone integration test runner
pyproject.toml           # Hatch configuration with CLI scripts
```

### Adding New Analysis Queries

1. Add your query function to `queries.py`
2. Add a corresponding endpoint in `main.py`
3. Update the `run_all_queries()` function if needed

## Key Features

- **Minimal Dependencies**: Only FastAPI, uvicorn, and pydantic
- **Native Python**: Uses Python 3.13's built-in HTTP libraries (no requests)
- **Fully Denormalized**: Single table design for maximum query performance
- **Hatch Integration**: Modern Python project management with CLI scripts
- **Comprehensive Demo Data**: Shows all analysis patterns immediately
- **Production Ready**: Proper error handling and graceful degradation

## Use Cases for PyCon Talk

This system demonstrates several key concepts:

1. **Observability**: How to instrument test suites for better visibility
2. **Data-Driven Decisions**: Using test execution data to improve reliability
3. **Pattern Recognition**: Automated detection of common failure modes
4. **CI/CD Integration**: Seamless integration with existing test workflows
5. **Closing the Loop**: Automatic CI protection based on test history analysis
6. **Modern Python**: Using latest Python features and best practices

## Future Enhancements

- Web dashboard for visualization
- Integration with more CI systems
- Machine learning for failure prediction
- Test result trending and alerting
- Integration with issue tracking systems

## License

This project is created for educational purposes as part of a PyCon talk demonstration.
