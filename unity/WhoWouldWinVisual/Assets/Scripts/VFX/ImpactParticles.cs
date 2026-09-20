using System.Collections.Generic;
using UnityEngine;

namespace WhoWouldWin.Visual
{
    /// <summary>Small particle pool re-simulated from source-event seeds on seek.</summary>
    public sealed class ImpactParticles
    {
        readonly List<ParticleSystem> pool=new();
        readonly Transform parent;
        readonly Material material;
        int used;
        public ImpactParticles(Transform parent){this.parent=parent;material=new Material(Resources.Load<Material>("CinematicAdditive"));material.mainTexture=Resources.Load<Sprite>("Art/fx/glow").texture;}
        public void Begin(){used=0;}
        public void Draw(Vector2 position,float age,float intensity,Color color,int seed)
        {
            if(age<0||age>.6f)return;
            if(used>=pool.Count)
            {
                var go=new GameObject("Pooled impact particles");go.transform.SetParent(parent);var ps=go.AddComponent<ParticleSystem>();ps.Stop();
                var main=ps.main;main.loop=false;main.duration=.7f;main.startLifetime=.55f;main.startSpeed=5;main.startSize=.11f;main.maxParticles=40;main.gravityModifier=.25f;main.simulationSpace=ParticleSystemSimulationSpace.World;
                var emission=ps.emission;emission.rateOverTime=0;emission.SetBursts(new[]{new ParticleSystem.Burst(0,22)});
                var shape=ps.shape;shape.shapeType=ParticleSystemShapeType.Circle;shape.radius=.1f;
                var size=ps.sizeOverLifetime;size.enabled=true;size.size=new ParticleSystem.MinMaxCurve(1,AnimationCurve.Linear(0,1,1,0));
                var renderer=go.GetComponent<ParticleSystemRenderer>();renderer.sharedMaterial=material;renderer.sortingOrder=130;
                pool.Add(ps);
            }
            var effect=pool[used++];effect.gameObject.SetActive(true);effect.transform.position=position;
            var settings=effect.main;settings.startColor=color;settings.startSpeed=3+intensity*7;
            effect.Stop(true,ParticleSystemStopBehavior.StopEmittingAndClear);
            effect.useAutoRandomSeed=false;effect.randomSeed=(uint)Mathf.Abs(seed+137);
            effect.Simulate(age,true,true,true);effect.Pause();
        }
        public void End(){for(int i=used;i<pool.Count;i++)pool[i].gameObject.SetActive(false);}
        public void Dispose(){if(material)Object.Destroy(material);}
    }
}
