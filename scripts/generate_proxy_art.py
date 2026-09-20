"""Original illustrated layered proxies and arena textures, generated from vector shapes.

No downloaded art or copyrighted sprites are used. Parts share explicit pivots
in ProxyRig.cs and can be replaced individually in a CharacterVisualProfile.
"""
from pathlib import Path
import math
import random
import wave
import struct
from PIL import Image, ImageDraw, ImageFilter

ROOT=Path("unity/WhoWouldWinVisual/Assets/Resources")
INK="#10172C"


def canvas(size=(256,384)):
    im=Image.new("RGBA",size)
    return im,ImageDraw.Draw(im)


def poly(d,points,fill,outline=INK,width=6):
    d.polygon(points,fill=fill)
    d.line(points+[points[0]],fill=outline,width=width,joint="curve")


def save(im,style,name):
    path=ROOT/"Art"/style/f"{name}.png"
    path.parent.mkdir(parents=True,exist_ok=True)
    im.save(path)


def character(style):
    ninja=style=="ninja"
    main="#223449" if ninja else "#E3DBCE"
    shade="#12243A" if ninja else "#9B9EAB"
    light="#42616D" if ninja else "#FFF7DE"
    trim="#F4A54B" if ninja else "#C8434C"
    skin="#D99F79" if ninja else "#D5A482"
    im,d=canvas()
    poly(d,[(65,30),(190,30),(224,91),(192,196),(175,340),(78,340),(62,196),(32,91)],main)
    poly(d,[(65,35),(126,65),(125,310),(77,335),(67,196),(37,91)],shade,width=3)
    poly(d,[(128,66),(185,43),(213,95),(180,142),(139,137)],light,width=3)
    poly(d,[(78,132),(126,152),(177,137),(186,163),(127,187),(73,164)],trim,width=3)
    poly(d,[(79,264),(178,263),(177,294),(79,298)],trim,width=3)
    d.line([(128,165),(128,250)],fill=INK,width=5)
    d.line([(145,195),(174,183)],fill=shade,width=5)
    d.line([(146,222),(172,210)],fill=shade,width=5)
    if ninja:
        for x in (67,147):
            poly(d,[(x,90),(x+40,83),(x+46,119),(x+2,126)],"#54696B",width=3)
        d.line([(162,44),(142,251)],fill=trim,width=12)
    else:
        poly(d,[(94,60),(133,84),(170,61),(149,115),(130,133),(111,114)],trim,width=4)
    save(im,style,"torso")
    im,d=canvas((320,320))
    poly(d,[(85,101),(213,92),(242,156),(229,245),(184,283),(111,256),(76,177)],skin)
    poly(d,[(81,130),(121,152),(121,231),(183,276),(111,256),(78,180)],"#A36C60",width=3)
    poly(d,[(139,223),(207,211),(208,233),(175,242)],"#83544B",width=3)
    poly(d,[(100,129),(145,113),(215,121),(229,140),(157,139)],"#FFF0CD",width=2)
    d.line([(148,161),(170,157)],fill=INK,width=7)
    d.line([(197,158),(224,151)],fill=INK,width=7)
    d.ellipse((206,155,214,164),fill="#7DE7EC")
    poly(d,[(209,168),(220,192),(204,196)],"#BC8065",width=3)
    if ninja:
        poly(d,[(70,135),(41,101),(80,94),(60,62),(105,72),(113,29),(141,67),(175,29),(188,65),(234,54),(223,83),(260,101),(217,120),(167,111),(110,123)],"#172839")
        poly(d,[(75,121),(142,105),(229,118),(228,139),(144,130),(76,147)],"#EDAD57",width=4)
        poly(d,[(98,199),(146,186),(219,205),(208,247),(167,255),(113,236)],"#253950",width=4)
        d.line([(117,211),(193,235)],fill="#50707A",width=4)
        poly(d,[(79,133),(35,160),(14,140),(60,120)],trim,width=4)
    else:
        poly(d,[(74,135),(55,98),(88,70),(137,59),(190,61),(231,93),(218,129),(193,100),(144,96),(104,113)],"#C1C6CF")
        d.line([(83,101),(144,78),(199,86)],fill="#F9E9D0",width=9)
        poly(d,[(137,211),(174,202),(209,211),(211,226),(181,219),(160,231),(140,224)],"#34394B",width=3)
    save(im,style,"head")
    im,d=canvas((128,128))
    poly(d,[(30,0),(98,0),(105,107),(79,127),(29,110)],skin,width=3)
    poly(d,[(30,0),(59,0),(57,119),(29,110)],"#A36C60",width=1)
    save(im,style,"neck")
    for part in ("upperarm","forearm","thigh","shin"):
        im,d=canvas()
        wide=part in ("upperarm","thigh")
        left,right=(48,208) if wide else (65,190)
        color=main if part in ("upperarm","thigh") else trim
        poly(d,[(left+20,24),(right-20,24),(right,77),(right-18,282),(166,350),(88,350),(left+13,282),(left,77)],color)
        poly(d,[(left+10,72),(106,54),(112,317),(87,336),(left+18,278)],shade,width=3)
        d.line([(right-30,71),(right-38,247)],fill=light,width=12)
        d.line([(84,290),(164,289)],fill=INK,width=6)
        if ninja and part in ("forearm","shin"):
            for y in range(80,271,32): d.line([(74,y),(182,y-17)],fill="#DBC5A5",width=13)
        if part=="thigh":poly(d,[(139,92),(199,98),(184,210),(140,203)],trim,width=4)
        save(im,style,part)
    im,d=canvas((256,256))
    poly(d,[(65,46),(173,34),(214,92),(200,190),(157,222),(93,209),(56,162)],trim)
    for x in (103,134,165):d.line([(x,90),(x+5,161)],fill=shade,width=5)
    poly(d,[(61,135),(92,122),(116,168),(102,189),(73,175)],light,width=4)
    save(im,style,"hand")
    im,d=canvas((320,160))
    poly(d,[(50,25),(159,26),(181,77),(281,88),(303,125),(286,145),(39,145),(28,107)],shade)
    poly(d,[(52,27),(152,28),(170,77),(100,90),(43,84)],trim,width=4)
    d.line([(51,134),(286,134)],fill=light,width=8)
    save(im,style,"foot")
    im,d=canvas()
    poly(d,[(26,62),(224,62),(212,268),(177,334),(132,279),(86,334),(42,270)],shade)
    poly(d,[(33,65),(218,65),(215,113),(36,113)],trim,width=4)
    d.rectangle((115,71,146,108),fill=light,outline=INK,width=4)
    save(im,style,"hips")
    im,d=canvas((512,640))
    poly(d,[(112,20),(340,20),(430,193),(468,395),(399,620),(310,545),(250,627),(158,531),(68,590),(81,368),(27,213)],"#7F293F")
    poly(d,[(130,25),(318,29),(375,230),(355,531),(274,447),(244,570),(193,442),(116,542),(143,261)],"#DB535B",width=4)
    d.line([(222,50),(191,385)],fill="#F78379",width=15)
    save(im,style,"cape")


def environment():
    rng=random.Random(121)
    im=Image.new("RGBA",(2048,1536));pixels=im.load()
    for y in range(1536):
        t=y/1535
        col=tuple(int(a*(1-t)+b*t) for a,b in zip((17,20,49),(160,106,113)))+(255,)
        for x in range(2048):pixels[x,y]=col
    d=ImageDraw.Draw(im)
    d.ellipse((1480,280,1550,350),fill="#F6D8B2")
    d.ellipse((1491,297,1508,316),fill="#D9B897")
    d.ellipse((1520,317,1535,332),fill="#E9C8A5")
    for _ in range(150):
        x,y=rng.randrange(2048),rng.randrange(950)
        d.ellipse((x,y,x+2,y+2),fill="#CCBDD0")
    for y in (420,650,830):
        d.polygon([(0,y),(300,y-40),(760,y+15),(1040,y-10),(1510,y+30),(2048,y-30),(2048,y+45),(0,y+50)],fill=(126,91,124,110))
    save(im,"arena","sky")
    for layer in ("far","near"):
        im,d=canvas((2048,1024));x=0
        while x<2048:
            w=rng.randrange(65,145);h=rng.randrange(160,610 if layer=="far" else 850);top=1024-h
            color="#33354F" if layer=="far" else "#20283F"
            poly(d,[(x,1024),(x,top),(x+w*.3,top),(x+w*.3,top-25),(x+w*.7,top-25),(x+w*.7,top),(x+w,top),(x+w,1024)],color,width=3)
            for wy in range(top+35,1000,34):
                for wx in range(x+12,x+w-10,22):
                    if rng.random()<.37:d.rectangle((wx,wy,wx+7,wy+11),fill="#E6A66E" if layer=="near" else "#716A80")
            x+=w+rng.randrange(10,38)
        save(im,"arena",layer)
    im,d=canvas((2048,256));d.rectangle((0,0,2048,256),fill="#25344A")
    d.rectangle((0,0,2048,12),fill="#DBC0AF");d.rectangle((0,12,2048,22),fill="#735866")
    for x in range(0,2048,110):
        d.line([(x,23),(x-60,256)],fill="#152337",width=4)
    d.line([(0,140),(2048,140)],fill="#44536A",width=3)
    for _ in range(70):
        x=rng.randrange(2048);y=rng.randrange(30,220)
        d.line([(x,y),(x+25,y+10),(x+35,y+8)],fill="#657080",width=2)
    save(im,"arena","ground")


def effects():
    for kind in ("glow","ring","slash","dust","spark"):
        im,d=canvas((256,256))
        if kind=="glow":
            for r in range(120,0,-1):d.ellipse((128-r,128-r,128+r,128+r),fill=(255,255,255,int(170*(1-r/120)**1.7)))
        elif kind=="ring": d.ellipse((16,16,240,240),outline="white",width=8)
        elif kind=="slash":poly(d,[(15,210),(85,82),(224,14),(130,110)],"white",outline="white",width=1)
        elif kind=="spark":poly(d,[(128,0),(141,105),(250,127),(142,145),(128,254),(107,143),(0,127),(106,109)],"white",outline="white",width=1)
        else:
            for x,y,r in ((78,140,48),(121,90,46),(161,143,67),(85,168,42)):d.ellipse((x-r,y-r,x+r,y+r),fill="white")
            im=im.filter(ImageFilter.GaussianBlur(7))
        save(im,"fx",kind)


def audio():
    output=ROOT/"Audio";output.mkdir(exist_ok=True)
    for index,key in enumerate(("punch","heavy","dash","projectile","explosion","charge","block","transform","ko")):
        duration=.22 if key in ("punch","block") else (.5 if key in ("dash","projectile","heavy") else 1.2)
        rng=random.Random(index);rate=22050;frames=[];last=0
        for i in range(int(rate*duration)):
            t=i/rate;u=t/duration
            noise=rng.uniform(-1,1);last=.82*last+.18*noise
            freq=(90 if key in ("heavy","explosion","ko") else 260)*(1-.7*u)
            envelope=(1-u)**3 if key not in ("charge","transform") else math.sin(math.pi*u)**2
            sample=(last*.8+math.sin(math.tau*freq*t)*.3)*envelope*.55
            frames.append(struct.pack('<h',int(max(-1,min(1,sample))*32767)))
        with wave.open(str(output/f'{key}.wav'),'wb') as handle:
            handle.setnchannels(1);handle.setsampwidth(2);handle.setframerate(rate);handle.writeframes(b''.join(frames))


if __name__=="__main__":
    character("ninja");character("titan");environment();effects();audio()
    (ROOT/"Art/PROVENANCE.txt").write_text("Original project-generated geometric illustrations and synthesized sounds. No downloaded character artwork or voice recordings.\nSource: scripts/generate_proxy_art.py. These are temporary ninja and flying-bruiser proxies, not canonical character assets.\n")
