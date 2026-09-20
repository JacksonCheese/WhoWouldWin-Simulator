using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

namespace WhoWouldWin.Visual
{
    /// <summary>One manual Animator graph for supplied sheets and SpriteSkin prefabs.
    /// Clips are sampled from timeline phase, so scrubbing never restarts an Animator.</summary>
    public sealed class AnimationGraphBridge
    {
        PlayableGraph graph;
        AnimationMixerPlayable mixer;
        readonly Dictionary<string,int> slots=new();
        readonly List<AnimationClipPlayable> clips=new();
        readonly List<StateBinding> definitions=new();
        public void Initialize(Animator animator,CharacterVisualProfile profile)
        {
            animator.applyRootMotion=false;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
            graph=PlayableGraph.Create("Replay animation");graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
            mixer=AnimationMixerPlayable.Create(graph,profile.animations.Length);
            var output=AnimationPlayableOutput.Create(graph,"Character",animator);output.SetSourcePlayable(mixer);
            for(int i=0;i<profile.animations.Length;i++)
            {
                var binding=profile.animations[i];if(binding.clip==null)continue;
                var clip=AnimationClipPlayable.Create(graph,binding.clip);clip.SetApplyFootIK(false);
                graph.Connect(clip,0,mixer,i);slots[binding.state]=i;clips.Add(clip);definitions.Add(binding);
            }
            graph.Play();
        }
        public void Evaluate(PoseMachine state,double simulation)
        {
            if(!graph.IsValid())return;
            for(int i=0;i<mixer.GetInputCount();i++)mixer.SetInputWeight(i,0);
            string baseState=slots.ContainsKey(state.Locomotion)?state.Locomotion:"Idle";
            if(slots.TryGetValue(baseState,out int baseIndex))mixer.SetInputWeight(baseIndex,1);
            foreach(var layer in state.Layers)
            {
                if(!slots.TryGetValue(layer.state,out int slot))continue;
                for(int i=0;i<mixer.GetInputCount();i++)mixer.SetInputWeight(i,mixer.GetInputWeight(i)*(1-layer.weight));
                mixer.SetInputWeight(slot,mixer.GetInputWeight(slot)+layer.weight);
            }
            for(int i=0;i<clips.Count;i++)
            {
                var binding=definitions[i];double phase=state.LocomotionPhase;
                bool action=false;
                foreach(var layer in state.Layers)if(layer.state==binding.state && layer.weight>.001f){phase=layer.phase;action=true;}
                double length=System.Math.Max(.001,binding.clip.length);
                clips[i].SetTime(binding.loop&&!action?simulation%length:Mathf.Clamp01((float)phase)*length);
            }
            graph.Evaluate(0);
        }
        public void Dispose(){if(graph.IsValid())graph.Destroy();}
    }
}
