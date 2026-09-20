"""Reuse the validated Motion Lab renderer for the separate directing pass."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_combat_motion_lab as render

render.OUT = render.ROOT / "outputs/combat_motion_lab_astra"
render.main()
