"""Exactly 60 seconds: eight years old, 10 June 2021, Gagarin Park, Komsomolsk.
Real park photographs, an explicitly imagined bedroom, original score and narration.
Run: .venv/bin/python tools/make_nostalgia.py
"""
from pathlib import Path
import json,math,re,subprocess,wave
import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageEnhance,ImageOps
import make_history as a
ROOT=a.ROOT;AS=ROOT/'assets/nostalgia';OUT=ROOT/'exports/nostalgia';OUT.mkdir(parents=True,exist_ok=True)
STORY=json.loads((AS/'story.json').read_text());FF=a.FF;SR=44100;FPS=30
CREAM='#fff2d4';INK='#493c3c';GOLD='#ffdd96';PALE='#d8c5a6'
rr,rect,ell,line,poly,txt=a.rr,a.rect,a.ell,a.line,a.poly,a.txt

def grade(image):
 ar=np.asarray(image.convert('RGB')).astype(np.float32)
 ar=ar*np.array([1.018,1.005,.968])+np.array([2.,1.,2.])
 return ImageEnhance.Contrast(Image.fromarray(np.clip(ar,0,255).astype('uint8'))).enhance(.97)
PHOTOS={k:grade(Image.open(AS/'photos'/name)) for k,name in {
 'entrance':'entrance-2017.jpg','alley':'alley-2016.jpg','train':'train-2016.jpg','park':'park-2016.jpg'}.items()}
ROOM=grade(Image.open(AS/'morning-room.jpg'))
BACK={k:ImageEnhance.Brightness(ImageOps.fit(im,(720,1280)).filter(ImageFilter.GaussianBlur(25))).enhance(.65) for k,im in PHOTOS.items()}
ROOM=ImageOps.fit(ROOM,(720,1280));rng=np.random.default_rng(2021)
# Small low-amplitude grain textures are cached, not expensive per-frame noise.
GRAIN=[]
for i in range(12):
 ar=rng.integers(85,171,(320,180),dtype=np.uint8)
 GRAIN.append(Image.fromarray(ar).resize((720,1280),Image.Resampling.BILINEAR).convert('RGB'))
# Caption shadow and corner fade retain the bright summer palette above.
y=np.arange(1280)[:,None];bottom=np.clip((y-885)/360,0,1)*211
BOTTOM=Image.fromarray(np.tile(bottom.astype('uint8'),(1,720)));DARK=Image.new('RGB',(720,1280),'#322a2b')

def shadow_text(s,x,y,size=20,c=CREAM,center=True):
 txt(s,x+.7,y+1.2,size,'#54403b',center);txt(s,x,y,size,c,center)
def dust(t):
 for i in range(18):
  x=(i*83+t*(2+i%3))%380-10;yy=130+(i*47-t*(3+i%4))%350
  alpha=int(30+abs(math.sin(t*.5+i))*34)
  # Transparent pollen glows without inventing park structures.
  r=.5+(i%3)*.25
  ell((x-r,yy-r,x+r,yy+r),'#dacbae')
def photo(kind,t,local,caption=None):
 a.im=BACK[kind].copy();a.d=ImageDraw.Draw(a.im)
 # A framed, uncropped-looking original photo rather than an AI replacement.
 landscape=kind=='entrance';x,y,w,h=(18,151,324,266) if landscape else (18,134,324,349)
 rr((x+2,y+5,x+w+2,y+h+5),'#51463f',3)
 rr((x,y,x+w,y+h),'#f5e7c8',3)
 px,py,pw,ph=(x+10,y+10,w-20,228 if landscape else 304)
 original=PHOTOS[kind];factor=1+min(.035,local*.006)
 img=ImageOps.fit(original,(round(pw*2*factor),round(ph*2*factor)),method=Image.Resampling.LANCZOS)
 left=(img.width-round(pw*2))//2+int(math.sin(t*.3));top=(img.height-round(ph*2))//2
 img=img.crop((left,top,left+round(pw*2),top+round(ph*2)))
 a.im.paste(img,(round(px*2),round(py*2)));a.d=ImageDraw.Draw(a.im)
 text='Парк Гагарина · настоящий снимок 2017' if landscape else 'Парк Гагарина · фото А. Карлина, 2016'
 txt(text,180,y+h-20,8,INK,True)
 shadow_text(caption or 'ЛЕТО, КОТОРОЕ ХОЧЕТСЯ ВЕРНУТЬ',180,105,12,GOLD)
 dust(t)
def room(t,local,zoomkind='wake'):
 factor=1.025+local*.004
 img=ROOM.resize((round(720*factor),round(1280*factor)),Image.Resampling.BICUBIC)
 xx=(img.width-720)//2+round(math.sin(t*.4)*3);yy=(img.height-1280)//2
 if zoomkind=='window':yy=max(0,yy-17)
 a.im=img.crop((xx,yy,xx+720,yy+1280));a.d=ImageDraw.Draw(a.im);dust(t)
 if zoomkind=='calendar':
  rr((35,147,325,333),'#f6e8c9',7,'#c6a87b',2)
  txt('ЧЕТВЕРГ',180,164,14,'#a16a54',True);txt('10',180,190,42,'#91544a',True)
  txt('ИЮНЯ 2021',180,249,27,INK,True)
  rr((123,292,237,324),'#c8a26e',15);txt('МНЕ 8 ЛЕТ',180,299,15,CREAM,True)
 if zoomkind=='wake':
  opening=min(1,max(0,(t-.12)/1.75));height=round(640*(1-opening)**1.5)
  if height>0:
   rect((0,0,360,height/2),'#29292c');rect((0,640-height/2,360,640),'#29292c')

def icecream(t):
 # A small scrapbook illustration over the genuine alley photograph.
 photo('alley',t,t%4,'ЛЕТО ПАХНЕТ ВАНИЛЬЮ')
 x=242+math.sin(t*1.7)*2;y=340+math.sin(t*1.4)*2
 poly([(x-30,y),(x+31,y),(x+2,y+113)],'#c99962',None)
 for i in range(5):
  line([(x-24+i*11,y+9),(x-9+i*5,y+74)],'#b27d53',1)
 ell((x-40,y-54,x+39,y+11),'#fff1c9');ell((x-27,y-61,x+23,y-10),'#fff6de')
 rr((x+13,y-4,x+20,y+31),'#fff1c9',3)
 # A simplified small hand; no user likeness is asserted.
 rr((x-21,y+71,x+18,y+112),'#dda586',12);poly([(x-16,y+91),(x+13,y+102),(x+42,535),(x-27,535)],'#dda586',None)

def swing(t):
 photo('alley',t,t%4,'ЕЩЁ ПЯТЬ МИНУТОЧЕК')
 # POV feet and chains drift independently from the photographic background.
 phase=math.sin(t*1.45);yy=420+phase*17
 for x in [42,319]:
  line([(x,140),(x+phase*6,yy)],'#9e9b8d',3)
  for y in range(151,int(yy),14):ell((x-2+phase*3,y,x+2+phase*3,y+7),None,'#ddd3b5',1)
 for dx,side in [(-1,-1),(1,1)]:
  xx=180+dx*33
  poly([(xx-15,496),(xx+16,496),(xx+21,yy+27),(xx-9,yy+20)],'#7296ad',None)
  rr((xx-15,yy,xx+22,yy+31),'#e5ddc6',9);line([(xx-9,yy+14),(xx+16,yy+14)],'#c08c7d',2)

def hands(t):
 photo('entrance',t,t%4,'МАМ, МОЖНО ЕЩЁ ПОГУЛЯТЬ?')
 # Warm, intentionally illustrative gesture, not a fabricated family photograph.
 poly([(32,526),(65,513),(149,405),(124,382)],'#e6b394',None)
 ell((117,367,153,415),'#e6b394')
 poly([(279,526),(309,526),(183,373),(153,394)],'#d6a486',None)
 ell((143,359,188,410),'#d6a486')
 line([(132,388),(148,396),(162,388)],'#c68d70',2)

def prepare():
 mix=np.zeros((60*SR,2),dtype=np.float32);music=np.zeros_like(mix);rng=np.random.default_rng(6102021)
 def tone(at,dur,f,vol=.04,kind='piano',pan=0,end=None):
  n=int(dur*SR);tt=np.arange(n,dtype=np.float32)/SR
  freq=np.linspace(f,f if end is None else end,n,dtype=np.float32)*(1+.0013*np.sin(tt*2*np.pi*.45))
  phase=np.cumsum(freq)/SR
  if kind=='piano':
   v=np.sin(2*np.pi*phase)*np.exp(-tt*2.7)+.23*np.sin(2*np.pi*phase*2.003)*np.exp(-tt*5)+.07*np.sin(2*np.pi*phase*3)*np.exp(-tt*8)
  else:v=np.sin(2*np.pi*phase)
  env=np.minimum(tt/.015,1)*np.minimum((dur-tt)/.15,1);v*=env*vol
  a0=int(at*SR);n=min(n,len(music)-a0)
  if n>0:music[a0:a0+n,0]+=v[:n]*(1-pan*.4);music[a0:a0+n,1]+=v[:n]*(1+pan*.4)
 midi=lambda n:440*2**((n-69)/12)
 # Original melody: no commercial nostalgic song or borrowed soundtrack.
 motif=[64,67,71,74,76,71,69,67,64,62,67,71,69,67,64,62]
 beat=60/76
 for i in range(75):tone(i*beat,1.35,midi(motif[i%16]),.050,'piano',.3)
 for bar in range(19):
  chord=[[48,55,59,64],[45,52,55,60],[41,48,52,57],[43,50,55,59]][bar%4]
  for n in chord:tone(bar*4*beat,3.8,midi(n),.013,'pad',-.25)
 # Low, filtered summer air and delicate analog texture.
 wind=rng.normal(0,1,len(music)).astype(np.float32);wind=np.convolve(wind,np.ones(35,dtype=np.float32)/35,mode='same')
 music[:,0]+=wind*.008;music[:,1]+=wind*.007
 for at in [1.8,5,9,14.5,18,23,26.8,30,35,39,43,48,54,57]:
  for j in range(3):tone(at+j*.14,.11,2600+j*310,.008,'bird',.65,end=3500+j*150)
 for at in [36.2,37.7,39.1]:tone(at,.32,620,.016,'creak',-.5,end=430)
 for at in [15.5,16.2,17,18.0,24.3,25.1]:tone(at,.08,95,.018,'step',-.2,end=50)
 timeline=[]
 for clip in STORY['dialogue']:
  raw=subprocess.run([FF,'-v','error','-i',str(AS/'voice'/clip['file']),'-f','f32le','-ac','1','-ar',str(SR),'-'],capture_output=True,check=True)
  voice=np.frombuffer(raw.stdout,dtype='<f4').copy();voice*=min(2.2,.70/max(np.max(np.abs(voice)),1e-6))
  start=clip['start'];end=start+len(voice)/SR;assert end<60
  i=int(start*SR);mix[i:i+len(voice)]+=voice[:,None]
  lo=max(0,i-int(.15*SR));hi=min(len(music),i+len(voice)+int(.25*SR))
  music[lo:i]*=np.linspace(1,.38,i-lo)[:,None];music[i:i+len(voice)]*=.38;music[i+len(voice):hi]*=np.linspace(.38,1,hi-i-len(voice))[:,None]
  step=441;n=len(voice)//step;rms=np.sqrt(np.mean(voice[:n*step].reshape(n,step)**2,axis=1));active=np.where(rms>max(.008,float(np.max(rms))*.06),1,.06);cum=np.cumsum(active)
  words=clip['text'].split();weights=np.array([max(1,len(re.findall('[аеёиоуыэюяАЕЁИОУЫЭЮЯ]',w)))+(.8 if re.search('[.!?]$',w) else .15) for w in words])
  bounds=np.concatenate([[0],np.cumsum(weights)/weights.sum()*cum[-1]]);times=np.interp(bounds,cum,np.arange(n)*step/SR,left=0,right=len(voice)/SR)+start
  cues=[dict(word=w,start=float(times[j]),end=float(times[j+1])) for j,w in enumerate(words)];groups=[];group=[]
  for w in cues:
   if group and (sum(len(z['word'])+1 for z in group)+len(w['word'])>40 or len(group)>=6):groups.append(group);group=[]
   group.append(w)
   if re.search('[.!?]$',w['word']) and len(group)>1:groups.append(group);group=[]
  if group:groups.append(group)
  timeline.append(dict(clip,end=end,words=cues,groups=groups))
 for i,c in enumerate(timeline):
  if i:assert timeline[i-1]['end']<c['start']
 mix+=music
 fade=np.minimum(np.arange(len(mix))/(SR*.18),1)*np.minimum((len(mix)-np.arange(len(mix)))/(SR*1.5),1)
 mix*=fade[:,None];mix*=min(1,.94/max(np.max(np.abs(mix)),1e-6))
 path=OUT/'soundtrack.wav'
 with wave.open(str(path),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes((mix*32767).astype('<i2').tobytes())
 return timeline,path

def captions(t,timeline):
 clip=next((c for c in timeline if c['start']<=t<c['end']),None)
 if not clip:return
 group=next((g for g in clip['groups'] if g[0]['start']<=t<g[-1]['end']),None)
 if not group:return
 lines=[[]]
 for w in group:
  candidate=' '.join(z['word'] for z in lines[-1]+[w])
  if a.tw(candidate,20)>318:lines.append([w])
  else:lines[-1].append(w)
 for j,ln in enumerate(lines[:2]):
  width=sum(a.tw(w['word']+' ',20) for w in ln)-a.tw(' ',20);x=(360-width)/2
  for w in ln:
   key=re.search('восемь|двадцать|первый|июня|лет|мам|парк|Гагарина|минут',w['word'],re.I)
   color='#cbbfae' if t>=w['end'] else (GOLD if key else CREAM)
   shadow_text(w['word'],x,510+j*27,20,color,False);x+=a.tw(w['word']+' ',20)

def frame(t,timeline):
 shot=next((s for s in STORY['shots'] if s['start']<=t<s['end']),STORY['shots'][-1]);kind=shot['kind'];local=t-shot['start']
 if kind in ['wake','calendar','bed','window']:room(t,local,kind)
 elif kind in ['entrance','alley','train']:photo(kind,t,local)
 elif kind=='icecream':icecream(t)
 elif kind=='swing':swing(t)
 elif kind=='hands':hands(t)
 else:photo('entrance',t,local,'ХОЧУ ЕЩЁ РАЗ ПРОЖИТЬ ЭТОТ ДЕНЬ')
 # Subtle film softness/grain is applied before the crisp phone-readable lettering.
 a.im=Image.blend(a.im,GRAIN[int(t*12)%len(GRAIN)],.025)
 a.im=Image.composite(DARK,a.im,BOTTOM);a.d=ImageDraw.Draw(a.im)
 # Home-video overlay; no claim that the reference photographs were taken in 2021.
 shadow_text('10 ИЮНЯ 2021',19,23,13,CREAM,False)
 ell((307,27,312,32),'#e5a17a');shadow_text('ЛЕТО',318,21,10,CREAM,False)
 if t<16:
  shadow_text('МНЕ СНОВА 8',180,80,24,GOLD)
 elif kind!='ending':shadow_text('КОМСОМОЛЬСК-НА-АМУРЕ',180,76,11,CREAM)
 if kind=='ending':
  shadow_text('Я ХОЧУ В 2021',180,446,29,GOLD)
  shadow_text('Где мне снова восемь.',180,486,17,CREAM)
 captions(t,timeline)
 if t>=56:
  shadow_text('Фото: А. Карлин / Фото городов; Центр ОПИК',180,599,7,PALE)
 elif kind in ['entrance','alley','train','icecream','swing','hands']:
  shadow_text('Настоящие фото места · воспоминание, не хроника этой даты',180,600,6 if 6 in a.F else 7,PALE)
 if t>59.3:
  opacity=min(1,(t-59.3)/.7);a.im=Image.blend(a.im,Image.new('RGB',(720,1280),'#302c2c'),opacity*.8)
 return a.im

def save(timeline):
 content=['# Мне снова восемь\n\nРовно 60 секунд. Пользователь: 2013 год рождения; в воспоминании ему 8 лет.\nДата воспоминания — 10 июня 2021, Комсомольск-на-Амуре, парк Гагарина.\nГотовый ролик сочетает реальное фото места с художественным детским POV.\n\nКомната — AI-сцена обычного летнего утра, не настоящая квартира пользователя.\nКачели, руки и мороженое — художественные иллюстрации. Фото парка\nиспользованы непосредственно, без нейросетевой замены архитектуры.\n\n## Озвучка\n'];srt=[];idx=1
 for c in timeline:
  content.append(f"- {a.stamp(c['start'])}–{a.stamp(c['end'])}: {c['text']}")
  for g in c['groups']:
   srt.append(f"{idx}\n{a.stamp(g[0]['start'],True)} --> {a.stamp(g[-1]['end'],True)}\n{' '.join(w['word'] for w in g)}");idx+=1
 content.append('\n## Сцены\n')
 for s in STORY['shots']:content.append(f"- {a.stamp(s['start'])}–{a.stamp(s['end'])}: {s['description']}")
 content.append('\n'+(AS/'sources.md').read_text())
 (OUT/'script-ru.md').write_text('\n'.join(content));(OUT/'captions.srt').write_text('\n\n'.join(srt)+'\n')
 (OUT/'timeline.json').write_text(json.dumps(dict(title=STORY['title'],duration=60,age=8,date=STORY['date'],shots=STORY['shots'],dialogue=[{k:v for k,v in c.items() if k!='groups'} for c in timeline]),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
 timeline,audio=prepare();save(timeline);video=OUT/'mne-snova-8-2021-komsomolsk.mp4'
 cmd=[FF,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','30','-i','-','-i',str(audio),'-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-t','60','-movflags','+faststart',str(video)]
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=(OUT/'encode.log').open('w'))
 for i in range(1800):
  image=frame(i/30,timeline)
  if i==660:image.save(OUT/'poster.png')
  if i in [45,180,930,1110,1710]:image.save(OUT/f'frame-{i}.png')
  if i%300==0:print(f'{i/30:.0f}s / 60s',flush=True)
  p.stdin.write(image.tobytes())
 p.stdin.close()
 if p.wait():raise RuntimeError('Encoding failed')
 print(video,flush=True)
