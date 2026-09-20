using System.Linq;
using UnityEngine;

namespace WhoWouldWin.Visual
{
    public sealed class ArenaPresentation:MonoBehaviour
    {
        Transform sky,far,near,ground;
        bool refined;
        public void Build()
        {
            var atlas=Resources.LoadAll<Sprite>("Art/Refined/skyline-atlas");
            refined=atlas.Any(s=>s.name=="city");
            if(refined)
            {
                sky=Layer(atlas.First(s=>s.name=="city"),new(12,8.91f,0),new(38,17.82f),-80);
                ground=Layer(atlas.First(s=>s.name=="ground"),new(12,-5.47f,0),new(60,10.94f),-10);
            }
            else
            {
                sky=Layer(Resources.Load<Sprite>("Art/arena/sky"),new(12,12,0),new(46,35),-100);
                far=Layer(Resources.Load<Sprite>("Art/arena/far"),new(12,4,0),new(62,10),-80);
                near=Layer(Resources.Load<Sprite>("Art/arena/near"),new(12,2,0),new(44,8),-60);
                ground=Layer(Resources.Load<Sprite>("Art/arena/ground"),new(12,-2.6f,0),new(90,5.2f),-10);
            }
        }
        Transform Layer(Sprite art,Vector3 position,Vector2 size,int order)
        {
            var go=new GameObject(art.name);go.transform.SetParent(transform);go.transform.position=position;
            var sr=go.AddComponent<SpriteRenderer>();sr.sprite=art;sr.sortingOrder=order;
            if(refined)sr.color=order<-20?new(.68f,.75f,.82f,1):new(.82f,.86f,.9f,1);
            go.transform.localScale=new(size.x/art.bounds.size.x,size.y/art.bounds.size.y,1);
            return go.transform;
        }
        public void Evaluate(Camera camera)
        {
            if(!sky)return;
            if(refined){sky.position=new(camera.transform.position.x*.82f,8.91f,0);ground.position=new(camera.transform.position.x*.28f,-5.47f,0);return;}
            sky.position=new(camera.transform.position.x*.95f-9,camera.transform.position.y*.9f-5,0);
            far.position=new(camera.transform.position.x*.78f,4,0);near.position=new(camera.transform.position.x*.55f,2,0);
        }
    }
}
