#!/usr/bin/env python3
"""B2-FS-RA: complete golden examples enter both B2 LLM stages."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_b2_fixed_examples import main


if __name__ == "__main__":
    main("both")
