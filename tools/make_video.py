"""Clawd / one evening: 40-second voiced pixel film, synthesized stereo audio.
Run from any directory: python tools/make_video.py
"""
from pathlib import Path
import math, subprocess, wave, textwrap, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'exports'; OUT.mkdir(exist_ok=True)
W,H,FPS,SR=360,640,30,44100
F={s:ImageFont.truetype(str(ROOT/'assets/PressStart2P-Regular.ttf'),s) for s in [6,7,8,9,10,11,12,14,16,18,20,22,24]}
BG='#141727'; CREAM='#f4e6cc'; ORANGE='#d77757'; GREEN='#b5d5a0'; RED='#ed7375'; BLUE='#8f9dc4'
# Each voice clip has its own interval; long Clawd delivery has a seven-second slot.
DIALOGUE=[
 (.4,'01-programmer.wav','ПРОГРАММИСТ','Клод, допишем проект и спать. Там всего одна кнопка!'),
 (4.2,'02-clawd.wav','КЛОД','Одна кнопка? Отлично. Я уже переписываю весь сайт.'),
 (9.6,'03-programmer.wav','ПРОГРАММИСТ','Какой ещё лимит? Мы же только начали!'),
 (13.,'04-clawd.wav','КЛОД','Можно купить подписку. Надежда станет дороже.'),
 (18.,'05-programmer.wav','ПРОГРАММИСТ','Оплачено! Теперь-то точно успеем до утра.'),
 (22.,'06-clawd.wav','КЛОД','Конечно! Добавим ещё чат, магазин... Ой. Снова лимит.'),
 (30.,'07-programmer.wav','ПРОГРАММИСТ','Я купил подписку, а не абонемент на ожидание!'),
 (34.5,'08-clawd.wav','КЛОД','Подписка есть. Безлимита нет. Пойдём спать.'),
]
CLIPS=[]
for start,name,speaker,words in DIALOGUE:
 with wave.open(str(ROOT/'assets/voices'/name)) as wf:
  duration=wf.getnframes()/wf.getframerate()
 CLIPS.append((start,start+duration,name,speaker,words))
for i,clip in enumerate(CLIPS):
 assert clip[1]<=40
 if i:assert CLIPS[i-1][1]<clip[0], 'Overlapping dialogue'
SPEAKER=None
# Exact official block-glyph silhouette, rendered with terminal cell aspect 1:2.
GLYPHS={' ':['00','00'],'▐':['01','01'],'▛':['11','10'],'█':['11','11'],'▜':['11','01'],'▌':['10','10'],'▝':['01','00'],'▘':['10','00']}
ROWS=[' ▐▛███▜▌ ','▝▜█████▛▘','  ▘▘ ▝▝  ']
MASK=[]
for row in ROWS:
 for half in range(2):
  bits=''.join(GLYPHS[c][half] for c in row)
  MASK.extend([bits,bits])
def box(a,c):d.rectangle(tuple(map(round,a)),fill=c)
def label(s,x,y,size=10,c=CREAM,center=False):
 if center:x-=d.textlength(s,font=F[size])/2
 d.text((round(x),round(y)),s,font=F[size],fill=c)
def centered(ss,y,size=12,c=CREAM,gap=22):
 for i,s in enumerate(ss):label(s,180,y+i*gap,size,c,True)
def window(x,y,w,h,edge=BLUE,fill='#202538'):
 box((x+4,y+4,x+w+4,y+h+4),'#0b0e1a');box((x,y,x+w,y+h),edge);box((x+2,y+2,x+w-2,y+h-2),fill)
def spark(x,y,c=CREAM):
 box((x-1,y-5,x+1,y+5),c);box((x-5,y-1,x+5,y+1),c)
def speech(ss,x,y,w):
 h=len(ss)*16+16;box((x+3,y+3,x+w+3,y+h+3),'#080c18');box((x,y,x+w,y+h),CREAM)
 d.polygon([(x+15,y+h),(x+24,y+h),(x+18,y+h+9)],fill=CREAM)
 for i,s in enumerate(ss):label(s,x+9,y+9+16*i,8,BG)
def clawd(x,y,t,scale=5,asleep=False):
 y+=round(math.sin(t*4)*2)
 for yy,row in enumerate(MASK):
  for xx,b in enumerate(row):
   if b=='1':box((x+xx*scale,y+yy*scale,x+(xx+1)*scale-1,y+(yy+1)*scale-1),ORANGE)
 if asleep:
  # Sleep symbol outside the silhouette; mascot itself remains unchanged.
  label('z',x+85,y-6,9,BLUE);label('Z',x+99,y-19,12,BLUE)
def person(x,y,t,typing=True,shock=False):
 # hoodie, chair and headphones; profile toward Clawd
 box((x-19,y+37,x+27,y+99),'#252b46');box((x-15,y+43,x+28,y+88),'#7788b5')
 box((x-12,y+88,x+2,y+119),'#363e5d');box((x+14,y+88,x+27,y+119),'#363e5d')
 box((x-17,y+116,x+3,y+122),'#d5d0c0');box((x+12,y+116,x+34,y+122),'#d5d0c0')
 box((x-20,y-3,x+25,y+38),'#e7b395');box((x-24,y-10,x+25,y+4),'#443a40')
 box((x-24,y-3,x-15,y+22),'#443a40');box((x-27,y+2,x-19,y+24),'#8f9dc4')
 box((x+25,y+2,x+30,y+23),'#8f9dc4');box((x-22,y-12,x+27,y-7),'#8f9dc4')
 for dx in [-6,14]:box((x+dx,y+12,x+dx+4,y+18),'#292538')
 if shock:box((x+4,y+27,x+11,y+35),'#67404a')
 else:box((x+2,y+28,x+12,y+30),'#67404a')
 if SPEAKER=='ПРОГРАММИСТ':box((x+2,y+27,x+12,y+30+int(t*15)%5),'#67404a')
 arm=round(math.sin(t*32)*2) if typing else 0
 box((x+24,y+49,x+41,y+59),'#7788b5');box((x+35,y+53+arm,x+49,y+62+arm),'#e7b395')
 box((x-15,y+53,x-7,y+66),'#e7b395')
def room(t,act,sleep=None):
 # wall, framed poster, window with rainy city, desk and foreground floor
 box((0,139,360,529),'#22273c');box((0,139,360,145),'#343b54')
 for y in [190,260,330,400]:box((0,y,360,y),'#292e45')
 window(240,165,99,129,'#535f80','#151c32')
 for i in range(7):
  xx=247+i*13;hh=[38,64,31,70,52,44,60][i]
  box((xx,286-hh,xx+9,289),'#2a3652')
  for yy in range(285-hh,282,12):box((xx+3,yy,xx+5,yy+3),'#a17d67')
 for i in range(11):
  xx=245+(i*19)%88; yy=170+(int(t*50)+i*23)%112
  box((xx,yy,xx,yy+6),'#556b90')
 window(22,167,63,82,'#6d6c7e','#34354b');label('SHIP',53,183,9,ORANGE,True);label('IT.',53,203,12,CREAM,True)
 box((17,264,92,269),'#a47661');box((68,245,80,263),'#d7aa7d');box((64,240,84,246),GREEN)
 for dx in [-3,4,10]:box((69+dx,228,72+dx,245),GREEN)
 # amber lamp
 box((18,310,23,395),'#7b7d8e');box((10,392,36,397),'#7b7d8e');d.polygon([(12,299),(33,299),(43,318),(3,318)],fill='#d7aa7d')
 box((0,466,360,529),'#191d30')
 for x in range(-180,540,45):d.line((180,465,x,529),fill='#2b324b',width=1)
 for yy in [478,498,528]:box((0,yy,360,yy),'#2b324b')
 person(86,353,t,typing=act in [0,3],shock=act in [1,4])
 # desk, two devices and mug
 box((34,427,218,437),'#b28368');box((39,437,47,506),'#70584f');box((203,437,211,506),'#70584f')
 box((121,382,193,421),'#101522');box((125,386,189,416),'#314350');box((153,420,162,427),'#757b91')
 for i in range(4):box((129,391+i*6,148+(int(t*9+i)%5)*7,392+i*6),GREEN if act not in [1,4] else RED)
 box((120,423,187,426),'#757b91');box((51,412,64,426),CREAM);box((63,415,68,421),CREAM)
 for i in range(3):box((55+i*3,400-round((t*10+i*6)%9),56+i*3,403-round((t*10+i*6)%9)),'#6c6872')
 # Clawd on the floor next to programmer, exact reference silhouette
 box((242,488,334,492),'#101522');clawd(242,415,t,5,asleep=act in [1,4,5] if sleep is None else sleep)
 label('ПРОГРАММИСТ',88,514,6,BLUE,True);label('CLAWD',287,501,7,ORANGE,True)

def frame(t):
 global d,SPEAKER
 actual=t
 active=next((clip for clip in CLIPS if clip[0]<=actual<clip[1]),None)
 SPEAKER=active[3] if active else None
 t=float(np.interp(actual,[0,9.5,13,18,27,34,40],[0,4,7,11,16,21,25]))
 act=0 if t<4 else 1 if t<7 else 2 if t<11 else 3 if t<16 else 4 if t<21 else 5
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
 label('CLAUDE CODE',18,18,8,ORANGE);label('01 / ОДИН ВЕЧЕР',342,20,6,BLUE,True) if False else label('PIXEL FILM',262,20,7,BLUE)
 titles=[['ЩАС БЫСТРО','ДОПИШЕМ ПРОЕКТ.'],['ПЕРВЫЙ ЛИМИТ.','ВЕЧЕР ТОЛЬКО НАЧАЛСЯ.'],['А ЕСЛИ...','КУПИТЬ ПОДПИСКУ?'],['ОПЛАЧЕНО.','МЫ СНОВА В ДЕЛЕ!'],['ПЯТЬ МИНУТ СПУСТЯ*','ЗНАКОМОЕ ОКНО.'],['ПОДПИСКА ЕСТЬ.','БЕЗЛИМИТА — НЕТ.']]
 centered(titles[act],57,12 if act in [1,4] else 14,RED if act in [1,4] else CREAM,24)
 box((18,121,342,123),'#41465e')
 room(t,act)
 if SPEAKER:
  x,y,w=(15,287,164) if SPEAKER=='ПРОГРАММИСТ' else (214,342,130)
  speech(['Говорит...' if SPEAKER=='ПРОГРАММИСТ' else 'Клод онлайн'],x,y,w)
  # Moving audio bars make speaker identity visible while retaining Clawd's face.
  bx,by=(24,322) if SPEAKER=='ПРОГРАММИСТ' else (314,399)
  for bar in range(4):
   height=3+round(abs(math.sin(actual*18+bar))*10)
   box((bx+bar*5,by-height,bx+bar*5+2,by),GREEN if SPEAKER=='ПРОГРАММИСТ' else ORANGE)
 if act==3:
  for i in range(6):spark(219+(i*23)%119,310+(int(t*40)+i*17)%95,GREEN)
 # A story prop, not a permanent giant terminal overlay.
 if act in [1,4]:
  window(103,178,228,97,RED,'#2f2637');label('×  LIMIT REACHED',117,193,10,RED)
  label('Лимит использования',117,219,8);label('Попробуйте позже.',117,239,8,BLUE)
 elif act==2:
  window(99,174,234,107,ORANGE,'#2b2939');label('CLAUDE / ПОДПИСКА',115,190,9,ORANGE)
  if t<9.2:
   label('Разблокировать надежду?',111,219,8);box((121,244,311,266),GREEN);label('КУПИТЬ',216,252,10,BG,True)
   px=280-round(min(1,(t-7)/2.2)*45);py=272-round(min(1,(t-7)/2.2)*17)
   d.polygon([(px,py),(px,py+14),(px+4,py+10),(px+10,py+10)],fill=CREAM)
  else:
   label('ОПЛАТА ПРОШЛА',216,222,12,GREEN,True);label('мотивация +100',216,251,8,CREAM,True)
   for i in range(15):
    xx=20+(i*53)%320; yy=155+(i*31+int((t-9.2)*80))%160
    box((xx,yy,xx+3,yy+5),[GREEN,ORANGE,CREAM][i%3])
 elif act==3:
  window(106,187,225,80,GREEN,'#233438');label('> building the dream',118,203,8,GREEN)
  progress=min(1,(t-11)/4.5);box((119,229,318,241),'#141f2c');box((119,229,119+199*progress,241),GREEN)
  label(f'{int(progress*100):02d}%  /  ещё одну фичу?',118,251,7,CREAM)
 elif act==0:
  window(105,181,227,83,BLUE);label('> claude',119,194,9,ORANGE)
  s='Сделай проект мечты';label(s[:int(t*8)],119,221,9)
  if int(t*3)%2:box((119,246,124,253),GREEN)
 else:
  window(107,181,225,85,ORANGE);label('> /пойти_спать',120,198,10,GREEN);label('Задача выполнена.',120,229,9)
 # cinematic caption strip
 box((0,534,360,640),'#101421')
 captions=[['ОДНА МЕЛОЧЬ.','ПОСЛЕДНИЙ ПРОМПТ. ЧЕСТНО.'],['НАПАРНИК УШЁЛ НА ПЕРЕРЫВ.','ТЕБЯ НЕ СПРОСИЛ.'],['КОШЕЛЁК: − ДЕНЬГИ','НАДЕЖДА: +100'],['КЛАВИАТУРА ГОРИТ.','ДЕДЛАЙН УЖЕ НЕ СТРАШЕН.'],['ЛИМИТ ВЕРНУЛСЯ.','ДЕНЬГИ — НЕТ.'],['КУПИЛ НЕ БЕЗЛИМИТ.','КУПИЛ НАДЕЖДУ.']]
 if active:
  label(active[3],180,541,7,ORANGE if SPEAKER=='КЛОД' else BLUE,True)
  centered(textwrap.wrap(active[4],width=36),558,8,CREAM,15)
 else:
  centered(captions[act],551,10,ORANGE if act==5 else CREAM,22)
 label('*ШУТКА. НЕ УСЛОВИЯ ПОДПИСКИ.',180,602,6,BLUE,True)
 box((18,622,342,624),'#343b54');box((18,622,18+t/25*324,624),ORANGE)
 # brief camera shutter-style pixel transition between acts
 for cut in [4,7,11,16,21]:
  dt=t-cut
  if 0<=dt<.12:
   for y in range(0,H,16):box((0,y,W,y+int((1-dt/.12)*14)),BG)
 return im

if __name__ == '__main__':
 # Entirely synthesized soundtrack: no downloaded music or sound samples.
 rng=np.random.default_rng(41); mix=np.zeros((40*SR,2),dtype=np.float64)
 def synth(at,dur,hz=440,vol=.1,kind='pulse',pan=0,end=None):
  n=int(dur*SR);tt=np.arange(n)/SR
  if kind=='noise':sig=rng.uniform(-1,1,n)
  else:
   f=np.linspace(hz,end if end is not None else hz,n);phase=np.cumsum(f)/SR
   if kind=='sine':sig=np.sin(2*np.pi*phase)
   elif kind=='tri':sig=2*np.abs(2*(phase%1)-1)-1
   else:sig=np.where(phase%1<.25,1.,-.333)
  env=np.minimum(tt/.004,1)*np.minimum((dur-tt)/.035,1)
  if kind=='noise':env*=np.exp(-tt*25)
  sig*=env*vol;i=round(at*SR);n=min(n,len(mix)-i)
  if n>0:
   mix[i:i+n,0]+=sig[:n]*(1-pan*.6);mix[i:i+n,1]+=sig[:n]*(1+pan*.6)
 def midi(n):return 440*2**((n-69)/12)
 # Original four-bar loop, quieter and minor/downward during limit scenes.
 mel=[72,76,79,76,74,71,67,71,69,72,76,72,67,71,74,71]
 for k in range(160):
  at=k*.25;sad=9.5<=at<13 or 27<=at<34
  note=mel[k%16]-(3 if sad else 0)
  synth(at,.14,midi(note),.035 if not sad else .018,'tri',.45)
  if k%2==0:synth(at,.21,midi([48,45,41,43][k//8%4]),.055,'tri',-.25)
  if k%2==1:synth(at,.025,vol=.025,kind='noise',pan=.7)
  if k%4==0:synth(at,.10,95,.07,'sine',end=37)
 # Key switches, staggered stereo clicks in productive scenes.
 for start,stop in [(0,9.3),(18,26.9)]:
  for at in np.arange(start+.1,stop,.105):
   synth(float(at),.027,float(rng.integers(600,1600)),.055,'noise',-.65)
   synth(float(at),.018,1800,.028,'pulse',-.55,end=650)
 # Mouse click; payment/coin cascade; upward start sound.
 for at in [13.4,16.62]:synth(at,.045,vol=.11,kind='noise',pan=-.4)
 for i,n in enumerate([76,83,88,95]):synth(16.75+i*.10,.17,midi(n),.12,'pulse',.2)
 for i,n in enumerate([60,64,67,72,76,79]):synth(18+i*.075,.16,midi(n),.10,'tri',.1)
 # Double warning and power-down, timed exactly to both limit reveals.
 for at in [9.5,27]:
  for off in [0,.20]:synth(at+off,.14,740,.14,'pulse',.45)
  synth(at+.45,.60,440,.13,'pulse',.4,end=65)
 # Terminal completion and sleepy descending ending.
 for i,n in enumerate([72,67,64,60]):synth(34.1+i*.22,.29,midi(n),.10,'tri',.25)
 # Small synthetic snore (not a voice sample).
 for at in [39.0]:
  synth(at,.45,65,.065,'tri',.55,end=95);synth(at+.46,.23,90,.045,'tri',.55,end=45)
 # Duck background under speech, then mix generated voices with gentle stereo placement.
 duck=np.ones(len(mix))
 for start,end,name,speaker,words in CLIPS:
  lo=max(0,int((start-.1)*SR));a=int(start*SR);b=int(end*SR);hi=min(len(mix),int((end+.2)*SR))
  duck[lo:a]=np.minimum(duck[lo:a],np.linspace(1,.23,a-lo))
  duck[a:b]=np.minimum(duck[a:b],.23)
  duck[b:hi]=np.minimum(duck[b:hi],np.linspace(.23,1,hi-b))
 mix*=duck[:,None]
 ff=imageio_ffmpeg.get_ffmpeg_exe()
 for start,end,name,speaker,words in CLIPS:
  result=subprocess.run([ff,'-v','error','-i',str(ROOT/'assets/voices'/name),'-f','f32le','-ac','1','-ar',str(SR),'-'],capture_output=True,check=True)
  voice=np.frombuffer(result.stdout,dtype='<f4').astype(np.float64)
  # Peak normalization with cap; no dialogue overlaps or speed changes.
  peak=np.max(np.abs(voice));voice*=min(2.5,.73/max(peak,1e-6))
  edge=min(220,len(voice)//2);voice[:edge]*=np.linspace(0,1,edge);voice[-edge:]*=np.linspace(1,0,edge)
  i=int(start*SR);n=min(len(voice),len(mix)-i);pan=-.10 if speaker=='ПРОГРАММИСТ' else .10
  mix[i:i+n,0]+=voice[:n]*(1-pan);mix[i:i+n,1]+=voice[:n]*(1+pan)
 mix*=np.minimum(np.arange(len(mix))/(SR*.05),1)[:,None]
 mix*=np.minimum((len(mix)-np.arange(len(mix)))/(SR*.5),1)[:,None]
 mix=np.tanh(mix*1.2)*.93
 wav=OUT/'soundtrack.wav'
 with wave.open(str(wav),'wb') as f:
  f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes((mix*32767).astype('<i2').tobytes())
 def stamp(t):
  ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
 (OUT/'dialogue-40s.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{speaker}: {words}' for i,(a,b,_,speaker,words) in enumerate(CLIPS))+'\n')
 (OUT/'dialogue-40s.json').write_text(json.dumps([dict(start=a,end=b,file=name,speaker=speaker,text=words) for a,b,name,speaker,words in CLIPS],ensure_ascii=False,indent=2)+'\n')
 dest=OUT/'claude-code-pixel-40s-voiced.mp4'
 cmd=[ff,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','360x640','-r','30','-i','-','-i',str(wav),'-vf','scale=720:1280:flags=neighbor','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t','40','-movflags','+faststart',str(dest)]
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
 for i in range(1200):
  im=frame(i/30)
  if i==705:im.resize((720,1280),Image.Resampling.NEAREST).save(OUT/'preview-40s.png')
  p.stdin.write(im.tobytes())
 p.stdin.close()
 if p.wait():raise RuntimeError('Encoding failed')
 subprocess.run([ff,'-y','-i',str(wav),'-c:a','libmp3lame','-b:a','192k',str(OUT/'soundtrack-40s-voiced.mp3')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 print(dest)
