using UnityEngine;

namespace WhoWouldWin.Visual
{
    /// <summary>Presentation-space blocking, separate from authoritative coordinates.
    /// Portrait uses compressed distance and a taller stage, not a cropped landscape view.</summary>
    public sealed class StageProjection
    {
        public bool Portrait=true;
        public MovementKey[] Samples=new MovementKey[2];
        public Vector2[] Feet=new Vector2[2];
        public float Center;
        public void Evaluate(ReplayDocument replay,double time)
        {
            for(int i=0;i<2;i++) Samples[i]=ReplaySampler.Motion(replay.fighters[i],time);
            Center=(Samples[0].x+Samples[1].x)*.5f;
            for(int i=0;i<2;i++)
            {
                // A bounded symmetric smoothing filter softens instantaneous
                // charge displacements while explicit teleport retains its cut.
                Vector2 p=Vector2.zero;float total=0;
                for(int k=-2;k<=2;k++)
                {
                    var m=ReplaySampler.Motion(replay.fighters[i],time+k*.035);
                    float weight=3-Mathf.Abs(k);
                    if(Samples[i].teleport){m=Samples[i];}
                    p+=Project(m.x,m.y)*weight;total+=weight;
                }
                Feet[i]=p/total;
            }
        }
        public Vector2 Project(float x,float y)
        {
            float relative=x-Center;
            float horizontal=Portrait ? .6f*(float)System.Math.Tanh(relative/1.3f)+2.4f*(float)System.Math.Tanh(relative/9f) : relative*.32f;
            return new Vector2(Center*.14f+horizontal,(y-1)*.62f);
        }
        public Vector2 ProjectilePoint(ProjectileTrack track,double presentation)
        {
            float phase=Mathf.Clamp01((float)((presentation-track.start)/System.Math.Max(.001,track.end-track.start)));
            if(track.points.Length==1)return Project(track.points[0].x,track.points[0].y)+Vector2.up*1.95f;
            double time=track.simulationStart+phase*(track.simulationEnd-track.simulationStart);
            int i=ReplaySampler.Find(track.points.Length,n=>track.points[n].time,time);
            var a=track.points[i];var b=track.points[Mathf.Min(i+1,track.points.Length-1)];
            float t=track.simulationEnd-track.simulationStart<.001?phase:Mathf.Clamp01((float)((time-a.time)/System.Math.Max(.001,b.time-a.time)));
            if(track.simulationEnd-track.simulationStart<.001){a=track.points[0];b=track.points[track.points.Length-1];}
            return Project(Mathf.Lerp(a.x,b.x,t),Mathf.Lerp(a.y,b.y,t))+Vector2.up*1.95f;
        }
    }
}
