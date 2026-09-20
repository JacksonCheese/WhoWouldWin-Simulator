"""Golden workflow reuses episode files, provenance, storyboard and FFmpeg boundaries."""

import json
import math
from pathlib import Path
import shutil
from whowouldwin.simulation.replay import digest
from whowouldwin.cinematic.episodes.project import (
    load_episode,
    write_json,
    record_asset,
    file_hash,
    cached,
    save_manifest,
    now,
    storyboard_episode,
    set_shot_status,
)
from whowouldwin.cinematic.episodes.schemas import (
    EpisodeManifest,
    EventLog,
    CinematicMoment,
    GoldenDirectorSettings,
    ShotStatus,
    VisualProfile,
    ProviderSettings,
)
from whowouldwin.cinematic.episodes.visual_bibles import (
    load_visuals,
    load_arena,
    data_directory,
)
from whowouldwin.cinematic.episodes.providers import (
    MockImageProvider,
    MockVideoProvider,
    ImageRequest,
    VideoOptions,
    run_ffmpeg,
)
from whowouldwin.cinematic.episodes.storyboard import StoryboardFrame, contact_sheet
from whowouldwin.cinematic.episodes.editor import assemble_video, inspect_video
from .schemas import GoldenState, EpisodeStyleProfile, AbilityVisualProfile
from .director import load_abilities, select_window, GoldenDirector
from .prompts import PromptCompiler
from .runway import (
    RunwaySession,
    RunwayImageProvider,
    RunwayVideoProvider,
    project_lock,
    save_state,
    totals,
    generation_cost,
)
from .references import import_pack, for_shot


def load(project):
    manifest, shots = load_episode(project)
    if manifest.golden is None:
        raise ValueError(
            "This is not a golden sequence; first run golden-sequence on an existing episode"
        )
    state = GoldenState.model_validate(manifest.golden)
    for key in ["ability_visuals", "style", "prompt_debug"]:
        record = manifest.assets.get(key)
        if not record or file_hash(project / record.path) != record.sha256:
            raise ValueError(f"Golden {key} changed outside the revision workflow")
    return manifest, shots, state


def commit_shots(project, manifest, shots):
    write_json(project / "shot_list.json", shots)
    record_asset(project, manifest, "shot_list", project / "shot_list.json")
    manifest.shot_versions = {s.shot_id: s.version for s in shots.shots}
    manifest.approval_status = {s.shot_id: s.status for s in shots.shots}


def create_sequence(
    parent,
    output,
    *,
    duration=10,
    shots=7,
    width=720,
    fps=30,
    start_time=None,
    end_time=None,
    start_moment=None,
    end_moment=None,
):
    parent = Path(parent).resolve()
    output = Path(output).resolve()
    original, oldshots = load_episode(parent)
    log = EventLog.model_validate_json((parent / "events.json").read_text())
    moments = [
        CinematicMoment.model_validate(x)
        for x in json.loads((parent / "moments.json").read_text())
    ]
    start, end, selected, reason = select_window(
        log,
        moments,
        start_time=start_time,
        end_time=end_time,
        start_moment=start_moment,
        end_moment=end_moment,
    )
    settings = GoldenDirectorSettings(
        duration_seconds=duration,
        shot_count=shots,
        width=width,
        height=round(width * 16 / 9 / 2) * 2,
        fps=fps,
    )
    if output.exists() and (output / "manifest.json").exists():
        existing, plan, state = load(output)
        if (
            existing.source_checksum != log.source_checksum
            or plan.settings != settings
            or (start, end) != (state.selection_start, state.selection_end)
        ):
            raise ValueError(
                "Existing golden sequence has different settings or source; choose a fresh output"
            )
        return output
    if output.exists() and any(output.iterdir()):
        raise ValueError("Golden output directory must be empty")
    visuals = load_visuals(
        log.fighter_profile_ids, data_directory() / "golden_visual_bibles"
    )
    arena = load_arena(parent / "arena_visual.json")
    abilities = load_abilities(log)
    style = EpisodeStyleProfile()
    plan = GoldenDirector().direct(log, selected, visuals, arena, abilities, settings)
    by_id = {v.ability_visual_id: v for v in abilities.values()}
    debug = {}
    for shot in plan.shots:
        (
            shot.keyframe_prompt,
            shot.motion_prompt,
            debug[shot.shot_id],
        ) = PromptCompiler().compile(
            shot, visuals, by_id[shot.ability_visual_id], arena, style
        )
    state = GoldenState(
        parent_episode=str(parent),
        parent_manifest_sha256=file_hash(parent / "manifest.json"),
        selection_start=start,
        selection_end=end,
        selection_moment_ids=[m.moment_id for m in selected],
        selection_reason=reason,
        style=style,
    )
    for folder in ["references", "storyboard", "keyframes", "clips", "audio", "final"]:
        (output / folder).mkdir(parents=True, exist_ok=True)
    for name in ["simulation.json", "events.json", "arena_visual.json"]:
        shutil.copyfile(parent / name, output / name)
    write_json(output / "moments.json", [m.model_dump(mode="json") for m in selected])
    write_json(output / "shot_list.json", plan)
    write_json(
        output / "continuity.json",
        {s.shot_id: s.continuity_state.model_dump(mode="json") for s in plan.shots},
    )
    write_json(
        output / "visual_profiles.json",
        {k: v.model_dump(mode="json") for k, v in visuals.items()},
    )
    write_json(
        output / "ability_visuals.json",
        {key: v.model_dump(mode="json") for key, v in by_id.items()},
    )
    write_json(output / "style.json", style)
    write_json(output / "prompt_debug.json", debug)
    manifest = EpisodeManifest(
        episode_id="golden_" + original.episode_id,
        created_at=now(),
        updated_at=now(),
        simulation_seed=log.simulation_seed,
        source_checksum=log.source_checksum,
        outcome_digest=digest(log.outcome),
        fighter_versions=log.fighter_versions,
        visual_versions={k: v.version_id for k, v in visuals.items()},
        representative_battle="Contiguous golden sequence from " + original.episode_id,
        director_settings=settings,
        selector_settings=original.selector_settings,
        shot_versions={s.shot_id: s.version for s in plan.shots},
        approval_status={s.shot_id: s.status for s in plan.shots},
        golden=state.model_dump(mode="json"),
    )
    for name in [
        "simulation",
        "events",
        "moments",
        "shot_list",
        "continuity",
        "visual_profiles",
        "arena_visual",
        "ability_visuals",
        "style",
        "prompt_debug",
    ]:
        record_asset(output, manifest, name, output / f"{name}.json")
    save_manifest(
        output, manifest, "Golden coverage plan created; no media provider called"
    )
    storyboard_episode(output)
    quality_report(output)
    return output


def references(project, directory=None, *, approve=False):
    project = Path(project).resolve()
    with project_lock(project):
        m, shots, state = load(project)
        chars = list(
            EventLog.model_validate_json(
                (project / "events.json").read_text()
            ).fighter_profile_ids.values()
        )
        import_pack(
            project,
            m,
            state,
            directory or project / "references",
            chars,
            approve=approve,
        )
        save_state(
            project,
            m,
            state,
            "Local reference pack imported"
            + (
                " and explicitly approved"
                if approve
                else "; awaiting reference approval"
            ),
        )
        quality_report(project)


def estimate(
    project, image_model="gen4_image_turbo", video_model="gen4_turbo", seconds=5
):
    m, shots, state = load(Path(project).resolve())
    count = len(shots.shots)
    images = count * generation_cost("image", image_model)
    videos = count * generation_cost("video", video_model, seconds)
    return {
        "shots": count,
        "image_model": image_model,
        "video_model": video_model,
        "full_generation_seconds_per_shot": seconds,
        "image_cost_usd": round(images, 6),
        "video_cost_usd": round(videos, 6),
        "one_pass_usd": round(images + videos, 6),
        "committed_usd": totals(state)[1],
        "confirmed_usd": totals(state)[0],
        "basis": "Runway API price snapshot 2026-09-06; excludes tax; actual provider task costs recorded when returned.",
    }


def selected_shots(shots, shot_id):
    selected = [s for s in shots.shots if not shot_id or s.shot_id == shot_id]
    if not selected:
        raise ValueError(f"Unknown shot: {shot_id}")
    return selected


def opt_in(provider, real, max_cost):
    if provider not in {"mock", "runway"}:
        raise ValueError("Choose mock or runway")
    if (provider == "runway") != real:
        raise ValueError("Real generation requires both --provider runway and --real")
    if real and (max_cost is None or not math.isfinite(max_cost) or max_cost < 0):
        raise ValueError("Real generation requires --max-cost")


def budget_preflight(state, selected, manifest, kind, provider, cost, max_cost):
    if provider == "mock":
        return
    needed = 0
    for shot in selected:
        record = manifest.assets.get(
            ("keyframe:" if kind == "image" else "full_clip:") + shot.shot_id
        )
        if (
            record
            and record.shot_version == shot.version
            and record.provider == provider
        ):
            continue
        # Existing nonterminal reservations already occupy budget; resumption is free.
        if any(
            j.kind == kind
            and j.shot_id == shot.shot_id
            and j.shot_version == shot.version
            and j.state not in {"FAILED", "CANCELLED"}
            for j in state.jobs
        ):
            continue
        needed += cost
    if totals(state)[1] + needed > max_cost + 1e-9:
        raise ValueError(
            f"Budget rejected before submission: ${totals(state)[1]:.2f} committed + ${needed:.2f} planned exceeds ${max_cost:.2f}"
        )


def regenerate(project, shot_id):
    if not shot_id:
        raise ValueError(
            "Regeneration requires --shot to avoid replacing the entire paid sequence"
        )
    set_shot_status(project, shot_id, ShotStatus.NEEDS_REGENERATION)
    m, shots, state = load(project)
    state.keyframe_approvals.pop(shot_id, None)
    for key in ["keyframe:", "full_clip:", "clip:"]:
        m.assets.pop(key + shot_id, None)
    shot = next(s for s in shots.shots if s.shot_id == shot_id)
    shot.status = ShotStatus.DRAFT
    commit_shots(project, m, shots)
    save_state(project, m, state, "Explicit single-keyframe regeneration requested")
    storyboard_episode(project)


def keyframes(
    project,
    *,
    provider="mock",
    real=False,
    max_cost=None,
    model="gen4_image_turbo",
    shot_id=None,
    regenerate_one=False,
    retry_failed=False,
    session_factory=RunwaySession,
):
    project = Path(project).resolve()
    opt_in(provider, real, max_cost)
    with project_lock(project):
        if regenerate_one:
            regenerate(project, shot_id)
        manifest, shots, state = load(project)
        selected = selected_shots(shots, shot_id)
        cost = generation_cost("image", model) if real else 0
        references_by_shot = (
            {s.shot_id: for_shot(project, state, s) for s in selected} if real else {}
        )
        budget_preflight(state, selected, manifest, "image", provider, cost, max_cost)
        try:
            for shot in selected:
                existing = cached(
                    project, manifest, "keyframe:" + shot.shot_id, shot.version
                )
                if (
                    existing
                    and manifest.assets["keyframe:" + shot.shot_id].provider == provider
                ):
                    continue
                board = cached(
                    project, manifest, "storyboard:" + shot.shot_id, shot.version
                )
                if not board:
                    raise ValueError("Generate current storyboards before keyframes")
                output = (
                    project
                    / "keyframes"
                    / f"{shot.shot_id}-v{shot.version}-{provider}.png"
                )
                adapter = (
                    RunwayImageProvider(
                        session_factory(
                            project,
                            real=True,
                            max_cost=max_cost,
                            retry_failed=retry_failed,
                        ),
                        shot,
                        model,
                    )
                    if real
                    else MockImageProvider()
                )
                asset = adapter.generate_keyframe(
                    ImageRequest(
                        shot.keyframe_prompt,
                        tuple(shot.negative_constraints),
                        "9:16",
                        references_by_shot.get(shot.shot_id, ()),
                        shots.settings.width,
                        shots.settings.height,
                        output,
                        board,
                    )
                )
                manifest, _, state = load(
                    project
                )  # Provider durably updated tasks/cost; never overwrite that ledger.
                record_asset(
                    project,
                    manifest,
                    "keyframe:" + shot.shot_id,
                    asset.path,
                    shot.version,
                    provider,
                )
                state.keyframe_approvals.pop(shot.shot_id, None)
                for key in ["full_clip:", "clip:"]:
                    manifest.assets.pop(key + shot.shot_id, None)
                manifest.assets.pop("final_video", None)
                manifest.render_approvals.pop(shot.shot_id, None)
                shot.status = ShotStatus.DRAFT
                commit_shots(project, manifest, shots)
                if real:
                    manifest.provider_settings = ProviderSettings(
                        image_provider="runway",
                        network_enabled=True,
                        credentials_required=True,
                    )
                manifest.stage = "KEYFRAMES_AWAITING_APPROVAL"
                save_state(
                    project,
                    manifest,
                    state,
                    f"{shot.shot_id}: keyframe ready; animation NOT started",
                )
                print(
                    f"Keyframe: {shot.shot_id} ({provider}); awaiting review",
                    flush=True,
                )
        finally:
            keyframe_contact_sheet(project)
            quality_report(project)


def keyframe_contact_sheet(project):
    m, shots, state = load(project)
    frames = []
    for shot in shots.shots:
        path = cached(project, m, "keyframe:" + shot.shot_id, shot.version) or cached(
            project, m, "storyboard:" + shot.shot_id, shot.version
        )
        if path:
            frames.append(
                StoryboardFrame(
                    shot.shot_id,
                    path,
                    shots.settings.width,
                    shots.settings.height,
                    file_hash(path),
                )
            )
    if frames:
        path = contact_sheet(frames, project / "contact-sheet.png")
        record_asset(project, m, "keyframe_contact_sheet", path)
        save_state(
            project,
            m,
            state,
            "Keyframe contact sheet updated; ungenerated frames use labelled mock storyboard",
        )


def approve_keyframes(project, shot_id=None, *, reject=False):
    project = Path(project).resolve()
    with project_lock(project):
        m, shots, state = load(project)
        for shot in selected_shots(shots, shot_id):
            path = cached(project, m, "keyframe:" + shot.shot_id, shot.version)
            if not path:
                raise ValueError(f"{shot.shot_id}: no current keyframe to review")
            if reject:
                state.keyframe_approvals.pop(shot.shot_id, None)
                shot.status = ShotStatus.REJECTED
                m.assets.pop("clip:" + shot.shot_id, None)
                m.assets.pop("full_clip:" + shot.shot_id, None)
            else:
                state.keyframe_approvals[shot.shot_id] = file_hash(path)
                shot.status = ShotStatus.APPROVED
        m.assets.pop("final_video", None)
        commit_shots(project, m, shots)
        save_state(
            project,
            m,
            state,
            "Keyframes explicitly "
            + ("rejected" if reject else "approved")
            + " by user command",
        )
        quality_report(project)


def animate(
    project,
    *,
    provider="mock",
    real=False,
    max_cost=None,
    model="gen4_turbo",
    seconds=5,
    shot_id=None,
    allow_draft=False,
    retry_failed=False,
    session_factory=RunwaySession,
):
    project = Path(project).resolve()
    opt_in(provider, real, max_cost)
    if real and allow_draft:
        raise ValueError("Real video never bypasses keyframe approval")
    with project_lock(project):
        manifest, shots, state = load(project)
        selected = selected_shots(shots, shot_id)
        cost = generation_cost("video", model, seconds) if real else 0
        for shot in selected:
            frame = cached(project, manifest, "keyframe:" + shot.shot_id, shot.version)
            if not frame:
                raise ValueError(f"{shot.shot_id}: generate keyframe first")
            if shot.status in {ShotStatus.REJECTED, ShotStatus.NEEDS_REGENERATION}:
                raise ValueError(f"{shot.shot_id}: keyframe is rejected or outdated")
            if (
                state.keyframe_approvals.get(shot.shot_id) != file_hash(frame)
                and not allow_draft
            ):
                raise ValueError(
                    f"{shot.shot_id}: approve this exact keyframe before animation"
                )
            if (
                real
                and manifest.assets["keyframe:" + shot.shot_id].provider != "runway"
            ):
                raise ValueError(
                    "Real animation requires an approved real keyframe; generate Runway keyframes first"
                )
            if seconds < shot.duration_seconds + shot.edit_in_seconds:
                raise ValueError("Generation must cover the requested edit interval")
        budget_preflight(state, selected, manifest, "video", provider, cost, max_cost)
        try:
            for shot in selected:
                existing = cached(
                    project, manifest, "full_clip:" + shot.shot_id, shot.version
                )
                if (
                    existing
                    and manifest.assets["full_clip:" + shot.shot_id].provider
                    == provider
                ):
                    continue
                frame = cached(
                    project, manifest, "keyframe:" + shot.shot_id, shot.version
                )
                options = VideoOptions(
                    shots.settings.width,
                    shots.settings.height,
                    shots.settings.fps,
                    round(seconds * shots.settings.fps),
                    shot.camera_motion,
                    shot.editorial,
                )
                output = (
                    project
                    / "clips"
                    / f"{shot.shot_id}-v{shot.version}-{provider}-full.mp4"
                )
                adapter = (
                    RunwayVideoProvider(
                        session_factory(
                            project,
                            real=True,
                            max_cost=max_cost,
                            retry_failed=retry_failed,
                        ),
                        shot,
                        model,
                    )
                    if real
                    else MockVideoProvider()
                )
                asset = adapter.generate_video(
                    frame, shot.motion_prompt, seconds, "9:16", (), options, output
                )
                metadata = inspect_video(asset.path)
                if (
                    metadata["duration"] + 1 / metadata["fps"]
                    < shot.duration_seconds + shot.edit_in_seconds
                ):
                    raise ValueError(
                        "Generated clip is shorter than the selected edit; full output retained for review"
                    )
                manifest, _, state = load(project)
                record_asset(
                    project,
                    manifest,
                    "full_clip:" + shot.shot_id,
                    asset.path,
                    shot.version,
                    provider,
                )
                manifest.render_approvals[shot.shot_id] = (
                    "approved keyframe " + file_hash(frame)
                    if state.keyframe_approvals.get(shot.shot_id) == file_hash(frame)
                    else "explicit mock draft override"
                )
                shot.status = ShotStatus.RENDERED
                commit_shots(project, manifest, shots)
                if real:
                    manifest.provider_settings = ProviderSettings(
                        image_provider="runway",
                        video_provider="runway",
                        network_enabled=True,
                        credentials_required=True,
                    )
                manifest.stage = "GOLDEN_CLIPS_READY"
                save_state(
                    project,
                    manifest,
                    state,
                    f'{shot.shot_id}: full clip retained ({metadata["duration"]}s)',
                )
        finally:
            quality_report(project)


def trim(project, shot_id, seconds):
    project = Path(project).resolve()
    with project_lock(project):
        m, shots, state = load(project)
        shot = selected_shots(shots, shot_id)[0]
        if seconds < 0:
            raise ValueError("Edit start must be nonnegative")
        full = cached(project, m, "full_clip:" + shot_id, shot.version)
        if not full:
            raise ValueError(
                "Generate the full clip before selecting its best interval"
            )
        if seconds + shot.duration_seconds > inspect_video(full)["duration"] + 1e-6:
            raise ValueError("Edit exceeds the full clip duration")
        shot.edit_in_seconds = seconds
        m.assets.pop("clip:" + shot_id, None)
        m.assets.pop("final_video", None)
        commit_shots(project, m, shots)
        save_state(
            project,
            m,
            state,
            f"{shot_id}: local trim starts {seconds}s; no regeneration or approval reset",
        )


def assemble(project):
    project = Path(project).resolve()
    with project_lock(project):
        m, shots, state = load(project)
        clips = []
        providers = set()
        for shot in shots.shots:
            full = cached(project, m, "full_clip:" + shot.shot_id, shot.version)
            if not full or shot.status != ShotStatus.RENDERED:
                raise ValueError(f"{shot.shot_id}: missing current full clip")
            provider = m.assets["full_clip:" + shot.shot_id].provider
            providers.add(provider)
            if provider == "runway":
                frame = cached(project, m, "keyframe:" + shot.shot_id, shot.version)
                if not frame or state.keyframe_approvals.get(shot.shot_id) != file_hash(
                    frame
                ):
                    raise ValueError(
                        "Real assembly requires current approved keyframe provenance"
                    )
            target = project / "clips" / f"{shot.shot_id}-v{shot.version}-edit.mp4"
            settings = shots.settings
            filters = f"trim=start={shot.edit_in_seconds},setpts=PTS-STARTPTS,scale={settings.width}:{settings.height}:force_original_aspect_ratio=decrease,pad={settings.width}:{settings.height}:(ow-iw)/2:(oh-ih)/2,fps={settings.fps}:eof_action=pass,trim=end_frame={shot.frame_count}"
            run_ffmpeg(
                [
                    "-i",
                    str(full),
                    "-vf",
                    filters,
                    "-frames:v",
                    str(shot.frame_count),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    "-threads",
                    "2",
                    str(target),
                ]
            )
            if inspect_video(target)["frames"] != shot.frame_count:
                raise ValueError("Edited shot does not meet its frame budget")
            clips.append(target)
            record_asset(
                project, m, "clip:" + shot.shot_id, target, shot.version, provider
            )
        if len(providers) > 1:
            raise ValueError(
                "Finish all shots with the same provider before assembling; mixed mock/real output is not a golden quality test"
            )
        provider = next(iter(providers))
        video = assemble_video(
            project,
            shots,
            clips,
            comment=f"{provider.upper()} golden sequence; cinematic interpretation of an unchanged simulated outcome",
        )
        final = project / "final/golden_sequence.mp4"
        video.replace(final)
        metadata = inspect_video(final)
        if metadata["frames"] != round(
            shots.settings.duration_seconds * shots.settings.fps
        ):
            raise ValueError("Golden export frame budget differs")
        write_json(
            project / "final/validation.json",
            dict(
                metadata,
                provider=provider,
                source_checksum=m.source_checksum,
                outcome_digest=m.outcome_digest,
                conservative_cost_usd=totals(state)[1],
                actual_cost_usd=totals(state)[0],
            ),
        )
        record_asset(project, m, "final_video", final)
        record_asset(project, m, "video_validation", project / "final/validation.json")
        m.stage = "GOLDEN_ASSEMBLED"
        save_state(
            project,
            m,
            state,
            f"Assembled {provider} golden clip; full source generations preserved",
        )
        quality_report(project)
        return final


def link_task(project, job_key, task_id):
    project = Path(project).resolve()
    with project_lock(project):
        m, _, state = load(project)
        job = next((j for j in state.jobs if j.job_key == job_key), None)
        if (
            not job
            or job.task_id
            or job.state not in {"SUBMITTING", "UNKNOWN", "RESERVED"}
        ):
            raise ValueError(
                "Only an unresolved submission without a task ID can be linked"
            )
        if not task_id or len(task_id) > 100:
            raise ValueError("Supply the exact task ID from your Runway dashboard")
        job.task_id = task_id
        job.state = "PENDING"
        save_state(
            project,
            m,
            state,
            f"User linked unresolved submission to task {task_id}; no API submission",
        )


def quality_report(project):
    m, shots, state = load(project)
    actual, conservative = totals(state)
    real = bool(state.jobs)
    rows = [
        "# Golden sequence quality review",
        "",
        f"Source: seed {m.simulation_seed}; {state.selection_start:.2f}–{state.selection_end:.2f} simulation seconds.",
        state.selection_reason,
        "",
        f"Edit: {len(shots.shots)} shots, {shots.settings.duration_seconds}s, 9:16. Stage: {m.stage}.",
        f"Confirmed API cost: ${actual:.2f}. Conservative committed cost including unresolved tasks: ${conservative:.2f}.",
        "Task costs are recorded when returned by Runway; pending/unknown costs remain reserved. No billing inference is presented as a confirmed charge.",
        "",
        (
            "Real-provider tasks have been attempted; review their status below. Visual quality requires human review of successful outputs."
            if real
            else "No real generations have been run. Current visuals are mocks; visual quality claims cannot yet be assessed."
        ),
        "",
        "| Check | Evidence / review status |",
        "| --- | --- |",
        "| Character consistency | Shared tagged reference boards; actual generated identity consistency not yet assessed. |",
        "| Costume consistency | Reference-bound costumes and exact form metadata; inspect every keyframe before approval. |",
        "| Arena consistency | Shared style/arena board, lighting and intact rooftop constraint; human review pending. |",
        "| Action readability | Specific ability semantics and one-contact coverage; real motion readability pending. |",
        f"| Camera variety | {len({s.camera_angle for s in shots.shots})} angles; {len({s.camera_motion for s in shots.shots})} directed moves. |",
        "| Continuity | Source event IDs reused across coverage; no new damage; current forms/wear attached. |",
        "| Best prompts | No automatic winner claimed; compare keyframes with prompt_debug.json after real generation. |",
        "",
        "| Shot | Role | Edit seconds | Render state / keyframe approval | Tasks / retries | Confirmed / reserved USD |",
        "| --- | --- | ---: | --- | --- | ---: |",
    ]
    for shot in shots.shots:
        jobs = [j for j in state.jobs if j.shot_id == shot.shot_id]
        cost = sum(j.actual_usd or 0 for j in jobs)
        reserved = sum(
            j.reserved_usd if j.actual_usd is None else j.actual_usd for j in jobs
        )
        frame = cached(project, m, "keyframe:" + shot.shot_id, shot.version)
        approval = (
            "approved exact frame"
            if frame and state.keyframe_approvals.get(shot.shot_id) == file_hash(frame)
            else "NOT APPROVED"
        )
        rows.append(
            f"| {shot.shot_id} | {shot.coverage_role} | {shot.duration_seconds:.2f} | {shot.status.value} / {approval} | {len(jobs)} tasks; {sum(j.poll_retries for j in jobs)} polling retries | ${cost:.2f} / ${reserved:.2f} |"
        )
    rows += [
        "",
        "## Failed generations and retries",
        "",
        *(["- " + s for s in state.failures] or ["None recorded."]),
        "",
        "## Before attempting 30–60 seconds",
        "",
        "Review identity, costume, handedness, single-contact action and contact timing for every real shot. Select the best edit-in point with golden-trim. Record your observations in quality_notes.md (retained when this report refreshes). Regenerate only rejected shots. Validate the 10-second assembled clip before scaling up.",
        "",
        "No TTS is integrated. The existing editor supplies local placeholder audio only.",
    ]
    (project / "quality_report.md").write_text("\n".join(rows) + "\n")
