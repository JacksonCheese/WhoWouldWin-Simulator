"""The Seedance 2.5 upload units remain small and canonical-event safe."""

import json
import shutil

import pytest

from whowouldwin.cinematic.seedance.seedance25 import (
    EVENT_SHA,
    SEQUENCES,
    SHARED_NAMES,
    build,
    validate,
)


def test_sequence_package_and_continuity(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg is required for local motion references")
    output, status = build(tmp_path / "seedance25", fps=5)
    assert status["ready_for_sequence_01_test"]
    assert status["final_production_approved"] is False
    assert status["canonical_event_sha256"] == EVENT_SHA
    assert sum(sequence.duration for sequence in SEQUENCES) == 62
    assert len(list((output / "shared_references").glob("*.png"))) == len(SHARED_NAMES) == 12
    for index in range(1, 6):
        folder = output / "sequences" / f"sequence_{index:02d}"
        manifest = json.loads((folder / "reference_manifest.json").read_text())
        assert manifest["upload_image_count"] <= 9
        assert manifest["upload_video_count"] == 1
        assert len(manifest["identity_references"]) == 4
        assert (folder / "motion_reference.mp4").stat().st_size > 0
        if index > 1:
            previous = output / "sequences" / f"sequence_{index-1:02d}"
            assert (previous / "end_frame.png").read_bytes() == (folder / "start_frame.png").read_bytes()
    prompt = (output / "sequences/sequence_04/sequence_prompt.txt").read_text()
    assert "hand-held melee strike" in prompt
    assert "non-damaging" in prompt
    final_prompt = (output / "sequences/sequence_05/sequence_prompt.txt").read_text()
    assert "decisive recorded KO" in final_prompt
    assert validate(output)["ready_for_sequence_01_test"]
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        build(output, fps=5)

    # A missing upload asset must block readiness rather than silently pass.
    (output / "sequences/sequence_01/start_frame.png").unlink()
    failed = validate(output)
    assert failed["ready_for_sequence_01_test"] is False
    assert any("start_frame.png" in issue for issue in failed["issues"])
