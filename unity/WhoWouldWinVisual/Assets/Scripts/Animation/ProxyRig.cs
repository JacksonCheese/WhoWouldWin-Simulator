using System;
using UnityEngine;

namespace WhoWouldWin.Visual
{
    [Serializable] public class Limb {public Transform root,bend,end;}
    public class ProxyRig:MonoBehaviour
    {
        [SerializeField] Transform body,head,cape;
        [SerializeField] Limb arm,backArm,leg,backLeg;
        SpriteRenderer[] sprites;
        SpriteRenderer face;
        CharacterVisualProfile profile;
        public void Build(CharacterVisualProfile definition)
        {
            profile=definition;
            if(body!=null){sprites=GetComponentsInChildren<SpriteRenderer>();face=head.GetComponentInChildren<SpriteRenderer>();return;}
            body=Node("Body",transform,new(0,1.45f,0));
            if(definition.artPrefix.Contains("titan"))
                {
                cape=Node("Cape anchor",body,new(-.25f,1.02f,0));
                Part("cape",cape,new(definition.layers!=null&&definition.layers.Length>0?-.8f:-.2f,-1.16f,0),new(1.48f,2.4f),-4);
            }
            Part("hips",body,new(0,-.04f,0),new(.66f,.52f),4);
            Part("torso",body,new(0,.58f,0),new(definition.artPrefix.Contains("titan")?1.13f:.98f,1.36f),8);
            Part("neck",body,new(0,1.23f,0),new(.31f,.35f),7);
            head=Node("Head",body,new(0,1.47f,0));face=Part("head",head,new(0,.07f,0),new(.83f,.91f),12);
            backLeg=Chain("BackLeg",body,new(-.2f,-.1f,0),"thigh","shin","foot",.67f,.63f,0);
            leg=Chain("Leg",body,new(.2f,-.1f,0),"thigh","shin","foot",.67f,.63f,5);
            backArm=Chain("BackArm",body,new(-.4f,1.03f,0),"upperarm","forearm","hand",.55f,.53f,1);
            arm=Chain("Arm",body,new(.4f,1.03f,0),"upperarm","forearm","hand",.55f,.53f,15);
            sprites=GetComponentsInChildren<SpriteRenderer>();
        }
        Limb Chain(string name,Transform parent,Vector3 origin,string a,string b,string c,float l1,float l2,int order)
        {
            var root=Node(name,parent,origin);
            Part(a,root,new(0,-l1*.43f,0),new(a=="thigh"?.46f:(profile.artPrefix.Contains("titan")?.42f:.34f),l1*1.15f),order);
            var bend=Node("Bend",root,new(0,-l1,0));
            Part(b,bend,new(0,-l2*.42f,0),new(b=="shin"?.34f:.28f,l2*1.15f),order+1);
            var tip=Node("End",bend,new(0,-l2,0));
            Part(c,tip,new(c=="foot"?.11f:0,0,0),c=="foot"?new(.53f,.25f):new(.3f,.33f),order+2);
            return new Limb{root=root,bend=bend,end=tip};
        }
        public static Transform Node(string name,Transform parent,Vector3 position)
        {var t=new GameObject(name).transform;t.SetParent(parent,false);t.localPosition=position;return t;}
        SpriteRenderer Part(string name,Transform parent,Vector3 position,Vector2 size,int order)
        {
            var t=Node(name,parent,position);var sr=t.gameObject.AddComponent<SpriteRenderer>();sr.sprite=profile.Part(name);sr.sortingOrder=30+order;
            var binding=Array.Find(profile.layers??Array.Empty<LayerBinding>(),b=>b.part==name);if(binding!=null){t.localRotation=Quaternion.Euler(0,0,binding.rotation);sr.flipX=binding.flipX;}
            if(sr.sprite!=null)t.localScale=new(size.x/sr.sprite.bounds.size.x,size.y/sr.sprite.bounds.size.y,1);
            return sr;
        }
        static void Rotate(Transform t,float value){if(t)t.localRotation=Quaternion.Euler(0,0,value);}
        public void Apply(FighterPose p,float facing,double simulation,bool form,float opacity=1,bool hurt=false)
        {
            if(body==null)return;
            var expression=profile.Part(hurt?"head_hurt":"head");
            if(face && expression){face.sprite=expression;face.transform.localScale=new(.83f/expression.bounds.size.x,.91f/expression.bounds.size.y,1);}
            body.localPosition=new(p.offset.x,1.45f+p.drop+p.offset.y,0);Rotate(body,p.body);Rotate(head,p.head);
            Rotate(arm.root,p.arm);Rotate(arm.bend,p.elbow);Rotate(backArm.root,p.backArm);Rotate(backArm.bend,p.backElbow);
            Rotate(leg.root,p.leg);Rotate(leg.bend,p.knee);Rotate(backLeg.root,p.backLeg);Rotate(backLeg.bend,p.backKnee);
            if(cape)
            {
                float down=Mathf.SmoothStep(0,1,(Mathf.Abs(p.body)-65)/23);
                Rotate(cape,(-p.body*.35f+Mathf.Sin((float)simulation*7)*8)*(1-down));
                cape.localScale=new(Mathf.Lerp(1,.25f,down),1,1);
            }
            transform.localScale=new Vector3(facing*profile.scale,profile.scale,1);
            foreach(var sr in sprites)sr.color=form?new Color(1.2f,1.1f,.74f,opacity):new Color(1,1,1,opacity);
        }
        public SpriteRenderer[] Sprites=>sprites??GetComponentsInChildren<SpriteRenderer>();
    }
}
