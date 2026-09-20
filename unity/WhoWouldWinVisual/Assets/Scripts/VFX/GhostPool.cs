using UnityEngine;
using UnityEngine.Rendering;

namespace WhoWouldWin.Visual
{
    /// <summary>Duplicates use the selected character art, including imported sheets/rigs.</summary>
    public sealed class GhostPool
    {
        sealed class Ghost
        {
            public Transform root;
            public ProxyRig rig;
            public AnimationGraphBridge graph;
            public SpriteRenderer[] sprites;
        }
        readonly Ghost[,] ghosts=new Ghost[2,3];
        public GhostPool(Transform parent,CharacterActor[] actors)
        {
            for(int i=0;i<2;i++)for(int j=0;j<3;j++)
            {
                var profile=actors[i].Profile;
                var go=profile.prefab?Object.Instantiate(profile.prefab,parent):new GameObject("Presentational duplicate");
                go.transform.SetParent(parent,false);go.name="Presentational duplicate";
                var group=go.GetComponent<SortingGroup>();if(!group)group=go.AddComponent<SortingGroup>();group.sortingOrder=40+i;
                var ghost=new Ghost{root=go.transform};
                if(profile.artMode==ArtMode.LayeredProxy){ghost.rig=go.GetComponent<ProxyRig>();if(!ghost.rig)ghost.rig=go.AddComponent<ProxyRig>();ghost.rig.Build(profile);}
                else {ghost.graph=new AnimationGraphBridge();ghost.graph.Initialize(go.GetComponentInChildren<Animator>(),profile);}
                ghost.sprites=go.GetComponentsInChildren<SpriteRenderer>();ghosts[i,j]=ghost;go.SetActive(false);
            }
        }
        public void Begin(){foreach(var ghost in ghosts)ghost.root.gameObject.SetActive(false);}
        public void Draw(int actor,CharacterActor source,StageProjection stage,ReplayDocument replay,double simulation,float opacity,bool clones)
        {
            for(int i=0;i<3;i++)
            {
                var ghost=ghosts[actor,i];ghost.root.gameObject.SetActive(true);
                var m=ReplaySampler.Motion(replay.fighters[actor],simulation-(i+1)*.07);
                ghost.root.position=clones?(Vector2)source.transform.position+new Vector2((i-1)*1.35f,i==1?.5f:0):stage.Project(m.x,m.y)-Vector2.right*source.Facing*(i+1)*.23f;
                if(ghost.rig)ghost.rig.Apply(source.Pose,source.Facing,simulation,source.Form,opacity/(i+1),source.Machine.State is "HitLight" or "HitHeavy");
                else
                {
                    ghost.root.localScale=new(source.Facing*source.Profile.scale,source.Profile.scale,1);
                    ghost.graph.Evaluate(source.Machine,simulation);
                    foreach(var sprite in ghost.sprites)sprite.color=new(1,1,1,opacity/(i+1));
                }
            }
        }
        public void Dispose(){foreach(var ghost in ghosts)ghost.graph?.Dispose();}
    }
}
