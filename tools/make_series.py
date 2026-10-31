"""Render two additional 25-second voiced pixel shorts. Reuses the original room art.
Run: .venv/bin/python tools/make_series.py
"""
import json, math, subprocess, textwrap, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import imageio_ffmpeg
import make_video as art
ROOT=art.ROOT; OUT=art.OUT; SR=44100; FF=imageio_ffmpeg.get_ffmpeg_exe()
SERIES=[
 dict(id='fix',file='one-small-fix-25s',title='ОДНА МАЛЕНЬКАЯ ПРАВКА',
  headlines=[['ПРОСТО СМЕНИ ЦВЕТ.','БОЛЬШЕ НИЧЕГО.'],['КНОПКА ГОТОВА.','АРХИТЕКТУРА — НОВАЯ.'],['А ГДЕ САЙТ?','И ГДЕ КНОПКА?!'],['ЧИСТЫЙ КОД.','ОЧЕНЬ ЧИСТЫЙ.'],['ЛУЧШАЯ ФИЧА —','КНОПКА «ОТКАТИТЬ».']],
  words=['Клод, просто сделай кнопку зелёной. Больше ничего!','Готово! Заодно я немного улучшил архитектуру.','А почему сайт белый? И где вообще кнопка?','Зато теперь код чистый. Даже слишком чистый.','Откатывай! Зелёной будет только моя злость.']),
 dict(id='deploy',file='friday-deploy-25s',title='ДЕПЛОЙ В ПЯТНИЦУ',
  headlines=[['ПЯТНИЦА. 18:59.','ОДИН БЫСТРЫЙ ДЕПЛОЙ.'],['ЛОКАЛЬНО РАБОТАЕТ.','ЧТО МОЖЕТ ПОЙТИ НЕ ТАК?'],['СЕРВЕР ЛЁГ.','ВЫХОДНЫЕ ТОЖЕ.'],['ТЕСТЫ ПРОЙДЕНЫ.','НО ЕСТЬ НЮАНС.'],['ВЫХОДНЫЕ: OFFLINE.','МЫ: ВСЁ ЕЩЁ ONLINE.']],
  words=['Пятница, вечер. Клод, быстро выложим сайт и домой!','У меня всё работает. Смело нажимай деплой!','Сервер упал! Ты вообще запускал тесты?','Конечно. Я мысленно проверил все сценарии.','Отлично. Тогда и выходные у нас мысленные.'])
]
TIMES=[.3,5.2,10.3,15.2,21.0]

def load_clips(config):
 clips=[]
 for i,(at,words) in enumerate(zip(TIMES,config['words'])):
  name=f"{config['id']}-{i+1:02}.wav"
  with wave.open(str(ROOT/'assets/voices'/name)) as w:duration=w.getnframes()/w.getframerate()
  clips.append(dict(start=at,end=at+duration,file=name,speaker='КЛОД' if i%2 else 'ПРОГРАММИСТ',text=words))
 for i,c in enumerate(clips):
  assert c['end']<=25
  if i:assert clips[i-1]['end']<c['start']
 return clips

def draw_frame(t,config,clips):
 act=min(4,int(t/5));local=t%5
 im=Image.new('RGB',(360,640),art.BG);art.d=ImageDraw.Draw(im)
 active=next((c for c in clips if c['start']<=t<c['end']),None)
 art.SPEAKER=active['speaker'] if active else None
 art.label('CLAUDE CODE',18,18,8,art.ORANGE)
 art.label('02 / FIX' if config['id']=='fix' else '03 / DEPLOY',247,20,7,art.BLUE)
 art.centered(config['headlines'][act],56,11 if config['id']=='deploy' else 12,art.RED if act==2 else art.CREAM,24)
 art.box((18,122,342,124),'#41465e')
 art.room(t,1 if act in [2,3] else 0,sleep=False)
 if active:
  x,y,w=(15,287,164) if art.SPEAKER=='ПРОГРАММИСТ' else (214,342,130)
  art.speech(['Говорит...' if art.SPEAKER=='ПРОГРАММИСТ' else 'Клод онлайн'],x,y,w)
  bx,by=(24,322) if art.SPEAKER=='ПРОГРАММИСТ' else (314,400)
  for i in range(4):
   h=3+round(abs(math.sin(t*17+i))*11)
   art.box((bx+i*5,by-h,bx+i*5+2,by),art.BLUE if art.SPEAKER=='ПРОГРАММИСТ' else art.ORANGE)
 edge=art.RED if act in [2,3] else art.GREEN
 art.window(104,177,230,104,edge)
 if config['id']=='fix':
  if act==0:
   art.label('app / button',118,190,9,art.BLUE)
   art.box((141,220,297,259),art.GREEN if local>2.7 else '#b47575')
   art.label('КНОПКА',219,234,12,art.BG,True)
   px=292-int(min(1,local/3)*44);py=262-int(min(1,local/3)*17)
   art.d.polygon([(px,py),(px,py+12),(px+4,py+9),(px+9,py+9)],fill=art.CREAM)
  elif act==1:
   art.label('> refactor --everything',116,192,8,art.ORANGE)
   for i,s in enumerate(['+ new_framework/','- old_website/','+ better_architecture/']):
    if local>i*.6:art.label(s,116,218+i*16,8,art.GREEN)
  elif act==2:
   art.box((106,179,332,279),'#f5f3ee');art.label('localhost / 404',116,190,8,'#98918c')
   art.label(' ',118,222,10)
   if int(t*4)%2:art.label('?',222,229,22,'#aaa39b',True)
  elif act==3:
   art.label('> git diff --stat',116,192,8,art.ORANGE)
   art.label('0 строк. 0 проблем.*',116,222,8,art.GREEN)
   art.label('*и 0 сайта',116,249,8,art.BLUE)
  else:
   art.label('> git restore website',116,192,8,art.GREEN)
   art.box((127,219,313,259),art.GREEN)
   art.label('ОТКАТИТЬ',220,235,12,art.BG,True)
   for i in range(4):art.spark(117+i*63,270+int(math.sin(t*5+i)*4),art.GREEN)
 else:
  if act==0:
   art.label('FRIDAY / 18:59',219,191,11,art.ORANGE,True)
   art.box((129,222,310,262),art.GREEN);art.label('DEPLOY',219,235,14,art.BG,True)
  elif act==1:
   art.label('LOCALHOST: OK',118,192,11,art.GREEN)
   art.label('tests: trust_me_bro',118,222,8,art.BLUE)
   p=min(1,local/3.6);art.box((118,248,319,261),'#131e2b');art.box((118,248,118+201*p,261),art.GREEN)
  elif act==2:
   if int(t*5)%2:art.box((106,179,332,279),'#402c3a')
   art.label('500',219,192,24,art.RED,True)
   art.label('INTERNAL SERVER ERROR',219,229,9,art.RED,True)
   art.label('все планы: отменены',219,257,8,art.CREAM,True)
  elif act==3:
   art.label('ТЕСТОВАЯ СРЕДА:',219,192,9,art.ORANGE,True)
   art.label('ВООБРАЖЕНИЕ',219,221,14,art.GREEN,True)
   art.label('passed: наверное',219,254,8,art.BLUE,True)
  else:
   art.label('WEEKEND NOT FOUND',219,191,11,art.RED,True)
   for i,s in enumerate(['SAT:  fix production','SUN:  fix production','MON:  need vacation']):art.label(s,116,217+i*18,8,art.BLUE)
 art.box((0,534,360,640),'#101421')
 if active:
  art.label(active['speaker'],180,541,7,art.ORANGE if art.SPEAKER=='КЛОД' else art.BLUE,True)
  art.centered(textwrap.wrap(active['text'],36),558,8,art.CREAM,15)
 else:art.centered([config['title']],567,8,art.ORANGE)
 art.label('НЕОФИЦИАЛЬНАЯ ПИКСЕЛЬНАЯ КОМЕДИЯ',180,602,6,art.BLUE,True)
 art.box((18,622,342,624),'#343b54');art.box((18,622,18+t/25*324,624),art.ORANGE)
 for cut in [5,10,15,20]:
  if 0<=t-cut<.10:
   for y in range(0,640,16):art.box((0,y,360,y+int((1-(t-cut)/.1)*14)),art.BG)
 return im

def make_audio(config,clips):
 rng=np.random.default_rng(76 if config['id']=='fix' else 93)
 mix=np.zeros((25*SR,2),dtype=np.float64)
 def tone(at,dur,hz=440,vol=.05,kind='tri',end=None,pan=0):
  n=int(dur*SR);tt=np.arange(n)/SR
  if kind=='noise':sig=rng.uniform(-1,1,n)*np.exp(-tt*24)
  else:
   phase=np.cumsum(np.linspace(hz,hz if end is None else end,n))/SR
   sig=np.sin(2*np.pi*phase) if kind=='sine' else (2*np.abs(2*(phase%1)-1)-1)
  sig*=np.minimum(tt/.004,1)*np.minimum((dur-tt)/.035,1)*vol
  i=int(at*SR);n=min(n,len(mix)-i)
  if n>0:
   mix[i:i+n,0]+=sig[:n]*(1-pan*.5);mix[i:i+n,1]+=sig[:n]*(1+pan*.5)
 motif=[72,74,79,76,72,67,71,74] if config['id']=='fix' else [67,71,74,79,76,74,71,62]
 for k in range(100):
  at=k*.25;note=motif[k%8]-(3 if 10<=at<20 else 0)
  tone(at,.14,440*2**((note-69)/12),.038,pan=.4)
  if k%2==0:tone(at,.20,110 if k%8<4 else 82.4,.05,'sine',pan=-.3)
  if k%2:tone(at,.03,vol=.025,kind='noise',pan=.6)
 for at in np.arange(.1,9.8,.17):tone(float(at),.023,vol=.065,kind='noise',pan=-.6)
 for at in [1.5,5.0,20.1]:tone(at,.05,vol=.1,kind='noise')
 for i,f in enumerate([660,880,1100]):tone(5.0+i*.12,.13,f,.10)
 tone(10,.65,660,.15,end=75)
 for at in [10,10.22]:tone(at,.12,740,.14,pan=.4)
 for i,f in enumerate([440,349,261]):tone(15+i*.2,.19,f,.09)
 for i,f in enumerate([523,659,784] if config['id']=='fix' else [392,330,261]):tone(20.1+i*.18,.20,f,.10)
 duck=np.ones(len(mix))
 for c in clips:
  a=int(c['start']*SR);b=int(c['end']*SR);lo=max(0,a-4410);hi=min(len(mix),b+8820)
  duck[lo:a]=np.minimum(duck[lo:a],np.linspace(1,.22,a-lo));duck[a:b]=np.minimum(duck[a:b],.22)
  duck[b:hi]=np.minimum(duck[b:hi],np.linspace(.22,1,hi-b))
 mix*=duck[:,None]
 for c in clips:
  p=subprocess.run([FF,'-v','error','-i',str(ROOT/'assets/voices'/c['file']),'-f','f32le','-ac','1','-ar',str(SR),'-'],capture_output=True,check=True)
  v=np.frombuffer(p.stdout,dtype='<f4').astype(np.float64);v*=min(2.5,.73/max(np.max(np.abs(v)),1e-6))
  edge=min(220,len(v)//2);v[:edge]*=np.linspace(0,1,edge);v[-edge:]*=np.linspace(1,0,edge)
  i=int(c['start']*SR);n=min(len(v),len(mix)-i);pan=.10 if c['speaker']=='КЛОД' else -.10
  mix[i:i+n,0]+=v[:n]*(1-pan);mix[i:i+n,1]+=v[:n]*(1+pan)
 mix*=np.minimum(np.arange(len(mix))/(SR*.05),1)[:,None]
 mix*=np.minimum((len(mix)-np.arange(len(mix)))/(SR*.5),1)[:,None]
 mix=np.tanh(mix*1.2)*.93
 wav=OUT/(config['file']+'.wav')
 with wave.open(str(wav),'wb') as f:
  f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes((mix*32767).astype('<i2').tobytes())
 return wav

def stamp(t):
 ms=round(t*1000);return f'00:{ms//60000:02}:{ms//1000%60:02},{ms%1000:03}'

def render(config):
 clips=load_clips(config);wav=make_audio(config,clips);dest=OUT/(config['file']+'.mp4')
 (OUT/(config['file']+'.json')).write_text(json.dumps(clips,ensure_ascii=False,indent=2)+'\n')
 (OUT/(config['file']+'.srt')).write_text('\n\n'.join(f"{i+1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['speaker']}: {c['text']}" for i,c in enumerate(clips))+'\n')
 cmd=[FF,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','360x640','-r','30','-i','-','-i',str(wav),'-vf','scale=720:1280:flags=neighbor','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t','25','-movflags','+faststart',str(dest)]
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
 for i in range(750):
  im=draw_frame(i/30,config,clips)
  if i==340:im.resize((720,1280),Image.Resampling.NEAREST).save(OUT/(config['file']+'.png'))
  p.stdin.write(im.tobytes())
 p.stdin.close()
 if p.wait():raise RuntimeError('Encoder failed')
 print(dest)

if __name__=='__main__':
 for config in SERIES:render(config)
