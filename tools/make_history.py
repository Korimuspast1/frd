"""Original second-person historical short. Procedural flat-vector animation.
Run: .venv/bin/python tools/make_history.py
Voice sources are stored locally; no generation API is needed to re-render.
"""
from pathlib import Path
import json, math, re, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]; AS=ROOT/'assets/history'; OUT=ROOT/'exports/history'; OUT.mkdir(parents=True,exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe(); SR=48000; FPS=30; SCALE=2
STORY=json.loads((AS/'story.json').read_text())
FONT=AS/'NunitoSans.ttf'
F={}
for sz in range(7,43):
 f=ImageFont.truetype(str(FONT),sz*SCALE)
 try:
  axes=f.get_variation_axes();f.set_variation_by_axes([850 if a['name']==b'Weight' else a['default'] for a in axes])
 except (ValueError,OSError):pass
 F[sz]=f
BG='#202235'; INK='#201c30'; CREAM='#fff0d0'; GOLD='#ffd35d'; TEAL='#2aafa5'; RED='#f56b66'; PURPLE='#8e69b0'; MUTED='#b1a3ac'
PAL={'boy':TEAL,'friend':'#edb83e','mother':'#d75e68','vendor':PURPLE}

def rr(b,c,r=8,outline=None,width=2):
 d.rounded_rectangle(tuple(int(v*SCALE) for v in b),radius=int(r*SCALE),fill=c,outline=outline,width=width*SCALE)
def rect(b,c):d.rectangle(tuple(int(v*SCALE) for v in b),fill=c)
def ell(b,c,outline=None,width=2):d.ellipse(tuple(int(v*SCALE) for v in b),fill=c,outline=outline,width=width*SCALE)
def line(points,c,w=2):d.line([(int(x*SCALE),int(y*SCALE)) for x,y in points],fill=c,width=w*SCALE,joint='curve')
def poly(points,c,outline=INK,w=2):
 pts=[(int(x*SCALE),int(y*SCALE)) for x,y in points];d.polygon(pts,fill=c)
 if outline:d.line(pts+[pts[0]],fill=outline,width=w*SCALE,joint='curve')
def txt(s,x,y,size=14,c=CREAM,center=False):
 if center:x-=d.textlength(s,font=F[size])/SCALE/2
 d.text((int(x*SCALE),int(y*SCALE)),s,font=F[size],fill=c,stroke_width=0)
def tw(s,size):return d.textlength(s,font=F[size])/SCALE
def textlines(ss,x,y,size=16,c=CREAM,gap=24,center=True):
 for i,s in enumerate(ss):txt(s,x,y+i*gap,size,c,center)
def badge(s,x=18,y=60,c=GOLD,size=10):
 w=tw(s,size)+22;rr((x,y,x+w,y+25),c,12);txt(s,x+11,y+5,size,INK)
def card(x,y,w,h,color='#36344c',edge='#656079'):
 rr((x+3,y+5,x+w+3,y+h+5),'#171826',12);rr((x,y,x+w,y+h),color,12,edge,2)
def glow(x,y,r,col):
 layer=Image.new('RGBA',im.size);ld=ImageDraw.Draw(layer);ld.ellipse(((x-r)*2,(y-r)*2,(x+r)*2,(y+r)*2),fill=col)
 im.paste(Image.alpha_composite(im.convert('RGBA'),layer.filter(ImageFilter.GaussianBlur(22))).convert('RGB'))
def speech(s,x,y,w=145):
 rr((x,y,x+w,y+44),CREAM,10,INK);poly([(x+21,y+43),(x+29,y+43),(x+23,y+52)],CREAM,None)
 words=s.split();ls=['']
 for word in words:
  test=(ls[-1]+' '+word).strip()
  if tw(test,12)>w-18:ls.append(word)
  else:ls[-1]=test
 textlines(ls,x+w/2,y+7,12,INK,15)

LAMP_GLOW=Image.new('RGBA',(720,1280))
ImageDraw.Draw(LAMP_GLOW).ellipse((250,425,485,640),fill=(255,190,95,24))
LAMP_GLOW=LAMP_GLOW.filter(ImageFilter.GaussianBlur(28))

# The teen is a fictional 1938 character: teal cardigan, not a modern hoodie.
def char(kind,x,y,t,scale=1,mood='normal',gesture=False):
 global d
 # local character layer allows natural head/body bounce without moving the set
 old_d=d;layer=Image.new('RGBA',(220,350));d=ImageDraw.Draw(layer)
 # coordinates here remain in logical half-scale space
 skin='#e8ac83' if kind!='friend' else '#b97c62';cl=PAL[kind];bob=math.sin(t*3.3+len(kind))*.8
 if kind=='mother':
  poly([(34,80),(66,80),(80,146),(22,146)],cl);rr((38,93,64,140),'#f0c9a0',5,INK)
 else:rr((27,81,76,131),cl,12,INK)
 # legs and 1930s leather shoes
 for dx in [34,59]:
  rr((dx,130,dx+12,159),'#50465e',4,INK);rr((dx-6,154,dx+13,162),'#3a2d3e',4,INK)
 # arms, one gesturing
 line([(30,91),(17,111),(27,120)],INK,11);line([(30,91),(17,111),(27,120)],cl,8)
 arm_y=77+math.sin(t*5)*5 if gesture else 118
 line([(74,93),(89,arm_y+3),(97,arm_y)],INK,11);line([(74,93),(89,arm_y+3),(97,arm_y)],cl,8)
 ell((91,arm_y-5,102,arm_y+6),skin,INK)
 # neck and head
 rr((44,71,59,88),skin,4,INK);ell((21,19+bob,81,82+bob),skin,INK)
 ell((16,47+bob,28,61+bob),skin,INK);ell((75,47+bob,86,61+bob),skin,INK)
 if kind=='mother':
  ell((17,10+bob,84,45+bob),'#493345',INK);ell((69,7+bob,93,29+bob),'#493345',INK)
 elif kind=='vendor':
  rr((22,14+bob,82,36+bob),'#5d4d78',10,INK);rect((20,30+bob,86,36+bob),'#b99ad4')
 else:
  poly([(23,42+bob),(21,26+bob),(34,13+bob),(63,13+bob),(81,29+bob),(77,42+bob),(61,29+bob),(34,34+bob)],'#4b3341')
 if kind=='friend':
  rr((19,10+bob,82,32+bob),GOLD,9,INK);rr((45,27+bob,94,35+bob),GOLD,4,INK)
 blink=(int(t*30+len(kind)*13)%117)<4
 for ex in [38,63]:
  if blink:line([(ex-8,51+bob),(ex+7,51+bob)],INK,2)
  else:
   ell((ex-9,41+bob,ex+8,60+bob),'#fff9e6',INK,1)
   look=2 if gesture else math.sin(t*.8)*1.5
   ell((ex-3+look,46+bob,ex+3+look,55+bob),INK);ell((ex+1+look,47+bob,ex+3+look,49+bob),'#ffffff')
 if mood=='shock':ell((45,65+bob,57,76+bob),'#783849',INK,1)
 elif gesture and int(t*12)%3:ell((44,65+bob,58,73+bob),'#783849',INK,1)
 else:line([(44,67+bob),(50,70+bob),(58,66+bob)],INK,2)
 if kind=='vendor':poly([(37,64+bob),(48,60+bob),(52,63+bob),(58,60+bob),(67,64+bob),(52,68+bob)],'#463243',None)
 d=old_d
 resized=layer.resize((round(220*scale),round(350*scale)),Image.Resampling.LANCZOS)
 im.paste(resized,(round((x-55*scale)*2),round((y+bob)*2)),resized)

def comic(x,y,w=83,damaged=False):
 h=w*1.45
 rr((x+2,y+4,x+w+2,y+h+4),'#161624',3)
 rect((x,y,x+w,y+h),'#eed768');line([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],INK,2)
 txt('ЭКШЕН',x+w/2,y+3,max(7,int(w/9)),RED,True);txt('КОМИКС №1',x+w/2,y+w*.18,max(7,int(w/13)),INK,True)
 txt('10¢',x+w*.79,y+w*.32,max(7,int(w/13)),INK)
 # car, red cape and blue-clad figure are a simplified original interpretation
 poly([(x+w*.05,y+h*.8),(x+w*.2,y+h*.62),(x+w*.7,y+h*.61),(x+w*.89,y+h*.75)],'#80ad7b',INK,1)
 for dx in [.25,.7]:ell((x+w*dx-5,y+h*.73,x+w*dx+5,y+h*.73+10),'#3c3b3b')
 poly([(x+w*.48,y+h*.39),(x+w*.78,y+h*.58),(x+w*.54,y+h*.7),(x+w*.38,y+h*.62)],'#d84e50',None)
 line([(x+w*.42,y+h*.46),(x+w*.5,y+h*.57),(x+w*.33,y+h*.78)],'#41749d',max(2,int(w/14)))
 ell((x+w*.39,y+h*.35,x+w*.51,y+h*.44),'#e7b292')
 if damaged:
  poly([(x+w-16,y),(x+w,y),(x+w,y+20)],'#b69264',None)
  line([(x+5,y+h*.82),(x+w-7,y+h*.2)],'#8f795a',1)

def background(kind,t):
 # Dark softly lit gradient base with two parallax planes.
 global im,d
 phase=(t%3.2)/3.2;dx=math.sin(t*.25)*4
 if kind in ['street','kiosk','coin','vendor','choice']:
  rect((0,100,360,460),'#343447');ell((-65+dx,125,60+dx,250),'#624652')
  for i in range(6):
   x=-30+i*75+dx;rect((x,170-(i%3)*15,x+61,431),['#514254','#403e52','#534657'][i%3])
   for yy in [208,257,306]:
    for xx in [x+12,x+38]:rr((xx,yy,xx+13,yy+20),'#bc8d65',2)
  rect((0,425,360,640),'#4e424e');poly([(0,463),(360,450),(360,486),(0,505)],'#756273',None)
  # kiosk and 1930s awning
  rr((135+dx,205,350+dx,441),'#845956',4,INK)
  rect((148+dx,235,337+dx,388),'#312d42')
  for i in range(7):
   x=131+i*33+dx;poly([(x,186),(x+32,186),(x+43,223),(x-8,223)],RED if i%2==0 else '#f4d592')
  for i in range(5):
   x=150+i*36+dx;rr((x,317,x+29,378),'#f2dcb7',2,INK,1);txt('ГАЗЕТА',x+14,321,7,INK,True)
   for yy in [336,345,354]:line([(x+4,yy),(x+24,yy)],'#98786e',1)
  txt('ПРЕССА',244+dx,395,18,CREAM,True)
  # warm street lamp
  line([(28,190),(28,430)],INK,6);rr((14,168,42,201),GOLD,6,INK)
 else:
  rect((0,115,360,455),'#42384c');rect((0,443,360,640),'#654a50')
  for x in range(0,360,45):line([(x,120),(x,442)],'#4d4055',1)
  # window and moonlight
  rr((232+dx,155,340+dx,318),'#c79878',9,INK,3);rect((242+dx,165,330+dx,305),'#2b4560')
  ell((294+dx,178,314+dx,198),'#e8c98f');line([(286+dx,166),(286+dx,305)],'#b2836e',5);line([(242+dx,232),(330+dx,232)],'#b2836e',5)
  poly([(235+dx,152),(260+dx,152),(246+dx,305),(218+dx,321)],'#85617f');poly([(319+dx,152),(345+dx,152),(353+dx,322),(330+dx,305)],'#85617f')
  ell((28,459,333,541),'#9b5361',INK);ell((51,470,310,529),'#b36d70');ell((92,481,268,518),'#d39975')
  # era-appropriate wood radio, lamp and a small shelf
  rr((24,194,128,269),'#95684f',12,INK);rr((34,207,87,255),'#4c3e3d',7,INK)
  for xx in range(39,86,7):line([(xx,213),(xx,249)],'#bf9e6a',2)
  ell((99,219,116,236),GOLD,INK);line([(23,274),(133,274)],'#c39978',6)
  line([(184,245),(184,353)],INK,4);poly([(160,244),(207,244),(222,282),(145,282)],GOLD)
  if kind in ['kitchen','mother','cup']:
   rr((24,358,255,377),'#b78262',5,INK);line([(42,376),(42,484)],INK,7);line([(237,376),(237,484)],INK,7)
   ell((78,345,145,359),'#e8cba5',INK)
  else:
   rr((26,354,199,427),'#85677c',8,INK);rr((29,350,182,387),'#c38a7c',8,INK)
   rect((31,426,195,437),'#4f3b4c')
   line([(211,361),(337,361)],'#c39370',7)
   for i in range(6):rr((217+i*17,319-i%2*6,230+i*17,355),['#b15e6c','#5f9a97','#d1ad6b'][i%3],2,INK,1)
 # A soft, cached warm halo on the era-appropriate lamp.
 if kind not in ['street','kiosk','coin','vendor','choice']:
  im.paste(LAMP_GLOW,(0,0),LAMP_GLOW)

def make_scene(kind,t,sec,local,progress):
 background(kind,t)
 # foreground: four distinctive repeating silhouettes
 if kind in ['street','kiosk','vendor','choice']:
  char('vendor',255,265,t,.90,gesture=kind=='vendor');char('boy',91,307,t,1.05,gesture=True)
  if kind=='vendor':speech('Ну наконец-то!',154,241,176)
 elif kind in ['kitchen','mother','school']:
  char('boy',100,323,t,1.04,gesture=True);char('mother',265,285,t,1.1,gesture=True)
  if kind=='mother':speech('А математика?',196,250,151)
  if kind=='school':
   card(24,155,311,113,'#315c59','#c79c77');txt('НОВАЯ ЭПОХА',180,169,21,GOLD,True);txt('начинается с уроков',180,209,18,CREAM,True)
 elif kind=='friend':
  char('boy',99,306,t,1.08,gesture=True);char('friend',265,302,t,1.03,mood='shock',gesture=True)
  speech('Ты вообще нормальный?',151,238,193);comic(143,370,64)
 elif kind in ['bedroom','boy','shelf','door','bundle']:
  char('boy',145 if kind=='boy' else 105,290,t,1.35 if kind=='boy' else 1.1,gesture=True)
  if kind=='bedroom':comic(171,350,75)
  if kind=='shelf':card(204,322,135,60,'#8b6559');txt('МЕСТО ЕСТЬ!',271,340,15,GOLD,True)
  if kind in ['door','bundle']:
   if kind=='door':rr((212,153,345,458),'#69475c',5,INK,3);ell((225,308,234,317),GOLD)
   for i in range(4):rr((195-i*2,365+i*16,306+i*2,384+i*16),'#d5c0a1',2,INK)
   comic(215,348,48,True);line([(247,346),(247,432)],'#f0d4a2',3)
   if kind=='bundle':speech('Я уже это читал.',26,223,187)
 elif kind in ['comic','fold','cup','coin','creators']:
  char('boy',66,339,t,.9)
  if kind=='coin':
   ell((111,203,298,390),'#c4935b',INK,4);ell((122,214,287,379),'#e8c27a','#9e6e45',3);txt('10¢',204,250,42,INK,True);txt('ОДНА МОНЕТА',180,432,24,GOLD,True)
  elif kind=='creators':
   card(32,186,296,206);txt('СОЗДАТЕЛИ СУПЕРМЕНА',180,207,18,GOLD,True)
   txt('Джерри Сигел',180,255,26,CREAM,True);txt('+',180,292,20,GOLD,True);txt('Джо Шустер',180,323,26,CREAM,True)
  else:
   comic(102,174,168,kind in ['fold','cup'])
   if kind=='fold':badge('УГОЛОК ЗАГНУТ',50,432,RED,16)
   if kind=='cup':
    ell((157,298,262,340),'#b28c6e');rr((169,256,240,324),'#f3dabc',14,INK,3);ell((225,266,258,302),'#f3dabc',INK,3);ell((232,274,249,294),'#98726d');ell((172,250,237,271),'#6d4240',INK)
    for j in range(3):line([(184+j*15,243),(180+j*15+math.sin(t*3+j)*5,229),(186+j*15,213)],'#c9b5b0',2)
 elif kind=='choice':pass
 # Choice overlay remains in front of the kiosk, with an animated cursor.
 if kind=='choice':
  card(20,155,320,239,'#302f47',GOLD);txt('Что ты выберешь?',180,174,24,GOLD,True)
  opts=['A  Оставить монету','B  Купить комикс','C  Мучить продавца']
  for i,s in enumerate(opts):
   chosen=progress>.50 and i==1;y=220+i*52
   rr((35,y,325,y+42),TEAL if chosen else '#484359',10,GOLD if chosen else '#746479',2);txt(s,48,y+10,17,CREAM)
  cy=241+52*min(1,progress*2);cx=307-math.sin(progress*math.pi)*17
  poly([(cx,cy),(cx+2,cy+22),(cx+8,cy+15),(cx+16,cy+14)],GOLD,INK,1)
 # Modern fact section: deliberately no present-day device in 1938 rooms.
 if kind in ['disclaimer','timeline','auction','bids','grade','money','ratio','compare','stamp','part2']:
  rect((0,110,360,530),'#27263d')
  for i in range(4):ell((-140+i*110+math.sin(t*.4)*5,160+i*42,150+i*110,450+i*42),['#302b47','#342c48','#2d3046','#293b46'][i])
  if kind=='disclaimer':
   card(24,173,312,258,'#333348');txt('РАЗДЕЛЯЕМ',180,190,26,GOLD,True)
   rr((40,241,320,310),'#62506c',10);textlines(['ГЕРОЙ И ЕГО ВЫБОР','— ВЫМЫШЛЕНЫ'],180,251,17,CREAM,24)
   rr((40,324,320,399),'#2c6862',10);textlines(['ЖУРНАЛ И ПРОДАЖА','— РЕАЛЬНЫ'],180,338,17,CREAM,24)
  elif kind=='timeline':
   line([(58,294),(302,294)],GOLD,5)
   for x,s in [(62,'1938'),(180,'1939'),(298,'2024')]:ell((x-7,287,x+7,301),GOLD);txt(s,x,320,20,CREAM,True)
   txt('86 ЛЕТ',180,217,38,GOLD,True);txt('не одно мгновение',180,377,18,MUTED,True)
  elif kind in ['auction','bids','money']:
   rr((37,144,323,435),'#5d4563',14,INK,3)
   comic(113,169,130)
   # auction podium and moving gavel
   rr((40,390,320,448),'#a56b5b',8,INK);txt('АУКЦИОН · 2024',180,405,19,CREAM,True)
   angle=math.sin(t*6)*7;line([(281,348),(302,320+angle)],GOLD,7);rr((285,301+angle,324,321+angle),GOLD,5,INK)
   if kind=='bids':
    value=[1000000,2400000,4200000,6000000][min(3,int(local*1.25))]
    card(24,284,312,91,'#2d524f',GOLD);txt(f'${value:,}'.replace(',',' '),180,301,35,GOLD,True);txt('ставки растут',180,349,12,CREAM,True)
   if kind=='money':
    card(16,275,328,125,'#343248',GOLD);txt('$6 000 000',180,291,39,GOLD,True);txt('цена конкретного экземпляра',180,353,14,CREAM,True)
  elif kind=='grade':
   rr((90,151,271,444),'#849da8',12,'#d6e1d8',3);rr((100,159,261,196),'#b5d8df',6)
   txt('CGC',116,168,15,INK);txt('8,5 / 10',247,168,15,INK,False) if False else txt('8,5 / 10',213,168,15,INK,True)
   comic(109,209,143);badge('СОСТОЯНИЕ РЕШАЕТ',39,462,GOLD,16)
  elif kind=='ratio':
   card(22,173,316,278);txt('10¢',180,195,42,CREAM,True);txt('↓',180,250,34,TEAL,True);txt('$6 000 000',180,298,37,GOLD,True)
   rr((40,370,320,423),'#6f4059',10);txt('×60 000 000',180,376,30,GOLD,True);txt('Сравнение ценников. Не доходность.',180,470,12,MUTED,True)
  elif kind=='compare':
   comic(46,185,100,True);comic(212,185,100)
   textlines(['ПОМЯТЫЙ','≠'],94,350,20,RED,32);textlines(['РЕДКИЙ','СОХРАННЫЙ'],266,350,16,GOLD,25)
   txt('Не обещание богатства',180,448,20,CREAM,True)
  elif kind in ['stamp','part2']:
   # An original schematic Inverted Jenny: red frame, blue upside-down biplane.
   rr((60,179,300,392),'#f8dfbd',2,INK,3)
   for x in range(65,300,15):ell((x-4,175,x+4,183),BG);ell((x-4,388,x+4,396),BG)
   for y in range(185,392,15):ell((56,y-4,64,y+4),BG);ell((296,y-4,304,y+4),BG)
   rr((76,196,284,376),'#ad515b',3);rr((90,226,270,344),'#f0d8b2',2)
   txt('АВИАПОЧТА · 1918',180,201,14,CREAM,True);txt('24 ЦЕНТА',180,349,14,CREAM,True)
   # inverted fuselage and stacked wings
   line([(123,282),(239,282)],'#365b80',9);poly([(123,282),(111,269),(136,275)],'#365b80',None)
   line([(164,257),(164,310)],'#365b80',6);line([(200,253),(200,314)],'#365b80',6)
   for x in [161,198]:line([(x,256),(x+5,312)],'#4e7192',2)
   ell((218,256,230,268),'#365b80');line([(230,257),(230,246)],'#365b80',2)
   if kind=='part2':
    rect((0,143,360,175),'#27263d');txt('ЧАСТЬ 2',180,403,42,GOLD,True);txt('Самая дорогая ошибка?',180,461,20,CREAM,True)
   else:txt('САМОЛЁТ ВВЕРХ НОГАМИ',180,424,21,GOLD,True)

# Prepare narration at an energetic pace, and derive caption timing from syllabic
# weights on a voice-activity timeline. Frame-level word cues are saved for editing.
def prepare_audio():
 sections=[];cursor=.2
 for i,section in enumerate(STORY['sections']):
  raw=subprocess.run([FF,'-v','error','-i',str(AS/'voice'/f'{i+1:02}.wav'),'-af',f"atempo={STORY['speed']}",'-f','f32le','-ac','1','-ar',str(SR),'-'],capture_output=True,check=True)
  voice=np.frombuffer(raw.stdout,dtype='<f4').copy();voice*=min(2,.76/max(np.max(np.abs(voice)),1e-6))
  sec=dict(section,index=i,start=cursor,end=cursor+len(voice)/SR,audio=voice)
  words=section['text'].split();step=480;n=len(voice)//step
  rms=np.sqrt(np.mean(voice[:n*step].reshape(n,step)**2,axis=1))
  activity=np.where(rms>max(.008,float(np.max(rms))*.06),1.,.07)
  # Preserve pauses: voiced frames carry most of the word-duration mass.
  cum=np.cumsum(activity);weights=np.array([max(1,len(re.findall('[аеёиоуыэюяАЕЁИОУЫЭЮЯ]',w)))+(.7 if re.search('[.!?]$',w) else .15) for w in words])
  bounds=np.concatenate([[0],np.cumsum(weights)/weights.sum()*cum[-1]])
  starts=np.interp(bounds,cum,np.arange(n)*step/SR,left=0,right=len(voice)/SR)+cursor
  sec['words']=[dict(word=w,start=float(starts[j]),end=float(starts[j+1])) for j,w in enumerate(words)]
  # Phone-readable groups: at most 2 lines and 42 combined characters.
  groups=[];group=[]
  for w in sec['words']:
   if group and (sum(len(z['word'])+1 for z in group)+len(w['word'])>42 or len(group)>=7):groups.append(group);group=[]
   group.append(w)
   if re.search('[.!?]$',w['word']) and len(group)>2:groups.append(group);group=[]
  if group:groups.append(group)
  sec['groups']=groups
  nshots=math.ceil((sec['end']-sec['start']+.22)/3.65);span=(sec['end']-sec['start']+.22)/nshots
  sec['shots']=[dict(start=cursor+j*span,end=cursor+(j+1)*span,kind=section['shots'][min(3,int(j/nshots*4))]) for j in range(nshots)]
  sections.append(sec);cursor=sec['end']+.22
 duration=math.ceil((cursor+1.25)*FPS)/FPS
 mix=np.zeros((round(duration*SR),2));rng=np.random.default_rng(1938)
 def tone(at,dur,f=440,vol=.04,kind='sine',end=None,pan=0):
  n=int(dur*SR);tt=np.arange(n)/SR
  if kind=='noise':v=rng.uniform(-1,1,n)*np.exp(-tt*16)
  else:
   phase=np.cumsum(np.linspace(f,f if end is None else end,n))/SR
   v=np.sin(2*np.pi*phase) if kind=='sine' else 2*np.abs(2*(phase%1)-1)-1
  env=np.minimum(tt/.01,1)*np.minimum((dur-tt)/.06,1);v*=env*vol
  a=int(at*SR);n=min(n,len(mix)-a)
  if n>0:mix[a:a+n,0]+=v[:n]*(1-pan*.4);mix[a:a+n,1]+=v[:n]*(1+pan*.4)
 # Original restrained instrumental ostinato, darker before the auction reveal.
 for k in range(int(duration/.3)):
  at=k*.3;note=[57,60,64,67,64,60,55,59][k%8];amp=.016 if at<sections[7]['start'] else .024
  tone(at,.22,440*2**((note-69)/12),amp,'tri',pan=.45)
  if k%2==0:tone(at,.28,110 if k//8%2==0 else 82.4,.022,'sine',pan=-.3)
  if k%4==0:tone(at,.14,70,.022,'sine',end=35)
  if k%2:tone(at,.05,vol=.01,kind='noise',pan=.6)
 for sec in sections:
  for shot in sec['shots'][1:]:tone(shot['start'],.12,vol=.035,kind='noise',pan=.5)
 for ix in [1,2]:
  for off,f in [(.2,790),(.31,1180)]:tone(sections[ix]['start']+off,.12,f,.065,'tri')
 for at in [sections[4]['start']+5,sections[5]['start']+7]:tone(at,.14,vol=.09,kind='noise');tone(at,.16,85,.06,end=40)
 for i,f in enumerate([660,830,990,1320]):tone(sections[7]['start']+4+i*.12,.21,f,.075,'tri')
 tone(sections[7]['start']+.1,.17,65,.12,end=38)
 for i,f in enumerate([330,392,494]):tone(sections[9]['end']-.8+i*.15,.9,f,.045,'tri')
 # Narrator dominates the mix; music never competes with dialogue.
 for sec in sections:
  v=sec['audio'];a=int(sec['start']*SR);n=min(len(v),len(mix)-a)
  mix[a:a+n]+=v[:n,None]*.97
 mix*=np.minimum(np.arange(len(mix))/(SR*.03),1)[:,None]
 mix*=np.minimum((len(mix)-np.arange(len(mix)))/(SR*.7),1)[:,None]
 peak=np.max(np.abs(mix));mix*=min(1,.94/max(peak,1e-6))
 path=OUT/'soundtrack.wav'
 with wave.open(str(path),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes((mix*32767).astype('<i2').tobytes())
 return sections,duration,path

# Static bottom vignette, composited over every frame.
y=np.arange(1280)[:,None];alpha=np.clip((y-860)/340,0,1)*245
VIGNETTE=Image.fromarray(np.tile(alpha.astype('uint8'),(1,720)))
DARK=Image.new('RGB',(720,1280),'#151421')
def caption(t,sec):
 group=next((g for g in sec['groups'] if g[0]['start']<=t<g[-1]['end']),None)
 if not group:return
 # Wrap using measured font widths, retaining individual word coloring.
 lines=[[]]
 for w in group:
  candidate=' '.join(z['word'] for z in lines[-1]+[w])
  if tw(candidate,21)>326:lines.append([w])
  else:lines[-1].append(w)
 if len(lines)>2:
  # A rare long Russian word group uses a slightly smaller size, never 3 lines.
  size=18;lines=[group[:len(group)//2],group[len(group)//2:]]
 else:size=21
 for i,ln in enumerate(lines):
  width=sum(tw(w['word'],size) for w in ln)+tw(' ',size)*(len(ln)-1);x=(360-width)/2
  for w in ln:
   word=w['word'];key=bool(re.search(r'\d|цент|монет|миллион|Супермен|журнал|комикс|марка|самолёт|ошибк',word,re.I));bad=bool(re.search('мусор|выброс|нет|нечаянно',word,re.I))
   color='#9c94a4' if t>=w['end'] else (RED if bad else GOLD if key else '#fff7ec')
   txt(word,x,513+i*29,size,color)
   if w['start']<=t<w['end']:rr((x,540+i*29,x+tw(word,size),542+i*29),GOLD,1)
   x+=tw(word+' ',size)

def frame(t,sections):
 global im,d
 sec=next((s for s in sections if s['start']<=t<s['end']+.22),sections[-1] if t>.3 else sections[0])
 shots=sec['shots'];shot=next((s for s in shots if s['start']<=t<s['end']),shots[-1]);kind=shot['kind']
 local=max(0,t-shot['start']);progress=(t-sec['start'])/(sec['end']-sec['start'])
 im=Image.new('RGB',(720,1280),BG);d=ImageDraw.Draw(im)
 make_scene(kind,t,sec,local,progress)
 # Gentle push-in on each shot: resize/crop the entire set; foreground bubbles,
 # rain/window details and character gestures provide independent motion.
 zoom=1+min(.033,local*.010);nw=int(720*zoom);nh=int(1280*zoom)
 if nw>720:
  im=im.resize((nw,nh),Image.Resampling.BICUBIC);left=(nw-720)//2+round(math.sin(t*.5)*2);top=(nh-1280)//2
  im=im.crop((left,top,left+720,top+1280))
 im=Image.composite(DARK,im,VIGNETTE);d=ImageDraw.Draw(im)
 txt('ОДНА МОНЕТА · ОДИН ВЫБОР',18,18,11,GOLD)
 badge(sec['tag'],18,49,GOLD if sec['index']<7 else TEAL,9)
 if t<4.8:badge('ТЕБЕ 17',18,86,GOLD,17)
 if sec['index']<6:txt('ИСТОРИЧЕСКОЕ «ЧТО, ЕСЛИ» · ВЫМЫШЛЕННЫЙ ГЕРОЙ',180,592,7,MUTED,True)
 elif sec['index']==7:txt('Heritage · 04.04.2024 · CGC 8,5 · другой экземпляр',180,592,7,MUTED,True)
 else:txt('ФАКТЫ И ИСТОЧНИКИ — В СЦЕНАРИИ',180,592,8,MUTED,True)
 caption(t,sec)
 rr((18,619,342,621),'#57485f',1);rr((18,619,18+324*min(1,t/TOTAL),621),GOLD,1)
 # Visual cut accent, two frames only: not a slideshow crossfade.
 if local<.055 and t>.3:rect((0,106,360,108),GOLD)
 return im

def stamp(t,srt=False):
 n=round(t*1000);sep=',' if srt else '.';return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02}{sep}{n%1000:03}'

def save_script(sections,duration):
 public=[];blocks=[];srt=[];j=1
 for s in sections:
  clean={k:v for k,v in s.items() if k not in ['audio','groups']};public.append(clean)
  blocks.append(f"## {stamp(s['start'])} — {stamp(s['end'])}\n\n**Метка:** {s['tag']}\n\n**Озвучка:** {s['text']}\n\n**Планы:**")
  for sh in s['shots']:blocks.append(f"- {stamp(sh['start'])}–{stamp(sh['end'])}: {DESCRIPTIONS[sh['kind']]}.")
  blocks.append('')
  for g in s['groups']:
   srt.append(f"{j}\n{stamp(g[0]['start'],True)} --> {stamp(g[-1]['end'],True)}\n{' '.join(w['word'] for w in g)}");j+=1
 (OUT/'timeline.json').write_text(json.dumps(dict(title=STORY['title'],duration=duration,fps=FPS,sections=public),ensure_ascii=False,indent=2)+'\n')
 (OUT/'captions.srt').write_text('\n\n'.join(srt)+'\n')
 intro=f"# {STORY['title']}\n\nГотовый оригинальный сценарий, русский язык. Длительность: {duration:.2f} с.\nВертикаль 9:16, 720×1280, 30 fps. Рассказчик обращается к зрителю на «ты».\n\nГерой: 17-летний подросток в бирюзовом кардигане. Друг — жёлтая кепка;\nмама — красное платье и фартук; продавец — фиолетовый жилет и усы.\nГерой и бытовые события вымышлены. Исторические факты выделены ниже.\n\nВизуал: оригинальная процедурная 2D-рисовка, плоские формы и тёмные контуры,\nтёплые акценты; непрерывная мимика и жесты, параллакс, наезд камеры,\nсмена плана каждые 2–4 секунды, нижняя виньетка во всех кадрах.\n\nЗвук: выбранный синтезированный русский рассказчик, ускорение 1,4×;\nоригинальная тихая инструментальная музыка, клики, бумага, удары и аукционные пинги.\nСубтитры встроены; слова подсвечены по фонетически взвешенному таймлайну\nс учётом пауз в аудио. `timeline.json` содержит все пословные монтажные метки.\n\n"
 sources=(AS/'sources.md').read_text()
 (OUT/'script-ru.md').write_text(intro+'\n'.join(blocks)+'\n'+sources)

DESCRIPTIONS={
 'street':'Общий план американской улицы 1938 года; герой в бирюзовом кардигане и жёлтая плашка «Тебе 17»',
 'coin':'Крупный план монеты 10 центов, тёплый свет и мягкий наезд',
 'kiosk':'Киоск с газетами, полосатый тент, продавец в фиолетовом',
 'boy':'Средний план подростка: большие глаза, моргание и жест рукой',
 'choice':'Карточка «Что ты выберешь?» с тремя вариантами A/B/C; курсор выбирает B, «Купить комикс»',
 'vendor':'Продавец с усами и репликой «Ну наконец-то!»',
 'comic':'Крупный план условно нарисованной обложки первого номера: герой, автомобиль, ценник 10¢',
 'creators':'Карточка имён Джерри Сигела и Джо Шустера',
 'friend':'Друг в жёлтой кепке удивляется обложке; герой держит журнал',
 'kitchen':'Кухня 1930-х: деревянное радио, стол, лампа; мама и подросток',
 'mother':'Мама в красном платье спрашивает про математику',
 'school':'Домашняя сцена с карточкой «Новая эпоха начинается с уроков»',
 'bedroom':'Комната с ковром, кроватью, деревянным радио и журналом',
 'fold':'Загнутый угол и складка на журнале, красная предупреждающая плашка',
 'cup':'Чашка с паром поверх комикса: контраст супергероя и подставки под чай',
 'shelf':'Полка и карточка об освободившемся месте; иронический возврат к бытовой выгоде',
 'bundle':'Пачка старых газет, комикс под бечёвкой, реплика «Я уже это читал»',
 'door':'Старая дверь, газетная пачка готова к выносу',
 'disclaimer':'Явное разделение: герой и выбор вымышлены; журнал и продажа реальны',
 'timeline':'Шкала 1938 → 1939 → 2024, надпись «86 лет»',
 'auction':'Современная аукционная витрина; комикс и движущийся молоток',
 'bids':'Нарастающие условные суммы ставок — драматическая визуализация, не протокол торгов',
 'grade':'Защитная капсула и оценка CGC 8,5/10; плашка «Состояние решает»',
 'money':'Кульминационная карточка $6 000 000, пометка «цена конкретного экземпляра»',
 'ratio':'10¢ → $6 000 000; ×60 000 000, явно обозначено сравнение ценников, а не доходность',
 'compare':'Два условных экземпляра с разным состоянием; знак неравенства, предупреждение об отсутствии гарантий',
 'stamp':'Схематичная марка 1918 года с перевёрнутым бипланом: тизер Inverted Jenny',
 'part2':'Финальная крупная карточка «ЧАСТЬ 2» и вопрос «Самая дорогая ошибка?»'
}

if __name__=='__main__':
 sections,TOTAL,audio=prepare_audio();save_script(sections,TOTAL)
 print(f'Rendering {TOTAL:.2f}s, {round(TOTAL*FPS)} frames',flush=True)
 video=OUT/'ten-cents-history-ru.mp4'
 cmd=[FF,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','30','-i','-','-i',str(audio),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-t',str(TOTAL),'-movflags','+faststart',str(video)]
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=(OUT/'encode.log').open('w'))
 for i in range(round(TOTAL*FPS)):
  image=frame(i/FPS,sections)
  if i in [60,600,1500,2400,round(TOTAL*FPS)-30]:image.save(OUT/f'frame-{i}.png')
  if i==600:image.save(OUT/'poster.png')
  if i%600==0:print(f'{i/FPS:.0f}s / {TOTAL:.0f}s',flush=True)
  p.stdin.write(image.tobytes())
 p.stdin.close()
 if p.wait():raise RuntimeError('Encoding failed: see exports/history/encode.log')
 print(video,flush=True)
