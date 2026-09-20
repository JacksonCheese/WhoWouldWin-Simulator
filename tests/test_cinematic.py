import copy
import json
from pathlib import Path
import pytest
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.replay import save_replay, load_replay, digest
from whowouldwin.cinematic.director import compile_cinematic
from whowouldwin.cinematic.exporter import export_unity
from whowouldwin.cinematic.profiles import load_visual_profile, validate_visual_profile, STATES


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    engine=Engine(seed=69,record=True)
    engine.run()
    path=save_replay(engine,tmp_path_factory.mktemp("cinematic")/"fight.json")
    return path,load_replay(path)


def test_unity_export_deterministic_and_leaves_source_untouched(source,tmp_path):
    path,raw=source
    before=digest(raw)
    first=export_unity(path,tmp_path/"first.json")
    second=export_unity(path,tmp_path/"second.json")
    assert first==second
    assert (tmp_path/"first.json").read_bytes()==(tmp_path/"second.json").read_bytes()
    assert digest(raw)==before
    assert first["metadata"]["sourceChecksum"]==raw["checksum"]


def test_damage_and_health_timeline_exact(source):
    _,raw=source
    film=compile_cinematic(raw)
    original=[e for frame in raw["frames"] for e in frame["events"] if e["type"]=="DamageApplied"]
    assert len(original)==len(film["damageTimeline"])
    for a,b in zip(original,film["damageTimeline"]):
        assert (a["timestamp"],a["fighter"],a["target"],a["action"],a["values"]["damage"],a["values"]["health"]) == (b["simulationTime"],b["actor"],b["target"],b["ability"],b["damage"],b["healthAfter"])
    for slot in range(2):
        assert [k["health"] for k in film["fighters"][slot]["health"]]==[f["state"]["fighters"][slot]["health"] for f in raw["frames"]]
        assert [k["energy"] for k in film["fighters"][slot]["health"]]==[f["state"]["fighters"][slot]["energy"] for f in raw["frames"]]


def test_final_outcome_and_duration_preserved(source):
    _,raw=source
    film=compile_cinematic(raw)
    assert film["finalOutcome"]["winner"]==raw["result"]["winner"]
    assert film["finalOutcome"]["condition"]==raw["result"]["condition"]
    assert film["finalOutcome"]["simulationDuration"]==raw["result"]["duration"]
    assert film["finalOutcome"]["health"]==[f["health"] for f in raw["result"]["fighters"]]
    assert film["metadata"]["outcomeDigest"]==digest(raw["result"])
    assert film["metadata"]["presentationDuration"]>raw["result"]["duration"]


def test_cinematic_clock_is_continuous_ordered_and_has_hitstop(source):
    film=compile_cinematic(source[1])
    segments=film["timeMap"]
    assert segments[0]["start"]==0
    for a,b in zip(segments,segments[1:]):
        assert a["end"]==pytest.approx(b["start"])
        assert a["simulationEnd"]==pytest.approx(b["simulationStart"])
        assert a["end"]>a["start"]
        assert a["simulationEnd"]>=a["simulationStart"]
    assert segments[-1]["end"]==film["metadata"]["presentationDuration"]
    assert any(s["kind"]=="hitstop" and s["simulationEnd"]==s["simulationStart"] for s in segments)


def test_source_event_order_and_choreography_order(source):
    film=compile_cinematic(source[1])
    authority=film["authoritativeTimeline"]
    assert [e["sourceIndex"] for e in authority]==sorted(e["sourceIndex"] for e in authority)
    assert [e["presentationTime"] for e in authority]==sorted(e["presentationTime"] for e in authority)
    assert [c["start"] for c in film["cues"]]==sorted(c["start"] for c in film["cues"])
    assert all(c["presentationalOnly"] for c in film["cues"])
    assert all(c["end"]>c["start"] for c in film["cues"])


def test_all_starter_abilities_have_valid_mappings(profiles):
    for p in profiles:
        visual=load_visual_profile(p.model_dump(mode="json"))
        assert {m["abilityId"] for m in visual["abilities"]}=={a.id for a in p.abilities}
        assert set(visual["requiredStates"])==set(STATES)


def test_missing_presentation_mapping_fails(profiles):
    character=profiles[0].model_dump(mode="json")
    profile=load_visual_profile(character)
    profile["abilities"].pop()
    with pytest.raises(ValueError,match="mapping"):
        validate_visual_profile(profile,character)


def test_projectiles_have_visible_travel_and_preserved_endpoints(source):
    film=compile_cinematic(source[1])
    assert film["projectiles"]
    for p in film["projectiles"]:
        assert p["end"]-p["start"]>=.139999
        assert p["outcome"] in {"hit","miss","block","dodge","inFlight"}
        assert p["points"][0]["time"]==p["simulationStart"]
        assert p["points"][-1]["time"]<=p["simulationEnd"]


def test_director_generates_required_visual_mechanics(source):
    film=compile_cinematic(source[1])
    kinds={c["kind"] for c in film["cues"]}
    assert {"AnticipateAttack","Lunge","ProjectileCast","SuccessfulDodge","BlockImpact","Launcher","Transformation","Finisher","Flight"}<=kinds
    assert any(c["variant"]>0 for c in film["cues"] if c["kind"]=="Lunge")
