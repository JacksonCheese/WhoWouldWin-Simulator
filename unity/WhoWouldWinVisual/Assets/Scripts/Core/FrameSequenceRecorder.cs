using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace WhoWouldWin.Visual
{
    public sealed class FrameSequenceRecorder:MonoBehaviour
    {
        public void Begin(ReplayController owner,string directory,int width,int height,int fps,bool quit)
        {
            if(width<64||height<64||width>4096||height>4096||fps<1||fps>120)throw new ArgumentException("Capture dimensions/fps out of range");
            StartCoroutine(Capture(owner,directory,width,height,fps,quit));
        }
        IEnumerator Capture(ReplayController owner,string directory,int width,int height,int fps,bool quit)
        {
            Directory.CreateDirectory(directory);owner.Capturing=true;owner.Hud.HideBrowser();
            owner.Stage.Portrait=height>width;owner.Hud.Layout(owner.Stage.Portrait);
            var target=new RenderTexture(width,height,24,RenderTextureFormat.ARGB32);target.Create();
            var previous=owner.Camera.targetTexture;owner.Camera.targetTexture=target;
            var texture=new Texture2D(width,height,TextureFormat.RGB24,false);
            double start=double.TryParse(ReplayController.Argument("-capture-start"),out double offset)?Math.Clamp(offset,0,owner.Replay.metadata.presentationDuration):0;
            int total=(int)Math.Ceiling((owner.Replay.metadata.presentationDuration-start)*fps)+1;
            int limit=int.TryParse(ReplayController.Argument("-capture-frames"),out int value)?Math.Clamp(value,1,total):total;
            for(int frame=0;frame<limit;frame++)
            {
                owner.Evaluate(Math.Min(start+(double)frame/fps,owner.Replay.metadata.presentationDuration));
                if(Application.isBatchMode)
                {
                    // Editor batch tests do not dispatch WaitForEndOfFrame.
                    yield return null;Canvas.ForceUpdateCanvases();
                    RenderPipeline.SubmitRenderRequest(owner.Camera,new UniversalRenderPipeline.SingleCameraRequest{destination=target});
                }
                else yield return new WaitForEndOfFrame();
                var active=RenderTexture.active;RenderTexture.active=target;
                texture.ReadPixels(new Rect(0,0,width,height),0,0,false);texture.Apply(false);
                File.WriteAllBytes(Path.Combine(directory,$"frame_{frame:D05}.png"),texture.EncodeToPNG());
                RenderTexture.active=active;
                if(frame%120==0)Debug.Log($"CAPTURE {frame}/{limit} at {owner.TimePosition:F3}s");
            }
            var manifest=new CaptureManifest{width=width,height=height,fps=fps,frames=limit,sourceReplay=owner.CurrentPath,
                sourceChecksum=owner.Replay.metadata.sourceChecksum,presentationDuration=owner.Replay.metadata.presentationDuration,
                capturedStart=start,capturedEnd=owner.TimePosition,finalOutcome=owner.Replay.finalOutcome,complete=owner.TimePosition>=owner.Replay.metadata.presentationDuration-1e-8};
            File.WriteAllText(Path.Combine(directory,"capture.json"),JsonUtility.ToJson(manifest,true));
            owner.Camera.targetTexture=previous;target.Release();Destroy(target);Destroy(texture);
            owner.Capturing=false;owner.Paused=true;owner.Status="Saved frame sequence: "+directory;
            Debug.Log("CAPTURE_COMPLETE "+directory+" "+limit+" frames; authoritative winner "+owner.Replay.finalOutcome.winner);
            if(quit)Application.Quit(0);
        }
        [Serializable] class CaptureManifest{public int width,height,fps,frames;public string sourceReplay,sourceChecksum;public double presentationDuration,capturedStart,capturedEnd;public bool complete;public FinalOutcome finalOutcome;}
    }
}
