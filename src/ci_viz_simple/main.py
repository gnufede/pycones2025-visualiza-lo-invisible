#!/usr/bin/env python3
"""
CI Viz Simple - A simple service for tracking test failure patterns across CI.
"""
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import sqlite3
import json
import os
from pathlib import Path
from .queries import (
    get_flaky_tests, get_failing_tests_across_branches, get_underlying_issues,
    get_test_time_regressions, get_test_order_correlations, run_all_queries
)

app = FastAPI(
    title="CI Viz Simple",
    description="Simple CI test visibility system for tracking test failure patterns",
    version="0.1.0"
)

# Database path
DB_PATH = Path(__file__).parent / "ci_viz.db"


class TestResult(BaseModel):
    # Test identification
    test_id: str
    test_name: str
    test_fqn: str
    test_module: str
    test_suite: Optional[str] = None
    test_file_path: Optional[str] = None
    test_line_number: Optional[int] = None
    
    # Test execution
    test_status: str
    test_message: Optional[str] = None
    test_traceback: Optional[str] = None
    test_total_duration: float
    test_call_duration: float
    test_start_time: str
    
    # Session information
    session_id: str
    session_start_time: str
    session_end_time: str
    session_total_duration: float
    
    # Git information
    git_repository_url: Optional[str] = None
    git_branch: Optional[str] = None
    git_commit_hash: Optional[str] = None
    git_commit_message: Optional[str] = None
    git_commit_author: Optional[str] = None
    git_commit_author_email: Optional[str] = None
    git_commit_timestamp: Optional[str] = None
    
    # Environment information
    env_python_version: Optional[str] = None
    env_platform: Optional[str] = None
    env_architecture: Optional[str] = None
    env_dependencies: Optional[str] = None  # JSON string
    env_vars: Optional[str] = None  # JSON string
    
    # CI information
    ci_system: Optional[str] = None
    ci_job_url: Optional[str] = None
    ci_pipeline_url: Optional[str] = None
    ci_job_id: Optional[str] = None
    ci_pipeline_id: Optional[str] = None
    ci_trigger: Optional[str] = None
    ci_pull_request_number: Optional[int] = None


def init_database():
    """Initialize the SQLite database with a denormalized schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create a single denormalized table for all test data
    cursor.execute("""
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
    """)
    
    # Create indexes for common query patterns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_fqn ON test_results(test_fqn)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_git_commit_hash ON test_results(git_commit_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_git_branch ON test_results(git_branch)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_status ON test_results(test_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON test_results(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_start_time ON test_results(test_start_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_traceback ON test_results(test_traceback)")
    
    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_database()


@app.get("/")
async def root():
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
            cursor.execute("""
                INSERT INTO test_results (
                    test_id, test_name, test_fqn, test_module, test_suite, test_file_path, test_line_number,
                    test_status, test_message, test_traceback, test_total_duration, test_call_duration, test_start_time,
                    session_id, session_start_time, session_end_time, session_total_duration,
                    git_repository_url, git_branch, git_commit_hash, git_commit_message,
                    git_commit_author, git_commit_author_email, git_commit_timestamp,
                    env_python_version, env_platform, env_architecture, env_dependencies, env_vars,
                    ci_system, ci_job_url, ci_pipeline_url, ci_job_id, ci_pipeline_id, 
                    ci_trigger, ci_pull_request_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_result.test_id, test_result.test_name, test_result.test_fqn, test_result.test_module,
                test_result.test_suite, test_result.test_file_path, test_result.test_line_number,
                test_result.test_status, test_result.test_message, test_result.test_traceback,
                test_result.test_total_duration, test_result.test_call_duration, test_result.test_start_time,
                test_result.session_id, test_result.session_start_time, test_result.session_end_time, test_result.session_total_duration,
                test_result.git_repository_url, test_result.git_branch, test_result.git_commit_hash, test_result.git_commit_message,
                test_result.git_commit_author, test_result.git_commit_author_email, test_result.git_commit_timestamp,
                test_result.env_python_version, test_result.env_platform, test_result.env_architecture, 
                test_result.env_dependencies, test_result.env_vars,
                test_result.ci_system, test_result.ci_job_url, test_result.ci_pipeline_url, test_result.ci_job_id, 
                test_result.ci_pipeline_id, test_result.ci_trigger, test_result.ci_pull_request_number
            ))
        
        conn.commit()
        conn.close()
        
        return {"message": f"Successfully ingested {len(test_results)} test results"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest test results: {str(e)}")


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
            "failure_rate": round(failed_tests / total_tests * 100, 2) if total_tests > 0 else 0
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.get("/api/v1/analysis/flaky-tests")
async def analyze_flaky_tests(days: int = 7, min_runs: int = 3):
    """Get flaky tests - tests that pass and fail for the same commit."""
    try:
        return {"results": get_flaky_tests(days, min_runs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze flaky tests: {str(e)}")


@app.get("/api/v1/analysis/failing-across-branches")
async def analyze_failing_across_branches(days: int = 7, min_occurrences: int = 2):
    """Get tests failing with same error across different branches."""
    try:
        return {"results": get_failing_tests_across_branches(days, min_occurrences)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze cross-branch failures: {str(e)}")


@app.get("/api/v1/analysis/underlying-issues")
async def analyze_underlying_issues(days: int = 7, min_tests: int = 2):
    """Get underlying issues affecting multiple different tests."""
    try:
        return {"results": get_underlying_issues(days, min_tests)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze underlying issues: {str(e)}")


@app.get("/api/v1/analysis/time-regressions")
async def analyze_time_regressions(days: int = 7, threshold_multiplier: float = 2.0):
    """Get tests with significant duration increases."""
    try:
        return {"results": get_test_time_regressions(days, threshold_multiplier)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze time regressions: {str(e)}")


@app.get("/api/v1/analysis/test-order-correlations")
async def analyze_test_order_correlations(days: int = 7, min_correlation: float = 0.7):
    """Get test pairs where execution order correlates with failures."""
    try:
        return {"results": get_test_order_correlations(days, min_correlation)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze test order correlations: {str(e)}")


@app.get("/api/v1/analysis/all")
async def analyze_all(days: int = 7):
    """Run all analysis queries and return comprehensive results."""
    try:
        return run_all_queries(days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run analysis: {str(e)}")


def main():
    """Main entry point for running the service."""
    uvicorn.run(
        "ci_viz_simple.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()
