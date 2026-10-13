#!/usr/bin/env python3
"""B2-FS-A: complete golden examples enter only the action selector."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_b2_fixed_examples import main


if __name__ == "__main__":
    main("action")
