# SQL Learning Guide for CI Viz Queries

This guide explains the key SQL concepts used in the CI Viz queries, perfect for SQL beginners!

## 🎯 Key SQL Concepts Used

### 1. **CTEs (Common Table Expressions) - `WITH`**
```sql
WITH my_cte AS (
    SELECT * FROM table1
)
SELECT * FROM my_cte
```
- **What it does**: Creates a temporary named result set that you can reference later
- **Why we use it**: Breaks complex queries into readable steps
- **Think of it as**: Like creating a variable in programming, but for SQL data

### 2. **GROUP BY and Aggregation**
```sql
SELECT column1, COUNT(*), SUM(column2)
FROM table
GROUP BY column1
```
- **What it does**: Groups rows with the same values together and calculates totals
- **Why we use it**: To count, sum, or average data within groups
- **Example**: Group all test runs by test name to count how many times each test ran

### 3. **Conditional Aggregation - `CASE WHEN`**
```sql
SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed_count
```
- **What it does**: Counts only rows that meet a specific condition
- **Why we use it**: To count different types of things in one query
- **Example**: Count how many tests passed vs failed in the same query

### 4. **Window Functions - `ROW_NUMBER() OVER`**
```sql
ROW_NUMBER() OVER (PARTITION BY test_fqn ORDER BY test_start_time) as run_order
```
- **What it does**: Creates a sequence number for each row within a group
- **Why we use it**: To order things and find "first", "second", "last" items
- **Example**: Number test runs chronologically to find the first 5 runs (baseline)

### 5. **JOINs**
```sql
FROM table1 t1
JOIN table2 t2 ON t1.id = t2.foreign_id
```
- **What it does**: Combines data from multiple tables
- **Why we use it**: To get related information together
- **Example**: Join test runs with their baseline data

### 6. **HAVING vs WHERE**
```sql
WHERE condition1          -- Filters individual rows
GROUP BY column
HAVING condition2         -- Filters groups after grouping
```
- **WHERE**: Filters rows before grouping
- **HAVING**: Filters groups after grouping
- **Example**: `WHERE test_status = 'failed'` vs `HAVING COUNT(*) > 5`

## 🔍 Query-by-Query Breakdown

### **Query 1: Flaky Tests**
**Goal**: Find tests that sometimes pass and sometimes fail on the same commit

**Key Logic**:
1. Group all test runs by `(test_fqn, git_commit_hash)` - same test, same commit
2. Count how many passed vs failed within each group
3. Only keep groups where both `passed_count > 0` AND `failed_count > 0`

**SQL Techniques**:
- `GROUP BY` to group runs by test and commit
- `CASE WHEN` to count different statuses
- `HAVING` to filter groups (not individual rows)

### **Query 2: Cross-Branch Failures**
**Goal**: Find tests failing with identical errors across multiple branches

**Key Logic**:
1. Group failures by `(test_fqn, test_traceback)` - same test, same error
2. Count how many different branches are affected
3. Only keep groups where `affected_branches > 1`

**SQL Techniques**:
- `GROUP BY` with two columns
- `COUNT(DISTINCT git_branch)` to count unique branches
- `GROUP_CONCAT()` to create comma-separated lists

### **Query 3: Underlying Issues**
**Goal**: Find identical error patterns affecting multiple different tests

**Key Logic**:
1. Group ALL failures by `test_traceback` only - same error, any test
2. Count how many different tests are affected
3. Only keep groups where `affected_tests >= min_tests`

**SQL Techniques**:
- `GROUP BY` with just one column (traceback)
- `COUNT(DISTINCT test_fqn)` to count unique tests
- This finds systemic issues (like database problems) affecting multiple tests

### **Query 4: Time Regressions**
**Goal**: Find tests that have gotten significantly slower over time

**Key Logic**:
1. Number all test runs chronologically using `ROW_NUMBER()`
2. Use first 5 runs as "baseline" (normal speed)
3. Compare recent runs against baseline
4. Flag runs that are significantly slower

**SQL Techniques**:
- `ROW_NUMBER() OVER()` to create chronological order
- Multiple CTEs to break down the logic
- `JOIN` to match tests with their baselines
- Division to calculate speed ratios

### **Query 5: Test Order Correlations**
**Goal**: Find tests that might be causing other tests to fail

**Key Logic**:
1. Number all tests within each session by execution time
2. Create all possible pairs of tests that ran in the same session
3. Count how often the second test fails when the first test passes
4. Calculate correlation ratios

**SQL Techniques**:
- `ROW_NUMBER() OVER()` to order tests within sessions
- Self-`JOIN` to create all possible pairs
- Complex `CASE WHEN` statements to count different scenarios
- Mathematical ratios to measure correlation strength

## 🧠 Mental Models

### **GROUP BY**: "Group similar things together"
- Like sorting your laundry: all shirts together, all pants together
- Then count how many of each type you have

### **CTEs**: "Break big problems into smaller steps"
- Like cooking: first prep ingredients, then cook, then serve
- Each CTE is one step in the recipe

### **Window Functions**: "Number things in order"
- Like giving people numbers in a line: 1st, 2nd, 3rd...
- But you can restart numbering for each group

### **JOINs**: "Connect related information"
- Like looking up a person's address in a phone book
- Connect two pieces of information that belong together

## 🎯 Common Patterns

### **Counting with Conditions**
```sql
SUM(CASE WHEN condition THEN 1 ELSE 0 END)
```
- Counts only rows that meet the condition
- More efficient than filtering and counting separately

### **Finding "First" or "Last" Items**
```sql
ROW_NUMBER() OVER (PARTITION BY group ORDER BY time) as order
WHERE order = 1  -- First item
```

### **Grouping and Filtering**
```sql
GROUP BY column
HAVING COUNT(*) > threshold  -- Filter groups, not individual rows
```

### **Creating Lists**
```sql
GROUP_CONCAT(DISTINCT column)  -- Creates comma-separated lists
```

## 🚀 Next Steps

1. **Practice with simpler queries first** - Start with basic SELECT, WHERE, GROUP BY
2. **Understand the data** - Look at the `test_results` table structure
3. **Experiment** - Try modifying the queries to see what happens
4. **Read the comments** - Each query has detailed inline comments explaining every step

Remember: SQL is like a very powerful calculator for data. You're telling it what data you want and how you want it organized!
