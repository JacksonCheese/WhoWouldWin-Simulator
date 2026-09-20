using System.IO;
using UnityEngine;
using UnityEngine.UI;

namespace WhoWouldWin.Visual
{
    public sealed class CinematicHud:MonoBehaviour
    {
        Canvas canvas;CanvasScaler scaler;ReplayController owner;Font font;
        GameObject chrome,browser;
        Text[] names=new Text[2],numbers=new Text[2],forms=new Text[2];
        Image[] health=new Image[2],energy=new Image[2];
        RectTransform[] cards=new RectTransform[2];
        Text title,clock,verdict,subtitle,debug,status;
        Image flash;
        GameObject menuButton;
        static Sprite white;
        Slider scrub;Dropdown chooser;
        bool suppress;
        public Canvas Canvas=>canvas;
        public void Initialize(ReplayController controller)
        {
            owner=controller;font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            canvas=gameObject.AddComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceCamera;canvas.worldCamera=owner.Camera;canvas.planeDistance=1;canvas.sortingOrder=200;
            scaler=gameObject.AddComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scaler.matchWidthOrHeight=.5f;
            gameObject.AddComponent<GraphicRaycaster>();
            chrome=Rect("Cinematic information",transform,new(.5f,.5f),Vector2.zero,Vector2.zero).gameObject;
            var rt=chrome.GetComponent<RectTransform>();rt.anchorMin=Vector2.zero;rt.anchorMax=Vector2.one;rt.offsetMin=rt.offsetMax=Vector2.zero;
            title=Label("WHO WOULD WIN  /  CINEMATIC LAB",chrome.transform,new(.5f,1),new(0,-105),new(940,44),24,TextAnchor.MiddleCenter);
            title.color=new(.94f,.84f,.73f);
            for(int i=0;i<2;i++)
            {
                cards[i]=Rect("Fighter "+i,chrome.transform,new(.5f,1),new(i==0?-238:238,-227),new(446,146));
                Panel(cards[i],new(.035f,.055f,.1f,.85f));
                names[i]=Label("",cards[i],new(0,1),new(25,-36),new(360,46),36,TextAnchor.MiddleLeft,new(0,.5f));
                numbers[i]=Label("",cards[i],new(1,1),new(-22,-36),new(120,35),20,TextAnchor.MiddleRight,new(1,.5f));
                health[i]=Bar(cards[i],new(0,-7),new(394,12));energy[i]=Bar(cards[i],new(0,-29),new(394,4));
                forms[i]=Label("",cards[i],new(.5f,0),new(0,17),new(390,28),16,TextAnchor.MiddleLeft);
            }
            clock=Label("",chrome.transform,new(.5f,1),new(0,-343),new(700,40),21,TextAnchor.MiddleCenter);
            verdict=Label("",chrome.transform,new(.5f,.235f),Vector2.zero,new(970,95),57,TextAnchor.MiddleCenter);
            subtitle=Label("",chrome.transform,new(.5f,0),new(0,240),new(950,65),27,TextAnchor.MiddleCenter);
            Label("DEVELOPMENT PROXIES  ·  PLACEHOLDER SCALING",chrome.transform,new(.5f,0),new(0,148),new(940,40),18,TextAnchor.MiddleCenter).color=new(.72f,.74f,.8f);
            debug=Label("",transform,new(0,.5f),new(34,0),new(500,400),19,TextAnchor.UpperLeft,new(0,.5f));
            flash=Rect("Impact flash",transform,new(.5f,.5f),Vector2.zero,new(5000,5000)).gameObject.AddComponent<Image>();flash.color=Color.clear;flash.raycastTarget=false;
            BuildBrowser();Layout(true);
        }
        public void Layout(bool portrait)
        {
            scaler.referenceResolution=portrait?new(1080,1920):new(1920,1080);
            for(int i=0;i<2;i++)cards[i].anchoredPosition=new(i==0?(portrait?-238:-620):(portrait?238:620),portrait?-227:-125);
            title.rectTransform.anchoredPosition=new(0,portrait?-105:-48);clock.rectTransform.anchoredPosition=new(0,portrait?-343:-125);
            subtitle.rectTransform.anchoredPosition=new(0,portrait?240:140);
        }
        public void SetReplay(ReplayDocument replay)
        {
            for(int i=0;i<2;i++)
            {names[i].text=replay.fighters[i].name.ToUpperInvariant();ColorUtility.TryParseHtmlString(replay.fighters[i].visual.accent,out Color color);names[i].color=health[i].color=color;energy[i].color=new(.96f,.76f,.43f);}
        }
        public void Refresh(ReplayController controller,float impactFlash)
        {
            chrome.SetActive(controller.ShowHud);debug.gameObject.SetActive(controller.ShowDebug&&!controller.Capturing);
            menuButton.SetActive(controller.ShowHud&&!controller.Capturing);
            flash.color=new(1,.94f,.83f,impactFlash);
            var replay=controller.Replay;if(replay==null)return;
            for(int i=0;i<2;i++)
            {
                var f=replay.fighters[i];var r=ReplaySampler.Resources(f,controller.SimulationPosition);
                health[i].fillAmount=(float)(r.health/f.maxHealth);energy[i].fillAmount=(float)(r.energy/f.maxEnergy);
                numbers[i].text=$"{r.health:0} HP";forms[i].text=controller.Actors[i].Form?"TRANSFORMED":"ENERGY";
            }
            clock.text=$"{controller.SimulationPosition:00.00} SEC   /   {(controller.Paused?"PAUSED":controller.Speed.ToString("0.##")+"×")}";
            verdict.text="";subtitle.text="SKYLINE 07  /  ROOFTOP BATTLEGROUND";
            if(controller.TimePosition<1.6){verdict.fontSize=46;verdict.rectTransform.sizeDelta=new(960,200);verdict.text=replay.fighters[0].name.ToUpperInvariant()+"\nVS\n"+replay.fighters[1].name.ToUpperInvariant();}
            else{verdict.fontSize=57;verdict.rectTransform.sizeDelta=new(970,95);}
            if(controller.SimulationPosition>=replay.metadata.simulationDuration-1e-8)
            {verdict.text=replay.finalOutcome.winner>=0?replay.fighters[replay.finalOutcome.winner].name.ToUpperInvariant()+" WINS":"DRAW";subtitle.text=replay.finalOutcome.condition.Replace('_',' ').ToUpperInvariant()+"  ·  "+replay.metadata.simulationDuration.ToString("0.00")+" SECONDS";}
            else foreach(var moment in replay.moments)
                if(controller.TimePosition>=moment.time&&controller.TimePosition<moment.time+.65&&moment.importance>.9)
                    subtitle.text=moment.kind=="transformation"?"POWER UNLEASHED":"HEAVY IMPACT";
            debug.text=$"PRESENTATION {controller.TimePosition:0.000}\nSIMULATION {controller.SimulationPosition:0.000}\nSEED {replay.metadata.seed}\n";
            for(int i=0;i<2;i++){var m=controller.Actors[i].Machine;debug.text+=$"\n{replay.fighters[i].name}\nLocomotion: {m.Locomotion}\nCombat: {m.Combat}\nReaction: {m.Reaction}\nSpecial: {m.Special}\nState: {m.State}";}
            suppress=true;scrub.value=(float)(controller.TimePosition/replay.metadata.presentationDuration);suppress=false;
            status.text=controller.Status;
        }
        public void ToggleBrowser(){browser.SetActive(!browser.activeSelf);if(browser.activeSelf)RefreshFiles();}
        public void HideBrowser()=>browser.SetActive(false);
        void BuildBrowser()
        {
            browser=Rect("Replay Browser",transform,new(.5f,.5f),Vector2.zero,new(960,650)).gameObject;Panel(browser.transform,new(.03f,.045f,.08f,.98f));
            Label("REPLAY ROOM",browser.transform,new(.5f,1),new(0,-53),new(850,58),36,TextAnchor.MiddleLeft);
            var dropRect=Rect("Replay files",browser.transform,new(.5f,1),new(0,-140),new(840,60));Panel(dropRect,new(.12f,.16f,.22f,1));chooser=dropRect.gameObject.AddComponent<Dropdown>();
            var caption=Label("",dropRect,new(.5f,.5f),Vector2.zero,new(800,52),24,TextAnchor.MiddleLeft);chooser.captionText=caption;
            var template=Rect("Template",dropRect,new(.5f,0),new(0,-120),new(840,220));Panel(template,new(.08f,.1f,.16f,1));
            var item=Rect("Item",template,new(.5f,1),new(0,-25),new(810,48));var toggle=item.gameObject.AddComponent<Toggle>();var itemLabel=Label("Replay",item,new(.5f,.5f),Vector2.zero,new(760,45),22,TextAnchor.MiddleLeft);
            toggle.targetGraphic=itemLabel;chooser.template=template;chooser.itemText=itemLabel;template.gameObject.SetActive(false);
            Button("PLAY",new(-315,-235),()=>{if(owner.ReplayFiles.Length>0)owner.Load(owner.ReplayFiles[chooser.value]);HideBrowser();});
            Button("PAUSE",new(-105,-235),()=>owner.Paused=!owner.Paused);Button("RESTART",new(105,-235),owner.Restart);Button("CLOSE",new(315,-235),HideBrowser);
            Button("0.25×",new(-315,-320),()=>owner.Speed=.25f);Button("1×",new(-105,-320),()=>owner.Speed=1);Button("2×",new(105,-320),()=>owner.Speed=2);Button("4×",new(315,-320),()=>owner.Speed=4);
            var sliderRect=Rect("Scrub",browser.transform,new(.5f,1),new(0,-395),new(840,26));Panel(sliderRect,new(.2f,.23f,.3f,1));scrub=sliderRect.gameObject.AddComponent<Slider>();
            var fill=Rect("Fill",sliderRect,new(.5f,.5f),Vector2.zero,new(840,26));Panel(fill,new(.23f,.75f,.8f,1));scrub.fillRect=fill;scrub.direction=Slider.Direction.LeftToRight;
            scrub.onValueChanged.AddListener(v=>{if(!suppress)owner.Seek(v);});
            Button("HUD",new(-315,-475),()=>owner.ShowHud=!owner.ShowHud);Button("DEBUG",new(-105,-475),()=>owner.ShowDebug=!owner.ShowDebug);Button("9:16 / 16:9",new(105,-475),owner.ToggleOrientation);Button("RECORD",new(315,-475),()=>owner.BeginCapture());
            status=Label("",browser.transform,new(.5f,0),new(0,55),new(850,65),17,TextAnchor.MiddleLeft);
            browser.SetActive(false);
            var menu=Rect("Browser button",transform,new(1,0),new(-100,63),new(160,45));menuButton=menu.gameObject;Panel(menu,new(.04f,.06f,.1f,.8f));var btn=menu.gameObject.AddComponent<Button>();btn.onClick.AddListener(ToggleBrowser);Label("REPLAYS  [B]",menu,new(.5f,.5f),Vector2.zero,new(150,40),17,TextAnchor.MiddleCenter);
        }
        void RefreshFiles(){chooser.ClearOptions();foreach(var p in owner.ReplayFiles)chooser.options.Add(new Dropdown.OptionData(Path.GetFileNameWithoutExtension(p)));int selected=System.Array.IndexOf(owner.ReplayFiles,owner.CurrentPath);chooser.SetValueWithoutNotify(Mathf.Max(0,selected));chooser.RefreshShownValue();}
        void Button(string text,Vector2 position,UnityEngine.Events.UnityAction action)
        {var rt=Rect(text,browser.transform,new(.5f,1),position,new(190,60));var image=Panel(rt,new(.14f,.2f,.27f,1));var button=rt.gameObject.AddComponent<Button>();button.targetGraphic=image;button.onClick.AddListener(action);Label(text,rt,new(.5f,.5f),Vector2.zero,new(180,54),21,TextAnchor.MiddleCenter);}
        Image Bar(Transform parent,Vector2 position,Vector2 size)
        {var bg=Rect("Track",parent,new(.5f,.5f),position,size);Panel(bg,new(.18f,.21f,.27f,1));var fill=Rect("Fill",bg,new(.5f,.5f),Vector2.zero,size);var image=Panel(fill,Color.white);image.type=Image.Type.Filled;image.fillMethod=Image.FillMethod.Horizontal;return image;}
        Text Label(string value,Transform parent,Vector2 anchor,Vector2 position,Vector2 size,int fontSize,TextAnchor alignment,Vector2? pivot=null)
        {var rt=Rect(value,parent,anchor,position,size);if(pivot.HasValue)rt.pivot=pivot.Value;var t=rt.gameObject.AddComponent<Text>();t.font=font;t.text=value;t.fontSize=fontSize;t.color=new(.94f,.92f,.9f);t.alignment=alignment;t.raycastTarget=false;t.horizontalOverflow=HorizontalWrapMode.Overflow;return t;}
        static Image Panel(Transform parent,Color color){if(!white){var t=Texture2D.whiteTexture;white=Sprite.Create(t,new Rect(0,0,t.width,t.height),new(.5f,.5f));}var image=parent.gameObject.AddComponent<Image>();image.sprite=white;image.color=color;return image;}
        static RectTransform Rect(string name,Transform parent,Vector2 anchor,Vector2 position,Vector2 size)
        {var rt=new GameObject(name,typeof(RectTransform)).GetComponent<RectTransform>();rt.SetParent(parent,false);rt.anchorMin=rt.anchorMax=anchor;rt.pivot=new(.5f,.5f);rt.anchoredPosition=position;rt.sizeDelta=size;return rt;}
    }
}
