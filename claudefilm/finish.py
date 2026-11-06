import numpy as np, math, wave, subprocess, os
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
S=44100; dur=18; t=np.arange(int(S*dur))/S; audio=np.zeros_like(t)
def note(at,f,length,vol=.06):
 n=int(length*S); tt=np.arange(n)/S; env=np.minimum(1,tt/.035)*np.exp(-tt*2.4); sound=(np.sin(2*np.pi*f*tt)+.25*np.sin(4*np.pi*f*tt)+.1*np.sin(6*np.pi*f*tt))*env*vol; i=int(at*S);audio[i:i+min(n,len(audio)-i)]+=sound[:min(n,len(audio)-i)]
# gentle, original synthesized lo-fi piano arpeggio
chords=[[130.81,164.81,196,261.63],[110,130.81,164.81,220],[87.31,130.81,174.61,220],[98,146.83,196,246.94]]
for beat in range(36):
 at=beat*.5; chord=chords[(beat//4)%4];note(at,chord[beat%4],1.5,.045);note(at,chord[0]/2,1.6,.025)
# soft typing clicks and warning chime
rng=np.random.default_rng(37)
for at in [2.6,2.78,2.95,3.16,4.2,4.35,4.48,4.6,5.2,5.35,5.5,5.65,6.0,6.15,6.3,7.4,7.52,7.7,8.2]:
 i=int(at*S);n=int(.025*S);audio[i:i+n]+=rng.normal(0,1,n)*np.exp(-np.arange(n)/S*140)*.025
note(10.05,440,.6,.08);note(10.3,349.23,.9,.07)
for a,f in [(15.3,523.25),(15.48,659.25),(15.66,783.99)]:note(a,f,1,.055)
fade=np.minimum(1,t/1.0)*np.minimum(1,(dur-t)/1.4);audio=np.clip(audio*fade,-.95,.95)
with wave.open('/home/user/claude_audio.wav','wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(S);w.writeframes((audio*32767).astype('<i2').tobytes())
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf';f=ImageFont.truetype(font,19);b=ImageFont.truetype(bold,15);small=ImageFont.truetype(font,11)
def caption(sec):
 if sec<3.5:return 'ВЫ', 'Привет! Поможешь мне с проектом?'
 if sec<6.5:return 'CLAUDE CODE', 'Конечно! Сейчас всё сделаем.'
 if sec<9.8:return 'ВЫ', 'И ещё одну маленькую фичу...'
 if sec<12.5:return 'СИСТЕМА', 'Лимит сообщений исчерпан.'
 if sec<15.4:return 'CLAUDE CODE', 'Кажется, нужен небольшой перерыв.'
 return 'ВЫ', 'Ну что, кофе? Продолжим позже!'
ff=imageio_ffmpeg.get_ffmpeg_exe(); out='claudefilm/claude_code_3d_sound.mp4'
cmd=[ff,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','640x360','-r','6','-i','-','-i','/home/user/claude_audio.wav','-vf','minterpolate=fps=12:mi_mode=blend' ,'-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-shortest','-movflags','+faststart',out]
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
for n in range(1,109):
 im=Image.open(f'/home/user/claude_frames/{n:04d}.png').convert('RGB'); overlay=Image.new('RGBA',im.size);d=ImageDraw.Draw(overlay)
 d.rounded_rectangle((24,270,616,338),radius=12,fill=(12,17,25,205),outline=(240,182,144,110),width=1)
 who,line=caption((n-1)/6);d.text((39,279),who,font=b,fill=(255,173,127,255));d.text((39,302),line,font=f,fill=(255,246,236,255))
 d.text((20,17),'CLAUDE CODE  /  НЕОФИЦИАЛЬНАЯ ИСТОРИЯ',font=small,fill=(255,236,222,180))
 im=Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB');p.stdin.write(im.tobytes())
p.stdin.close();p.wait();print(out,p.returncode)
