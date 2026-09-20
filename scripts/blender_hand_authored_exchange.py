"""Build an isolated, hand-authored WWS paired hero exchange.

The two performers are keyed together on one 108-frame timeline.  Existing
rigs, adapters, debug bodies, event provenance, and collision math are reused;
no Mixamo clip or procedural pose generator supplies body motion.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/combat_motion_lab_hero_exchange"
OUTPUT = ROOT / "outputs/combat_motion_lab_hand_authored_hero_exchange"
FPS = 30
END = 108
CONTACT_FRAME = 82
HOLD_FRAMES = (82, 84)

sys.path.insert(0, str(ROOT / "scripts"))
import blender_combat_motion_lab as motion_lab


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_collision_module():
    path = ROOT / "scripts/blender_first_production_fight_v2.py"
    spec = importlib.util.spec_from_file_location("ha_collision_math", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reset_derived_state() -> None:
    """Remove old hero-exchange adaptation constraints, never source assets."""
    for rig_name in ("fighter_a_Rig", "fighter_b_Rig"):
        rig = bpy.data.objects[rig_name]
        if not rig.animation_data:
            rig.animation_data_create()
        rig.animation_data.action = None
        for track in list(rig.animation_data.nla_tracks):
            rig.animation_data.nla_tracks.remove(track)
        for bone in rig.pose.bones:
            for constraint in list(bone.constraints):
                if constraint.name.startswith(("HERO ", "HA ", "Procedural contact")):
                    bone.constraints.remove(constraint)
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = (0.0, 0.0, 0.0)
    for rig_name in ("fighter_a_ProductionRig", "fighter_b_ProductionRig"):
        rig = bpy.data.objects[rig_name]
        for bone in rig.pose.bones:
            for constraint in bone.constraints:
                if constraint.name.startswith(("HERO ", "ASTRA support", "ASTRA sole")):
                    constraint.mute = True
                    constraint.influence = 0.0
    for name in ("HERO_FOOT_PINS", "HERO_CONTACT_CONTROLS", "HERO_REVIEW_CAMERAS"):
        collection = bpy.data.collections.get(name)
        if collection:
            for obj in list(collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(collection)


# Rotation channels are local Euler XYZ radians.  Every major beat keys the
# whole contract.  Values deliberately stay moderate through pelvis/spine/chest
# so the rib cage remains stacked instead of folding at three adjacent hinges.
BONES = (
    "root", "pelvis", "spine", "chest", "neck", "head",
    "clavicle.L", "upper_arm.L", "forearm.L", "hand.L",
    "clavicle.R", "upper_arm.R", "forearm.R", "hand.R",
    "thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R",
)


def pose(**values):
    result = {name: (0.0, 0.0, 0.0) for name in BONES}
    result.update(values)
    return result


OMNI_POSES = {
    1: pose(**{
        "pelvis": (0, -.08, .12), "spine": (0, -.05, .10), "chest": (0, .04, .12),
        "head": (0, -.04, -.08), "clavicle.L": (0, 0, -.10), "clavicle.R": (0, 0, .10),
        "upper_arm.L": (-.62, .02, -.48), "forearm.L": (-1.10, -.08, .06),
        "upper_arm.R": (-.70, -.03, .55), "forearm.R": (-1.16, .08, -.05),
        "thigh.L": (.20, 0, -.05), "shin.L": (-.32, 0, 0), "foot.L": (.10, 0, 0),
        "thigh.R": (-.17, 0, .04), "shin.R": (-.16, 0, 0), "foot.R": (.04, 0, 0),
    }),
    8: pose(**{
        "pelvis": (0, -.16, .30), "spine": (0, -.12, .22), "chest": (0, -.05, .34),
        "head": (0, -.05, -.20), "clavicle.R": (0, -.05, .24),
        "upper_arm.R": (-1.30, -.05, .88), "forearm.R": (-1.38, .06, -.12), "hand.R": (0, .08, -.18),
        "upper_arm.L": (-.56, .05, -.36), "forearm.L": (-1.16, -.04, .08),
        "thigh.L": (.36, 0, -.08), "shin.L": (-.52, 0, 0), "foot.L": (.14, 0, 0),
        "thigh.R": (-.32, 0, .08), "shin.R": (-.30, 0, 0), "foot.R": (.12, 0, 0),
    }),
    14: pose(**{
        "pelvis": (0, -.10, -.05), "spine": (0, .02, -.12), "chest": (0, .03, -.22),
        "head": (0, -.03, .05), "clavicle.R": (0, 0, -.12),
        "upper_arm.R": (-.62, -.06, -.38), "forearm.R": (-.70, .04, -.12), "hand.R": (0, .05, -.08),
        "upper_arm.L": (-.70, .05, -.40), "forearm.L": (-1.22, -.08, .10),
        "thigh.L": (-.18, 0, -.03), "shin.L": (-.18, 0, 0), "thigh.R": (.34, 0, .06), "shin.R": (-.48, 0, 0),
    }),
    17: pose(**{
        "pelvis": (0, .08, -.38), "spine": (0, .10, -.30), "chest": (0, .06, -.42),
        "head": (0, -.02, .14), "clavicle.R": (0, 0, -.25),
        "upper_arm.R": (.03, -.03, -1.30), "forearm.R": (-.04, .02, -.03), "hand.R": (0, .02, -.05),
        "upper_arm.L": (-.52, .05, -.34), "forearm.L": (-1.18, -.08, .10),
        "thigh.L": (-.26, 0, -.06), "shin.L": (-.14, 0, 0), "thigh.R": (.48, 0, .08), "shin.R": (-.58, 0, 0),
    }),
    22: pose(**{
        "pelvis": (0, .10, -.44), "spine": (0, .12, -.34), "chest": (0, .08, -.48),
        "head": (0, -.02, .18), "upper_arm.R": (.20, -.02, -1.18), "forearm.R": (-.10, .02, -.08),
        "upper_arm.L": (-.46, .06, -.28), "forearm.L": (-1.02, -.06, .12),
        "thigh.L": (-.12, 0, -.05), "shin.L": (-.22, 0, 0), "thigh.R": (.30, 0, .04), "shin.R": (-.42, 0, 0),
    }),
    28: pose(**{
        "pelvis": (0, -.03, -.18), "spine": (0, -.02, -.12), "chest": (0, .02, -.08),
        "head": (0, 0, .04), "upper_arm.R": (-.60, 0, .48), "forearm.R": (-1.16, .05, -.08),
        "upper_arm.L": (-.76, .02, -.34), "forearm.L": (-1.22, -.05, .04),
        "thigh.L": (.18, 0, -.04), "shin.L": (-.34, 0, 0), "thigh.R": (-.12, 0, .02), "shin.R": (-.20, 0, 0),
    }),
    33: pose(**{
        "pelvis": (0, -.05, .12), "spine": (0, -.03, .18), "chest": (0, .02, .24),
        "head": (0, -.03, -.10), "clavicle.L": (0, 0, -.14),
        "upper_arm.L": (-.34, .02, -1.02), "forearm.L": (-.78, -.04, -.20), "hand.L": (0, -.10, .16),
        "upper_arm.R": (-.70, 0, .42), "forearm.R": (-1.18, .06, -.08),
        "thigh.L": (.22, 0, -.02), "shin.L": (-.38, 0, 0), "thigh.R": (-.16, 0, .03), "shin.R": (-.20, 0, 0),
    }),
    36: pose(**{
        "pelvis": (0, -.04, .18), "spine": (0, -.02, .20), "chest": (0, .03, .28),
        "head": (0, -.02, -.12), "clavicle.L": (0, 0, -.22),
        "upper_arm.L": (-.20, .02, -1.18), "forearm.L": (-.62, -.04, -.22), "hand.L": (0, -.12, .22),
        "upper_arm.R": (-.68, 0, .38), "forearm.R": (-1.16, .05, -.08),
        "thigh.L": (.24, 0, -.02), "shin.L": (-.40, 0, 0), "thigh.R": (-.14, 0, .03), "shin.R": (-.22, 0, 0),
    }),
    43: pose(**{
        "pelvis": (0, -.04, .10), "spine": (0, -.03, .08), "chest": (0, .02, .10),
        "head": (0, -.02, -.04), "upper_arm.L": (-.52, .02, -.78), "forearm.L": (-1.00, -.04, -.12),
        "upper_arm.R": (-.72, 0, .46), "forearm.R": (-1.18, .05, -.08),
        "thigh.L": (.18, 0, -.02), "shin.L": (-.34, 0, 0), "thigh.R": (-.14, 0, .02), "shin.R": (-.20, 0, 0),
    }),
    52: pose(**{
        "pelvis": (0, -.09, -.16), "spine": (0, -.04, -.10), "chest": (0, .04, -.08),
        "head": (0, -.04, .10), "upper_arm.L": (-.70, .02, -.34), "forearm.L": (-1.18, -.05, .08),
        "upper_arm.R": (-.70, 0, .48), "forearm.R": (-1.18, .05, -.08),
        "thigh.L": (.22, 0, -.04), "shin.L": (-.38, 0, 0), "thigh.R": (-.18, 0, .03), "shin.R": (-.22, 0, 0),
    }),
    65: pose(**{
        "pelvis": (0, -.12, -.24), "spine": (0, -.08, -.16), "chest": (0, .03, -.14),
        "head": (0, -.04, .12), "upper_arm.L": (-.66, .03, -.42), "forearm.L": (-1.14, -.05, .06),
        "upper_arm.R": (-.60, 0, .60), "forearm.R": (-1.05, .06, -.10),
        "thigh.L": (.28, 0, -.05), "shin.L": (-.44, 0, 0), "thigh.R": (-.22, 0, .04), "shin.R": (-.28, 0, 0),
    }),
    76: pose(**{
        "pelvis": (0, -.06, .08), "spine": (0, -.03, .12), "chest": (0, .02, .18),
        "head": (0, -.02, -.06), "upper_arm.L": (-.56, .02, -.68), "forearm.L": (-1.02, -.05, -.04),
        "upper_arm.R": (-.40, .02, .72), "forearm.R": (-.82, .05, -.10),
        "thigh.L": (.20, 0, -.03), "shin.L": (-.34, 0, 0), "thigh.R": (-.16, 0, .02), "shin.R": (-.22, 0, 0),
    }),
    82: pose(**{
        "pelvis": (0, .02, .16), "spine": (0, -.02, .20), "chest": (0, -.12, .28),
        "head": (0, .04, -.12), "clavicle.L": (0, 0, -.12), "clavicle.R": (0, 0, .12),
        "upper_arm.L": (-.62, .04, -.55), "forearm.L": (-1.06, -.05, .02),
        "upper_arm.R": (-.54, .02, .64), "forearm.R": (-.96, .06, -.12),
        "thigh.L": (.25, 0, -.05), "shin.L": (-.42, 0, 0), "thigh.R": (-.18, 0, .03), "shin.R": (-.28, 0, 0),
    }),
    84: pose(**{
        "pelvis": (0, .02, .16), "spine": (0, -.02, .20), "chest": (0, -.12, .28),
        "head": (0, .04, -.12), "clavicle.L": (0, 0, -.12), "clavicle.R": (0, 0, .12),
        "upper_arm.L": (-.62, .04, -.55), "forearm.L": (-1.06, -.05, .02),
        "upper_arm.R": (-.54, .02, .64), "forearm.R": (-.96, .06, -.12),
        "thigh.L": (.25, 0, -.05), "shin.L": (-.42, 0, 0), "thigh.R": (-.18, 0, .03), "shin.R": (-.28, 0, 0),
    }),
    90: pose(**{
        "pelvis": (0, -.10, .34), "spine": (0, -.18, .32), "chest": (0, -.28, .42),
        "head": (0, .16, -.18), "clavicle.L": (0, .05, .18), "clavicle.R": (0, -.05, -.18),
        "upper_arm.L": (.18, .08, .62), "forearm.L": (-.52, -.08, .20),
        "upper_arm.R": (-.12, -.08, -.54), "forearm.R": (-.48, .08, -.18),
        "thigh.L": (-.10, 0, .10), "shin.L": (-.24, 0, 0), "thigh.R": (.30, 0, -.12), "shin.R": (-.40, 0, 0),
    }),
    98: pose(**{
        "pelvis": (0, -.12, .24), "spine": (0, -.12, .20), "chest": (0, -.18, .26),
        "head": (0, .10, -.12), "upper_arm.L": (-.20, .05, .34), "forearm.L": (-.78, -.06, .12),
        "upper_arm.R": (-.30, -.05, -.22), "forearm.R": (-.72, .05, -.10),
        "thigh.L": (.18, 0, .05), "shin.L": (-.32, 0, 0), "thigh.R": (-.08, 0, -.04), "shin.R": (-.22, 0, 0),
    }),
    108: pose(**{
        "pelvis": (0, -.08, .10), "spine": (0, -.04, .08), "chest": (0, .02, .10),
        "head": (0, -.02, -.04), "upper_arm.L": (-.56, .02, -.42), "forearm.L": (-1.02, -.05, .06),
        "upper_arm.R": (-.62, 0, .50), "forearm.R": (-1.06, .05, -.08),
        "thigh.L": (.18, 0, -.03), "shin.L": (-.32, 0, 0), "thigh.R": (-.14, 0, .02), "shin.R": (-.20, 0, 0),
    }),
}


NARUTO_POSES = {
    1: pose(**{
        "pelvis": (0, -.14, -.12), "spine": (0, .08, -.08), "chest": (0, .05, -.10),
        "head": (0, -.04, .08), "upper_arm.L": (-.72, .02, -.56), "forearm.L": (-1.28, -.05, .08),
        "upper_arm.R": (-.78, -.02, .62), "forearm.R": (-1.30, .05, -.08),
        "thigh.L": (.42, 0, -.06), "shin.L": (-.58, 0, 0), "foot.L": (.14, 0, 0),
        "thigh.R": (-.28, 0, .06), "shin.R": (-.34, 0, 0), "foot.R": (.10, 0, 0),
    }),
    8: pose(**{
        "pelvis": (0, -.20, -.16), "spine": (0, .10, -.12), "chest": (0, .06, -.12),
        "head": (0, -.03, .10), "upper_arm.L": (-.68, .02, -.50), "forearm.L": (-1.22, -.05, .08),
        "upper_arm.R": (-.76, -.02, .58), "forearm.R": (-1.26, .05, -.08),
        "thigh.L": (.54, 0, -.08), "shin.L": (-.68, 0, 0), "foot.L": (.16, 0, 0),
        "thigh.R": (-.34, 0, .08), "shin.R": (-.40, 0, 0), "foot.R": (.12, 0, 0),
    }),
    14: pose(**{
        "pelvis": (0, -.24, -.42), "spine": (0, -.08, -.24), "chest": (0, -.10, -.38),
        "head": (0, .10, .32), "upper_arm.L": (-.56, .06, -.38), "forearm.L": (-1.18, -.08, .12),
        "upper_arm.R": (-.66, -.04, .44), "forearm.R": (-1.20, .08, -.10),
        "thigh.L": (.64, 0, -.12), "shin.L": (-.74, 0, 0), "foot.L": (.18, 0, 0),
        "thigh.R": (-.22, 0, .12), "shin.R": (-.42, 0, 0), "foot.R": (.10, 0, 0),
    }),
    17: pose(**{
        "pelvis": (0, -.20, -.56), "spine": (0, -.10, -.34), "chest": (0, -.12, -.54),
        "head": (0, .14, .40), "upper_arm.L": (-.48, .08, -.30), "forearm.L": (-1.10, -.10, .12),
        "upper_arm.R": (-.58, -.06, .34), "forearm.R": (-1.12, .10, -.12),
        "thigh.L": (.58, 0, -.14), "shin.L": (-.70, 0, 0), "foot.L": (.18, 0, 0),
        "thigh.R": (-.12, 0, .14), "shin.R": (-.38, 0, 0), "foot.R": (.08, 0, 0),
    }),
    22: pose(**{
        "pelvis": (0, -.12, -.34), "spine": (0, -.04, -.20), "chest": (0, -.05, -.28),
        "head": (0, .08, .22), "upper_arm.L": (-.74, .02, .34), "forearm.L": (-1.42, -.04, .06),
        "upper_arm.R": (-.64, -.02, .46), "forearm.R": (-1.22, .06, -.08),
        "thigh.L": (.30, 0, -.08), "shin.L": (-.46, 0, 0), "thigh.R": (-.16, 0, .08), "shin.R": (-.28, 0, 0),
    }),
    27: pose(**{
        "pelvis": (0, -.18, .22), "spine": (0, -.10, .26), "chest": (0, -.06, .30),
        "head": (0, -.02, -.12), "clavicle.L": (0, 0, .16),
        "upper_arm.L": (-1.28, -.04, .86), "forearm.L": (-1.34, .06, -.16), "hand.L": (0, .10, -.16),
        "upper_arm.R": (-.70, -.02, .52), "forearm.R": (-1.24, .06, -.08),
        "thigh.L": (.28, 0, -.05), "shin.L": (-.46, 0, 0), "thigh.R": (-.30, 0, .08), "shin.R": (-.34, 0, 0),
    }),
    33: pose(**{
        "pelvis": (0, .06, -.30), "spine": (0, .08, -.24), "chest": (0, .04, -.34),
        "head": (0, -.03, .14), "clavicle.L": (0, 0, -.18),
        "upper_arm.L": (.02, -.02, -1.26), "forearm.L": (-.05, .02, -.06), "hand.L": (0, -.06, .04),
        "upper_arm.R": (-.62, -.02, .50), "forearm.R": (-1.18, .06, -.08),
        "thigh.L": (-.18, 0, -.04), "shin.L": (-.24, 0, 0), "thigh.R": (.42, 0, .08), "shin.R": (-.54, 0, 0),
    }),
    36: pose(**{
        "pelvis": (0, .08, -.34), "spine": (0, .10, -.26), "chest": (0, .05, -.36),
        "head": (0, -.02, .15), "upper_arm.L": (.10, -.02, -1.18), "forearm.L": (-.10, .02, -.08),
        "upper_arm.R": (-.64, -.02, .46), "forearm.R": (-1.18, .06, -.08),
        "thigh.L": (-.14, 0, -.04), "shin.L": (-.26, 0, 0), "thigh.R": (.38, 0, .08), "shin.R": (-.52, 0, 0),
    }),
    43: pose(**{
        "pelvis": (0, -.06, -.20), "spine": (0, -.02, -.12), "chest": (0, -.03, -.16),
        "head": (0, 0, .08), "upper_arm.L": (-.42, -.02, -.64), "forearm.L": (-.86, .03, -.10),
        "upper_arm.R": (-.70, -.02, .50), "forearm.R": (-1.20, .06, -.08),
        "thigh.L": (.12, 0, -.04), "shin.L": (-.32, 0, 0), "thigh.R": (.16, 0, .06), "shin.R": (-.36, 0, 0),
    }),
    51: pose(**{
        "pelvis": (0, -.20, .22), "spine": (0, -.10, .18), "chest": (0, -.04, .22),
        "head": (0, -.02, -.08), "upper_arm.L": (-.58, .02, -.42), "forearm.L": (-1.08, -.04, .06),
        "upper_arm.R": (-1.20, -.02, .72), "forearm.R": (-1.34, .08, -.12), "hand.R": (0, .08, -.16),
        "thigh.L": (.46, 0, -.10), "shin.L": (-.60, 0, 0), "foot.L": (.16, 0, 0),
        "thigh.R": (-.34, 0, .10), "shin.R": (-.40, 0, 0), "foot.R": (.12, 0, 0),
    }),
    61: pose(**{
        "pelvis": (0, -.24, .28), "spine": (0, -.12, .24), "chest": (0, -.08, .28),
        "head": (0, -.02, -.10), "clavicle.R": (0, 0, .16),
        "upper_arm.R": (-1.38, -.03, .92), "forearm.R": (-1.42, .08, -.18), "hand.R": (0, .12, -.20),
        "upper_arm.L": (-.62, .02, -.46), "forearm.L": (-1.14, -.05, .08),
        "thigh.L": (.52, 0, -.12), "shin.L": (-.66, 0, 0), "foot.L": (.18, 0, 0),
        "thigh.R": (-.40, 0, .12), "shin.R": (-.46, 0, 0), "foot.R": (.14, 0, 0),
    }),
    72: pose(**{
        "pelvis": (0, -.10, -.14), "spine": (0, .04, -.12), "chest": (0, .02, -.18),
        "head": (0, -.02, .08), "clavicle.R": (0, 0, -.12),
        "upper_arm.R": (-.72, -.02, -.58), "forearm.R": (-1.10, .06, -.14), "hand.R": (0, .10, -.18),
        "upper_arm.L": (-.72, .02, -.44), "forearm.L": (-1.18, -.05, .08),
        "thigh.L": (-.12, 0, -.06), "shin.L": (-.28, 0, 0), "thigh.R": (.42, 0, .10), "shin.R": (-.54, 0, 0),
    }),
    79: pose(**{
        "pelvis": (0, .08, -.34), "spine": (0, .10, -.28), "chest": (0, .05, -.38),
        "head": (0, -.03, .14), "clavicle.R": (0, 0, -.24),
        "upper_arm.R": (-.12, -.02, -1.20), "forearm.R": (-.36, .04, -.12), "hand.R": (0, .08, -.14),
        "upper_arm.L": (-.58, .02, -.42), "forearm.L": (-1.10, -.05, .06),
        "thigh.L": (-.22, 0, -.04), "shin.L": (-.22, 0, 0), "thigh.R": (.50, 0, .08), "shin.R": (-.62, 0, 0),
    }),
    82: pose(**{
        "pelvis": (0, .12, -.40), "spine": (0, .12, -.32), "chest": (0, .06, -.42),
        "head": (0, -.03, .16), "clavicle.R": (0, 0, -.28),
        "upper_arm.R": (.02, -.02, -1.34), "forearm.R": (-.10, .03, -.08), "hand.R": (0, .04, -.08),
        "upper_arm.L": (-.52, .02, -.40), "forearm.L": (-1.04, -.05, .06),
        "thigh.L": (-.20, 0, -.04), "shin.L": (-.24, 0, 0), "thigh.R": (.48, 0, .08), "shin.R": (-.60, 0, 0),
    }),
    84: pose(**{
        "pelvis": (0, .12, -.40), "spine": (0, .12, -.32), "chest": (0, .06, -.42),
        "head": (0, -.03, .16), "clavicle.R": (0, 0, -.28),
        "upper_arm.R": (.02, -.02, -1.34), "forearm.R": (-.10, .03, -.08), "hand.R": (0, .04, -.08),
        "upper_arm.L": (-.52, .02, -.40), "forearm.L": (-1.04, -.05, .06),
        "thigh.L": (-.20, 0, -.04), "shin.L": (-.24, 0, 0), "thigh.R": (.48, 0, .08), "shin.R": (-.60, 0, 0),
    }),
    90: pose(**{
        "pelvis": (0, .08, -.28), "spine": (0, .08, -.20), "chest": (0, .02, -.26),
        "head": (0, -.02, .10), "upper_arm.R": (.22, -.02, -1.12), "forearm.R": (-.20, .03, -.06),
        "upper_arm.L": (-.58, .02, -.42), "forearm.L": (-1.08, -.05, .06),
        "thigh.L": (.06, 0, -.03), "shin.L": (-.30, 0, 0), "thigh.R": (.22, 0, .06), "shin.R": (-.42, 0, 0),
    }),
    98: pose(**{
        "pelvis": (0, -.12, -.14), "spine": (0, .04, -.10), "chest": (0, .02, -.12),
        "head": (0, -.02, .06), "upper_arm.R": (-.48, -.02, .36), "forearm.R": (-1.02, .05, -.06),
        "upper_arm.L": (-.66, .02, -.46), "forearm.L": (-1.14, -.05, .08),
        "thigh.L": (.34, 0, -.06), "shin.L": (-.48, 0, 0), "thigh.R": (-.20, 0, .06), "shin.R": (-.28, 0, 0),
    }),
    108: pose(**{
        "pelvis": (0, -.14, -.10), "spine": (0, .06, -.08), "chest": (0, .03, -.10),
        "head": (0, -.02, .06), "upper_arm.L": (-.70, .02, -.52), "forearm.L": (-1.22, -.05, .08),
        "upper_arm.R": (-.76, -.02, .58), "forearm.R": (-1.24, .05, -.08),
        "thigh.L": (.38, 0, -.06), "shin.L": (-.54, 0, 0), "thigh.R": (-.24, 0, .06), "shin.R": (-.32, 0, 0),
    }),
}


# The compact control rig's forearm local axes are highly non-intuitive. These
# reviewed arm shapes are manually selected individual-pose references from the
# existing WWS rig, then sequenced and targeted as the new paired performance.
# They are not copied animation clips and contain no source timing.
OMNI_ARM_SHAPES = {
    "guard": {
        "upper_arm.L": (-.592, .114, -.427), "forearm.L": (.560, -.729, -2.682),
        "upper_arm.R": (.555, -.044, -.285), "forearm.R": (-1.780, -.910, -.401),
    },
    "punch_load": {
        "upper_arm.L": (-.562, .005, -.437), "forearm.L": (-.800, -.195, -.180),
        "upper_arm.R": (-1.432, -.042, .857), "forearm.R": (-1.235, -.104, -.064),
    },
    "punch_travel": {
        "upper_arm.L": (-.749, 0, -.438), "forearm.L": (-.720, -.076, 0),
        "upper_arm.R": (-.867, -.033, -.407), "forearm.R": (-.645, .084, -.007),
    },
    "punch_extension": {
        "upper_arm.L": (-.620, -.001, -.459), "forearm.L": (-.721, -.084, 0),
        "upper_arm.R": (.271, -.048, -1.442), "forearm.R": (.076, .084, .014),
    },
    "parry_ready": {
        "upper_arm.L": (-.640, .206, -.432), "forearm.L": (-.015, -.613, -1.719),
        "upper_arm.R": (.485, -.052, -.211), "forearm.R": (-1.145, -.668, -.645),
    },
    "parry": {
        "upper_arm.L": (-.754, .583, -.428), "forearm.L": (.226, -1.451, -2.517),
        "upper_arm.R": (.626, -.249, -.243), "forearm.R": (-2.305, -.946, .153),
    },
    "brace": {
        "upper_arm.L": (-.110, .594, .568), "forearm.L": (.252, -.217, -1.791),
        "upper_arm.R": (.064, -.271, .362), "forearm.R": (.437, -.887, -2.186),
    },
    "recoil": {
        "upper_arm.L": (-.035, 1.917, 1.590), "forearm.L": (1.573, .091, .037),
        "upper_arm.R": (-.410, .824, -.238), "forearm.R": (.871, -.233, 1.605),
    },
    "recover": {
        "upper_arm.L": (.362, -.348, .958), "forearm.L": (-1.341, -.477, -.862),
        "upper_arm.R": (-.480, .472, -.172), "forearm.R": (1.874, -.031, .247),
    },
}

NARUTO_ARM_SHAPES = {
    "guard": {
        "upper_arm.L": (-.705, .261, -.628), "forearm.L": (-1.773, -1.326, -.411),
        "upper_arm.R": (.523, -.052, -.096), "forearm.R": (-2.069, -.791, -.083),
    },
    "slip": {
        "upper_arm.L": (.380, .012, -.704), "forearm.L": (-1.021, -.160, -.115),
        "upper_arm.R": (-.953, -.030, .420), "forearm.R": (-1.198, -.109, -.077),
    },
    "counter_load": {
        "upper_arm.L": (-.094, -.003, -.551), "forearm.L": (-.740, -.036, -.005),
        "upper_arm.R": (-1.199, -.014, .436), "forearm.R": (-.215, .036, 0),
    },
    "counter": {
        "upper_arm.L": (-.715, .002, -.706), "forearm.L": (-.849, -.087, .027),
        "upper_arm.R": (-.106, -.030, -.890), "forearm.R": (-.133, .084, -.007),
    },
    "redirect": {
        "upper_arm.L": (-.854, 0, -.875), "forearm.L": (-1.132, -.037, .076),
        "upper_arm.R": (-.438, -.025, -.123), "forearm.R": (-.468, .035, -.032),
    },
    "angle": {
        "upper_arm.L": (-1.061, -.003, -.838), "forearm.L": (-1.179, -.001, .080),
        "upper_arm.R": (-1.024, 0, .833), "forearm.R": (-1.102, -.002, -.087),
    },
    "rasengan": {
        "upper_arm.L": (-1.099, .029, -.683), "forearm.L": (-1.106, -.034, .092),
        "upper_arm.R": (-.330, .034, .594), "forearm.R": (-1.304, .034, -.122),
    },
    "recover": {
        "upper_arm.L": (-.642, .034, -.617), "forearm.L": (-.904, .027, .045),
        "upper_arm.R": (.087, -.046, -.460), "forearm.R": (-.321, .014, -.056),
    },
}


def apply_arm_shapes(poses, shapes, assignments):
    for frame, name in assignments.items():
        poses[frame].update(shapes[name])


apply_arm_shapes(OMNI_POSES, OMNI_ARM_SHAPES, {
    1: "guard", 8: "punch_load", 14: "punch_travel", 17: "punch_extension", 22: "punch_extension",
    28: "parry_ready", 33: "parry_ready", 36: "parry", 43: "parry", 52: "guard",
    65: "guard", 76: "brace", 82: "brace", 84: "brace", 90: "recoil", 98: "recover", 108: "guard",
})
apply_arm_shapes(NARUTO_POSES, NARUTO_ARM_SHAPES, {
    1: "guard", 8: "guard", 14: "slip", 17: "slip", 22: "slip", 27: "counter_load",
    33: "counter", 36: "counter", 43: "redirect", 51: "angle", 61: "rasengan",
    72: "rasengan", 79: "rasengan", 82: "rasengan", 84: "rasengan", 90: "rasengan",
    98: "recover", 108: "guard",
})


ROOT_KEYS = {
    "fighter_a": {
        1: (-1.70, .50, .04), 8: (-1.70, .50, .04), 12: (-1.55, .48, .04),
        17: (-.62, .30, .05), 22: (-.42, .20, .05), 28: (-.24, .19, .04),
        36: (-.18, .18, .04), 43: (-.14, .15, .04), 52: (-.10, .13, .04),
        65: (-.04, .12, .04), 76: (-.04, .12, .04), 82: (-.04, .12, .04),
        84: (-.04, .12, .04), 90: (-.72, -.05, .16), 98: (-1.05, -.18, .06), 108: (-1.10, -.18, .04),
    },
    "fighter_b": {
        1: (1.12, -.52, .03), 8: (1.12, -.52, .03), 12: (1.02, -.72, .03),
        17: (.98, -1.30, .03), 22: (.92, -1.28, .03), 28: (.90, -1.00, .03),
        36: (.94, -.90, .03), 43: (.90, -.94, .03), 52: (.96, 1.22, .03),
        61: (1.00, 1.24, .03), 68: (.98, 1.20, .03), 76: (.98, 1.16, .03),
        82: (1.06, 1.20, .03), 84: (1.06, 1.20, .03), 90: (1.12, 1.25, .03),
        98: (1.15, 1.08, .03), 108: (1.26, 1.10, .03),
    },
}


BEATS = [
    (1, "ready"), (8, "omni_attack_load"), (17, "omni_attack_naruto_outside_slip"),
    (22, "attack_overshoot"), (27, "naruto_counter_load"), (33, "counter_arrival"),
    (36, "omni_parry_redirect"), (43, "redirect_release"), (52, "naruto_angle_change"),
    (61, "rasengan_load"), (72, "rasengan_entry"), (79, "rasengan_acceleration"),
    (82, "rasengan_tangent_contact"), (84, "three_frame_hit_hold"), (90, "authored_recoil_separation"),
    (98, "recovery_settle"), (108, "recovery"),
]


def configure_curves(action, holds=()):
    holds = set(holds)
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            frame = round(key.co.x)
            key.interpolation = "CONSTANT" if frame in holds else "BEZIER"
            if key.interpolation == "BEZIER":
                key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"


def add_track(rig, action, name):
    track = rig.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(action.name, 1, action)
    strip.action_frame_start = 1
    strip.action_frame_end = END
    strip.frame_start = 1
    strip.frame_end = END
    strip.extrapolation = "HOLD"
    strip.blend_type = "REPLACE"
    return track


def build_body_action(rig, label, poses):
    action = bpy.data.actions.new(f"HA_BODY_{label}")
    action["wws_animation_source"] = "hand-authored paired keyframe performance"
    action["wws_mixamo_used"] = False
    action["wws_production_gate_status"] = "prototype_pending_review"
    rig.animation_data.action = action
    previous = {}
    for frame in sorted(poses):
        for name in BONES:
            bone = rig.pose.bones[name]
            bone.rotation_mode = "QUATERNION"
            values = list(poses[frame][name])
            if name in {"pelvis", "spine", "chest"}:
                # Preserve weight shift while preventing three adjacent spine
                # joints from accumulating into a folded torso.
                values[0] *= .78
                values[1] *= .78
                values[2] *= .52
            q = Euler(values, "XYZ").to_quaternion()
            if name in previous and previous[name].dot(q) < 0:
                q.negate()
            previous[name] = q.copy()
            bone.rotation_quaternion = q
            bone.keyframe_insert("rotation_quaternion", frame=frame, group=name)
    configure_curves(action, HOLD_FRAMES)
    rig.animation_data.action = None
    add_track(rig, action, "HA_PAIRED_BODY")
    return action


def interpolate_position(keys, frame):
    frames = sorted(keys)
    if frame <= frames[0]:
        return Vector(keys[frames[0]])
    if frame >= frames[-1]:
        return Vector(keys[frames[-1]])
    lo = max(value for value in frames if value <= frame)
    hi = min(value for value in frames if value >= frame)
    if lo == hi:
        return Vector(keys[lo])
    t = (frame - lo) / (hi - lo)
    return Vector(keys[lo]).lerp(Vector(keys[hi]), t)


def build_root_action(rig, fighter):
    action = bpy.data.actions.new(f"HA_ROOT_{fighter}")
    action["wws_root_motion_separate"] = True
    rig.animation_data.action = action
    own = ROOT_KEYS[fighter]
    other = ROOT_KEYS["fighter_b" if fighter == "fighter_a" else "fighter_a"]
    frames = sorted(set(own) | set(other))
    for frame in frames:
        location = interpolate_position(own, frame)
        target = interpolate_position(other, frame)
        yaw = math.atan2(target.y - location.y, target.x - location.x)
        rig.location = location
        rig.rotation_mode = "XYZ"
        rig.rotation_euler = (0.0, 0.0, yaw)
        rig.keyframe_insert("location", frame=frame, group="ROOT_TRAJECTORY")
        rig.keyframe_insert("rotation_euler", frame=frame, group="ROOT_TRAJECTORY")
    configure_curves(action, HOLD_FRAMES)
    rig.animation_data.action = None
    add_track(rig, action, "HA_ROOT_TRAJECTORY")
    return action


def new_empty(name, collection, location, display="PLAIN_AXES", size=.18):
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.empty_display_type = display
    obj.empty_display_size = size
    obj.location = location
    return obj


def key_control(obj, points):
    for frame, location in points:
        obj.location = location
        obj.keyframe_insert("location", frame=frame)
    if obj.animation_data and obj.animation_data.action:
        configure_curves(obj.animation_data.action, HOLD_FRAMES)


def key_influence(rig, action, constraint, values):
    rig.animation_data.action = action
    for frame, value in values:
        constraint.influence = value
        constraint.keyframe_insert("influence", frame=frame)
    rig.animation_data.action = None


def source_bone_point(rig_name, bone_name, frame, fraction=.5):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    rig = bpy.data.objects[rig_name]
    bone = rig.pose.bones[bone_name]
    return rig.matrix_world @ bone.head.lerp(bone.tail, fraction)


def add_arm_control(rig, controls_action, collection, name, side, target_points, influence_points, pole_points):
    target = new_empty(f"HA_{name}_TARGET", collection, target_points[0][1], "SPHERE", .12)
    pole = new_empty(f"HA_{name}_POLE", collection, pole_points[0][1], "CUBE", .10)
    key_control(target, target_points)
    key_control(pole, pole_points)
    forearm = rig.pose.bones[f"forearm.{side}"]
    ik = forearm.constraints.new("IK")
    ik.name = f"HA {name} partner target"
    ik.target = target
    ik.pole_target = pole
    ik.chain_count = 2
    ik.use_stretch = False
    ik.pole_angle = 0.0
    key_influence(rig, controls_action, ik, influence_points)
    return {
        "name": name, "side": side, "target": target.name, "pole": pole.name,
        "influence_keys": influence_points,
        "partner_relative": True,
    }


def add_foot_pin(rig, controls_action, collection, fighter, side, start, end, release, pole_sign, name_prefix="SOURCE"):
    bpy.context.scene.frame_set(start)
    bpy.context.view_layer.update()
    source_names = f"shin.{side}" in rig.pose.bones
    shin = rig.pose.bones[f"shin.{side}" if source_names else f"LowerLeg_{side}"]
    foot = rig.pose.bones[f"foot.{side}" if source_names else f"Foot_{side}"]
    ankle = rig.matrix_world @ shin.tail
    knee = rig.matrix_world @ shin.head
    facing = rig.matrix_world.to_quaternion() @ Vector((1, 0, 0))
    lateral = rig.matrix_world.to_quaternion() @ Vector((0, pole_sign, 0))
    target = new_empty(f"HA_{name_prefix}_{fighter}_FOOT_{side}_{start:03d}", collection, ankle, "CUBE", .11)
    target.rotation_mode = "QUATERNION"
    target.rotation_quaternion = (rig.matrix_world @ foot.matrix).to_quaternion()
    pole = new_empty(f"HA_{name_prefix}_{fighter}_KNEE_{side}_{start:03d}", collection, knee + facing * .55 + lateral * .12, "CUBE", .09)
    ik = shin.constraints.new("IK")
    ik.name = f"HA planted foot {start}-{end}"
    ik.target = target
    ik.pole_target = pole
    ik.chain_count = 2
    ik.use_stretch = False
    sole = foot.constraints.new("COPY_ROTATION")
    sole.name = f"HA planted sole {start}-{end}"
    sole.target = target
    values = ((1, 0.0), (max(1, start - 2), 0.0), (start, 1.0), (end, 1.0), (release, 0.0), (END, 0.0))
    key_influence(rig, controls_action, ik, values)
    key_influence(rig, controls_action, sole, values)
    return {"fighter": fighter, "rig_layer": name_prefix.lower(), "side": side, "frames": [start, end], "release": release, "target": [round(v, 5) for v in ankle], "target_object": target.name}


def bake_foot_lock_compensation(records):
    """Bake the small evaluated-rig IK residual out of planted intervals.

    Blender's compact review rig and production adapter use different segment
    lengths.  The IK residual is corrected at the invisible target only; roots
    and authored body poses remain untouched.
    """
    scene = bpy.context.scene
    results = []
    for record in records:
        fighter = record["fighter"]
        side = record["side"]
        start, end = record["frames"]
        rig = bpy.data.objects[fighter + "_ProductionRig"]
        target = bpy.data.objects[record["target_object"]]
        bone = rig.pose.bones["Foot_" + side]
        scene.frame_set(start)
        bpy.context.view_layer.update()
        anchor = rig.matrix_world @ bone.head
        for frame in range(start, end + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            # Two small solver iterations converge the review rig without an
            # abrupt per-frame body correction.
            for _ in range(2):
                current = rig.matrix_world @ bone.head
                target.location += anchor - current
                bpy.context.view_layer.update()
            target.keyframe_insert("location", frame=frame)
        if target.animation_data and target.animation_data.action:
            for curve in target.animation_data.action.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = "LINEAR"
        results.append({"fighter": fighter, "side": side, "frames": [start, end], "anchor": [round(v, 5) for v in anchor]})
    return results


def build_adaptation_controls(collision):
    collection = bpy.data.collections.new("HA_AUTHORED_CONTROLS")
    bpy.context.scene.collection.children.link(collection)
    omni = bpy.data.objects["fighter_a_Rig"]
    naruto = bpy.data.objects["fighter_b_Rig"]
    actions = {}
    for fighter, rig in (("fighter_a", omni), ("fighter_b", naruto)):
        action = bpy.data.actions.new(f"HA_CONTROLS_{fighter}")
        action["wws_role"] = "minor authored contact and plant cleanup"
        action["wws_collision_solver"] = False
        actions[fighter] = action

    # Omni-Man's attack is aimed at Naruto's pre-slip head position.  Naruto's
    # evaluated head vacates it, so the authored punch passes through empty air.
    old_head = source_bone_point("fighter_b_ProductionRig", "Head", 8, .60)
    omni_shoulder = source_bone_point("fighter_a_ProductionRig", "UpperArm_R", 8, .10)
    controls = [add_arm_control(
        omni, actions["fighter_a"], collection, "OMNI_PUNCH_MISS", "R",
        [(8, omni_shoulder), (13, omni_shoulder.lerp(old_head, .48)), (17, old_head), (22, old_head + Vector((.32, -.05, -.04)))],
        ((1, 0), (8, 0), (12, .18), (15, .70), (17, 1), (20, .55), (23, 0), (END, 0)),
        [(8, omni_shoulder + Vector((0, -.65, -.30))), (17, old_head + Vector((-.25, -.62, -.36))), (22, old_head + Vector((.10, -.58, -.40)))],
    )]

    # Paired parry point is authored from both evaluated forearms, then frozen
    # in world space.  This avoids a circular target dependency.
    naruto_counter = source_bone_point("fighter_b_ProductionRig", "Hand_L", 33, .55)
    omni_guard = source_bone_point("fighter_a_ProductionRig", "LowerArm_L", 36, .55)
    parry_point = naruto_counter.lerp(omni_guard, .58) + Vector((0, 0, -.12))
    n_shoulder = source_bone_point("fighter_b_ProductionRig", "UpperArm_L", 27, .12)
    o_shoulder = source_bone_point("fighter_a_ProductionRig", "UpperArm_L", 28, .12)
    controls.append(add_arm_control(
        naruto, actions["fighter_b"], collection, "NARUTO_COUNTER", "L",
        [(27, n_shoulder), (30, n_shoulder.lerp(parry_point, .42)), (33, parry_point), (36, parry_point + Vector((.04, .08, .02))), (42, parry_point + Vector((-.20, .18, -.06)))],
        ((1, 0), (27, 0), (30, .25), (33, .82), (36, .68), (39, .25), (43, 0), (END, 0)),
        [(27, n_shoulder + Vector((0, .55, -.28))), (33, parry_point + Vector((-.20, .55, -.34))), (42, parry_point + Vector((-.30, .48, -.30)))],
    ))
    controls.append(add_arm_control(
        omni, actions["fighter_a"], collection, "OMNI_PARRY", "L",
        [(28, o_shoulder), (32, o_shoulder.lerp(parry_point, .46)), (36, parry_point + Vector((.03, -.03, .03))), (39, parry_point + Vector((.16, .20, .02))), (43, parry_point + Vector((.28, .34, -.04)))],
        ((1, 0), (28, 0), (32, .24), (35, .76), (36, .92), (39, .55), (43, 0), (END, 0)),
        [(28, o_shoulder + Vector((0, -.55, -.25))), (36, parry_point + Vector((.20, -.58, -.34))), (43, parry_point + Vector((.30, -.46, -.30)))],
    ))

    # The Rasengan effector ends at the outside surface of the chest capsule.
    bpy.context.scene.frame_set(CONTACT_FRAME)
    bpy.context.view_layer.update()
    chest = collision.capsule_for(bpy.data.objects["fighter_a_ProductionRig"], "omniman", "chest")
    center = chest.a.lerp(chest.b, .50)
    naruto_center = source_bone_point("fighter_b_ProductionRig", "SpineUpper", CONTACT_FRAME, .50)
    outward = naruto_center - center
    outward.z = 0
    if outward.length < 1e-6:
        outward = Vector((1, 0, 0))
    outward.normalize()
    tangent = center + outward * (chest.radius + .035)
    shoulder = source_bone_point("fighter_b_ProductionRig", "UpperArm_R", 61, .10)
    controls.append(add_arm_control(
        naruto, actions["fighter_b"], collection, "RASENGAN_TANGENT", "R",
        [(61, shoulder), (72, shoulder.lerp(tangent, .30) + Vector((0, .05, .05))),
         (78, shoulder.lerp(tangent, .72) + Vector((0, .02, .03))), (82, tangent), (84, tangent),
         (88, tangent + outward * .18), (92, tangent + outward * .42)],
        ((1, 0), (61, 0), (72, .10), (78, .42), (81, .82), (82, 1), (84, 1), (87, .55), (91, 0), (END, 0)),
        [(61, shoulder + Vector((0, -.62, -.32))), (78, tangent + Vector((.10, -.60, -.38))),
         (82, tangent + Vector((.16, -.56, -.34))), (92, tangent + Vector((.30, -.48, -.28)))],
    ))

    production_actions = {}
    for fighter in ("fighter_a", "fighter_b"):
        action = bpy.data.actions.new(f"HA_EVALUATED_CONTROLS_{fighter}")
        action["wws_role"] = "minor evaluated-rig contact and plant cleanup"
        action["wws_collision_solver"] = False
        production_actions[fighter] = action

    # The compact authoring rig and evaluated production rig have different
    # rest proportions. Reuse the same authored targets as a narrow retarget
    # correction on the evaluated arms; this does not move roots or invent arcs.
    production_arm_map = {
        "OMNI_PUNCH_MISS": ("fighter_a", "R"),
        "NARUTO_COUNTER": ("fighter_b", "L"),
        "OMNI_PARRY": ("fighter_a", "L"),
        "RASENGAN_TANGENT": ("fighter_b", "R"),
    }
    for control in controls:
        fighter, side = production_arm_map[control["name"]]
        production = bpy.data.objects[fighter + "_ProductionRig"]
        forearm = production.pose.bones[f"LowerArm_{side}"]
        ik = forearm.constraints.new("IK")
        ik.name = f"HA evaluated {control['name']}"
        target = bpy.data.objects[control["target"]]
        if control["name"] == "RASENGAN_TANGENT":
            # The evaluated arm has a longer rest offset than the compact
            # authoring rig. A constant, documented retarget offset makes the
            # evaluated wrist tangent while preserving the authored arc.
            corrected = new_empty("HA_EVALUATED_RASENGAN_TARGET", collection, (0, 0, 0), "SPHERE", .10)
            corrected.parent = target
            corrected.location = -outward * .29
            target = corrected
            control["evaluated_target"] = corrected.name
            control["evaluated_retarget_offset"] = [round(v, 5) for v in corrected.location]
        ik.target = target
        ik.pole_target = bpy.data.objects[control["pole"]]
        ik.chain_count = 2
        ik.use_stretch = False
        key_influence(production, production_actions[fighter], ik, control["influence_keys"])

    foot_pins = []
    pin_specs = (
        ("fighter_a", "R", 1, 8, 12, -1),
        ("fighter_a", "R", 36, 40, 43, -1),
        ("fighter_a", "L", 52, 60, 64, 1),
        ("fighter_a", "R", 79, 84, 88, -1),
        ("fighter_b", "L", 1, 7, 11, 1),
        ("fighter_b", "R", 52, 58, 62, -1),
        ("fighter_b", "R", 81, 84, 88, -1),
        ("fighter_b", "L", 98, 104, 108, 1),
    )
    for fighter, rig in (("fighter_a", omni), ("fighter_b", naruto)):
        configure_curves(actions[fighter], HOLD_FRAMES)
        rig.animation_data.action = None
        add_track(rig, actions[fighter], "HA_CONTACT_AND_PLANT_CONTROLS")

    # Retargeted limb proportions differ slightly from the compact source rig.
    # A second, presentation-only foot lock on the evaluated production rig
    # preserves the same authored support windows without moving either root.
    for fighter, side, start, end, release, pole_sign in pin_specs:
        production = bpy.data.objects[fighter + "_ProductionRig"]
        if not production.animation_data:
            production.animation_data_create()
        foot_pins.append(add_foot_pin(production, production_actions[fighter], collection, fighter, side, start, end, release, pole_sign, "PRODUCTION"))
    for fighter in ("fighter_a", "fighter_b"):
        production = bpy.data.objects[fighter + "_ProductionRig"]
        configure_curves(production_actions[fighter], HOLD_FRAMES)
        production.animation_data.action = None
        add_track(production, production_actions[fighter], "HA_EVALUATED_CONTACT_AND_PLANTS")
    bake_foot_lock_compensation(foot_pins)
    return controls, foot_pins, tangent


def configure_rasengan_marker():
    old = bpy.data.objects.get("HERO_RasenganMarker") or bpy.data.objects.get("ML_RasenganSphere")
    if old:
        old.hide_render = True
    collection = bpy.data.collections["WWS_MOTION_DEBUG_BODY"]
    marker = motion_lab.sphere("HA_RasenganContactMarker", .15, motion_lab.material("HA_RasenganBlue", (.02, .38, 1.0, 1)), collection)
    marker.parent = bpy.data.objects["ML_Naruto_hand.R_carrier"]
    marker.location = (0, .28, 0)
    marker.hide_render = True
    marker.keyframe_insert("hide_render", frame=1)
    marker.keyframe_insert("hide_render", frame=54)
    marker.hide_render = False
    marker.keyframe_insert("hide_render", frame=55)
    marker.keyframe_insert("hide_render", frame=91)
    marker.hide_render = True
    marker.keyframe_insert("hide_render", frame=92)
    return marker


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_camera(name, location, target, lens, collection, ortho=None):
    data = bpy.data.cameras.new(name + "_DATA")
    camera = bpy.data.objects.new(name, data)
    collection.objects.link(camera)
    camera.location = location
    data.lens = lens
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = ortho
    look_at(camera, target)
    return camera


def configure_review_scene():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = END
    scene.render.fps = FPS
    scene.render.resolution_x = 360
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    for name in ("WWS_MOTION_OVERLAYS",):
        collection = bpy.data.collections.get(name)
        if collection:
            collection.hide_render = True
            collection.hide_viewport = True
    cameras = bpy.data.collections.new("HA_REVIEW_CAMERAS")
    scene.collection.children.link(cameras)
    target = (-.05, .03, 1.42)
    specs = {
        # Primary view keeps feet in frame while preserving a tight phone-sized
        # three-quarter silhouette for the parry and Rasengan contact.
        "three-quarter": ((-4.70, -6.90, 3.15), target, 60, None),
        "side": ((-.05, -9.2, 2.55), target, 54, 4.25),
        "front-diagonal": ((-5.65, -6.15, 3.0), target, 56, None),
        "top": ((-.05, .03, 11.8), (-.05, .03, 0), 50, 5.2),
        "contact": ((3.35, -4.55, 2.45), (0.15, .25, 1.72), 68, None),
    }
    for label, (location, aim, lens, ortho) in specs.items():
        add_camera("HA_CAM_" + label, location, aim, lens, cameras, ortho)
    scene.camera = bpy.data.objects["HA_CAM_three-quarter"]
    for marker in scene.timeline_markers:
        marker.camera = scene.camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "rim.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    return specs


def write_provenance(body_actions, root_actions, controls, pins, tangent, cameras):
    source_events = SOURCE / "source/events.json"
    mixamo_dir = ROOT / "outputs/combat_motion_lab_source_readiness/source/incoming/combat_mixamo"
    payload = {
        "schema_version": 2,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "hand-authored shot-specific paired prototype",
        "presentation_only": True,
        "source_scene": str(SOURCE / "scene.blend"),
        "source_scene_sha256": digest(SOURCE / "scene.blend"),
        "source_events": str(source_events),
        "source_events_sha256": digest(source_events),
        "source_events_copied_unchanged": digest(source_events) == digest(OUTPUT / "source/events.json"),
        "body_actions": [action.name for action in body_actions],
        "root_actions": [action.name for action in root_actions],
        "root_motion_separate_from_body_actions": True,
        "controls_actions": ["HA_CONTROLS_fighter_a", "HA_CONTROLS_fighter_b", "HA_EVALUATED_CONTROLS_fighter_a", "HA_EVALUATED_CONTROLS_fighter_b"],
        "shared_timeline": [1, END],
        "fps": FPS,
        "beats": [{"frame": frame, "beat": beat} for frame, beat in BEATS],
        "contact_window": {"contact": CONTACT_FRAME, "hold": list(HOLD_FRAMES), "release": 85},
        "partner_relative_controls": controls,
        "foot_pins": pins,
        "rasengan_tangent_world": [round(value, 5) for value in tangent],
        "rig_contract": motion_lab.PRODUCTION_BONES,
        "mixamo_reference_directory": str(mixamo_dir),
        "mixamo_animation_data_used": False,
        "paired_mocap_used": False,
        "procedural_pose_generation_used": False,
        "collision_solver_used": False,
        "camera_specs": cameras,
        "builder": str(Path(__file__)),
        "builder_sha256": digest(Path(__file__)),
    }
    path = OUTPUT / "review/action-provenance.json"
    path.write_text(json.dumps(payload, indent=2, default=list))
    return payload


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for folder in ("source", "review", "renders"):
        (OUTPUT / folder).mkdir(exist_ok=True)
    shutil.copyfile(SOURCE / "source/events.json", OUTPUT / "source/events.json")
    reset_derived_state()
    omni = bpy.data.objects["fighter_a_Rig"]
    naruto = bpy.data.objects["fighter_b_Rig"]
    body = [build_body_action(omni, "OMNI", OMNI_POSES), build_body_action(naruto, "NARUTO", NARUTO_POSES)]
    roots = [build_root_action(omni, "fighter_a"), build_root_action(naruto, "fighter_b")]
    collision = load_collision_module()
    controls, pins, tangent = build_adaptation_controls(collision)
    configure_rasengan_marker()
    cameras = configure_review_scene()
    scene = bpy.context.scene
    scene["wws_hand_authored_pair"] = True
    scene["wws_source_events_sha256"] = digest(OUTPUT / "source/events.json")
    scene["wws_source_scene_sha256"] = digest(SOURCE / "scene.blend")
    scene["wws_builder_sha256"] = digest(Path(__file__))
    scene["wws_animation_strategy"] = "hand-authored shot-specific paired keyframes"
    scene["wws_production_animation_gate"] = "PENDING HUMAN REVIEW"
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))
    provenance = write_provenance(body, roots, controls, pins, tangent, cameras)
    print("HAND_AUTHORED_EXCHANGE_BUILT", json.dumps({
        "scene": str(OUTPUT / "scene.blend"),
        "event_sha256": provenance["source_events_sha256"],
        "body_actions": provenance["body_actions"],
        "root_actions": provenance["root_actions"],
    }))


if __name__ == "__main__":
    main()
