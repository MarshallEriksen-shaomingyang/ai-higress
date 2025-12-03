"""
Shared pytest configuration.

This file ensures the project root is on sys.path so that `import app`
works consistently in all tests.
"""

import sys
from pathlib import Path

# Ensure project root is importable for test modules.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
