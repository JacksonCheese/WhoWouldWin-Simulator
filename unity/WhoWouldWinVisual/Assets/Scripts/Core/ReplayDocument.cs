using System;
using System.IO;
using UnityEngine;

namespace WhoWouldWin.Visual
{
    [Serializable] public class ReplayDocument
    {
        public int formatVersion;
        public string directorVersion, checksum;
        public ReplayMetadata metadata;
        public ArenaData arena;
        public FighterTrack[] fighters;
        public TimeSegment[] timeMap;
        public AuthorityEvent[] authoritativeTimeline;
        public DamageEvent[] damageTimeline;
        public ChoreographyCue[] cues;
        public CinematicMoment[] moments;
        public ProjectileTrack[] projectiles;
        public FinalOutcome finalOutcome;

        public static ReplayDocument Load(string path)
        {
            var document = JsonUtility.FromJson<ReplayDocument>(File.ReadAllText(path));
            document.Validate();
            return document;
        }
        public void Validate()
        {
            if (formatVersion != 1 || metadata == null || fighters == null || fighters.Length != 2)
                throw new InvalidDataException("Expected cinematic replay v1 with two fighters.");
            if (timeMap == null || timeMap.Length == 0 || finalOutcome == null)
                throw new InvalidDataException("Replay is missing its time map or final outcome.");
            double last = -1;
            foreach (var e in authoritativeTimeline)
            {
                if (e.simulationTime < last || e.simulationTime > metadata.simulationDuration)
                    throw new InvalidDataException("Authoritative event ordering is invalid.");
                last = e.simulationTime;
            }
            foreach (var f in fighters)
            {
                if (f.movement.Length < 2 || f.health.Length < 2 || f.visual.abilities.Length == 0)
                    throw new InvalidDataException("Missing fighter motion, resources or ability bindings.");
                if (f.health[f.health.Length-1].health != finalOutcome.health[f.slot])
                    throw new InvalidDataException("Health timeline disagrees with final outcome.");
            }
            if (Math.Abs(timeMap[timeMap.Length-1].end - metadata.presentationDuration) > 1e-7)
                throw new InvalidDataException("Presentation duration does not match time map.");
        }
    }
    [Serializable] public class ReplayMetadata { public string title, seed, engineVersion, sourceChecksum, scalingNote, outcomeDigest, damageDigest; public double simulationDuration, presentationDuration, timestep; }
    [Serializable] public class ArenaData { public float width, height, gravity; }
    [Serializable] public class FighterTrack { public int slot; public string id, name; public double maxHealth, maxEnergy, maxStamina; public VisualSpec visual; public MovementKey[] movement; public ResourceKey[] health; }
    [Serializable] public class VisualSpec { public string characterId, proxyStyle, artPrefix, accent, secondary; public float scale; public string[] requiredStates; public AbilityBinding[] abilities; }
    [Serializable] public class AbilityBinding { public string abilityId, state, primitive, vfx, sound; public float anticipation, weight; }
    [Serializable] public class MovementKey { public double time; public float x, y, vx, vy; public bool flying, stunned, teleport; public string form; }
    [Serializable] public class ResourceKey { public double time, health, energy, stamina; }
    [Serializable] public class TimeSegment { public double start, end, simulationStart, simulationEnd; public string kind; }
    [Serializable] public class AuthorityEvent { public int sourceIndex, tick, actor, target; public double simulationTime, presentationTime, damage, healthAfter; public float x, y; public string type, ability, valuesJson; }
    [Serializable] public class DamageEvent { public int sourceIndex, tick, actor, target; public double simulationTime, presentationTime, damage, healthAfter; public string ability; }
    [Serializable] public class ChoreographyCue { public string kind, ability, vfx, sound; public int actor, target, sourceIndex, variant; public double start, end, simulationTime; public float intensity; public bool presentationalOnly; public float Phase(double t) => Mathf.Clamp01((float)((t-start)/Math.Max(.001,end-start))); public bool Active(double t) => t>=start && t<end; }
    [Serializable] public class CinematicMoment { public double time, simulationTime; public string kind; public float importance; public int actor; }
    [Serializable] public class ProjectileTrack { public int id, actor, target; public string ability, outcome; public double start, end, simulationStart, simulationEnd; public ProjectileKey[] points; }
    [Serializable] public class ProjectileKey { public double time; public float x, y; }
    [Serializable] public class FinalOutcome { public int winner; public string condition, finisher; public double simulationDuration; public double[] health; }
}
