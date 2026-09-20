using System.Collections.Generic;
using UnityEngine;

namespace WhoWouldWin.Visual
{
    public sealed class EffectPool
    {
        readonly Transform parent;
        readonly List<SpriteRenderer> sprites=new();
        readonly List<LineRenderer> lines=new();
        readonly Dictionary<string,Sprite> art=new();
        readonly Material material;
        int usedSprites,usedLines;
        public EffectPool(Transform parent)
        {this.parent=parent;material=new Material(Resources.Load<Material>("CinematicAdditive"));}
        public void Begin(){usedSprites=usedLines=0;}
        public void Sprite(string name,Vector2 position,Vector2 size,Color color,float angle=0,int order=120)
        {
            if(usedSprites>=sprites.Count){var go=new GameObject("Pooled effect");go.transform.SetParent(parent);sprites.Add(go.AddComponent<SpriteRenderer>());}
            var sr=sprites[usedSprites++];sr.gameObject.SetActive(true);
            if(!art.ContainsKey(name))art[name]=Resources.Load<Sprite>("Art/fx/"+name);
            sr.sprite=art[name];sr.sharedMaterial=material;sr.color=color;sr.sortingOrder=order;
            sr.transform.position=position;sr.transform.rotation=Quaternion.Euler(0,0,angle);
            if(sr.sprite)sr.transform.localScale=new(size.x/sr.sprite.bounds.size.x,size.y/sr.sprite.bounds.size.y,1);
        }
        public void Line(Vector2 start,Vector2 end,Color color,float width)
        {
            if(usedLines>=lines.Count)
            {var go=new GameObject("Pooled streak");go.transform.SetParent(parent);var line=go.AddComponent<LineRenderer>();line.positionCount=2;line.numCapVertices=2;line.sharedMaterial=material;line.sortingOrder=118;lines.Add(line);}
            var l=lines[usedLines++];l.gameObject.SetActive(true);l.SetPosition(0,start);l.SetPosition(1,end);
            l.startWidth=width;l.endWidth=width*.08f;l.startColor=color;l.endColor=new(color.r,color.g,color.b,0);
        }
        public void End()
        {for(int i=usedSprites;i<sprites.Count;i++)sprites[i].gameObject.SetActive(false);for(int i=usedLines;i<lines.Count;i++)lines[i].gameObject.SetActive(false);}
        public void Dispose(){if(material)Object.Destroy(material);}
    }
}
