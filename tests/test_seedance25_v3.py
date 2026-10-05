"""The visual revision adds camera variety without changing canonical combat."""

import json
import shutil

import pytest

from whowouldwin.cinematic.seedance.longform_seed289 import EVENT_SHA
from whowouldwin.cinematic.seedance.seedance25_v2 import SEQUENCES
from whowouldwin.cinematic.seedance.seedance25_v3 import build, upgrade_motion_references, validate_v3
from whowouldwin.cinematic.seedance.seedance25_v3_art import CAMERAS, frame_at


def test_camera_plan_has_distinct_views_and_original_motion_frames():
    angles = {cue.angle for cues in CAMERAS.values() for cue in cues}
    assert {"low", "side", "three_quarter", "high", "overhead", "over_shoulder"} <= angles
    assert all(len(CAMERAS[index]) >= 3 for index in range(1, 10))
    sequence = SEQUENCES[3]
    side = frame_at(sequence.keys, sequence.index, 3.8)
    overhead = frame_at(sequence.keys, sequence.index, 2.2)
    assert side.size == (360, 640)
    assert side.tobytes() != overhead.tobytes()


def test_v3_package_preserves_events_and_has_multi_angle_uploads(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg is needed to prepare local motion guides")
    output, status = build(tmp_path / "v3", fps=3)
    assert status["ready_for_sequence_01_test"], status["issues"]
    assert status["canonical_event_sha256"] == EVENT_SHA
    assert status["sequence_count"] == 9
    assert status["total_target_duration_seconds"] == 60
    assert status["shared_reference_count"] == 10
    assert status["dreamina_motion_refs_compliant"]
    assert status["provider_calls"] == 0
    assert not status["final_production_approved"]
    report = json.loads((output / "review/motion_resolution_compliance.json").read_text())
    assert report["all_compliant"]
    assert report["originals_removed"]
    assert report["sequence_files_hardlinked_to_masters"]
    assert not (output / "motion_refs").exists()
    for index in range(1, 10):
        folder = output / "sequences" / f"sequence_{index:02d}"
        manifest = json.loads((folder / "reference_manifest.json").read_text())
        assert len(manifest["camera_cues"]) >= 3
        assert (folder / "motion_reference.mp4").stat().st_size > 0
        assert manifest["motion_reference_resolution"]["pixel_count"] == 921_600
        master = output / "motion_refs_seedance" / manifest["motion_reference_master"]
        assert master.samefile(folder / "motion_reference.mp4")
        assert "Do not copy its characters or exact choreography." in (folder / "sequence_prompt.txt").read_text()
        if index > 1:
            previous = output / "sequences" / f"sequence_{index-1:02d}"
            assert (previous / "end_frame.png").read_bytes() == (folder / "start_frame.png").read_bytes()
    assert validate_v3(output)["ready_for_sequence_01_test"]
    assert upgrade_motion_references(output)["all_compliant"]
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        build(output, fps=3)
