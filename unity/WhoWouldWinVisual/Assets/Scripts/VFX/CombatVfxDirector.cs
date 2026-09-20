using UnityEngine;

namespace WhoWouldWin.Visual
{
    public sealed class CombatVfxDirector:MonoBehaviour
    {
        EffectPool pool;
        ImpactParticles particles;
        GhostPool ghosts;
        public float Flash{get;private set;}
        public void Initialize(CharacterActor[] actors){pool=new EffectPool(transform);particles=new ImpactParticles(transform);ghosts=new GhostPool(transform,actors);}
        static Color Alpha(Color c,float alpha){c.a=alpha;return c;}
        public void Evaluate(ReplayDocument replay,StageProjection stage,CharacterActor[] actors,double time,double simulation)
        {
            pool.Begin();particles.Begin();ghosts.Begin();Flash=0;
            for(int i=0;i<2;i++)
            {
                var actor=actors[i];Color color=actor.Profile.accent;
                if(actor.Form)
                {
                    float breathe=1+Mathf.Sin((float)simulation*11)*.06f;
                    pool.Sprite("glow",actor.Chest,new(3.5f*breathe,4.5f*breathe),Alpha(color,.26f),0,21);
                    pool.Sprite("ring",actor.transform.position+Vector3.up*.1f,new(2.1f,.25f),Alpha(color,.5f),0,22);
                    for(int k=0;k<8;k++)
                    {float phase=(float)(simulation*.8+k*.13)%1;pool.Line((Vector2)actor.transform.position+new Vector2(Mathf.Sin(k*11)*.85f,phase*3.7f),(Vector2)actor.transform.position+new Vector2(Mathf.Sin(k*11)*.85f,phase*3.7f+.25f),Alpha(color,(1-phase)*.5f),.035f);}
                }
                if(Mathf.Abs(stage.Samples[i].vx)>12)
                {
                    pool.Sprite("dust",actor.transform.position,new(1.3f,.45f),new(.76f,.63f,.61f,.22f),0,25);
                    for(int k=0;k<4;k++)pool.Line(actor.Chest+new Vector2(-actor.Facing*.8f,k*.18f-.25f),actor.Chest+new Vector2(-actor.Facing*2.3f,k*.18f-.25f),Alpha(color,.22f),.035f);
                }
            }
            foreach(var track in replay.projectiles)
            {
                if(time<track.start || time>track.end+.18)continue;
                var color=actors[track.actor].Profile.accent;
                var p=stage.ProjectilePoint(track,System.Math.Min(time,track.end));
                float radius=actors[track.actor].Profile.Ability(track.ability)?.vfx=="vortex"?.7f:.28f;
                if(time<=track.end)
                {
                    pool.Sprite("glow",p,Vector2.one*radius*4,Alpha(color,.55f));
                    pool.Sprite("ring",p,Vector2.one*radius*2,Alpha(color,.85f),(float)time*240);
                    pool.Sprite("glow",p,Vector2.one*radius,Color.white);
                    var previous=stage.ProjectilePoint(track,System.Math.Max(track.start,time-.08));pool.Line(p,previous,Alpha(color,.8f),radius*.7f);
                }
                else if(track.outcome is "miss" or "dodge")
                {float age=(float)(time-track.end);var direction=(p-actors[track.actor].Chest).normalized;pool.Line(p+direction*age*12,p,Alpha(color,(1-age/.18f)*.7f),radius*.6f);}
            }
            foreach(var c in replay.cues)
            {
                if(!c.Active(time))continue;
                var a=actors[c.actor];var target=actors[c.target];var color=a.Profile.accent;
                float age=(float)(time-c.start),phase=c.Phase(time),fade=1-phase;
                switch(c.kind)
                {
                    case "AnticipateAttack":case "Charge":
                        var binding=a.Profile.Ability(c.ability);
                        if(binding!=null && binding.vfx is "energy" or "vortex" or "aura")
                        {var hand=a.Chest+Vector2.right*a.Facing*.6f;pool.Sprite("glow",hand,Vector2.one*(.5f+phase*1.6f),Alpha(color,.5f));pool.Sprite("ring",hand,Vector2.one*(1.1f-phase*.6f),Alpha(color,.7f),(float)time*160);}
                        break;
                    case "DashPast":case "Teleport":
                        ghosts.Draw(c.actor,a,stage,replay,simulation,.33f,false);
                        pool.Sprite("ring",a.Chest-Vector2.right*a.Facing*.7f,new(.25f+phase*.5f,2+phase*2),Alpha(color,.7f*fade));
                        for(int k=0;k<7;k++)pool.Line(a.Chest+new Vector2(-a.Facing*.4f,k*.2f-.6f),a.Chest+new Vector2(-a.Facing*(1.2f+phase*2),k*.2f-.6f),Alpha(color,.5f*fade),.045f);
                        break;
                    case "CloneFeint":ghosts.Draw(c.actor,a,stage,replay,simulation,.45f*fade,true);pool.Sprite("dust",a.transform.position,new(3.5f,1),new(.7f,.9f,1,.25f*fade));break;
                    case "SuccessfulDodge":
                        ghosts.Draw(c.actor,a,stage,replay,simulation,.22f,false);pool.Sprite("slash",a.Chest,new(1.8f,.45f),Alpha(color,.35f*fade),a.Facing*25);break;
                    case "Lunge":pool.Sprite("slash",Vector2.Lerp(a.Chest,target.Chest,.65f),new(1.7f,.8f),new(1,.83f,.6f,.4f*fade),c.variant==2?-45:25);break;
                    case "BlockImpact":case "Guard":
                        pool.Sprite("ring",a.Chest+Vector2.right*a.Facing*.4f,new(.35f,1.5f),Alpha(color,.5f*fade));
                        if(c.kind=="BlockImpact"){pool.Sprite("spark",a.Chest+Vector2.right*a.Facing*.55f,Vector2.one*.8f,new(1,.9f,.55f,fade),45);particles.Draw(a.Chest,age,.2f,color,c.sourceIndex);}
                        break;
                    case "MeleeHit":case "HeavyHit":case "Finisher":case "Clash":
                        Vector2 point=c.kind=="Clash"?(a.Chest+target.Chest)*.5f:a.Chest;
                        float size=.65f+c.intensity*1.3f;
                        pool.Sprite("spark",point,Vector2.one*size*(1+phase),new(1,.89f,.61f,fade*fade),c.sourceIndex*37);
                        pool.Sprite("ring",point,Vector2.one*(.2f+age*7*c.intensity),Alpha(color,fade*.65f));
                        if(c.intensity>.6f)
                        {
                            pool.Sprite("glow",point,Vector2.one*3,new(1,.65f,.35f,fade*.3f));
                            for(int k=0;k<12;k++)
                            {var dir=new Vector2(Mathf.Cos(k*2.399f),Mathf.Sin(k*2.399f));pool.Line(point+dir*(.5f+age*4),point+dir*(1.3f+age*8),new(1,.87f,.66f,fade*.65f),.055f);}
                        }
                        particles.Draw(point,age,c.intensity,new(1,.78f,.48f),c.sourceIndex);
                        Flash=Mathf.Max(Flash,Mathf.Max(0,1-age/.075f)*c.intensity*.2f);
                        break;
                    case "GroundImpact":
                        var ground=(Vector2)a.transform.position;
                        pool.Sprite("dust",ground,new(1+phase*3,.35f+phase*.8f),new(.8f,.64f,.55f,.5f*fade),0,28);
                        pool.Sprite("ring",ground,new(.5f+phase*3,.15f+phase*.3f),new(.85f,.7f,.55f,.4f*fade));break;
                    case "Transformation":
                        pool.Sprite("glow",a.Chest,new(3,5),Alpha(color,.55f*fade));pool.Sprite("ring",a.Chest,Vector2.one*(1+phase*7),Alpha(color,.7f*fade));particles.Draw(a.Chest,age,1,color,c.sourceIndex);break;
                    case "BeamCast":
                        pool.Line(target.Chest,a.Chest,new(1,.32f,.27f,.9f*fade),.3f);
                        pool.Line(target.Chest,a.Chest,new(1,1,.8f,fade),.09f);break;
                }
            }
            pool.End();particles.End();
        }
        void OnDestroy(){pool?.Dispose();particles?.Dispose();ghosts?.Dispose();}
    }
}
