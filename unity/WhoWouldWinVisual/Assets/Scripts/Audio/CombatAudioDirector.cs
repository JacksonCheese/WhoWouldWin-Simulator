using UnityEngine;

namespace WhoWouldWin.Visual
{
    public sealed class CombatAudioDirector:MonoBehaviour
    {
        AudioSource source;
        public bool Muted;
        void Awake(){source=gameObject.AddComponent<AudioSource>();source.spatialBlend=0;source.volume=.5f;}
        public static string SoundFor(ChoreographyCue c)=>c.kind switch
        {
            "Finisher"=>"ko","HeavyHit" when c.vfx is "vortex" or "shockwave"=>"explosion","HeavyHit"=>"heavy","MeleeHit"=>"punch","BlockImpact"=>"block","Clash"=>"block",
            "AnticipateAttack" when c.vfx is "energy" or "vortex"=>"charge",
            "Charge"=>"charge","ProjectileCast"=>"projectile","BeamCast"=>"projectile",
            "DashPast" or "Teleport" or "Flight" or "SuccessfulDodge"=>"dash",
            "Transformation"=>"transform","GroundImpact"=>"heavy",_=>""
        };
        public void Evaluate(ReplayDocument replay,CharacterActor[] actors,double previous,double time)
        {
            if(Muted || time<previous || time-previous>.3)return;
            foreach(var c in replay.cues)
            {
                if(c.start<=previous || c.start>time)continue;
                string sound=SoundFor(c);
                if(sound.Length==0)continue;
                var clip=actors[c.actor].Profile.Sound(sound)??Resources.Load<AudioClip>("Audio/"+sound);
                if(clip)source.PlayOneShot(clip,.35f+c.intensity*.45f);
            }
        }
    }
}
