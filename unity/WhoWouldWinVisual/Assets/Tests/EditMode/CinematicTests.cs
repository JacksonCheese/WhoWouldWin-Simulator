using System;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using WhoWouldWin.Visual;
using WhoWouldWin.Editor;

public class CinematicTests
{
    ReplayDocument Replay()=>ReplayDocument.Load(Path.Combine(Application.streamingAssetsPath,"Replays/upset.json"));
    [Test] public void ReplayLoadsWithUnchangedFinalHealth()
    {
        var r=Replay();Assert.AreEqual(0,r.finalOutcome.winner);Assert.AreEqual(22.55,r.metadata.simulationDuration);
        foreach(var f in r.fighters)Assert.AreEqual(r.finalOutcome.health[f.slot],ReplaySampler.Resources(f,r.metadata.simulationDuration).health);
    }
    [Test] public void ClockHasMonotonicSimulationTimeAndFinishesExactly()
    {
        var r=Replay();double previous=0;
        for(double t=0;t<r.metadata.presentationDuration;t+=.01){double s=ReplaySampler.SimulationTime(r,t);Assert.GreaterOrEqual(s,previous);previous=s;}
        Assert.AreEqual(r.metadata.simulationDuration,ReplaySampler.SimulationTime(r,r.metadata.presentationDuration));
        foreach(var hold in r.timeMap.Where(s=>s.kind=="hitstop"))Assert.AreEqual(ReplaySampler.SimulationTime(r,hold.start+.001),ReplaySampler.SimulationTime(r,hold.end-.001));
    }
    [Test] public void EveryAbilityHasAVisualBindingAndAllRequiredStatesExist()
    {
        foreach(var f in Replay().fighters)
        {
            var p=Resources.Load<CharacterVisualProfile>("Profiles/"+f.id);Assert.NotNull(p);Assert.NotNull(p.prefab);
            foreach(var binding in f.visual.abilities)Assert.NotNull(p.Ability(binding.abilityId),binding.abilityId);
            CollectionAssert.AreEquivalent(f.visual.requiredStates,p.animations.Select(a=>a.state));
        }
    }
    [Test] public void PortraitProjectionAndAnimationAreFiniteAndSeekable()
    {
        var r=Replay();var stage=new StageProjection();var machine=new PoseMachine();var profile=Resources.Load<CharacterVisualProfile>("Profiles/naruto");
        for(double t=0;t<r.metadata.simulationDuration;t+=.033)
        {
            stage.Evaluate(r,t);Assert.Less(Mathf.Abs(stage.Feet[0].x-stage.Feet[1].x),6.1f);
            Assert.IsFalse(float.IsNaN(stage.Feet[0].x));var pose=machine.Evaluate(stage.Samples[0],r,profile,0,t,t,100);
            Assert.IsFalse(float.IsNaN(pose.arm));
        }
        stage.Evaluate(r,5);var first=stage.Feet[0];stage.Evaluate(r,16);stage.Evaluate(r,5);Assert.AreEqual(first,stage.Feet[0]);
    }
    [Test] public void SheetImporterCreatesRealSpriteAnimationsForEveryState()
    {
        const string folder="Assets/ArtImportTest";const string output="Assets/ImportedAnimations/__pipeline_test";
        AssetDatabase.DeleteAsset(folder);AssetDatabase.DeleteAsset(output);Directory.CreateDirectory(folder);
        var texture=new Texture2D(32,16);for(int y=0;y<16;y++)for(int x=0;x<32;x++)texture.SetPixel(x,y,x<16?Color.red:Color.blue);texture.Apply();File.WriteAllBytes(folder+"/sheet.png",texture.EncodeToPNG());UnityEngine.Object.DestroyImmediate(texture);
        AssetDatabase.Refresh();
        var prototype=Resources.Load<CharacterVisualProfile>("Profiles/naruto");
        var profile=ScriptableObject.CreateInstance<CharacterVisualProfile>();profile.characterId="__pipeline_test";profile.abilities=prototype.abilities;profile.animations=prototype.animations;
        var manifest=new SheetManifest{characterId=profile.characterId,texture="sheet.png",cellWidth=16,cellHeight=16,pixelsPerUnit=8,animations=prototype.animations.Select(a=>new SheetAnimation{state=a.state,row=0,start=0,count=2,fps=10,loop=true}).ToArray()};
        File.WriteAllText(folder+"/sheet.json",JsonUtility.ToJson(manifest));AssetDatabase.Refresh();
        try
        {
            CharacterArtImporter.ImportSheet(profile,AssetDatabase.LoadAssetAtPath<TextAsset>(folder+"/sheet.json"));
            var firstClip=profile.animations[0].clip;
            CharacterArtImporter.ImportSheet(profile,AssetDatabase.LoadAssetAtPath<TextAsset>(folder+"/sheet.json"));
            Assert.AreSame(firstClip,profile.animations[0].clip,"Reimport preserves clip asset references");
            Assert.AreEqual(ArtMode.SpriteSheet,profile.artMode);Assert.AreEqual(22,profile.animations.Length);
            var instance=UnityEngine.Object.Instantiate(profile.prefab);var renderer=instance.GetComponent<SpriteRenderer>();
            profile.animations[0].clip.SampleAnimation(instance,0);var first=renderer.sprite;
            profile.animations[0].clip.SampleAnimation(instance,.11f);Assert.AreNotEqual(first,renderer.sprite);
            UnityEngine.Object.DestroyImmediate(instance);
        }
        finally{UnityEngine.Object.DestroyImmediate(profile);AssetDatabase.DeleteAsset(folder);AssetDatabase.DeleteAsset(output);}
    }
}
