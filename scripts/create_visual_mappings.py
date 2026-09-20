"""Create starter presentation documents without modifying combat profiles."""
import json
from pathlib import Path
from whowouldwin.characters.loader import load_character
from whowouldwin.cinematic.profiles import STATES

TYPES = {
    "melee": ("LightAttack", "Lunge", "melee", "punch"),
    "charged_melee": ("HeavyAttack", "Lunge", "heavy", "heavy"),
    "projectile": ("RangedAttack", "ProjectileCast", "energy", "projectile"),
    "beam": ("RangedAttack", "BeamCast", "beam", "projectile"),
    "area": ("SpecialAttack", "HeavyHit", "shockwave", "explosion"),
    "dodge": ("Dodge", "SuccessfulDodge", "afterimage", "dash"),
    "block": ("Block", "Guard", "block", "block"),
    "dash": ("Dash", "DashPast", "speed", "dash"),
    "jump": ("Jump", "JumpAttack", "dust", "dash"),
    "flight": ("FlightMove", "Flight", "speed", "dash"),
    "grapple": ("HeavyAttack", "Lunge", "heavy", "heavy"),
    "teleport": ("Dash", "Teleport", "smoke", "dash"),
    "buff": ("SpecialAttack", "Buff", "aura", "charge"),
    "transform": ("Transformation", "Transformation", "aura", "transform"),
    "regenerate": ("Recovery", "Recovery", "aura", "charge"),
}


def main():
    directory = Path("data/presentation")
    directory.mkdir(exist_ok=True)
    for name in ("naruto", "omniman", "aang", "homelander"):
        p = load_character(name)
        bindings = []
        for a in p.abilities:
            state, primitive, vfx, sound = TYPES[a.type]
            if a.id == "charge": state, primitive, vfx, sound = "Dash", "DashPast", "sonic", "dash"
            if a.id == "decoy": state, primitive, vfx, sound = "SpecialAttack", "CloneFeint", "smoke", "charge"
            if a.id == "charged_vortex": state, primitive, vfx, sound = "SpecialAttack", "ProjectileCast", "vortex", "charge"
            bindings.append(dict(abilityId=a.id, state=state, primitive=primitive, vfx=vfx, sound=sound, anticipation=a.startup, weight=min(1,a.damage/180)))
        titan = name in ("omniman", "homelander")
        profile = dict(characterId=name, proxyStyle="titan" if titan else "ninja", artPrefix="Art/titan" if titan else "Art/ninja",
                       accent="#F05D54" if titan else "#46E8EE", secondary="#FFC56E" if titan else "#FFAE54",
                       scale=1.12 if titan else 1, requiredStates=list(STATES), abilities=bindings)
        (directory/f"{name}.json").write_text(json.dumps(profile,indent=2)+"\n")


if __name__ == "__main__": main()
