using System.Collections;
using System.IO;
using System.Linq;
using UnityEngine.UI;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using WhoWouldWin.Visual;

public class PlaybackTests
{
    [UnityTest] public IEnumerator FullPlaybackAndScrubbingPreserveAuthority()
    {
        SceneManager.LoadScene("CinematicArena");yield return null;yield return null;
        var player=Object.FindFirstObjectByType<ReplayController>();Assert.NotNull(player);player.Paused=true;
        var checksum=JsonUtility.ToJson(player.Replay.finalOutcome);
        player.Evaluate(5);var position=player.Actors[0].transform.position;
        player.Evaluate(12);player.Evaluate(5);Assert.AreEqual(position,player.Actors[0].transform.position);
        for(double t=0;t<player.Replay.metadata.presentationDuration;t+=.15)
        {
            player.Evaluate(t);
            foreach(var actor in player.Actors)
            {
                Assert.IsFalse(float.IsNaN(actor.transform.position.x));
                var bounds=actor.VisualBounds();
                Assert.GreaterOrEqual(player.Camera.WorldToViewportPoint(bounds.min).x,0,"Left body edge clipped");
                Assert.LessOrEqual(player.Camera.WorldToViewportPoint(bounds.max).x,1,"Right body edge clipped");
            }
        }
        player.Evaluate(player.Replay.metadata.presentationDuration);
        Assert.AreEqual(checksum,JsonUtility.ToJson(player.Replay.finalOutcome));
        Assert.AreEqual("Defeat",player.Actors[1].Machine.State);
        yield return null;
    }
    [UnityTest] public IEnumerator BrowserControlsLoadSeekAndTogglePlayback()
    {
        SceneManager.LoadScene("CinematicArena");yield return null;yield return null;
        var player=Object.FindFirstObjectByType<ReplayController>();player.Paused=true;player.Hud.ToggleBrowser();yield return null;
        var dropdown=player.Hud.GetComponentInChildren<Dropdown>();Assert.AreEqual(3,dropdown.options.Count);
        dropdown.Show();yield return null;
        Assert.IsTrue(player.Hud.GetComponentsInChildren<Toggle>().Length>=3,"Dropdown creates selectable replay rows");
        dropdown.Hide();dropdown.value=0;
        void Click(string name)=>player.Hud.GetComponentsInChildren<Button>().First(b=>b.name==name).onClick.Invoke();
        Click("PLAY");Assert.AreEqual(Path.GetFullPath(player.ReplayFiles[0]),player.CurrentPath);yield return null;
        player.Hud.ToggleBrowser();Click("PAUSE");Assert.IsTrue(player.Paused);
        Click("2×");Assert.AreEqual(2,player.Speed);
        var slider=player.Hud.GetComponentInChildren<Slider>();slider.value=.5f;
        Assert.AreEqual(player.Replay.metadata.presentationDuration/2,player.TimePosition,1e-5);
        Click("HUD");Assert.IsFalse(player.ShowHud);Click("DEBUG");Assert.IsTrue(player.ShowDebug);
        Click("9:16 / 16:9");Assert.IsFalse(player.Stage.Portrait);
        Click("RESTART");Assert.AreEqual(0,player.TimePosition);Assert.IsFalse(player.Paused);
        yield return null;
    }
    [UnityTest] public IEnumerator CaptureProducesFramesAndAnOutcomeManifest()
    {
        SceneManager.LoadScene("CinematicArena");yield return null;yield return null;
        var player=Object.FindFirstObjectByType<ReplayController>();player.Paused=true;
        string folder=Path.Combine(Application.temporaryCachePath,"WhoWouldWinCaptureTest");
        if(Directory.Exists(folder))Directory.Delete(folder,true);
        player.GetComponent<FrameSequenceRecorder>().Begin(player,folder,96,170,1,false);
        while(player.Capturing)yield return null;
        Assert.IsTrue(File.Exists(Path.Combine(folder,"frame_00000.png")));
        Assert.IsTrue(File.Exists(Path.Combine(folder,"capture.json")));
        StringAssert.Contains("\"complete\": true",File.ReadAllText(Path.Combine(folder,"capture.json")));
        var image=new Texture2D(2,2);image.LoadImage(File.ReadAllBytes(Path.Combine(folder,"frame_00000.png")));
        Assert.AreEqual(96,image.width);Assert.Greater(image.GetPixels32().Distinct().Count(),100,"Capture must contain a rendered scene");Object.Destroy(image);
    }
}
