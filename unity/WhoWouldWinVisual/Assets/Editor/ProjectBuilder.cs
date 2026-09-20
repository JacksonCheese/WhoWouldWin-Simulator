using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using WhoWouldWin.Visual;

namespace WhoWouldWin.Editor
{
    public static class ProjectBuilder
    {
        [MenuItem("WhoWouldWin/Setup or refresh cinematic project")]
        public static void Setup()
        {
            Directory.CreateDirectory("Assets/Resources/Profiles");Directory.CreateDirectory("Assets/Settings");Directory.CreateDirectory("Assets/Prefabs");
            ImportSprites();AssetDatabase.Refresh();
            // A Resources material keeps this shader in standalone builds.
            const string effectMaterialPath="Assets/Resources/CinematicAdditive.mat";
            if(!AssetDatabase.LoadAssetAtPath<Material>(effectMaterialPath))
                AssetDatabase.CreateAsset(new Material(Shader.Find("WhoWouldWin/AdditiveSprite")),effectMaterialPath);
            var renderer=AssetDatabase.LoadAssetAtPath<Renderer2DData>("Assets/Settings/Cinematic2DRenderer.asset");
            if(renderer==null){renderer=ScriptableObject.CreateInstance<Renderer2DData>();AssetDatabase.CreateAsset(renderer,"Assets/Settings/Cinematic2DRenderer.asset");}
            var pipeline=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/Settings/CinematicURP.asset");
            if(pipeline==null){pipeline=UniversalRenderPipelineAsset.Create(renderer);AssetDatabase.CreateAsset(pipeline,"Assets/Settings/CinematicURP.asset");}
            pipeline.msaaSampleCount=1;pipeline.renderScale=1;pipeline.supportsHDR=false;
            GraphicsSettings.defaultRenderPipeline=pipeline;QualitySettings.renderPipeline=pipeline;
            PlayerSettings.colorSpace=ColorSpace.Linear;PlayerSettings.companyName="WhoWouldWin";PlayerSettings.productName="WhoWouldWin Cinematic";
            PlayerSettings.defaultScreenWidth=608;PlayerSettings.defaultScreenHeight=1080;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
            PlayerSettings.runInBackground=true;PlayerSettings.resizableWindow=true;
            string definitions=Path.GetFullPath(Path.Combine(Application.dataPath,"../../../data/presentation"));
            foreach(string file in Directory.GetFiles(definitions,"*.json"))
            {
                var spec=JsonUtility.FromJson<VisualSpec>(File.ReadAllText(file));
                string path="Assets/Resources/Profiles/"+spec.characterId+".asset";
                var profile=AssetDatabase.LoadAssetAtPath<CharacterVisualProfile>(path);
                bool created=profile==null;
                if(created){profile=ScriptableObject.CreateInstance<CharacterVisualProfile>();AssetDatabase.CreateAsset(profile,path);}
                profile.characterId=spec.characterId;profile.abilities=spec.abilities;
                if(created)
                {
                    profile.artPrefix=spec.artPrefix;profile.scale=spec.scale;
                    ColorUtility.TryParseHtmlString(spec.accent,out profile.accent);ColorUtility.TryParseHtmlString(spec.secondary,out profile.secondary);
                    profile.animations=spec.requiredStates.Select(s=>new StateBinding{state=s,animatorState=s}).ToArray();
                    profile.sounds=new[]{"punch","heavy","dash","projectile","explosion","charge","block","transform","ko"}.Select(s=>new SoundBinding{key=s,clip=Resources.Load<AudioClip>("Audio/"+s)}).ToArray();
                }
                // Refresh bundled procedural rigs while preserving imported art.
                if(created || (profile.artMode==ArtMode.LayeredProxy && AssetDatabase.GetAssetPath(profile.prefab)=="Assets/Prefabs/"+spec.characterId+".prefab"))
                {
                    var go=new GameObject(spec.characterId+" layered proxy");go.AddComponent<ProxyRig>().Build(profile);
                    profile.prefab=PrefabUtility.SaveAsPrefabAsset(go,"Assets/Prefabs/"+spec.characterId+".prefab");UnityEngine.Object.DestroyImmediate(go);
                }
                EditorUtility.SetDirty(profile);
            }
            RefinedArtInstaller.Install();
            string scene="Assets/Scenes/CinematicArena.unity";
            if(!File.Exists(scene))
            {
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
                var camera=new GameObject("Fight Camera");camera.tag="MainCamera";camera.AddComponent<Camera>().orthographic=true;camera.AddComponent<AudioListener>();camera.AddComponent<UniversalAdditionalCameraData>();
                new GameObject("Cinematic Replay Player").AddComponent<ReplayController>();
                EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(),scene);
            }
            EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(scene,true)};
            AssetDatabase.SaveAssets();AssetDatabase.Refresh();
            Debug.Log("CINEMATIC_PROJECT_READY: URP 2D, profiles, prefabs and arena scene generated.");
        }
        static void ImportSprites()
        {
            foreach(string path in Directory.GetFiles("Assets/Resources/Art","*.png",SearchOption.AllDirectories))
            {
                var importer=AssetImporter.GetAtPath(path) as TextureImporter;
                if(importer==null)continue;
                if(importer.textureType==TextureImporterType.Sprite)continue;
                importer.textureType=TextureImporterType.Sprite;importer.spriteImportMode=SpriteImportMode.Single;importer.spritePixelsPerUnit=100;
                importer.alphaIsTransparency=true;importer.mipmapEnabled=false;importer.textureCompression=TextureImporterCompression.Uncompressed;
                importer.maxTextureSize=2048;importer.filterMode=FilterMode.Bilinear;importer.SaveAndReimport();
            }
        }
        [MenuItem("WhoWouldWin/Build macOS cinematic player")]
        public static void BuildMac()
        {
            Setup();string output=ReplayController.Argument("-build-output","Builds/WhoWouldWinCinematic.app");
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output)));
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{"Assets/Scenes/CinematicArena.unity"},locationPathName=output,target=BuildTarget.StandaloneOSX,options=BuildOptions.None});
            if(report.summary.result!=UnityEditor.Build.Reporting.BuildResult.Succeeded)throw new Exception("Cinematic player build failed");
            Debug.Log("CINEMATIC_BUILD_SUCCESS "+output);
        }
    }
}
