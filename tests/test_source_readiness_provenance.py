from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_EVENT_SHA256 = "4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_readiness_does_not_change_canonical_events():
    paths = [
        ROOT / "outputs/combat_motion_lab_hero_exchange/source/events.json",
        ROOT / "outputs/combat_motion_lab_paired_source_gate/source/events.json",
        ROOT / "outputs/combat_motion_lab_source_readiness/source/events.json",
    ]
    assert all(path.exists() for path in paths)
    assert {digest(path) for path in paths} == {EXPECTED_EVENT_SHA256}
