"""DO RASSVETA: original 600-second, 150-shot Russian zombie survival film.
Procedural vector-style animation + stored Russian narration + original sound design.
Run: .venv/bin/python tools/make_survival.py
"""
from pathlib import Path
import json,math,re,subprocess,wave,os
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
import make_history as a
ROOT=a.ROOT;AS=ROOT/'assets/survival';OUT=ROOT/'exports/survival';OUT.mkdir(parents=True,exist_ok=True)
STORY=json.loads((AS/'story.json').read_text());DESCRIPTIONS=json.loads((AS/'shots-ru.json').read_text());FPS=30;SR=32000;TOTAL=600
FF=a.FF;rr,rect,ell,line,poly,txt,card=a.rr,a.rect,a.ell,a.line,a.poly,a.txt,a.card
INK='#121b29';WHITE='#f4ecd9';GOLD='#eec36e';RED='#ef7772';TEAL='#3ca79e';BLUE='#769cba'

# All 150 cuts have a separate edit index. Nothing in the finished movie is looped
# as a pre-rendered clip: characters, lighting, weather, camera and sound use time.
def actor(kind,x,y,t,size=1,pose='idle',look=1,emotion='alert'):
 old=a.d;layer=Image.new('RGBA',(240,364));a.d=ImageDraw.Draw(layer)
 colors={'anton':TEAL,'vera':'#c4925d','clerk':'#be5c72','driver':'#677b9c','child':'#e1b658','zombie':'#687880'}
 skin='#b7c1a1' if kind=='zombie' else '#e0ad8e';c=colors[kind];phase=t*(5.3 if pose=='run' else 3.1)
 walking=pose in ['walk','run'];bob=math.sin(phase*2)*(1.3 if walking else .35)
 cy=14 if pose=='crouch' else 0
 # backpack / elderly coat silhouette
 if kind=='anton':rr((23,81+cy,45,132+cy),'#5b4b52',7,INK,2)
 if kind=='vera':poly([(29,88+cy),(76,88+cy),(87,143),(20,143)],c,INK,2)
 # jointed legs and feet
 for i,xx in enumerate([40,65]):
  swing=math.sin(phase+i*math.pi)*(12 if pose=='run' else 7) if walking else 0
  yy=162-max(0,swing*.25);endx=xx+swing
  line([(xx,126+cy),(xx-swing*.35,144),(endx,yy)],INK,14);line([(xx,126+cy),(xx-swing*.35,144),(endx,yy)],'#414c61',10)
  rr((endx-7,yy-2,endx+12,yy+6),'#222b3d',4,INK,1)
 rr((26,79+cy,80,132+cy),c,10,INK,2)
 if kind=='anton':
  line([(53,82+cy),(53,130+cy)],'#236c73',1);rr((36,77+cy,72,88+cy),'#b8535e',4,INK,1)
  poly([(64,86+cy),(73,87+cy),(76,107+cy),(66,105+cy)],'#b8535e',INK,1)
 # arms use different poses: listening, helping, hiding, lifting and running
 for side in [-1,1]:
  sx=27 if side<0 else 79;sy=91+cy
  if kind=='zombie' and pose!='wave':elbow=(sx+side*8,94+cy);hand=(sx+side*17,88+cy+math.sin(t*1.5)*2)
  elif pose=='help' and side>0:elbow=(91,92+cy);hand=(104,88+cy)
  elif pose in ['listen','wave'] and side>0:elbow=(91,76+cy);hand=(94,53+cy+math.sin(t*4)*3)
  elif pose=='push':elbow=(88 if side>0 else 31,87+cy);hand=(105 if side>0 else 44,77+cy)
  elif pose=='hide':elbow=(43 if side<0 else 68,104+cy);hand=(54,98+cy)
  else:
   swing=math.sin(phase+(math.pi if side<0 else 0))*10 if walking else 0
   elbow=(sx+side*6,111+cy);hand=(sx+side*3+swing,126+cy)
  line([(sx,sy),elbow,hand],INK,13);line([(sx,sy),elbow,hand],c,9);ell((hand[0]-5,hand[1]-5,hand[0]+5,hand[1]+5),skin,INK,1)
 # head, hair, expressive eye direction and blinking
 hy=cy+bob
 rr((43,68+hy,62,84+hy),skin,4,INK,1);ell((20,14+hy,85,81+hy),skin,INK,2)
 ell((15,43+hy,27,58+hy),skin,INK,1);ell((79,43+hy,90,58+hy),skin,INK,1)
 if kind=='vera':
  ell((15,5+hy,87,39+hy),'#b3b8b7',INK,2);ell((75,4+hy,97,24+hy),'#b3b8b7',INK,1)
 elif kind in ['driver','child']:
  rr((19,6+hy,86,31+hy),BLUE if kind=='driver' else GOLD,8,INK,2);rr((46,27+hy,94,34+hy),BLUE if kind=='driver' else GOLD,3,INK,1)
 else:poly([(20,38+hy),(22,20+hy),(40,5+hy),(67,8+hy),(85,28+hy),(78,38+hy),(59,26+hy),(34,32+hy)],'#3e3341' if kind!='zombie' else '#465258',INK,2)
 blink=kind!='zombie' and int(t*30+len(kind)*11)%131<4
 for ex in [39,66]:
  if blink:line([(ex-8,50+hy),(ex+7,50+hy)],INK,2)
  else:
   ell((ex-10,39+hy,ex+9,60+hy),'#f3ecd4',INK,1)
   if kind=='zombie':ell((ex-3,45+hy,ex+3,52+hy),'#b66060')
   else:
    ell((ex-3+look*2,45+hy,ex+3+look*2,55+hy),INK);ell((ex+look*2,46+hy,ex+2+look*2,48+hy),'#ffffff')
  if emotion=='fear':line([(ex-8,34+hy),(ex+5,32+hy)],INK,2)
 if kind=='zombie':line([(42,68+hy),(58,65+hy)],'#655053',2)
 elif emotion=='fear':ell((45,65+hy,57,75+hy),'#6f3b4c',INK,1)
 elif emotion=='relief':line([(42,66+hy),(50,70+hy),(60,65+hy)],INK,2)
 else:line([(44,68+hy),(57,68+hy)],INK,2)
 if kind=='vera':
  for xx in [39,66]:ell((xx-12,38+hy,xx+11,61+hy),None,'#655467',1)
  line([(49,48+hy),(55,48+hy)],'#655467',1)
 a.d=old
 # pose includes breathing, head tilt and walking; no stiff sprite translation alone
 if kind=='zombie':layer=layer.rotate(math.sin(t*.8)*2,Image.Resampling.BICUBIC,expand=False)
 sprite=layer.resize((max(1,round(240*size)),max(1,round(364*size))),Image.Resampling.LANCZOS)
 a.im.paste(sprite,(round((x-60*size)*2),round((y+bob)*2)),sprite)

def pair(t,p=.5,where='walk',x=None,y=301,size=.95):
 xx=(71+178*p) if x is None else x
 actor('anton',xx,y,t,size,where if where in ['walk','run','help','hide'] else 'idle',emotion='fear')
 actor('vera',xx-53,y+11,t+.7,size*.86,'walk' if where in ['walk','run'] else 'idle',emotion='fear')

def outdoor(t,dawn=False,move=0):
 rect((0,90,360,438),'#384254' if dawn else '#192737')
 ell((280,113,309,142),'#d5c99f' if not dawn else '#da9f78')
 for i in range(7):
  xx=-28+i*65-move%65;top=154+(i%3)*23
  rect((xx,top,xx+57,443),['#344051','#2c3a49','#3a3f50'][i%3]);line([(xx+54,top),(xx+54,443)],'#485063',2)
  for row in range(6):
   for col in range(3):
    x=xx+7+col*16;y=top+17+row*36;rect((x,y,x+9,y+16),'#a38165' if (i+row+col)%5==0 else '#1e2d3d')
 rect((0,437,360,640),'#35404a');poly([(0,449),(360,426),(360,463),(0,488)],'#4d5360',None)
 # continuous cold drizzle and drifting mist, in parallax relative to the buildings
 for i in range(26):
  x=(i*53+int(t*14))%382-10;y=130+(i*89+int(t*110))%367
  line([(x,y),(x-3,y+11)],'#61727c',1)

def apartment(t,dark=False):
 rect((0,100,360,455),'#343344' if not dark else '#252a39');rect((0,455,360,640),'#57464c')
 for x in range(-20,400,48):line([(x,458),(x-35,640)],'#6b555b',1)
 rr((230,150,338,324),'#8b7470',7,INK,2);rr((238,160,329,313),'#263a4d',3)
 for i in range(3):rect((244+i*29,209,261+i*29,311),'#304657')
 line([(285,160),(285,314)],'#96796c',4);line([(238,236),(329,236)],'#96796c',4)
 poly([(221,146),(251,146),(239,309),(211,328)],'#6e5369');poly([(320,146),(344,146),(352,328),(332,315)],'#6e5369')
 rr((18,328,180,413),'#6f6072',12,INK);rr((21,323,176,364),'#957287',9,INK);rr((14,360,45,404),'#7f6579',7,INK)
 ell((39,451,312,516),'#8b626c',INK,2);ell((68,465,288,504),'#ac7a79')
 rr((164,368,276,381),'#b08773',5,INK);line([(176,381),(176,443)],INK,4);line([(266,381),(266,443)],INK,4)
 rr((17,175,176,281),'#161d2c',7,'#645d72',3);rr((24,183,168,273),'#243b50' if not dark else '#121b29',4)
 if not dark:
  txt('ЭКСТРЕННО',96,207,17,RED,True);txt('ОСТАВАЙТЕСЬ ДОМА',96,237,11,WHITE,True)
 rr((38,283,159,290),'#6c5666',4)

def bigdoor(t,action='idle',label='КВАРТИРА 47'):
 rect((0,105,360,640),'#282d3c');rr((72,143,305,487),'#776568',5,INK,3);rr((85,155,293,477),'#443b4b',3,'#9b7e75',2)
 rr((104,177,274,222),'#332f40',4);txt(label,189,192,14,WHITE,True)
 ell((175,249,187,261),'#a99978',INK,1)
 off=math.sin(t*13)*3 if action in ['bang','handle'] else 0
 rr((116,327+off,153,338+off),'#af9990',4,INK,1);ell((116,315,129,327),'#af9990',INK)
 if action=='scratch':
  for i in range(4):line([(225+i*6,287),(219+i*6,340)],'#c0a495',1)
 if action=='bang':
  for x in [62,314]:line([(x,251),(x-5,267),(x,283)],RED,2)

def stairs(t):
 rect((0,100,360,640),'#293743');rect((0,303,360,414),'#516e70');rect((0,417,360,640),'#454751')
 for i in range(8):
  yy=329+i*25;xx=-18+i*22;poly([(xx,yy),(360,yy),(360,yy+26),(xx+20,yy+26)],'#59616a',INK,1)
 line([(36,277),(309,478)],'#a8a79e',5)
 for i in range(5):line([(66+i*47,300+i*34),(66+i*47,365+i*32)],'#92999b',3)
 rr((205,141,320,277),'#79888c',5,INK);rr((213,149,312,269),'#1e3447',3);line([(263,150),(263,268)],'#7a8d94',3)
 txt('5',39,177,39,'#c5bcb0');rr((82,153,149,245),'#202b3a',4,'#666d7b',2)

def basement(t):
 rect((0,95,360,640),'#172c35');poly([(0,122),(175,218),(360,122),(360,640),(0,640)],'#233944',None)
 for yy in [158,191]:line([(0,yy),(177,252),(360,yy)],'#69716c',12);line([(0,yy-3),(177,249),(360,yy-3)],'#858b7a',3)
 for xx in [24,307]:line([(xx,170),(xx,433)],'#626c68',10)
 rr((117,221,244,405),'#23303b',3,'#536466',3);rr((130,234,231,392),'#15232d',2)
 rr((30,265,128,300),'#697d6e',3);txt('ВЫХОД',77,276,13,WHITE,True);line([(106,279),(118,279),(113,274)],WHITE,2);line([(118,279),(113,284)],WHITE,2)
 poly([(0,429),(360,425),(360,640),(0,640)],'#26454e',None)
 for i in range(16):
  xx=(i*47+int(t*6))%370-5;yy=444+(i*31)%165
  line([(xx,yy),(xx+12+math.sin(t*2+i)*6,yy)],'#4a6970',1)

def yard(t,dawn=False):
 outdoor(t,dawn)
 # shop, car, children's slide, typical apartment courtyard, no actual address
 rr((189,318,351,424),'#72605d',4,INK);rr((191,314,350,341),'#426765',4,INK)
 txt('ПРОДУКТЫ · 24',271,323,13,WHITE,True);rr((215,350,264,410),'#a3b598',3,INK);rr((283,350,330,415),'#253b42',3,INK)
 poly([(8,407),(53,364),(82,368),(93,419)],'#9f6b64',INK,2);line([(50,365),(50,438)],'#73867c',4)
 rr((89,449,221,493),'#5c6473',11,INK);poly([(113,445),(137,419),(188,420),(211,451)],'#596a79')
 for xx in [116,192]:ell((xx,480,xx+26,506),'#172130',INK)

def shop(t,dark=False):
 rect((0,102,360,454),'#3b424b' if not dark else '#252d3b');rect((0,455,360,640),'#4d5058')
 for row in range(3):
  yy=173+row*71;rr((16,yy+50,185,yy+58),'#948a7c',2,INK,1)
  for i in range(8):
   x=23+i*20;rr((x,yy+11,x+14,yy+48),['#9a736b','#7d9890','#ac9b74'][i%3],3,INK,1)
   rr((x+1,yy+3,x+13,yy+13),'#bda88b',2);rect((x+3,yy+24,x+12,yy+31),'#d1c3a3')
  txt('79 ₽',40,yy+58,9,WHITE);txt('119 ₽',119,yy+58,9,WHITE)
 rr((206,149,344,360),'#76878b',7,INK,3);rr((215,158,335,350),'#2a424c',4);line([(275,159),(275,349)],'#718b92',3)
 rr((32,393,200,456),'#846872',7,INK);rr((105,355,173,398),'#2b3445',6,INK);rr((114,364,163,385),'#89a897',3)
 if not dark:rr((65,116,291,124),'#c3d1b5',3)

def roof(t):
 outdoor(t);poly([(0,416),(360,380),(360,640),(0,640)],'#3e4b57',None)
 rr((218,225,343,420),'#5e6570',4,INK);rr((236,250,326,410),'#303d4a',3,'#77818a',2)
 for x in [19,54,87]:rr((x,334,x+22,418),'#687781',4,INK);ell((x-5,327,x+27,344),'#8b9694',INK,1)
 line([(0,442),(216,418)],'#7f8587',5)
 for i in range(6):line([(i*40,443-i*4),(i*40,399-i*4)],'#77858d',3)
 # snow/rain drift, always time-varying rather than a static roof plate
 for i in range(15):
  x=(i*79+int(t*45))%380-10;y=136+(i*37+int(t*9))%300;line([(x,y),(x+13,y-2)],'#758a96',1)

def bus_exterior(t,doors=False,dawn=False,moving=False):
 outdoor(t,dawn,move=t*20 if moving else 0)
 rr((12,263,350,467),'#aaad88',18,INK,3);rect((17,357,345,413),'#687d80')
 for i in range(5):rr((28+i*61,285,81+i*61,352),'#29414f',5,INK,2)
 rr((289,361,336,450),'#293f4a',3,INK,2)
 if doors:poly([(288,362),(305,366),(305,448),(288,452)],'#79918f');poly([(335,362),(319,366),(319,448),(335,452)],'#79918f')
 for xx in [58,267]:ell((xx,433,xx+46,483),'#172431',INK,3);ell((xx+12,446,xx+34,469),'#6a7d83',INK,1)
 txt('СЛУЖЕБНЫЙ',181,372,16,WHITE,True);rr((26,410,47,425),GOLD,4)

def bus_inside(t,dawn=False,stopped=False):
 rect((0,100,360,640),'#374552');rr((39,139,321,324),'#819092',12,INK,3)
 rr((49,150,310,314),'#536777' if dawn else '#233b4c',6)
 # outside lamps and road sliding only while bus actually moves
 move=0 if stopped else (t*31)%110
 for i in range(5):
  xx=57+i*62-move%62;rect((xx,185,xx+43,310),'#344b5c');rect((xx+12,215,xx+22,232),'#9f9270')
 line([(181,150),(181,313)],'#718991',5);line([(16,117),(16,591)],'#b6b4a0',5);line([(341,117),(341,591)],'#b6b4a0',5)
 for i in range(3):
  y=342+i*77;rr((28,y,113,y+67),'#677a84',11,INK);rr((250,y,334,y+67),'#677a84',11,INK)
 poly([(121,320),(239,320),(263,640),(97,640)],'#25323e',None)
 rr((51,307,308,329),'#566873',6,INK)

def phone(t,kind='phone'):
 apartment(t,True);rr((76,148,285,469),'#172231',24,'#8c9299',3);rr((88,171,272,446),'#233849',13)
 txt('МАМА',181,189,24,WHITE,True);txt('02:19',181,231,39,GOLD,True)
 rr((103,296,257,364),'#456b68',9);a.textlines(['Ты дома?','Не открывай никому.'],181,305,14,WHITE,22)
 txt('НЕТ СЕТИ' if kind=='no_signal' else 'ОТПРАВЛЯЕТСЯ…',181,389,15,RED,True)

def bag(t,kitten=False):
 rr((112+math.sin(t*4)*2,277,270,444),'#67565a',17,INK,3);rr((131,246,253,300),'#67565a',12,INK,3)
 rr((143,346,242,417),'#857064',9,INK,2);line([(134,294),(249,294)],'#d4b492',3)
 if kitten:
  ell((156,249,226,309),'#d9ae7b',INK,2);poly([(157,266),(159,232),(181,252)],'#d9ae7b');poly([(202,250),(225,231),(226,266)],'#d9ae7b')
  for x in [178,207]:ell((x-4,270,x+4,278),'#24333d')
  poly([(189,283),(196,283),(192,289)],'#af7174',None)
  for yy in [285,292]:line([(158,yy),(177,yy+2)],INK,1);line([(207,yy+2),(232,yy)],INK,1)

# Shot labels are meaningful during the dialogue-free suspense passages.
LABELS={
 'scratch':'Царапанье оборвалось.', 'door_handle':'Ручка медленно поворачивается.',
 'door_bang':'Дверь больше не кажется надёжной.', 'wait':'Ни одного лишнего звука.',
 'water':'В темноте — чужие шаги.', 'stop':'Дальше нельзя.',
 'yard_hide':'Они ждут за контейнерами.', 'yard_silence':'Сигнализация замолчала.',
 'window_crack':'Стекло долго не продержится.', 'board_crack':'Этот путь закрыт.',
 'engine_fail':'Двигатель не отвечает.', 'bus_closed':'Двери ещё закрыты.',
 'bag_move':'В рюкзаке что-то шевелится.', 'depot_wave':'Кто машет из пустого автобуса?',
 'end':'ДО РАССВЕТА · КОНЕЦ ПЕРВОЙ НОЧИ'
}

APART={'bed','hero_listen','tv','pack','lights_off','chair','bottle','window','balcony','balcony_walk','balcony_door','vera_wave'}
YARD={'yard_window','yard_crowd','containers','yard_exit','shop_light','shop_wave','yard_hide','car_alarm','zombies_turn','zombies_walk','yard_run','help_vera_yard','yard_silence'}
STAIRS={'stairs','stairs_walk','stair_zombie','light_hide','wait','stair_zombie_walk','vera_fall','hero_returns','help_vera','basement_door','listen','stairs_exit'}
BASEMENT={'water','pipes','basement_walk','metal_step','basement_face','stop','fork','side_door','door_stuck','push_door','opening','basement_chase'}
SHOP={'shop','survivors','child','driver','window_hands','shop_route','shop_lights_off','broken_bottle','hero_child','shop_stairs','window_crack','cash_keys','shop_door','shop_close'}
ROOF={'roof','bus_below','board','board_crack','stop_driver','roof_group','vent','roof_detour','help_vera_roof','roof_zombies','roof_walk','child_roof','roof_door'}
BUS_EXT={'bus_outside','driver_run','bus_closed','street_zombies','engine_fail','child_hand','headlights','bus_open','boarding','help_vera_bus','glass_hand','bus_move'}
BUS_INT={'bus_inside','bag_move','kitten','child_smile','dawn','radio','driver_stop','hero_close','bus_stopped'}

def zombie_group(t,n=5,move=0,base_y=310,small=.8):
 for i in range(n):
  xx=22+(i*67+move)%335;yy=base_y+(i%3)*20
  actor('zombie',xx,yy,t+i*2,small+(i%3)*.03,'walk' if move else 'idle',look=-1)

def scene(kind,t,ch,local,p):
 idx=ch['index'];s=(t%60)/60;fear='fear';camera_zoom=1
 if kind=='wait' and idx==5:kind='yard_hide'
 if kind=='help_vera' and idx==4:kind='stop'
 if kind in ['phone','no_signal','phone_ping']:phone(t,kind)
 elif kind in ['scratch','door_handle','door_bang']:
  bigdoor(t,{'scratch':'scratch','door_handle':'handle','door_bang':'bang'}[kind]);actor('anton',48,331,t,.78,'listen',emotion=fear)
 elif kind in ['intercom','peephole','hall_zombie','zombie_turn']:
  if kind in ['intercom','peephole']:
   rect((0,100,360,640),'#273440');rr((31,155,330,452),'#7f8b8d',16,INK,4);rr((49,175,312,425),'#1a2c35',6)
   actor('zombie',181,194,t,.99,'idle',look=-1 if kind=='intercom' else 1)
   for y in range(181,424,7):line([(51,y),(309,y)],'#30434b',1)
   txt('КАМЕРА · ПЛОЩАДКА',180,469,16,GOLD,True)
  else:
   stairs(t);actor('zombie',200,245,t,1.10,'idle',look=1 if kind=='zombie_turn' else -1)
 elif kind in APART:
  apartment(t,kind in ['lights_off','hero_listen','balcony_walk'])
  if kind=='bed':
   rr((25,351,195,415),'#b7a08c',8,INK);actor('anton',111,281,t,.93,'idle',emotion=fear)
  elif kind in ['balcony','balcony_walk','balcony_door','vera_wave']:
   rr((181,146,343,449),'#738085',5,INK,3);rr((194,158,333,436),'#273e4a',3)
   line([(201,363),(333,363)],'#9b9d96',5)
   for x in range(207,334,25):line([(x,363),(x,432)],'#999f9e',3)
   actor('vera',277,246,t,.94,'wave' if kind=='vera_wave' else 'idle',emotion=fear)
   actor('anton',76+p*95 if kind=='balcony_walk' else 102,307,t,1.02,'walk' if kind=='balcony_walk' else 'listen',emotion=fear)
  elif kind=='pack':
   actor('anton',110,277,t,1.12,'hide',emotion=fear);rr((183,326,252,419),'#756363',10,INK);rr((198,304,236,333),'#756363',7,INK)
   rr((272,329,291,375),TEAL,4,INK);rr((275,322,287,332),GOLD,2)
  elif kind=='bottle':
   actor('anton',101,290,t,1.08,'hide',emotion=fear);rr((203,235,270,396),'#5e999f',12,INK,3);rr((215,218,256,247),'#a1b6ae',5,INK)
  elif kind=='chair':
   actor('anton',86,297,t,1.08,'hide',emotion=fear)
   poly([(190,393),(256,421),(245,447),(179,416)],'#a48377');line([(180,419),(157,453)],INK,6);line([(245,448),(230,472)],INK,6)
  else:
   actor('anton',110 if kind!='window' else 203,281,t,1.14,'listen',emotion=fear)
   if kind=='tv':a.textlines(['НЕ ПОДХОДИТЕ','К ОКНАМ'],96,207,13,RED,19)
 elif kind in YARD:
  yard(t)
  if kind in ['yard_window','yard_crowd']:
   zombie_group(t,7,0,311,.63)
   if kind=='yard_window':
    # inside-window foreground framing: a distinct camera position, not another establishing shot
    rect((0,92,17,640),'#867471');rect((343,92,360,640),'#867471');line([(181,102),(181,570)],'#8a7975',8)
  elif kind in ['containers','yard_hide','yard_exit']:
   zombie_group(t,3,0,300,.69);pair(t,p,'hide',x=94,y=325,size=.92)
   rr((15,392,131,487),'#526f6b',7,INK,3);rr((14,383,134,399),'#71877c',5,INK)
  elif kind in ['shop_light','shop_wave']:
   actor('clerk',309,333,t,.55,'wave');pair(t,p,'hide',x=95,y=336,size=.9)
  elif kind in ['car_alarm','zombies_turn','zombies_walk']:
   zombie_group(t,5,p*115 if kind=='zombies_walk' else 0,296,.74)
   if math.sin(t*7)>0:rr((94,455,110,465),RED,3);rr((202,455,217,465),GOLD,3)
   if kind=='car_alarm':txt('ПИ-ПИ-ПИ',159,393,18,RED,True)
  elif kind in ['yard_run','help_vera_yard']:
   zombie_group(t,3,p*40,310,.65);pair(t,p,'run' if kind=='yard_run' else 'help',x=81+p*181,y=318,size=.92)
  else:zombie_group(t,5,0,310,.73)
 elif kind in STAIRS:
  stairs(t)
  if kind in ['stair_zombie','stair_zombie_walk']:
   actor('zombie',225+p*42 if kind.endswith('walk') else 245,235+p*52 if kind.endswith('walk') else 229,t,1.03,'walk' if kind.endswith('walk') else 'idle',look=-1)
  elif kind in ['light_hide','wait','listen']:
   pair(t,p,'hide',x=83,y=304,size=.92);rect((0,126,22,525),'#131e2e')
  elif kind=='vera_fall':
   actor('vera',225,350,t,.82,'crouch',emotion=fear);actor('anton',118,295,t,.98,'listen',look=1,emotion=fear)
  elif kind in ['hero_returns','help_vera']:
   actor('vera',234,327,t,.85,'idle',emotion=fear);actor('anton',118+p*66 if kind=='hero_returns' else 193,308,t,1.02,'walk' if kind=='hero_returns' else 'help',emotion=fear)
  elif kind=='basement_door':
   rr((82,190,289,453),'#4a615e',6,INK,3);txt('ПОДВАЛ',185,231,23,WHITE,True);pair(t,p,'help',x=97,y=305,size=.94)
  else:pair(t,p,'walk',x=91+p*137,y=279+p*45,size=.98)
 elif kind in BASEMENT:
  basement(t)
  if kind=='basement_face':actor('zombie',191,236,t,.86,'idle');rect((0,100,137,529),'#152b34');rect((245,100,360,529),'#152b34')
  elif kind in ['pipes','water']:
   pair(t,p,'hide',x=87,y=312,size=.9)
  elif kind in ['side_door','door_stuck','push_door','opening']:
   open_amount=p*45 if kind=='opening' else 0
   rr((181,177,338,450),'#5b6f6b',5,INK,3);rect((186,183,187+open_amount,441),'#8da5a4' if kind=='opening' else '#223b46')
   txt('ВЫХОД',263,224,20,WHITE,True);pair(t,p,'help' if kind!='push_door' else 'help',x=136,y=307,size=.96)
  elif kind in ['stop','fork','metal_step']:
   pair(t,p,'hide',x=148,y=299,size=.96)
   if kind=='fork':line([(90,198),(57,220),(91,236)],GOLD,5)
  else:
   pair(t,p,'run' if kind=='basement_chase' else 'walk',x=100+p*133,y=304,size=.93)
   if kind=='basement_chase':actor('zombie',40+p*42,306,t,.97,'walk')
  # a slowly sweeping flashlight cone in the water, independently animated
  if kind not in ['basement_face','stop']:line([(160,440),(252+math.sin(t*.8)*40,473)],'#78928d',3)
 elif kind in SHOP:
  shop(t,kind in ['shop_lights_off','broken_bottle','shop_stairs'])
  if kind in ['window_hands','window_crack']:
   for i in range(4):
    x=226+(i%2)*71;y=191+(i//2)*83+math.sin(t*2+i)*3
    ell((x-7,y,x+7,y+20),'#9ca990',INK,1)
    for j in range(4):rr((x-8+j*4,y-12-j%2*5,x-5+j*4,y+5),'#9ca990',2)
   if kind=='window_crack':line([(231,185),(269,238),(249,271),(309,322)],'#c5d8d0',2)
   actor('clerk',94,284,t,.97,'listen',emotion=fear)
  elif kind in ['child','hero_child']:
   actor('child',237,351,t,.65,'hide',emotion=fear);actor('anton',128,295,t,1.03,'help' if kind=='hero_child' else 'idle',emotion=fear)
  elif kind=='driver':actor('driver',242,255,t,1.17,'wave',emotion=fear);actor('anton',111,313,t,.94,'listen',emotion=fear)
  elif kind=='cash_keys':
   actor('clerk',96,278,t,.97,'hide',emotion=fear);ell((188,402,202,416),None,GOLD,2);line([(195,414),(214,432)],GOLD,3);line([(210,427),(218,424)],GOLD,2)
  elif kind=='broken_bottle':
   actor('child',246,341,t,.71,'hide',emotion=fear);poly([(143,448),(152,427),(167,447),(160,457)],'#98b7aa',INK,1);poly([(176,457),(189,434),(192,460)],'#98b7aa',INK,1)
  elif kind in ['shop_stairs','shop_route']:
   rr((231,164,339,443),'#41565a',3,INK,3);txt('НА КРЫШУ',284,199,12,WHITE,True)
   actor('driver',259,251-p*22,t,.93,'walk');pair(t,p,'walk',x=100+p*55,y=305,size=.92)
   actor('child',55+p*68,375,t,.61,'walk')
  elif kind in ['shop_door','shop_close']:
   actor('clerk',252,267,t,1.02,'push',emotion=fear);pair(t,p,'walk',x=125,y=309,size=.91)
  else:
   actor('clerk',61,298,t,.96,'listen',emotion=fear);actor('driver',254,266,t,1.04,'idle');actor('child',196,375,t,.61,'hide',emotion=fear);pair(t,p,'idle',x=143,y=305,size=.90)
 elif kind in ROOF:
  roof(t)
  if kind in ['board','board_crack','stop_driver']:
   poly([(108,428),(244,411),(250,427),(111,445)],'#a68e72');rect((111,444,251,520),'#152230')
   actor('driver',233-p*23,255,t,1.02,'walk' if kind=='board' else 'idle',emotion=fear)
   actor('anton',81,302,t,.99,'wave' if kind=='stop_driver' else 'idle',emotion=fear)
   if kind=='board_crack':line([(181,419),(168,429),(185,435)],INK,3)
  elif kind=='bus_below':
   # small bus in a street beyond the parapet
   rr((66,294,201,361),'#a1ab92',8,INK);rr((75,306,192,331),'#2c4d60',3)
   for xx in [85,165]:ell((xx,348,xx+22,370),INK)
   line([(0,439),(359,399)],'#8b9698',10)
  elif kind=='roof_zombies':zombie_group(t,4,p*27,298,.96)
  elif kind in ['help_vera_roof','roof_walk','roof_detour','child_roof']:
   pair(t,p,'help' if kind=='help_vera_roof' else 'walk',x=94+p*112,y=305,size=.97)
   actor('child',56+p*102,380,t,.60,'walk',emotion=fear)
  else:
   pair(t,p,'walk',x=101+p*81,y=303,size=.95);actor('driver',263,270,t,.97,'wave')
 elif kind in BUS_EXT:
  bus_exterior(t,doors=kind in ['bus_open','boarding','help_vera_bus'],moving=kind=='bus_move')
  if kind in ['street_zombies','glass_hand']:zombie_group(t,5,p*51,319,.93)
  elif kind in ['engine_fail','headlights']:
   actor('driver',272,298,t,.63,'hide')
   if kind=='headlights':poly([(24,413),(-5,392),(-5,477),(43,428)],'#c6bd8a',None)
   else:txt('…',265,244,37,RED,True)
  elif kind in ['boarding','help_vera_bus']:
   pair(t,p,'help' if kind=='help_vera_bus' else 'walk',x=184+p*71,y=324,size=.85)
   actor('child',293,373-p*42,t,.55,'walk',emotion=fear)
  elif kind=='driver_run':actor('driver',83+p*166,319,t,.89,'run',emotion=fear)
  elif kind=='child_hand':actor('anton',128,297,t,.98,'help',emotion=fear);actor('child',229,350,t,.68,'hide',emotion=fear)
  elif kind!='bus_move':pair(t,p,'idle',x=154,y=325,size=.88);actor('child',226,379,t,.60,'hide',emotion=fear)
 elif kind in BUS_INT:
  bus_inside(t,dawn=idx==9,stopped=kind in ['driver_stop','bus_stopped'])
  if kind in ['bag_move','kitten']:
   bag(t,kind=='kitten');actor('child',72,343,t,.69,'listen',emotion='relief' if kind=='kitten' else fear)
  elif kind=='radio':
   card(48,174,264,155,'#273c48','#74898a');txt('РАЦИЯ',180,191,22,GOLD,True)
   for i in range(17):
    h=4+abs(math.sin(t*7+i*.8))*30;line([(77+i*13,269-h/2),(77+i*13,269+h/2)],TEAL,3)
   a.textlines(['НЕ ВЪЕЗЖАЙТЕ','В ДЕПО'],180,356,25,RED,34)
  elif kind=='hero_close':actor('anton',179,203,t,1.56,'listen',emotion=fear)
  elif kind in ['driver_stop','bus_stopped']:actor('driver',252,252,t,1.02,'hide',emotion=fear);actor('anton',101,304,t,1.03,'listen',emotion=fear)
  elif kind=='dawn':
   rr((50,151,310,312),'#9b9691',7);ell((213,173,259,217),'#f1c58b');txt('05:41 · РАССВЕТ',180,225,20,WHITE,True)
   actor('anton',101,335,t,.98,'idle',emotion='relief')
  else:
   actor('anton',83,316,t,1.01,'idle',emotion='relief');actor('vera',276,339,t,.82,'idle',emotion='relief');actor('child',190,381,t,.62,'idle',emotion='relief')
 elif kind in ['depot','depot_lights','depot_wave','end']:
  outdoor(t,True);rr((15,219,344,445),'#6c7078',7,INK,3);txt('АВТОБУСНОЕ ДЕПО',180,235,22,WHITE,True)
  for i in range(3):
   xx=30+i*104;rr((xx,287,xx+90,433),'#a5aa92',8,INK);rr((xx+6,304,xx+84,354),'#789590' if kind in ['depot_wave','end'] or (kind=='depot_lights' and local>i*.9) else '#253b4b',3)
   rr((xx+10,368,xx+80,408),'#526e77',4)
  if kind in ['depot_wave','end']:actor('zombie',181,310,t,.30,'wave',look=-1)
  if kind=='end':
   card(28,448,304,77,'#263443',GOLD);txt('ДО РАССВЕТА',180,457,31,GOLD,True);txt('КОНЕЦ ПЕРВОЙ НОЧИ',180,501,13,WHITE,True)
 else:apartment(t,True);actor('anton',151,297,t,1.12,'listen',emotion=fear)

# Audio: 3 voiced passages per minute, separated by action and atmosphere.
# Quiet cut points are selected from the source waveform, not arbitrary sample cuts.
def prepare():
 sections=[];sound=np.zeros((TOTAL*SR,2),dtype=np.float32);rng=np.random.default_rng(2026)
 def fx(at,dur,f=80,vol=.03,end=None,noise=False,pan=0,decay=0):
  n=int(dur*SR);tt=np.arange(n,dtype=np.float32)/SR
  if noise:v=rng.uniform(-1,1,n).astype(np.float32)
  else:
   phase=np.cumsum(np.linspace(f,f if end is None else end,n,dtype=np.float32))/SR
   v=np.sin(2*np.pi*phase)+.22*np.sin(2*np.pi*phase*2.01)
  env=np.minimum(tt/.015,1)*np.minimum((dur-tt)/.06,1)
  if decay:env*=np.exp(-tt*decay)
  v*=env*vol;i=round(at*SR);n=min(n,len(sound)-i)
  if i>=0 and n>0:
   sound[i:i+n,0]+=v[:n]*(1-pan*.5);sound[i:i+n,1]+=v[:n]*(1+pan*.5)
 for ci,ch in enumerate(STORY['chapters']):
  raw=subprocess.run([FF,'-v','error','-i',str(AS/'voice'/f'{ci+1:02}.mp3'),'-f','f32le','-ac','1','-ar',str(SR),'-'],capture_output=True,check=True)
  v=np.frombuffer(raw.stdout,dtype='<f4').copy();v*=min(1.8,.72/max(np.max(np.abs(v)),1e-6))
  step=320;n=len(v)//step;rms=np.sqrt(np.mean(v[:n*step].reshape(n,step)**2,axis=1))
  cuts=[0]
  for ratio in [1/3,2/3]:
   center=round(n*ratio);lo=max(0,center-90);hi=min(n,center+90)
   # Prefer broad low-energy pauses; mild distance penalty avoids unnatural pacing.
   smooth=np.convolve(rms,np.ones(5)/5,mode='same');score=smooth[lo:hi]+np.abs(np.arange(lo,hi)-center)*.00009
   cuts.append((lo+int(np.argmin(score)))*step)
  cuts.append(len(v));starts=[ci*60+1.5,ci*60+22,ci*60+42]
  # Slightly shift a long last section earlier; every voiced chunk stays in its minute.
  for j in range(3):assert (cuts[j+1]-cuts[j])/SR<18.0
  mapping=[]
  for j,start in enumerate(starts):
   clip=v[cuts[j]:cuts[j+1]].copy();edge=min(160,len(clip)//2);clip[:edge]*=np.linspace(0,1,edge);clip[-edge:]*=np.linspace(1,0,edge)
   i=int(start*SR);sound[i:i+len(clip)]+=clip[:,None]*.98
   mapping.append(dict(source_start=cuts[j]/SR,source_end=cuts[j+1]/SR,start=start,end=start+len(clip)/SR))
  words=ch['text'].split();weights=np.array([max(1,len(re.findall('[аеёиоуыэюяАЕЁИОУЫЭЮЯ]',w)))+(.7 if re.search('[.!?]$',w) else .15) for w in words]);activity=np.where(rms>max(.008,float(np.max(rms))*.06),1,.07);cum=np.cumsum(activity)
  bounds=np.concatenate([[0],np.cumsum(weights)/weights.sum()*cum[-1]]);times=np.interp(bounds,cum,np.arange(n)*step/SR,left=0,right=len(v)/SR)
  cues=[]
  def convert(x,j):return mapping[j]['start']+max(0,min(x,mapping[j]['source_end'])-mapping[j]['source_start'])
  for wi,word in enumerate(words):
   mid=(times[wi]+times[wi+1])/2;j=min(2,next((k for k,m in enumerate(mapping) if m['source_start']<=mid<m['source_end']),2));m=mapping[j]
   aa=convert(max(times[wi],m['source_start']),j);bb=convert(min(times[wi+1],m['source_end']),j)
   cues.append(dict(word=word,start=float(aa),end=float(max(aa+.02,bb)),chunk=j))
  groups=[];group=[]
  for w in cues:
   if group and (w['chunk']!=group[-1]['chunk'] or sum(len(z['word'])+1 for z in group)+len(w['word'])>42 or len(group)>=7):groups.append(group);group=[]
   group.append(w)
   if re.search('[.!?]$',w['word']) and len(group)>2:groups.append(group);group=[]
  if group:groups.append(group)
  shots=[dict(index=ci*15+j,start=ci*60+j*4,end=ci*60+(j+1)*4,kind=kind) for j,kind in enumerate(ch['shots'])]
  sections.append(dict(ch,index=ci,start=ci*60,end=(ci+1)*60,words=cues,groups=groups,voice_spans=mapping,shots=shots))
 # Original evolving score: low strings-like harmonics, distant wind, restrained pulse.
 for k in range(TOTAL//4):
  at=k*4;chapter=min(9,int(at//60));fund=[49,49,55,46.25,43.65,49,51.9,46.25,55,61.7][chapter]
  fx(at,4.5,fund,.014,pan=-.25);fx(at+.13,4.3,fund*1.501,.008,pan=.4)
  if chapter in [4,6,7,8] and at%8==0:
   fx(at,.28,61,.027,end=43,decay=8);fx(at+.35,.21,68,.021,end=45,decay=8)
  fx(at,4.3,vol=.007,noise=True,pan=.6)
 # Each cut's action has its own synchronized effects.
 for ch in sections:
  for sh in ch['shots']:
   at=sh['start'];kind=sh['kind']
   if any(w in kind for w in ['walk','run','boarding','returns']):
    for off in np.arange(.2,3.9,.42 if 'run' in kind else .7):
     fx(at+float(off),.10,90,.048,end=52,noise=False,pan=(-1)**int(off*10)*.35,decay=19)
     if ch['index']==4:fx(at+float(off),.18,vol=.038,noise=True,decay=10)
   if kind in ['scratch','door_bang','door_handle','shop_close','balcony_door','opening']:
    for off in ([.35,1.45,2.6] if kind in ['scratch','door_bang'] else [.8]):
     fx(at+off,.18,85,.075 if kind=='door_bang' else .045,end=39,decay=14);fx(at+off,.12,vol=.052,noise=True,pan=.5,decay=24)
   if kind in ['metal_step','pipes','basement_face']:
    fx(at+1.1,.7,630,.038,end=490,decay=7);fx(at+2.7,.5,vol=.04,noise=True,decay=9)
   if kind in ['phone_ping','intercom']:fx(at+.8,.16,940,.065);fx(at+1,.16,1250,.05)
   if kind=='car_alarm':
    for off in np.arange(0,3.8,.5):fx(at+float(off),.28,650,.06,end=970,pan=.5)
   if kind in ['window_crack','broken_bottle','board_crack']:
    fx(at+1,.28,vol=.09,noise=True,decay=14)
    for j in range(5):fx(at+1+j*.05,.36,1200+j*310,.022,decay=10)
   if kind in ['engine_fail','headlights','bus_move','bus_inside','dawn']:
    fx(at,4,43,.029 if kind!='engine_fail' else .045,end=68 if kind=='headlights' else 46,pan=-.25)
   if kind=='radio':
    fx(at+.15,.38,vol=.065,noise=True,decay=5);fx(at+3.1,.35,vol=.055,noise=True,decay=5)
   if kind in ['stair_zombie','basement_face','depot_wave']:
    fx(at,3.7,39,.033,end=35,pan=.6)
   if kind=='bag_move':fx(at+.8,.45,vol=.045,noise=True,decay=5);fx(at+2.2,.5,vol=.045,noise=True,decay=5)
   if kind=='kitten':fx(at+.5,.32,590,.035,end=930);fx(at+.82,.22,930,.026,end=510)
 # Silence foreground atmospheres under speech without silencing the environment.
 # Narration was mixed separately above; score is intentionally low and stereo.
 sound*=np.minimum(np.arange(len(sound))/(SR*.6),1)[:,None]
 sound*=np.minimum((len(sound)-np.arange(len(sound)))/(SR*1.3),1)[:,None]
 peak=np.max(np.abs(sound));sound*=min(1,.94/max(peak,1e-6))
 audio=OUT/'soundtrack.wav'
 with wave.open(str(audio),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes((sound*32767).astype('<i2').tobytes())
 del sound
 return sections,audio

# Dark bottom gradient for captions; screen safe areas retained at 9:16.
def render_frame(t,sections):
 ch=sections[min(9,int(t//60))];shot=ch['shots'][min(14,int(t%60//4))];local=t-shot['start'];p=local/4
 a.im=Image.new('RGB',(720,1280),'#182432');a.d=ImageDraw.Draw(a.im)
 scene(shot['kind'],t,ch,local,p)
 # Camera patterns alternate wide, medium and detail plans, with a small push-in.
 base=1.0 if shot['index']%3==0 else (1.035 if shot['index']%3==1 else 1.065)
 zoom=base+local*.007;ww=int(720*zoom);hh=int(1280*zoom)
 a.im=a.im.resize((ww,hh),Image.Resampling.BICUBIC)
 cx=(ww-720)//2+int(math.sin(t*.3)*2);cy=(hh-1280)//2;a.im=a.im.crop((cx,cy,cx+720,cy+1280))
 a.im=Image.composite(a.DARK,a.im,a.VIGNETTE);a.d=ImageDraw.Draw(a.im)
 txt('ДО РАССВЕТА',18,17,14,GOLD);txt(f'{ch["index"]+1:02} / 10',338,21,10,BLUE,True)
 a.badge(f'ПЕРМЬ · {ch["time"]}',18,49,'#8ba4aa',9)
 txt(ch['title'],180,87,14,WHITE,True)
 active=any(span['start']<=t<span['end'] for span in ch['voice_spans'])
 if active:a.caption(t,ch,keywords=r'двер|свет|Антон|Вера|звук|тихо|темнот|зеркал|послед|нет|рассвет|депо|вместе|стекл')
 else:
  label=LABELS.get(shot['kind'],ch['goal'].capitalize()+'.')
  words=label.split();lines=['']
  for word in words:
   candidate=(lines[-1]+' '+word).strip()
   if a.tw(candidate,19)>319:lines.append(word)
   else:lines[-1]=candidate
  a.textlines(lines[:2],180,521,19,GOLD,27)
 txt('ВЫМЫШЛЕННАЯ ИСТОРИЯ · ПЕРМЬ БЕЗ КОНКРЕТНЫХ АДРЕСОВ',180,594,7,a.MUTED,True)
 rr((18,619,342,621),'#42505c',1);rr((18,619,18+324*t/TOTAL,621),GOLD,1)
 if local<.045 and t>0:rect((0,113,360,114),'#78918e')
 return a.im

def save(sections):
 public=[];text=['# ДО РАССВЕТА — Ночь в Перми\n\nОригинальная вымышленная история, 600 секунд (10:00), 150 планов по 4 секунды.\n9:16, 720×1280, 30 fps. Зритель наблюдает со стороны за Антоном,\nа не получает инструкцию по реальному выживанию. Пермь используется\nкак художественный фон: район и все события придуманы, реальных адресов нет.\n\nГерой: Антон, бирюзовая куртка, красный шарф и рюкзак. Вера: седые волосы,\nочки и охристое пальто. Продавщица: бордовая куртка. Водитель: синяя кепка.\nДевочка: жёлтая шапка. Зомби: серо-зелёная кожа, медленная походка, без крови.\n\nВ каждой минуте три голосовых отрезка, разделённых сценами действия и\nзвуками окружения. Монтажные пословные метки оценочные, по голосовой\nактивности и фонетическим весам. Оригинальные музыка и эффекты синтезированы\nкодом. Озвучка тем же выбранным русским рассказчиком.\n'];srt=[];idx=1
 for ch in sections:
  public.append({k:v for k,v in ch.items() if k!='groups'})
  text.append(f"## {a.stamp(ch['start'])} — {a.stamp(ch['end'])} · {ch['title']}\n\nВремя в истории: {ch['time']}. Цель: {ch['goal']}.\n\n**Рассказчик:** {ch['text']}\n\n**Монтажные планы:**")
  for sh in ch['shots']:text.append(f"- {a.stamp(sh['start'])}–{a.stamp(sh['end'])}: {DESCRIPTIONS.get(sh['kind'],sh['kind'])}")
  text.append('')
  for group in ch['groups']:
   srt.append(f"{idx}\n{a.stamp(group[0]['start'],True)} --> {a.stamp(group[-1]['end'],True)}\n{' '.join(w['word'] for w in group)}");idx+=1
 (OUT/'script-ru.md').write_text('\n'.join(text));(OUT/'captions.srt').write_text('\n\n'.join(srt)+'\n')
 (OUT/'timeline.json').write_text(json.dumps(dict(title=STORY['title'],duration=TOTAL,fps=FPS,sections=public),ensure_ascii=False,indent=2)+'\n')

def cover():
 a.im=Image.new('RGB',(720,1280),'#182432');a.d=ImageDraw.Draw(a.im)
 yard(330)
 for i in range(4):actor('zombie',53+i*82,290+(i%2)*12,330+i,.66,'walk',look=-1)
 actor('vera',244,319,330,.96,'idle',emotion='fear')
 actor('anton',116,284,330,1.25,'listen',emotion='fear')
 a.im=Image.composite(a.DARK,a.im,a.VIGNETTE);a.d=ImageDraw.Draw(a.im)
 txt('ОРИГИНАЛЬНЫЙ 2D-ФИЛЬМ · 10 МИНУТ',180,42,12,GOLD,True)
 txt('ДО РАССВЕТА',180,101,38,GOLD,True)
 a.badge('ПЕРМЬ · ОДНА НОЧЬ',86,167,'#93a9a8',12)
 a.textlines(['ЗА ДВЕРЬЮ','УЖЕ НЕ СОСЕД.'],180,508,27,WHITE,38)
 a.im.save(OUT/'poster.png')

if __name__=='__main__':
 sections,audio=prepare();save(sections);print('Audio and 150-shot timeline ready. Rendering 600 seconds.',flush=True)
 # A restrained VBV cap keeps a ten-minute file practical while preserving captions.
 # The original raw frames are always 720x1280; no loop, speed stretch or repeated clip.
 video=OUT/'do-rassveta-10min-ru.mp4'
 cmd=[FF,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','30','-i','-','-i',str(audio),'-c:v','libx264','-preset','medium','-crf','24','-maxrate','430k','-bufsize','1500k','-pix_fmt','yuv420p','-c:a','aac','-b:a','112k','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-t','600','-movflags','+faststart',str(video)]
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=(OUT/'encode.log').open('w'))
 for i in range(TOTAL*FPS):
  image=render_frame(i/FPS,sections)
  if i==12540:image.save(OUT/'poster.png')
  if i in [90,2700,5400,8100,10800,13500,16110,17820]:image.save(OUT/f'frame-{i}.png')
  if i%900==0:print(f'{i/FPS:.0f}s / 600s',flush=True)
  p.stdin.write(image.tobytes())
 p.stdin.close()
 if p.wait():raise RuntimeError('Encoding failed; inspect encode.log')
 cover()
 print(video,flush=True)
