"""Pytest bootstrap.

Puts the project root on sys.path so `import utils` and `import main` work no
matter how pytest is launched (pytest, python -m pytest, coverage run -m pytest)
and from any working directory.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
