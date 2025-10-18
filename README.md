# Test Observability Project

A simple demonstration system for tracking test failure patterns across CI environments. Built for a PyConES 2025 talk about test and CI visibility.

## Overview

This project demonstrates how to build a system that:
1. Captures comprehensive test execution data during pytest runs
2. Ingests this data into a FastAPI service with SQLite storage
3. Provides analysis endpoints to identify common test failure patterns
4. Exposes flaky tests via API to the pytest plugin 

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
hatch run ci-viz
```

The service will start on `http://localhost:8000`

### 3. Load Demo Data (Optional)

```bash
hatch run ci-viz-load-fixtures
```

This loads comprehensive fixture data that demonstrates all analysis patterns.

### 4. Run Tests

```bash
hatch test
```

The `conftest.py` will automatically capture test data and send it to the running service using standard Python 3.13 HTTP libraries.


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


## CI Integration: Problematic Tests Auto-Detection

The CI Viz system includes an advanced feature that automatically identifies problematic tests and marks them as expected failures during pytest runs. This prevents known flaky or consistently failing tests from breaking your CI pipeline while they're being investigated and fixed.

### How It Works

1. **At Session Start**: The pytest plugin calls the `/api/v1/problematic-tests` endpoint
2. **Analysis**: The system combines results from existing analysis queries to identify:
   - **Flaky tests**: From the flaky tests analysis (same test, same commit, different outcomes)
   - **Cross-branch failures**: From the cross-branch analysis (same error across branches)
   - **Systemic issues**: From the underlying issues analysis (common errors affecting multiple tests)
3. **Exception Matching**: The system provides a list of expected exception messages for each problematic test
4. **Runtime Checking**: When a test fails, the actual exception is compared against expected exceptions
5. **Smart xfail**: Only marks as xfail if the exception matches - **different exceptions fail normally to catch new bugs!**
6. **CI Protection**: Known failures won't break your CI build, but new bugs will still be caught

### Why Exception Matching?

**The Problem with Upfront Marking**: If we mark tests as xfail *before* they run, we hide ALL failures, including new bugs with different exceptions.

**Our Solution**: Match actual exceptions against expected ones at runtime:
- ✅ Test fails with known exception → Marked as xfail (expected failure)
- ✗ Test fails with different exception → Normal failure (alerts developers to new bug!)
- ✅ Test passes → Shows as xpassed (flakiness may be resolved!)

See `EXCEPTION_MATCHING.md` for detailed documentation and examples.

### Configuration

The integration is controlled by environment variables:

```bash
# Basic configuration
export CI_VIZ_URL="http://localhost:8000"
export CI_VIZ_DEBUG="true"

