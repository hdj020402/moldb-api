#!/usr/bin/env python3
"""Thin launcher for development use (python main.py ...)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from moldb.cli import main

if __name__ == "__main__":
    main()
