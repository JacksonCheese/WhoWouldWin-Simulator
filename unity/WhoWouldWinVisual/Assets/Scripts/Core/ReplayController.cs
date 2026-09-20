using System;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.EventSystems;

namespace WhoWouldWin.Visual
{
    public sealed class ReplayController:MonoBehaviour
    {
        public ReplayDocument Replay{get;private set;}
        public CharacterActor[] Actors{get;private set;}
        public StageProjection Stage{get;}=new();
        public Camera Camera{get;private set;}
        public CinematicHud Hud{get;private set;}
        public double TimePosition{get;private set;}
        public double SimulationPosition{get;private set;}
        public float Speed=1;
        public bool Paused,ShowHud=true,ShowDebug,Capturing;
        public string CurrentPath{get;private set;}
        public string[] ReplayFiles{get;private set;}
        public string Status="";
        FightCameraDirector cameraDirector;
        ArenaPresentation arena;
        CombatVfxDirector vfx;
        CombatAudioDirector audioDirector;
        FrameSequenceRecorder recorder;
        Transform actorRoot;

        public static string Argument(string name,string fallback=null)
        {var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,name);return i>=0&&i+1<args.Length?args[i+1]:fallback;}
        public static bool Flag(string name)=>Environment.GetCommandLineArgs().Contains(name);
        void Start()
        {
            Application.targetFrameRate=60;QualitySettings.vSyncCount=0;
            Stage.Portrait=!Flag("-landscape");ShowHud=!Flag("-hide-hud");
            if(!Application.isEditor && Argument("-capture-dir")==null)Screen.SetResolution(Stage.Portrait?608:1280,Stage.Portrait?1080:720,FullScreenMode.Windowed);
            Camera=UnityEngine.Camera.main;
            if(Camera==null){var go=new GameObject("Fight Camera");go.tag="MainCamera";Camera=go.AddComponent<Camera>();go.AddComponent<AudioListener>();}
            Camera.allowMSAA=false;Camera.orthographic=true;Camera.clearFlags=CameraClearFlags.SolidColor;Camera.backgroundColor=new(.06f,.07f,.13f);
            cameraDirector=Camera.gameObject.AddComponent<FightCameraDirector>();cameraDirector.Output=Camera;
            var environment=new GameObject("Skyline Arena");arena=environment.AddComponent<ArenaPresentation>();arena.Build();
            if(FindFirstObjectByType<EventSystem>()==null){var e=new GameObject("UI Input");e.AddComponent<EventSystem>();e.AddComponent<StandaloneInputModule>();}
            Hud=new GameObject("Cinematic HUD").AddComponent<CinematicHud>();Hud.Initialize(this);
            audioDirector=gameObject.AddComponent<CombatAudioDirector>();recorder=gameObject.AddComponent<FrameSequenceRecorder>();
            string folder=Path.Combine(Application.streamingAssetsPath,"Replays");
            ReplayFiles=Directory.Exists(folder)?Directory.GetFiles(folder,"*.json").OrderBy(p=>p).ToArray():Array.Empty<string>();
            string path=Argument("-replay",ReplayFiles.FirstOrDefault(p=>Path.GetFileName(p)=="upset.json")??ReplayFiles.FirstOrDefault());
            if(path==null){Status="Export a replay into StreamingAssets/Replays first.";return;}
            Load(path);
            if(float.TryParse(Argument("-speed"),out float speed))Speed=Mathf.Clamp(speed,.1f,4);
            string capture=Argument("-capture-dir");
            if(capture!=null)BeginCapture(capture);
        }
        public void Load(string path)
        {
            var next=ReplayDocument.Load(path); // Validate before replacing current playback.
            if(actorRoot)Destroy(actorRoot.gameObject);if(vfx)Destroy(vfx.gameObject);
            Replay=next;CurrentPath=Path.GetFullPath(path);TimePosition=0;Paused=false;
            actorRoot=new GameObject("Fighters - presentation only").transform;
            Actors=new CharacterActor[2];
            for(int i=0;i<2;i++){var go=new GameObject(Replay.fighters[i].name);go.transform.SetParent(actorRoot);Actors[i]=go.AddComponent<CharacterActor>();Actors[i].Initialize(Replay.fighters[i]);}
            vfx=new GameObject("Pooled Combat Effects").AddComponent<CombatVfxDirector>();vfx.Initialize(Actors);
            Hud.SetReplay(Replay);Evaluate(0);Status="Loaded "+Path.GetFileName(path);
        }
        void Update()
        {
            if(Replay==null||Capturing)return;
            if(Input.GetKeyDown(KeyCode.Space))Paused=!Paused;
            if(Input.GetKeyDown(KeyCode.R))Restart();
            if(Input.GetKeyDown(KeyCode.H))ShowHud=!ShowHud;
            if(Input.GetKeyDown(KeyCode.D))ShowDebug=!ShowDebug;
            if(Input.GetKeyDown(KeyCode.B))Hud.ToggleBrowser();
            if(Input.GetKeyDown(KeyCode.V))ToggleOrientation();
            if(Input.GetKeyDown(KeyCode.Alpha1))Speed=1;
            if(Input.GetKeyDown(KeyCode.Alpha2))Speed=2;
            if(Input.GetKeyDown(KeyCode.Alpha4))Speed=4;
            if(Input.GetKeyDown(KeyCode.Alpha0))Speed=.25f;
            if(Input.GetKeyDown(KeyCode.RightArrow)){Paused=true;Evaluate(TimePosition+1.0/60);}
            else if(!Paused)Evaluate(TimePosition+UnityEngine.Time.unscaledDeltaTime*Speed);
            else Hud.Refresh(this,vfx.Flash);
        }
        public void Evaluate(double presentation)
        {
            if(Replay==null)return;
            double previous=TimePosition;
            TimePosition=Math.Clamp(presentation,0,Replay.metadata.presentationDuration);
            SimulationPosition=ReplaySampler.SimulationTime(Replay,TimePosition);
            double animationTime=TimePosition;
            foreach(var segment in Replay.timeMap)
                if(segment.kind=="hitstop"&&TimePosition>=segment.start&&TimePosition<segment.end){animationTime=segment.start;break;}
            Stage.Evaluate(Replay,SimulationPosition);
            for(int i=0;i<2;i++)Actors[i].Evaluate(Replay,Stage,i,TimePosition,animationTime,SimulationPosition);
            cameraDirector.Evaluate(Replay,Stage,Actors,TimePosition);arena.Evaluate(Camera);
            vfx.Evaluate(Replay,Stage,Actors,TimePosition,SimulationPosition);
            audioDirector.Muted=Capturing;audioDirector.Evaluate(Replay,Actors,previous,TimePosition);
            Hud.Refresh(this,vfx.Flash);
            if(TimePosition>=Replay.metadata.presentationDuration)Paused=true;
        }
        public void Seek(float normalized){Paused=true;Evaluate(normalized*Replay.metadata.presentationDuration);}
        public void Restart(){Paused=false;Evaluate(0);}
        public void ToggleOrientation()
        {
            if(Capturing)return;Stage.Portrait=!Stage.Portrait;
            if(!Application.isEditor)Screen.SetResolution(Stage.Portrait?608:1280,Stage.Portrait?1080:720,FullScreenMode.Windowed);
            Hud.Layout(Stage.Portrait);Evaluate(TimePosition);
        }
        public void BeginCapture(string directory=null)
        {
            if(Capturing||Replay==null)return;
            directory??=Path.Combine(Application.persistentDataPath,"Captures",DateTime.Now.ToString("yyyyMMdd-HHmmss"));
            int width=int.Parse(Argument("-capture-width","1080")),height=int.Parse(Argument("-capture-height","1920"));
            int fps=int.Parse(Argument("-capture-fps","60"));
            recorder.Begin(this,directory,width,height,fps,Flag("-quit-after-capture"));
        }
    }
}
