using UnityEngine;
using System.Collections.Generic;

namespace WhoWouldWin.Visual
{
    public struct FighterPose
    {
        public float body,head,drop,arm,elbow,backArm,backElbow,leg,knee,backLeg,backKnee;
        public Vector2 offset;
        public static FighterPose Blend(FighterPose a,FighterPose b,float t)
        {
            return new FighterPose{body=Mathf.Lerp(a.body,b.body,t),head=Mathf.Lerp(a.head,b.head,t),drop=Mathf.Lerp(a.drop,b.drop,t),
                arm=Mathf.Lerp(a.arm,b.arm,t),elbow=Mathf.Lerp(a.elbow,b.elbow,t),backArm=Mathf.Lerp(a.backArm,b.backArm,t),backElbow=Mathf.Lerp(a.backElbow,b.backElbow,t),
                leg=Mathf.Lerp(a.leg,b.leg,t),knee=Mathf.Lerp(a.knee,b.knee,t),backLeg=Mathf.Lerp(a.backLeg,b.backLeg,t),backKnee=Mathf.Lerp(a.backKnee,b.backKnee,t),offset=Vector2.Lerp(a.offset,b.offset,t)};
        }
    }
    public struct ClipLayer { public string state;public float phase,weight; }
    public sealed class PoseMachine
    {
        public string Locomotion="CombatIdle", Combat="", Reaction="", Special="", Transformation="", State="CombatIdle";
        public float Phase,Weight;
        public float ClipPhase;
        public int ActionKey=-1;
        public float LocomotionPhase;
        public readonly List<ClipLayer> Layers=new();
        readonly List<ChoreographyCue> active=new();
        public FighterPose Evaluate(MovementKey m,ReplayDocument replay,CharacterVisualProfile profile,int actor,double time,double simulation,double health)
        {
            Layers.Clear();active.Clear();LocomotionPhase=m.vy>0?1-Mathf.Clamp01(m.vy/16):Mathf.Clamp01(-m.vy/20);
            Combat=Reaction=Special=Transformation="";Weight=0;Phase=(float)simulation;ClipPhase=Phase;ActionKey=-1;
            float speed=Mathf.Abs(m.vx),wave=Mathf.Sin((float)simulation*13);
            var p=new FighterPose{arm=35,elbow=105,backArm=-8,backElbow=60,leg=-9,knee=10,backLeg=18,backKnee=18,head=-3,drop=Mathf.Sin((float)simulation*2.5f)*.025f};
            Locomotion="CombatIdle";
            if(m.flying)
            {
                Locomotion=speed>4?"FlightMove":"FlightIdle";
                p.body=speed>4?-36:-5;p.arm=speed>4?-65:12;p.elbow=35;p.backArm=-20;p.backElbow=20;
                p.leg=-18;p.knee=32;p.backLeg=16;p.backKnee=30;p.drop=Mathf.Sin((float)simulation*3)*.055f;
            }
            else if(m.y>1.12f)
            {
                Locomotion=m.vy>0?"Jump":"Fall";p.body=-12;p.leg=48;p.knee=-65;p.backLeg=-25;p.backKnee=56;p.arm=70;p.elbow=50;
            }
            else if(speed>1.4f)
            {
                Locomotion=speed>12?"Sprint":"Run";p.body=-13;p.leg=wave*34;p.backLeg=-wave*34;p.knee=Mathf.Max(0,-wave)*50;p.backKnee=Mathf.Max(0,wave)*50;
                p.arm=-wave*45;p.backArm=wave*45;p.elbow=70;p.backElbow=70;p.drop=Mathf.Abs(wave)*.05f;
                if(profile.artPrefix.Contains("ninja") && speed>12){p.body=-24;p.arm=-55;p.backArm=-40;p.elbow=15;p.backElbow=20;}
            }
            State=Locomotion;

            foreach(var cue in replay.cues)
            {
                if(cue.actor!=actor || !cue.Active(time))continue;
                float phase=cue.Phase(time);int priority=Priority(cue.kind);
                if(cue.kind=="CloneFeint" && phase>.18f)continue;
                if(priority>0)active.Add(cue);
            }
            active.Sort((a,b)=>{int order=Priority(a.kind).CompareTo(Priority(b.kind));return order!=0?order:a.start.CompareTo(b.start);});
            foreach(var selected in active)
            {
                var c=selected;Phase=c.Phase(time);ClipPhase=Phase;ActionKey=c.sourceIndex;
                var action=p;float phase=Phase;
                Weight=Mathf.SmoothStep(0,1,phase*9)*Mathf.SmoothStep(0,1,(1-phase)*7);
                switch(c.kind)
                {
                    case "AnticipateAttack":
                        Combat=State=profile.Ability(c.ability)?.state??"HeavyAttack";
                        ClipPhase=phase*.35f;
                        action.body=15;action.arm=-70;action.elbow=105;action.backArm=40;action.backElbow=80;action.drop=-.12f;action.offset.x=-.12f*phase;
                        if(State is "RangedAttack" or "SpecialAttack")
                        {action.body=6;action.arm=42;action.elbow=105;action.backArm=66;action.backElbow=88;action.head=-6;}
                        break;
                    case "Lunge":
                        Combat=State=profile.Ability(c.ability)?.state??"LightAttack";ClipPhase=.35f+phase*.65f;
                        float punch=Mathf.Sin(Mathf.PI*Mathf.Min(1,phase*1.5f));
                        action.body=-18*punch;action.arm=90;action.elbow=-5;action.backArm=25;action.backElbow=120;action.drop=-.07f;action.offset.x=.32f*punch;
                        if(c.variant==1){action.arm=55;action.elbow=45;action.body=-27;}
                        if(c.variant==2){action.leg=82;action.knee=-12;action.arm=-25;action.elbow=85;action.offset.y=.14f*punch;}
                        break;
                    case "DashPast":case "Teleport":
                        Combat=State="Dash";action.body=-42;action.arm=-75;action.elbow=20;action.backArm=-45;action.backElbow=20;action.leg=50;action.knee=-30;action.backLeg=-40;action.backKnee=75;action.offset.x=.2f*Mathf.Sin(phase*Mathf.PI);break;
                    case "SuccessfulDodge":
                        Reaction=State="Dodge";action.body=38;action.arm=45;action.elbow=95;action.backArm=-30;action.leg=35;action.knee=-55;action.drop=-.4f;action.offset=new Vector2(-.32f,.12f)*Mathf.Sin(phase*Mathf.PI);break;
                    case "Guard":case "BlockImpact":
                        Reaction=State="Block";action.arm=58;action.elbow=107;action.backArm=78;action.backElbow=74;action.body=12;action.drop=-.12f;action.offset.x=-.1f*Mathf.Sin(phase*Mathf.PI);break;
                    case "ProjectileCast":case "BeamCast":
                        Special=State="RangedAttack";ClipPhase=.35f+phase*.65f;action.arm=93;action.elbow=0;action.backArm=63;action.backElbow=50;action.body=-13;action.leg=-20;action.backLeg=20;break;
                    case "Charge":case "CloneFeint":case "Buff":
                        Special=State="SpecialAttack";action.arm=48;action.elbow=110;action.backArm=75;action.backElbow=75;action.body=-5;action.drop=-.1f;break;
                    case "MeleeHit":case "HeavyHit":case "Launcher":
                        Reaction=State=c.intensity>.6f?"HitHeavy":"HitLight";action.body=32*c.intensity;action.head=20;action.arm=-40;action.elbow=25;action.backArm=-65;action.backElbow=15;
                        action.drop=-.08f;action.offset.x=-.2f*c.intensity*Mathf.Sin(phase*Mathf.PI);action.leg=15;action.knee=35;break;
                    case "Transformation":
                        Transformation=State="Transformation";action.arm=-35;action.elbow=10;action.backArm=-35;action.backElbow=15;action.body=0;action.head=12;action.drop=.1f;break;
                    case "GroundImpact":
                        Reaction=State="Recovery";action.drop=-.28f;action.body=-20;action.leg=35;action.knee=-55;break;
                    case "Finisher":
                        Reaction=State="Knockdown";Weight=1;action.body=Mathf.Lerp(20,88,Mathf.SmoothStep(0,1,phase));action.head=18;action.arm=-30;action.elbow=20;action.leg=20;action.knee=30;action.drop=-.65f*phase;break;
                }
                Layers.Add(new ClipLayer{state=State,phase=ClipPhase,weight=Weight});
                p=FighterPose.Blend(p,action,Weight);
            }
            if(health<=0)
            {
                State="Defeat";
                // Defeat grows continuously from the first finisher; replay ending
                // never resets this pose or returns the actor to idle.
                double defeat=0;foreach(var c in replay.cues)if(c.actor==actor&&c.kind=="Finisher")defeat=c.start;
                float settle=Mathf.SmoothStep(0,1,(float)((time-defeat)/.9));
                p=FighterPose.Blend(p,new FighterPose{body=88,head=10,arm=-15,elbow=10,backArm=12,leg=12,knee=10,drop=-.92f,offset=new Vector2(-.25f,0)},settle);
                Phase=(float)(time-defeat);ClipPhase=Mathf.Clamp01(Phase/.9f);Weight=1;
                Layers.Clear();Layers.Add(new ClipLayer{state="Defeat",phase=ClipPhase,weight=1});
            }
            return p;
        }
        static int Priority(string kind)=>kind switch{
            "Finisher"=>110,"HeavyHit"=>100,"MeleeHit"=>95,"Launcher"=>90,"SuccessfulDodge"=>85,"BlockImpact"=>80,
            "Lunge"=>70,"ProjectileCast"=>70,"BeamCast"=>70,"Transformation"=>65,"DashPast"=>60,"Teleport"=>60,
            "Guard"=>55,"AnticipateAttack"=>50,"CloneFeint"=>35,"Charge"=>30,"Buff"=>25,"GroundImpact"=>20,_=>0};
    }
}
