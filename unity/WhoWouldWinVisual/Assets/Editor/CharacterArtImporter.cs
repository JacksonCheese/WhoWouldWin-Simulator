using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.U2D.Sprites;
using UnityEngine;
using WhoWouldWin.Visual;

namespace WhoWouldWin.Editor
{
    [Serializable] public class SheetManifest{public string characterId,texture;public int cellWidth,cellHeight;public float pixelsPerUnit=100;public SheetAnimation[] animations;}
    [Serializable] public class SheetAnimation{public string state;public int row,start,count;public float fps=12;public bool loop;}
    public class CharacterArtImporter:EditorWindow
    {
        CharacterVisualProfile profile;TextAsset manifest;GameObject skeleton;DefaultAsset layerFolder;
        [MenuItem("WhoWouldWin/Import character art")]
        public static void Open()=>GetWindow<CharacterArtImporter>("Character Art");
        void OnGUI()
        {
            GUILayout.Label("REPLACE A FIGHTER'S PRESENTATION",EditorStyles.boldLabel);
            EditorGUILayout.HelpBox("Combat profiles and replay outcomes remain unchanged. Use art you own or have permission to use.",MessageType.Info);
            profile=(CharacterVisualProfile)EditorGUILayout.ObjectField("Visual profile",profile,typeof(CharacterVisualProfile),false);
            manifest=(TextAsset)EditorGUILayout.ObjectField("Sprite-sheet manifest",manifest,typeof(TextAsset),false);
            if(GUILayout.Button("Import sprite sheet + animation mappings") && profile && manifest)ImportSheet(profile,manifest);
            layerFolder=(DefaultAsset)EditorGUILayout.ObjectField("Layered PNG folder",layerFolder,typeof(DefaultAsset),false);
            if(GUILayout.Button("Apply named layered sprites")&&profile&&layerFolder)ImportLayers(profile,AssetDatabase.GetAssetPath(layerFolder));
            skeleton=(GameObject)EditorGUILayout.ObjectField("Animator / SpriteSkin prefab",skeleton,typeof(GameObject),false);
            if(GUILayout.Button("Use skeletal / Animator prefab")&&profile&&skeleton)
            {
                if(!skeleton.GetComponentInChildren<Animator>())throw new ArgumentException("Prefab must contain an Animator.");
                Undo.RecordObject(profile,"Replace character art");profile.prefab=skeleton;profile.artMode=ArtMode.AnimatorPrefab;EditorUtility.SetDirty(profile);AssetDatabase.SaveAssets();
            }
            if(GUILayout.Button("Validate all state and ability mappings")&&profile)Validate(profile);
            EditorGUILayout.HelpBox("For skeletal prefabs, assign Animation Clips to every required state in the profile Inspector. The manual Animator graph samples them deterministically; SpriteSkin deformation runs normally.",MessageType.None);
        }
        public static void Validate(CharacterVisualProfile p)
        {
            string[] required={"Idle","CombatIdle","Run","Sprint","Dash","Jump","Fall","FlightIdle","FlightMove","LightAttack","HeavyAttack","SpecialAttack","RangedAttack","Block","Dodge","HitLight","HitHeavy","Knockback","Knockdown","Recovery","Transformation","Defeat"};
            if(p.animations==null || !required.ToHashSet().IsSubsetOf(p.animations.Select(a=>a.state)) || p.animations.Select(a=>a.state).Distinct().Count()!=p.animations.Length)
                throw new ArgumentException("Missing or duplicate required animation states");
            if(p.abilities==null||p.abilities.Select(a=>a.abilityId).Distinct().Count()!=p.abilities.Length)throw new ArgumentException("Duplicate or missing ability bindings");
            foreach(var binding in p.abilities)
                if(!p.animations.Any(a=>a.state==binding.state)||string.IsNullOrWhiteSpace(binding.vfx)||string.IsNullOrWhiteSpace(binding.sound))
                    throw new ArgumentException("Incomplete presentation binding: "+binding.abilityId);
            if(p.artMode!=ArtMode.LayeredProxy)
            {
                foreach(var binding in p.animations)if(!binding.clip)throw new ArgumentException("Missing animation clip: "+binding.state);
                if(!p.prefab||!p.prefab.GetComponentInChildren<Animator>())throw new ArgumentException("Missing Animator prefab");
            }
            Debug.Log("VISUAL_PROFILE_VALID "+p.characterId);
        }
        public static void ImportLayers(CharacterVisualProfile p,string folder)
        {
            var parts=new[]{"head","torso","hips","upperarm","forearm","hand","thigh","shin","foot"};
            var list=new List<LayerBinding>();
            foreach(var part in parts.Concat(new[]{"cape","neck","head_hurt"}))
            {
                string path=folder+"/"+part+".png";
                if(!File.Exists(path)){if(part!="cape"&&part!="neck"&&part!="head_hurt")throw new ArgumentException("Missing layer "+path);continue;}
                var importer=(TextureImporter)AssetImporter.GetAtPath(path);importer.textureType=TextureImporterType.Sprite;importer.spriteImportMode=SpriteImportMode.Single;importer.alphaIsTransparency=true;importer.mipmapEnabled=false;importer.SaveAndReimport();
                list.Add(new LayerBinding{part=part,sprite=AssetDatabase.LoadAssetAtPath<Sprite>(path)});
            }
            Undo.RecordObject(p,"Import layered art");p.layers=list.ToArray();p.artMode=ArtMode.LayeredProxy;
            // A fresh rig builds from the new layer bindings, not serialized old sprites.
            var go=new GameObject(p.characterId+" custom layers");go.AddComponent<ProxyRig>().Build(p);
            string prefab="Assets/Prefabs/"+p.characterId+"-custom.prefab";p.prefab=PrefabUtility.SaveAsPrefabAsset(go,prefab);DestroyImmediate(go);
            EditorUtility.SetDirty(p);AssetDatabase.SaveAssets();
        }
        public static void ImportSheet(CharacterVisualProfile p,TextAsset asset)
        {
            var spec=JsonUtility.FromJson<SheetManifest>(asset.text);
            if(spec.characterId!=p.characterId||spec.cellWidth<1||spec.cellHeight<1||spec.pixelsPerUnit<=0||spec.animations==null)throw new ArgumentException("Invalid sheet manifest or character ID");
            var required=p.animations.Select(a=>a.state).ToHashSet();
            if(!required.SetEquals(spec.animations.Select(a=>a.state))||spec.animations.Select(a=>a.state).Distinct().Count()!=spec.animations.Length)throw new ArgumentException("Manifest must map every required animation state; frame ranges may be reused.");
            string texturePath=Path.GetFullPath(Path.Combine(Path.GetDirectoryName(AssetDatabase.GetAssetPath(asset)),spec.texture));
            if(!texturePath.StartsWith(Application.dataPath+Path.DirectorySeparatorChar))throw new ArgumentException("Texture must be inside Assets");
            texturePath="Assets"+texturePath.Substring(Application.dataPath.Length);
            var importer=AssetImporter.GetAtPath(texturePath) as TextureImporter;
            if(importer==null)throw new ArgumentException("Texture must be inside Assets");
            importer.textureType=TextureImporterType.Sprite;importer.spriteImportMode=SpriteImportMode.Multiple;importer.spritePixelsPerUnit=spec.pixelsPerUnit;importer.alphaIsTransparency=true;importer.mipmapEnabled=false;
            var texture=AssetDatabase.LoadAssetAtPath<Texture2D>(texturePath);
            var factories=new SpriteDataProviderFactories();factories.Init();var provider=factories.GetSpriteEditorDataProviderFromObject(importer);provider.InitSpriteEditorDataProvider();
            var rects=new List<SpriteRect>();
            foreach(var animation in spec.animations)
            {
                if(animation.count<1||animation.fps<=0||animation.row<0||animation.start<0)throw new ArgumentException("Invalid animation range");
                for(int i=0;i<animation.count;i++)
                {
                    var rect=new Rect((animation.start+i)*spec.cellWidth,texture.height-(animation.row+1)*spec.cellHeight,spec.cellWidth,spec.cellHeight);
                    if(rect.xMax>texture.width||rect.yMin<0)throw new ArgumentException("Animation frame lies outside texture");
                    rects.Add(new SpriteRect{name=animation.state+"_"+i,rect=rect,pivot=new(.5f,0),alignment=SpriteAlignment.Custom,spriteID=GUID.Generate()});
                }
            }
            provider.SetSpriteRects(rects.ToArray());provider.Apply();importer.SaveAndReimport();
            var sprites=AssetDatabase.LoadAllAssetsAtPath(texturePath).OfType<Sprite>().ToDictionary(s=>s.name);
            string folder="Assets/ImportedAnimations/"+p.characterId;Directory.CreateDirectory(folder);AssetDatabase.Refresh();
            var bindings=new List<StateBinding>();
            var controller=AssetDatabase.LoadAssetAtPath<AnimatorController>(folder+"/Character.controller")??AnimatorController.CreateAnimatorControllerAtPath(folder+"/Character.controller");
            foreach(var child in controller.layers[0].stateMachine.states)controller.layers[0].stateMachine.RemoveState(child.state);
            foreach(var animation in spec.animations)
            {
                string clipPath=folder+"/"+animation.state+".anim";
                var clip=AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
                if(!clip){clip=new AnimationClip{name=animation.state};AssetDatabase.CreateAsset(clip,clipPath);}
                clip.ClearCurves();clip.frameRate=animation.fps;
                var keys=Enumerable.Range(0,animation.count+1).Select(i=>new ObjectReferenceKeyframe{time=i/animation.fps,value=sprites[animation.state+"_"+Math.Min(i,animation.count-1)]}).ToArray();
                AnimationUtility.SetObjectReferenceCurve(clip,new EditorCurveBinding{path="",type=typeof(SpriteRenderer),propertyName="m_Sprite"},keys);
                var settings=AnimationUtility.GetAnimationClipSettings(clip);settings.loopTime=animation.loop;AnimationUtility.SetAnimationClipSettings(clip,settings);
                EditorUtility.SetDirty(clip);
                var state=controller.layers[0].stateMachine.AddState(animation.state);state.motion=clip;
                bindings.Add(new StateBinding{state=animation.state,animatorState=animation.state,clip=clip,loop=animation.loop});
            }
            var go=new GameObject(p.characterId+" spritesheet");go.AddComponent<SpriteRenderer>().sprite=sprites[spec.animations[0].state+"_0"];go.AddComponent<Animator>().runtimeAnimatorController=controller;
            p.prefab=PrefabUtility.SaveAsPrefabAsset(go,folder+"/Character.prefab");DestroyImmediate(go);
            p.animations=bindings.ToArray();p.artMode=ArtMode.SpriteSheet;EditorUtility.SetDirty(p);AssetDatabase.SaveAssets();Validate(p);
        }
    }
}
