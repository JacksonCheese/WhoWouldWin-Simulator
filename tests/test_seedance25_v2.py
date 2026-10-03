"""The faster edit shortens upload units without inventing source combat."""

import json
import shutil

import pytest

from whowouldwin.cinematic.seedance.seedance25 import EVENT_SHA
from whowouldwin.cinematic.seedance.seedance25_v2 import SEQUENCES, build, validate_v2


def test_faster_edit_preserves_source_and_has_short_connected_clips(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg is needed for the locally authored motion guides")
    assert len(SEQUENCES) == 9
    assert sum(sequence.duration for sequence in SEQUENCES) == 60
    assert max(sequence.duration for sequence in SEQUENCES) == 7
    assert [index for sequence in SEQUENCES for index in range(sequence.shot_first, sequence.shot_last + 1)] == list(range(1, 29))

    output, status = build(tmp_path / "fast", fps=3)
    assert status["ready_for_sequence_01_test"]
    assert status["canonical_event_sha256"] == EVENT_SHA
    assert status["final_production_approved"] is False
    assert status["provider_calls"] == 0
    assert status["sequence_count"] == 9
    assert status["motion_reference_count"] == 9
    assert len(list((output / "shared_references").glob("*.png"))) == 12
    assert (output / "review/episode_motion_animatic.mp4").stat().st_size > 0
    for index in range(1, 10):
        folder = output / "sequences" / f"sequence_{index:02d}"
        manifest = json.loads((folder / "reference_manifest.json").read_text())
        assert manifest["target_duration_seconds"] <= 7
        assert manifest["upload_image_count"] <= 9
        assert (folder / "motion_reference.mp4").stat().st_size > 0
        if index > 1:
            previous = output / "sequences" / f"sequence_{index-1:02d}"
            assert (previous / "end_frame.png").read_bytes() == (folder / "start_frame.png").read_bytes()
    assert "never becomes a beam" in (output / "sequences/sequence_08/sequence_prompt.txt").read_text()
    assert "recorded heavy strike alone" in (output / "sequences/sequence_09/sequence_prompt.txt").read_text()
    assert validate_v2(output)["ready_for_sequence_01_test"]

    with pytest.raises(ValueError, match="Refusing to overwrite"):
        build(output, fps=3)
