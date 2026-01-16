"""
Main entry point for 100AC.

This file now redirects to the CLI. For the full test suite, use:
    python cli.py test all

Or run this file directly: python main.py
"""

import sys
import subprocess


def main():
    """Run the comprehensive test suite via CLI."""
    print("Running 100AC test suite...\n")
    result = subprocess.run([sys.executable, "cli.py", "test", "all"])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
