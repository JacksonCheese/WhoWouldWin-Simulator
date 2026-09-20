using System;
using UnityEngine;

namespace WhoWouldWin.Visual
{
    public enum ArtMode { LayeredProxy, AnimatorPrefab, SpriteSheet }
    [CreateAssetMenu(menuName="WhoWouldWin/Character Visual Profile")]
    public class CharacterVisualProfile:ScriptableObject
    {
        public string characterId, artPrefix="Art/ninja";
        public ArtMode artMode;
        public GameObject prefab;
        public float scale=1;
        public Color accent=Color.cyan, secondary=Color.yellow;
        public AbilityBinding[] abilities;
        public StateBinding[] animations;
        public SoundBinding[] sounds;
        public LayerBinding[] layers;
        public AbilityBinding Ability(string id)=>Array.Find(abilities??Array.Empty<AbilityBinding>(),a=>a.abilityId==id);
        public string AnimatorState(string state)=>Array.Find(animations??Array.Empty<StateBinding>(),a=>a.state==state)?.animatorState??state;
        public Sprite Part(string part)=>Array.Find(layers??Array.Empty<LayerBinding>(),a=>a.part==part)?.sprite??Resources.Load<Sprite>(artPrefix+"/"+part);
        public AudioClip Sound(string key)=>Array.Find(sounds??Array.Empty<SoundBinding>(),s=>s.key==key)?.clip;
    }
    [Serializable] public class StateBinding{public string state, animatorState;public AnimationClip clip; public bool loop;}
    [Serializable] public class SoundBinding{public string key;public AudioClip clip;}
    [Serializable] public class LayerBinding{public string part;public Sprite sprite;public float rotation;public bool flipX;}
}
