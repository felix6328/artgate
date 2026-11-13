#!/usr/bin/env python3
"""评测入口。实现见 scripts/run_eval.py。"""
import runpy
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "scripts"))
runpy.run_path(str(root / "scripts" / "run_eval.py"), run_name="__main__")
