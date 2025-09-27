"""
SQL-like query parser for test results filtering.
"""
import re
from typing import List, Tuple


# Valid fields for security - all fields from test_results table
VALID_FIELDS = {
    # Test identification
    'id', 'test_id', 'test_name', 'test_fqn', 'test_module', 'test_suite', 
    'test_file_path', 'test_line_number',
    
    # Test execution
    'test_status', 'test_message', 'test_traceback', 'test_total_duration', 
    'test_call_duration', 'test_start_time',
    
    # Session information
    'session_id', 'session_start_time', 'session_end_time', 'session_total_duration',
    
    # Git information
    'git_repository_url', 'git_branch', 'git_commit_hash', 'git_commit_message',
    'git_commit_author', 'git_commit_author_email', 'git_commit_timestamp',
    
    # Environment information
    'env_python_version', 'env_platform', 'env_architecture', 'env_dependencies', 'env_vars',
    
    # CI information
    'ci_system', 'ci_job_url', 'ci_pipeline_url', 'ci_job_id', 'ci_pipeline_id',
    'ci_trigger', 'ci_pull_request_number',
    
    # Metadata
    'created_at'
}

VALID_OPERATORS = {'=', '!=', '<', '>', '<=', '>='}

def parse_sql_like_query(query: str) -> Tuple[str, List[str]]:
    """
    Parse a SQL-like query string into SQL WHERE clause and parameters.
    
    Supported operators: =, !=, <, >, <=, >=, LIKE, AND, OR
    Supported fields: All fields from test_results table
    
    Example: "test_name like '%test%' and git_branch = 'main'"
    """
    query = query.strip()
    if not query:
        raise ValueError("Empty query")
    
    # Split by AND/OR but preserve the operators
    parts = re.split(r'\s+(and|or)\s+', query, flags=re.IGNORECASE)
    
    if len(parts) == 1:
        # Single condition
        return parse_condition(parts[0].strip())
    else:
        # Multiple conditions
        where_parts = []
        all_params = []
        
        for i in range(0, len(parts), 2):
            condition = parts[i].strip()
            where_part, params = parse_condition(condition)
            where_parts.append(where_part)
            all_params.extend(params)
            
            # Add operator if not the last part
            if i + 1 < len(parts):
                operator = parts[i + 1].strip().upper()
                if operator not in ('AND', 'OR'):
                    raise ValueError(f"Invalid operator: {operator}")
                where_parts.append(operator)
        
        return ' '.join(where_parts), all_params


def parse_condition(condition: str) -> Tuple[str, List[str]]:
    """Parse a single condition like 'test_name like %test%'"""
    # Match field operator value pattern
    pattern = r'(\w+)\s+(=|!=|<|>|<=|>=|like)\s+(.+?)(?:\s*$)'
    match = re.match(pattern, condition, re.IGNORECASE)
    
    if not match:
        raise ValueError(f"Invalid condition format: {condition}")
    
    field, operator, value = match.groups()
    field = field.lower()
    
    # Validate field
    if field not in VALID_FIELDS:
        raise ValueError(f"Invalid field: {field}. Valid fields: {', '.join(sorted(VALID_FIELDS))}")
    
    # Clean up value (remove quotes)
    value = value.strip()
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        value = value[1:-1]
    
    # Handle LIKE operator
    if operator.upper() == 'LIKE':
        return f"{field} LIKE ?", [value]
    
    # Handle other operators

    if operator not in VALID_OPERATORS:
        raise ValueError(f"Invalid operator: {operator}")
    
    return f"{field} {operator} ?", [value]
