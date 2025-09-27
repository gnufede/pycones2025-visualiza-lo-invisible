"""
Fixture data for demonstrating all analysis use cases.
"""
import json
from datetime import datetime, timedelta
from .main import TestResult


def create_fixture_data():
    """Create comprehensive fixture data that demonstrates all analysis patterns."""
    base_time = datetime.now()
    
    # Common data
    common_git = {
        "git_repository_url": "https://github.com/example/ci-viz-demo.git",
        "git_commit_author": "Federico Mon",
        "git_commit_author_email": "federico.mon@datadoghq.com",
    }
    
    common_env = {
        "env_python_version": "3.13.0",
        "env_platform": "darwin",
        "env_architecture": "arm64",
        "env_dependencies": json.dumps(["pytest>=7.4.0", "fastapi>=0.104.0"]),
        "env_vars": json.dumps({"CI": "true", "CI_PROVIDER": "github-actions"}),
    }
    
    common_ci = {
        "ci_system": "GitHub Actions",
        "ci_job_url": "https://github.com/example/ci-viz-demo/actions/runs/123456",
        "ci_pipeline_url": "https://github.com/example/ci-viz-demo/actions",
        "ci_job_id": "123456",
        "ci_pipeline_id": "789",
        "ci_trigger": "push",
    }
    
    test_results = []
    
    # 1. FLAKY TESTS - Same test, same commit, different outcomes
    flaky_commit = "abc123flaky"
    flaky_times = [base_time - timedelta(hours=i) for i in range(5)]
    
    for i, test_time in enumerate(flaky_times):
        # Flaky test that passes 60% of the time
        status = "passed" if i % 5 < 3 else "failed"
        test_results.append(TestResult(
            test_id=f"test_flaky_{i}",
            test_name="test_flaky",
            test_fqn="tests/test_flaky.py::test_flaky",
            test_module="tests.test_flaky",
            test_suite=None,
            test_file_path="tests/test_flaky.py",
            test_line_number=10,
            test_status=status,
            test_message="Simulated flaky failure" if status == "failed" else None,
            test_traceback="AssertionError: Simulated flaky failure" if status == "failed" else None,
            test_total_duration=0.1 + (i * 0.01),
            test_call_duration=0.1 + (i * 0.01),
            test_start_time=test_time.isoformat(),
            session_id=f"session_flaky_{i}",
            session_start_time=(test_time - timedelta(minutes=1)).isoformat(),
            session_end_time=(test_time + timedelta(minutes=1)).isoformat(),
            session_total_duration=120.0,
            git_repository_url=common_git["git_repository_url"],
            git_branch="main",
            git_commit_hash=flaky_commit,
            git_commit_message="Add flaky test",
            git_commit_author=common_git["git_commit_author"],
            git_commit_author_email=common_git["git_commit_author_email"],
            git_commit_timestamp=(test_time - timedelta(days=1)).isoformat(),
            env_python_version=common_env["env_python_version"],
            env_platform=common_env["env_platform"],
            env_architecture=common_env["env_architecture"],
            env_dependencies=common_env["env_dependencies"],
            env_vars=common_env["env_vars"],
            ci_system=common_ci["ci_system"],
            ci_job_url=common_ci["ci_job_url"],
            ci_pipeline_url=common_ci["ci_pipeline_url"],
            ci_job_id=common_ci["ci_job_id"],
            ci_pipeline_id=common_ci["ci_pipeline_id"],
            ci_trigger=common_ci["ci_trigger"],
        ))
    
    # 2. FAILING TESTS ACROSS BRANCHES - Same error across different branches
    shared_error = "ConnectionError: Failed to connect to database"
    branches = ["main", "feature/auth", "hotfix/security"]
    
    for branch in branches:
        commit_hash = f"def456{branch.replace('/', '')}"
        test_time = base_time - timedelta(days=2)
        
        test_results.append(TestResult(
            test_id=f"test_db_connection_{branch}",
            test_name="test_db_connection",
            test_fqn="tests/test_database.py::test_db_connection",
            test_module="tests.test_database",
            test_suite=None,
            test_file_path="tests/test_database.py",
            test_line_number=25,
            test_status="failed",
            test_message=shared_error,
            test_traceback=f"Traceback (most recent call last):\n  File 'test_database.py', line 25, in test_db_connection\n    {shared_error}",
            test_total_duration=2.5,
            test_call_duration=2.5,
            test_start_time=test_time.isoformat(),
            session_id=f"session_db_{branch}",
            session_start_time=(test_time - timedelta(minutes=2)).isoformat(),
            session_end_time=(test_time + timedelta(minutes=2)).isoformat(),
            session_total_duration=240.0,
            git_repository_url=common_git["git_repository_url"],
            git_branch=branch,
            git_commit_hash=commit_hash,
            git_commit_message=f"Update database tests on {branch}",
            git_commit_author=common_git["git_commit_author"],
            git_commit_author_email=common_git["git_commit_author_email"],
            git_commit_timestamp=(test_time - timedelta(hours=6)).isoformat(),
            env_python_version=common_env["env_python_version"],
            env_platform=common_env["env_platform"],
            env_architecture=common_env["env_architecture"],
            env_dependencies=common_env["env_dependencies"],
            env_vars=common_env["env_vars"],
            ci_system=common_ci["ci_system"],
            ci_job_url=common_ci["ci_job_url"],
            ci_pipeline_url=common_ci["ci_pipeline_url"],
            ci_job_id=common_ci["ci_job_id"],
            ci_pipeline_id=common_ci["ci_pipeline_id"],
            ci_trigger=common_ci["ci_trigger"],
        ))
    
    # 3. UNDERLYING ISSUES - Same error affecting different tests
    underlying_error = "ImportError: No module named 'missing_dependency'"
    affected_tests = [
        "tests/test_auth.py::test_login",
        "tests/test_api.py::test_user_endpoint", 
        "tests/test_models.py::test_user_model"
    ]
    
    for i, test_fqn in enumerate(affected_tests):
        test_time = base_time - timedelta(days=1)
        test_results.append(TestResult(
            test_id=f"test_underlying_{i}",
            test_name=test_fqn.split("::")[-1],
            test_fqn=test_fqn,
            test_module=test_fqn.split("::")[0].replace("/", ".").replace(".py", ""),
            test_suite=None,
            test_file_path=test_fqn.split("::")[0],
            test_line_number=15 + (i * 5),
            test_status="failed",
            test_message=underlying_error,
            test_traceback=f"Traceback (most recent call last):\n  File '{test_fqn.split('::')[0]}', line {15 + (i * 5)}, in {test_fqn.split('::')[-1]}\n    {underlying_error}",
            test_total_duration=0.05,
            test_call_duration=0.05,
            test_start_time=test_time.isoformat(),
            session_id=f"session_underlying_{i}",
            session_start_time=(test_time - timedelta(minutes=1)).isoformat(),
            session_end_time=(test_time + timedelta(minutes=1)).isoformat(),
            session_total_duration=120.0,
            git_repository_url=common_git["git_repository_url"],
            git_branch="main",
            git_commit_hash="ghi789underlying",
            git_commit_message="Add new dependency requirements",
            git_commit_author=common_git["git_commit_author"],
            git_commit_author_email=common_git["git_commit_author_email"],
            git_commit_timestamp=(test_time - timedelta(hours=2)).isoformat(),
            env_python_version=common_env["env_python_version"],
            env_platform=common_env["env_platform"],
            env_architecture=common_env["env_architecture"],
            env_dependencies=common_env["env_dependencies"],
            env_vars=common_env["env_vars"],
            ci_system=common_ci["ci_system"],
            ci_job_url=common_ci["ci_job_url"],
            ci_pipeline_url=common_ci["ci_pipeline_url"],
            ci_job_id=common_ci["ci_job_id"],
            ci_pipeline_id=common_ci["ci_pipeline_id"],
            ci_trigger=common_ci["ci_trigger"],
        ))
    
    # 4. TEST TIME REGRESSIONS - Tests getting slower over time
    regression_commit = "jkl012regression"
    baseline_duration = 0.1
    
    for i in range(8):  # 8 runs showing regression
        test_time = base_time - timedelta(hours=12-i)
        # Duration increases from 0.1s to 2.0s (20x regression)
        duration = baseline_duration * (1 + i * 0.3)
        
        test_results.append(TestResult(
            test_id=f"test_slow_{i}",
            test_name="test_slow_operation",
            test_fqn="tests/test_performance.py::test_slow_operation",
            test_module="tests.test_performance",
            test_suite=None,
            test_file_path="tests/test_performance.py",
            test_line_number=30,
            test_status="passed",
            test_message=None,
            test_traceback=None,
            test_total_duration=duration,
            test_call_duration=duration,
            test_start_time=test_time.isoformat(),
            session_id=f"session_slow_{i}",
            session_start_time=(test_time - timedelta(minutes=1)).isoformat(),
            session_end_time=(test_time + timedelta(minutes=1)).isoformat(),
            session_total_duration=120.0,
            git_repository_url=common_git["git_repository_url"],
            git_branch="main",
            git_commit_hash=regression_commit,
            git_commit_message="Optimize slow operations",
            git_commit_author=common_git["git_commit_author"],
            git_commit_author_email=common_git["git_commit_author_email"],
            git_commit_timestamp=(test_time - timedelta(hours=1)).isoformat(),
            env_python_version=common_env["env_python_version"],
            env_platform=common_env["env_platform"],
            env_architecture=common_env["env_architecture"],
            env_dependencies=common_env["env_dependencies"],
            env_vars=common_env["env_vars"],
            ci_system=common_ci["ci_system"],
            ci_job_url=common_ci["ci_job_url"],
            ci_pipeline_url=common_ci["ci_pipeline_url"],
            ci_job_id=common_ci["ci_job_id"],
            ci_pipeline_id=common_ci["ci_pipeline_id"],
            ci_trigger=common_ci["ci_trigger"],
        ))
    
    # 5. TEST ORDER CORRELATIONS - Tests that fail when run after others
    correlation_tests = [
        ("tests/test_setup.py::test_global_setup", "passed"),
        ("tests/test_cleanup.py::test_global_cleanup", "failed"),
    ]
    
    for session_num in range(5):  # 5 sessions showing correlation
        session_time = base_time - timedelta(hours=6-session_num)
        
        for i, (test_fqn, expected_status) in enumerate(correlation_tests):
            # The cleanup test fails when run after setup test
            actual_status = "failed" if i == 1 and session_num > 2 else expected_status
            
            test_results.append(TestResult(
                test_id=f"test_correlation_{session_num}_{i}",
                test_name=test_fqn.split("::")[-1],
                test_fqn=test_fqn,
                test_module=test_fqn.split("::")[0].replace("/", ".").replace(".py", ""),
                test_suite=None,
                test_file_path=test_fqn.split("::")[0],
                test_line_number=20 + (i * 10),
                test_status=actual_status,
                test_message="Global state not properly reset" if actual_status == "failed" else None,
                test_traceback="AssertionError: Global state not properly reset" if actual_status == "failed" else None,
                test_total_duration=0.2 + (i * 0.1),
                test_call_duration=0.2 + (i * 0.1),
                test_start_time=(session_time + timedelta(minutes=i)).isoformat(),
                session_id=f"session_correlation_{session_num}",
                session_start_time=session_time.isoformat(),
                session_end_time=(session_time + timedelta(minutes=5)).isoformat(),
                session_total_duration=300.0,
                git_repository_url=common_git["git_repository_url"],
                git_branch="main",
                git_commit_hash=f"mno345correlation{session_num}",
                git_commit_message=f"Fix test isolation issues - session {session_num}",
                git_commit_author=common_git["git_commit_author"],
                git_commit_author_email=common_git["git_commit_author_email"],
                git_commit_timestamp=(session_time - timedelta(hours=1)).isoformat(),
                env_python_version=common_env["env_python_version"],
                env_platform=common_env["env_platform"],
                env_architecture=common_env["env_architecture"],
                env_dependencies=common_env["env_dependencies"],
                env_vars=common_env["env_vars"],
                ci_system=common_ci["ci_system"],
                ci_job_url=common_ci["ci_job_url"],
                ci_pipeline_url=common_ci["ci_pipeline_url"],
                ci_job_id=common_ci["ci_job_id"],
                ci_pipeline_id=common_ci["ci_pipeline_id"],
                ci_trigger=common_ci["ci_trigger"],
            ))
    
    return test_results


def load_fixture_data():
    """Load fixture data into the database."""
    from .main import DB_PATH
    import sqlite3
    
    test_results = create_fixture_data()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
    
    return len(test_results)


def load_fixtures_cli():
    """CLI entry point for loading fixture data."""
    import sys
    
    try:
        count = load_fixture_data()
        print(f"✅ Successfully loaded {count} fixture test results")
        print("🎯 The fixture data demonstrates all analysis patterns:")
        print("   - Flaky tests (same test, same commit, different outcomes)")
        print("   - Cross-branch failures (same error across branches)")
        print("   - Underlying issues (common errors affecting multiple tests)")
        print("   - Time regressions (tests getting significantly slower)")
        print("   - Test order correlations (execution order impact)")
        print("\n💡 You can now run analysis queries to see these patterns!")
        return 0
    except Exception as e:
        print(f"❌ Failed to load fixtures: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(load_fixtures_cli())
