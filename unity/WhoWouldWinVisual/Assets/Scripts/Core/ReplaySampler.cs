using System;
using UnityEngine;

namespace WhoWouldWin.Visual
{
    public static class ReplaySampler
    {
        public static double SimulationTime(ReplayDocument replay, double presentation)
        {
            foreach (var s in replay.timeMap)
                if (presentation < s.end)
                    return s.simulationStart + Math.Clamp((presentation-s.start)/Math.Max(1e-9,s.end-s.start),0,1)*(s.simulationEnd-s.simulationStart);
            return replay.metadata.simulationDuration;
        }
        public static ResourceKey Resources(FighterTrack fighter, double time)
        {
            int index = Find(fighter.health.Length, i=>fighter.health[i].time, time);
            // Step sampling: health is copied, never interpolated across a hit.
            return fighter.health[index];
        }
        public static MovementKey Motion(FighterTrack fighter, double time)
        {
            int i=Find(fighter.movement.Length,n=>fighter.movement[n].time,time);
            var a=fighter.movement[i];
            if(i>=fighter.movement.Length-1) return a;
            var b=fighter.movement[i+1];
            if(b.teleport && time<b.time) return a;
            float t=Mathf.Clamp01((float)((time-a.time)/Math.Max(1e-9,b.time-a.time)));
            // Cubic Hermite with bounded tangents prevents overshoot near walls.
            float span=(float)(b.time-a.time);
            Vector2 pa=new(a.x,a.y), pb=new(b.x,b.y);
            Vector2 delta=pb-pa;
            Vector2 va=Vector2.ClampMagnitude(new(a.vx,a.vy),delta.magnitude/Mathf.Max(.001f,span)*2);
            Vector2 vb=Vector2.ClampMagnitude(new(b.vx,b.vy),delta.magnitude/Mathf.Max(.001f,span)*2);
            var p=(2*t*t*t-3*t*t+1)*pa+(t*t*t-2*t*t+t)*span*va+(-2*t*t*t+3*t*t)*pb+(t*t*t-t*t)*span*vb;
            p.x=Mathf.Clamp(p.x,Mathf.Min(a.x,b.x)-.05f,Mathf.Max(a.x,b.x)+.05f);
            p.y=Mathf.Clamp(p.y,Mathf.Min(a.y,b.y)-.05f,Mathf.Max(a.y,b.y)+.05f);
            return new MovementKey{time=time,x=p.x,y=p.y,vx=Mathf.Lerp(a.vx,b.vx,t),vy=Mathf.Lerp(a.vy,b.vy,t),flying=a.flying,stunned=a.stunned,form=a.form,teleport=a.teleport};
        }
        public static int Find(int length, Func<int,double> time, double value)
        {
            int lo=0,hi=length-1;
            while(lo<hi){int mid=(lo+hi+1)/2;if(time(mid)<=value+1e-9)lo=mid;else hi=mid-1;}
            return lo;
        }
    }
}
