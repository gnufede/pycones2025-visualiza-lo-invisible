#!/usr/bin/env python3
"""
Standalone integration test script for CI Viz.

Usage:
    python run_integration_test.py

Or with hatch:
    hatch run python run_integration_test.py
"""

import sys
from pathlib import Path

# Add tests directory to path
sys.path.insert(0, str(Path(__file__).parent / "tests"))

from test_integration import main

if __name__ == "__main__":
    sys.exit(main())

