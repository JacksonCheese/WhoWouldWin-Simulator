using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.U2D.Sprites;
using UnityEngine;
using WhoWouldWin.Visual;

namespace WhoWouldWin.Editor
{
    /// <summary>Slices generated source atlases in Unity, preserving their original pixels and alpha.</summary>
    public static class RefinedArtInstaller
    {
        const string Root="Assets/Resources/Art/Refined/";
        sealed class Region
        {
            public string name;public int x,top,width,height;
            public Region(string name,int x,int top,int width,int height){this.name=name;this.x=x;this.top=top;this.width=width;this.height=height;}
        }
        [MenuItem("WhoWouldWin/Refresh bundled refined art")]
        public static void Install()
        {
            if(!File.Exists(Root+"ninja-atlas.png"))return;
            var ninja=Slice("ninja-atlas",new[]{
                new Region("head",0,0,385,343),new("torso",410,0,360,345),new("hips",800,0,400,345),new("neck",1240,95,280,230),
                new("upperarm",85,346,210,304),new("forearm",438,346,172,302),new("hand",770,425,325,190),new("foot",1170,550,350,95),
                new("thigh",25,655,270,369),new("shin",430,650,200,374),new("head_hurt",678,650,452,374)},true);
            var titan=Slice("titan-atlas",new[]{
                new Region("head",15,0,370,342),new("torso",400,0,375,343),new("hips",800,130,340,211),new("neck",1210,120,310,175),
                new("upperarm",95,343,195,309),new("forearm",468,343,150,205),new("hand",804,420,298,185),new("foot",1210,540,285,80),
                new("thigh",102,654,205,350),new("shin",480,656,155,342),new("head_hurt",762,641,369,348),new("cape",1153,620,383,404)},true);
            Slice("skyline-atlas",new[]{new Region("city",0,0,1536,720),new("ground",0,744,1536,280)},false);
            Apply("naruto",ninja);Apply("omniman",titan);AssetDatabase.SaveAssets();
        }
        static Dictionary<string,Sprite> Slice(string name,Region[] regions,bool trim)
        {
            string path=Root+name+".png";
            var importer=(TextureImporter)AssetImporter.GetAtPath(path);
            importer.textureType=TextureImporterType.Sprite;importer.spriteImportMode=SpriteImportMode.Multiple;
            importer.spritePixelsPerUnit=100;importer.alphaIsTransparency=true;importer.mipmapEnabled=false;
            importer.isReadable=true;importer.maxTextureSize=2048;importer.textureCompression=TextureImporterCompression.Uncompressed;
            importer.filterMode=FilterMode.Bilinear;importer.SaveAndReimport();
            var texture=AssetDatabase.LoadAssetAtPath<Texture2D>(path);var pixels=texture.GetPixels32();
            var factories=new SpriteDataProviderFactories();factories.Init();
            var provider=factories.GetSpriteEditorDataProviderFromObject(importer);provider.InitSpriteEditorDataProvider();
            var previous=provider.GetSpriteRects().ToDictionary(s=>s.name,s=>s.spriteID);
            var rects=new List<SpriteRect>();
            foreach(var region in regions)
            {
                int left=region.x,right=region.x+region.width-1,bottom=texture.height-region.top-region.height,top=texture.height-region.top-1;
                if(trim)
                {
                    int x0=right,x1=left,y0=top,y1=bottom;
                    for(int y=bottom;y<=top;y++)for(int x=left;x<=right;x++)if(pixels[y*texture.width+x].a>30)
                    {x0=Mathf.Min(x0,x);x1=Mathf.Max(x1,x);y0=Mathf.Min(y0,y);y1=Mathf.Max(y1,y);}
                    left=x0;right=x1;bottom=y0;top=y1;
                }
                rects.Add(new SpriteRect{name=region.name,rect=new Rect(left,bottom,right-left+1,top-bottom+1),
                    alignment=SpriteAlignment.Center,pivot=new(.5f,.5f),spriteID=previous.TryGetValue(region.name,out var id)?id:GUID.Generate()});
            }
            provider.SetSpriteRects(rects.ToArray());provider.Apply();importer.SaveAndReimport();
            return AssetDatabase.LoadAllAssetsAtPath(path).OfType<Sprite>().ToDictionary(s=>s.name);
        }
        static void Apply(string id,Dictionary<string,Sprite> parts)
        {
            var profile=Resources.Load<CharacterVisualProfile>("Profiles/"+id);if(!profile)return;
            string current=AssetDatabase.GetAssetPath(profile.prefab),output="Assets/Prefabs/"+id+"-refined.prefab";
            // Imported user art has its own prefab and is preserved by refresh.
            if(profile.artMode!=ArtMode.LayeredProxy || (current!="Assets/Prefabs/"+id+".prefab" && current!=output))return;
            profile.layers=parts.Select(p=>new LayerBinding{part=p.Key,sprite=p.Value,rotation=p.Key=="hand"?-90:0,flipX=p.Key=="cape"}).ToArray();
            var go=new GameObject(id+" refined layered rig");go.AddComponent<ProxyRig>().Build(profile);
            profile.prefab=PrefabUtility.SaveAsPrefabAsset(go,output);Object.DestroyImmediate(go);EditorUtility.SetDirty(profile);
        }
    }
}
