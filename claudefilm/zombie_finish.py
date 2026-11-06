import wave, math, subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
S=44100;dur=40;t=np.arange(S*dur)/S;rng=np.random.default_rng(5); audio=np.zeros_like(t)
def tone(at,f,length,vol):
 n=int(length*S);tt=np.arange(n)/S;env=np.minimum(1,tt/.025)*np.exp(-tt*2.7);v=(np.sin(2*np.pi*f*tt)+.24*np.sin(4*np.pi*f*tt))*env*vol;i=int(at*S);audio[i:i+n]+=v[:len(audio[i:i+n])]
# Cinematic synth bed and accelerating percussion.
audio+=(.025*np.sin(2*np.pi*55*t)+.014*np.sin(2*np.pi*82.41*t))*(.55+.45*np.sin(t*.18)**2)
for i in range(80):
 at=.5*i
 if at<8 or 34<at: notes=[110,130.81,164.81,196]
 else: notes=[110,116.54,146.83,164.81]
 tone(at,notes[(i//4+i)%4],.9,.025)
 if 8<at<35:
  n=int(.16*S);x=np.arange(n)/S;kick=np.sin(2*np.pi*(75*x-150*x*x))*np.exp(-x*24)*.09;start=int(at*S);audio[start:start+n]+=kick
# alarm, impact, footsteps and coffee throw
for at in [9,10.5,12,13.5,15,16.5,18,19.5,21,22.5,24,25.5,27,28.5,30,31.5]:tone(at,660,.2,.035)
for at in [8.2,10.1,11.0,12.2,13.1,14.4,16.0,17.2,18.1,20.3,22,23,24.4,26.1,27.3,28.5,29.4,30.2]:
 n=int(.12*S);tt=np.arange(n)/S;i=int(at*S);audio[i:i+n]+=rng.normal(size=n)*np.exp(-tt*35)*.035
for at in [28.0,29.1,29.5]:tone(at,100,.4,.12)
# Voices, time-aligned with on-screen subtitles; preserve original recordings.
lines=[(.4,'user1','ВЫ','Клод, помоги с проектом. Погоди...\nТы слышал это за окном?'),(4.3,'claude1','CLAUDE','Слышу. И, кажется, они совсем\nне похожи на разработчиков.'),(8.8,'user2','ВЫ','Зомби! Они идут сюда!\nБыстрее, запри дверь!'),(11.7,'claude2','CLAUDE','Запускаю защиту! Ещё секунда,\nи мы в безопасности!'),(17.0,'user3','ВЫ','Что?! Лимит закончился?\nТолько не сейчас!'),(20.0,'claude3','CLAUDE','Без паники. У меня есть\nрезервный план!'),(25.0,'user4','ВЫ','Кофе? Ты собираешься\nпобедить их кофе?'),(31.0,'claude4','CLAUDE','Перезагрузка зомби... выполнена.\nПохоже, им тоже нужен был перерыв.')]
for at,name,_,_ in lines:
 with wave.open('claudefilm/voice/'+name+'.wav','rb') as w:
  sr=w.getframerate();a=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
  a=np.interp(np.arange(int(len(a)*S/sr))/S,np.arange(len(a))/sr,a)
  i=int(at*S);audio[i:i+len(a)]+=a*.85
fade=np.minimum(1,t/.3)*np.minimum(1,(dur-t)/.6);audio=np.tanh(audio*fade*1.2)*.86
with wave.open('/home/user/zombie_audio.wav','wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(S);w.writeframes((audio*32767).astype('<i2').tobytes())
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf';f=ImageFont.truetype(font,16);b=ImageFont.truetype(bold,12);small=ImageFont.truetype(font,10)
ff=imageio_ffmpeg.get_ffmpeg_exe();cmd=[ff,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','576x324','-r','4','-i','-','-i','/home/user/zombie_audio.wav','-vf','minterpolate=fps=12:mi_mode=blend','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t','40','-movflags','+faststart','claudefilm/claude_zombie_apocalypse.mp4']
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
for n in range(1,161):
 sec=(n-1)/4;im=Image.open(f'/home/user/zombie_frames/{n:04d}.png').convert('RGBA');ov=Image.new('RGBA',im.size);d=ImageDraw.Draw(ov)
 d.text((17,13),'CLAUDE CODE  /  ЗОМБИ-АПОКАЛИПСИС',font=small,fill=(255,230,210,210))
 current=next((x for idx,x in enumerate(lines) if x[0]<=sec<(lines[idx+1][0] if idx+1<len(lines) else 39)),None)
 if current:
  _,name,who,line=current;d.rounded_rectangle((17,248,559,313),radius=9,fill=(8,12,20,218),outline=(245,151,112,100));d.text((29,255),who,font=b,fill=(255,165,115,255));d.multiline_text((29,274),line,font=f,fill=(255,247,239,255),spacing=2)
 if 17<=sec<20:d.rounded_rectangle((362,45,556,78),radius=7,fill=(105,22,20,230));d.text((375,54),'ЛИМИТ ИСЧЕРПАН',font=b,fill=(255,205,180,255))
 im=Image.alpha_composite(im,ov).convert('RGB');p.stdin.write(im.tobytes())
p.stdin.close();p.wait();print('Finished with code',p.returncode)
