using UnityEngine;

namespace WhoWouldWin.Visual
{
    public sealed class FightCameraDirector:MonoBehaviour
    {
        public Camera Output;
        public void Evaluate(ReplayDocument replay,StageProjection stage,CharacterActor[] actors,double time)
        {
            Vector2 a=actors[0].Chest,b=actors[1].Chest;
            Vector2 target=(a+b)*.5f+Vector2.up*.9f;
            float aspect=stage.Portrait?9f/16:16f/9;
            float surface=Output.targetTexture?(float)Output.targetTexture.width/Output.targetTexture.height:(float)Screen.width/Mathf.Max(1,Screen.height);
            if(surface>aspect){float width=aspect/surface;Output.rect=new Rect((1-width)/2,0,width,1);}
            else {float height=surface/aspect;Output.rect=new Rect(0,(1-height)/2,1,height);}
            Output.aspect=aspect;
            float size=Mathf.Max(stage.Portrait?5.8f:3.7f,Mathf.Abs(a.x-b.x)*.5f/aspect+1.5f/aspect);
            size=Mathf.Max(size,Mathf.Abs(a.y-b.y)*.5f+2.8f);
            Vector2 shake=Vector2.zero;float emphasis=0;
            foreach(var c in replay.cues)
            {
                if(c.kind=="AnticipateAttack" && c.Active(time)) emphasis=Mathf.Max(emphasis,.16f*c.Phase(time));
                if(c.kind is not ("MeleeHit" or "HeavyHit" or "Finisher" or "Clash" or "GroundImpact"))continue;
                float age=(float)(time-c.start);
                if(age<-.25f || age>1.2f)continue;
                if(age>=0)
                {
                    float decay=Mathf.Exp(-age*10)*c.intensity;
                    shake+=new Vector2(Mathf.Sin(age*73+c.sourceIndex),Mathf.Sin(age*91+c.sourceIndex*.7f))*.16f*decay;
                }
                emphasis=Mathf.Max(emphasis,c.intensity*.28f*Mathf.Exp(-age*age*9));
                if(c.kind=="Finisher")target=Vector2.Lerp(target,actors[c.actor].Chest+Vector2.up*.7f,.15f*Mathf.Exp(-Mathf.Max(0,age)*2));
            }
            // Distance always wins over dramatic zoom: both bodies stay in frame.
            float safe=Mathf.Abs(a.x-b.x)*.5f/aspect+1.25f/aspect;
            size=Mathf.Max(safe,size-emphasis);
            // Include the posed sprite bounds (extended fists, recoil and cape),
            // not just the authoritative collision centers.
            foreach(var actor in actors)
            {
                var bounds=actor.VisualBounds();
                size=Mathf.Max(size,(Mathf.Max(Mathf.Abs(bounds.min.x-target.x-shake.x),Mathf.Abs(bounds.max.x-target.x-shake.x))+.3f)/aspect);
                size=Mathf.Max(size,Mathf.Max(Mathf.Abs(bounds.min.y-target.y-shake.y),Mathf.Abs(bounds.max.y-target.y-shake.y))+1.2f);
            }
            Output.orthographic=true;Output.orthographicSize=size;
            Output.transform.position=new Vector3(target.x+shake.x,target.y+shake.y,-10);
        }
    }
}
