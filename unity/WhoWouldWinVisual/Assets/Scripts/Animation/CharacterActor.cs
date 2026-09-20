using UnityEngine;

namespace WhoWouldWin.Visual
{
    public sealed class CharacterActor:MonoBehaviour
    {
        public CharacterVisualProfile Profile{get;private set;}
        public PoseMachine Machine{get;}=new();
        public FighterPose Pose{get;private set;}
        public float Facing{get;private set;}=1;
        public bool Form{get;private set;}
        public Vector2 Chest=>(Vector2)transform.position+Vector2.up*1.9f;
        ProxyRig rig;
        SpriteRenderer[] bodySprites;
        SpriteRenderer shadow;
        GameObject visual;
        AnimationGraphBridge animationGraph;
        public void Initialize(FighterTrack fighter)
        {
            gameObject.AddComponent<UnityEngine.Rendering.SortingGroup>().sortingOrder=50+fighter.slot;
            Profile=Resources.Load<CharacterVisualProfile>("Profiles/"+fighter.id);
            if(Profile==null)throw new System.InvalidOperationException("Missing CharacterVisualProfile for "+fighter.id);
            var shadowObject=new GameObject("Ground shadow");shadowObject.transform.SetParent(transform,false);
            shadow=shadowObject.AddComponent<SpriteRenderer>();shadow.sprite=Resources.Load<Sprite>("Art/fx/glow");shadow.sortingOrder=-20;
            shadow.transform.localScale=new(1.1f,.1f,1);
            visual=Profile.prefab?Instantiate(Profile.prefab,transform):new GameObject("Layered Art");visual.transform.SetParent(transform,false);
            if(Profile.artMode==ArtMode.LayeredProxy)
            {rig=visual.GetComponent<ProxyRig>();if(!rig)rig=visual.AddComponent<ProxyRig>();rig.Build(Profile);}
            else
            {
                var animator=visual.GetComponentInChildren<Animator>();
                if(!animator)throw new System.InvalidOperationException("User art prefab requires Animator");
                animationGraph=new AnimationGraphBridge();animationGraph.Initialize(animator,Profile);
            }
        }
        public void Evaluate(ReplayDocument replay,StageProjection stage,int slot,double time,double animationTime,double simulation)
        {
            bodySprites??=visual.GetComponentsInChildren<SpriteRenderer>();
            var m=stage.Samples[slot];var opponent=stage.Samples[1-slot];
            Facing=opponent.x>=m.x?1:-1;Form=!string.IsNullOrEmpty(m.form);
            transform.position=stage.Feet[slot];
            var health=ReplaySampler.Resources(replay.fighters[slot],simulation).health;
            if(health<=0)
            {
                double defeat=0;foreach(var cue in replay.cues)if(cue.actor==slot&&cue.kind=="Finisher")defeat=cue.start;
                var feet=transform.position;feet.y=Mathf.Lerp(feet.y,0,Mathf.SmoothStep(0,1,(float)((time-defeat)/.9)));transform.position=feet;
            }
            shadow.transform.position=new(transform.position.x,.025f,0);shadow.color=new(0,0,0,.65f/(1+Mathf.Max(0,transform.position.y)*.25f));
            Pose=Machine.Evaluate(m,replay,Profile,slot,animationTime,simulation,health);
            if(rig)rig.Apply(Pose,Facing,simulation,Form,1,Machine.State is "HitLight" or "HitHeavy" or "Knockdown");
            else{visual.transform.localScale=new(Facing*Profile.scale,Profile.scale,1);animationGraph?.Evaluate(Machine,simulation);}
        }
        public Bounds VisualBounds()
        {
            var renderers=bodySprites??visual.GetComponentsInChildren<SpriteRenderer>();
            var bounds=new Bounds(transform.position+Vector3.up*1.6f,new Vector3(1,3.2f,0));
            foreach(var renderer in renderers)if(renderer.enabled)bounds.Encapsulate(renderer.bounds);
            return bounds;
        }
        void OnDestroy()=>animationGraph?.Dispose();
    }
}
