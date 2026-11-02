"""Original supernatural short: the reflection becomes stronger as you weaken.
Run: .venv/bin/python tools/make_mirror.py
"""
import json,math,subprocess,wave
import numpy as np
from PIL import Image,ImageDraw
import make_training as b
a=b.a;ROOT=a.ROOT;AS=ROOT/'assets/mirror';OUT=ROOT/'exports/mirror';OUT.mkdir(parents=True,exist_ok=True)
STORY=json.loads((AS/'story.json').read_text());a.AS=AS;a.OUT=OUT;a.STORY=STORY
rr,rect,ell,line,poly,txt,card=a.rr,a.rect,a.ell,a.line,a.poly,a.txt,a.card
GOLD,RED,TEAL,CREAM,INK=a.GOLD,a.RED,a.TEAL,a.CREAM,a.INK

def room(t,bath=False):
 rect((0,105,360,455),'#262737' if not bath else '#26383f');rect((0,455,360,640),'#393445')
 for x in range(-30,400,45):line([(x,457),(x-30,640)],'#524457',1)
 for yy in range(460,640,33):line([(0,yy),(360,yy)],'#524457',1)
 if bath:
  for x in range(0,361,45):line([(x,128),(x,450)],'#3f5257',1)
  for y in range(140,455,42):line([(0,y),(360,y)],'#3f5257',1)
 else:
  rr((20,152,128,269),'#2d3044',5,'#62627a',3)
  for x in [47,76,106]:line([(x,160),(x,262)],'#181d2d',5)
  line([(18,316),(130,316)],'#6d555b',4)
  for i in range(3):b.dumbbell(39+i*34,300,0,.5)
 # Irregular dimming, not rapid full-screen flashing.
 light='#b98685' if math.sin(t*1.7)+math.sin(t*3.1)<-.6 else '#b1c7b5'
 rr((146,113,302,124),light,4,INK);line([(224,103),(224,113)],'#6a596a',2)
 ell((24,457,334,510),'#263e43',INK,2)
 if bath:
  rr((153,420,347,449),'#8c9fa4',12,INK,3);ell((196,425,303,445),'#34434c');line([(249,417),(249,404),(267,404)],'#a0a8aa',5)

def reflection(t,stage=0,close=False,crack=False,trapped=False,delay=False):
 x,y,w,h=(169,150,175,277) if not close else (39,143,282,329)
 rr((x-5,y-5,x+w+5,y+h+5),'#5d4a61',7,INK,3);rr((x,y,x+w,y+h),'#203e47',4,'#98b6b3',2)
 # Character is rendered into the glass first and clipped to the mirror interior.
 before=a.im.copy();saved=a.d
 scale=(1.10+min(stage,4)*.045) if close else (.89+min(stage,4)*.04)
 cy=y+40 if close else y+48;cx=x+w/2
 old=a.PAL['boy'];a.PAL['boy']='#419d98' if not trapped else '#2d767b'
 a.char('boy',cx,cy,t*1.4 if delay else t+.9,scale,mood='shock' if trapped else 'normal',gesture=not trapped)
 a.PAL['boy']=old
 changed=a.im.copy();a.im.paste(before);box=tuple(round(v*2) for v in (x+3,y+3,x+w-3,y+h-3));a.im.paste(changed.crop(box),box);a.d=ImageDraw.Draw(a.im)
 if not trapped and stage>=2:
  for ex in [38,63]:
   gx=cx+(ex-55)*scale;gy=cy+50*scale
   ell((gx-2,gy-2,gx+2,gy+2),'#f1d2a0')
 if delay and not trapped:b.dumbbell(cx+36*scale,cy+76*scale+math.sin(t*5)*2,0,.65)
 # glass sheen never conceals the independent motion
 line([(x+12,y+14),(x+33,y+14),(x+w-17,y+h-13)],'#42636a',1)
 if crack:
  amount=min(1,max(0,(t%4)/1.5+.4));yy=y+h*.65
  line([(x+w*.45,yy),(x+w*.57,yy-42*amount),(x+w*.49,yy-77*amount),(x+w*.68,yy-135*amount)],'#d4e4d9',2)
  line([(x+w*.57,yy-42*amount),(x+w*.8,yy-61*amount)],'#d4e4d9',1)
 if trapped:
  # A hand silhouette is pressed to the inside of the glass.
  xx=x+w*.76;yy=y+h*.6
  ell((xx-7,yy,xx+7,yy+17),'#deb58f',INK,1)
  for j in range(4):rr((xx-8+j*4,yy-10-j%2*3,xx-5+j*4,yy+6),'#deb58f',2)

def foreground(t,stage,still=False):
 scale=max(.78,1.15-stage*.067)
 a.char('boy',89,295+(1.15-scale)*130,t if not still else 0,scale,mood='shock' if stage>0 else 'normal',gesture=not still)
 if stage<2:b.dumbbell(133,382+math.sin(t*4)*6,0,.8)
 elif stage<5:b.dumbbell(120,444,0,.55)

def scene(kind,t,s,local,p):
 stage=s['index'];room(t,kind in ['bathroom','message'])
 if kind in ['gym','mirror','lift','weak','delay','thanks','throw','crack','cross','trapped']:
  reflection(t,stage,crack=kind in ['throw','crack','cross'],trapped=kind=='trapped',delay=kind=='delay')
  if kind=='trapped':
   # Real hero is confined inside; the stronger double now stands outside.
   a.char('boy',92,284,t,1.25,gesture=True)
  elif kind=='cross':
   foreground(t,5,True);a.char('boy',213-local*12,251,t,1.22,gesture=True)
  else:foreground(t,stage,still=kind in ['delay','throw','crack'])
  if kind=='throw':b.dumbbell(118+min(1,local/1.3)*122,355-min(1,local/1.3)*55,local*4,.8)
  if kind=='thanks':a.speech('Спасибо.',188,179,137)
  if kind=='delay':a.badge('ТЫ УЖЕ ОСТАНОВИЛСЯ.',25,173,RED,13)
 elif kind=='mirrorclose':
  reflection(t,stage,True,delay=True)
  a.badge('ОНО НЕ ПОВТОРЯЕТ.',39,417,RED,17)
 elif kind in ['entrance','outside']:
  rect((0,132,360,453),'#242b3b');rr((25,155,336,229),'#3f5360',5,INK)
  txt('СИЛА ВНУТРИ',180,171,30,GOLD,True)
  rr((179,244,330,465),'#302f43',5,'#6a677a',3);rr((197,261,312,411),'#263d49',3);ell((190,360,197,367),GOLD)
  if kind=='entrance':
   a.char('boy',97,288,t,1.12,gesture=True);a.badge('ВЧЕРА: ПУСТАЯ АПТЕКА',21,247,RED,12)
  else:
   a.char('boy',115,284,t,1.25,gesture=True);a.char('friend',272,307,t,1.02,gesture=True);a.speech('Отлично выглядишь!',125,244,215)
 elif kind in ['contract','ticket','end']:
  card(34,160,292,285,'#514754','#a88483')
  txt('АБОНЕМЕНТ',180,180,29,GOLD,True)
  txt('ЗАЛ «СИЛА ВНУТРИ»',180,228,15,CREAM,True)
  line([(56,269),(304,269)],'#957787',1)
  text='ВЛАДЕЛЕЦ: ТЫ' if kind=='contract' else 'ВЛАДЕЛЕЦ: ТВОЙ ДРУГ'
  txt(text,180,287,18,CREAM,True)
  a.textlines(['КАЖДЫЙ ПОСЛЕДНИЙ ПОДХОД','— ПЕРЕД ЗЕРКАЛОМ'],180,339,15,RED,25)
  if kind=='end':txt('ТЕПЕРЬ ЕГО ОЧЕРЕДЬ.',180,470,25,GOLD,True)
 elif kind=='bottle':
  foreground(t,3,True);rr((190,231,287,399),'#558e94',16,INK,3);rr((211,205,266,241),'#91bab4',7,INK)
  txt('НЕ ОТКРЫВАЕТСЯ',180,174,23,RED,True);txt('А НИЧЕГО НЕ БОЛИТ.',180,430,20,CREAM,True)
 elif kind=='friend':
  a.char('boy',89,332,t,.87,mood='shock');a.char('friend',268,286,t,1.14,gesture=True);a.speech('Ты стал меньше.',141,216,199)
 elif kind=='video':
  rr((32,148,329,449),'#191d2c',17,'#77878b',3);rr((46,169,315,425),'#293c46',6)
  a.char('boy',113,245,0,.82);a.char('boy',255,224,t*1.7,.99,gesture=True)
  ell((63,184,72,193),RED);txt('ЗАПИСЬ С ТЕЛЕФОНА',185,181,12,CREAM,True)
  txt('00:17 → 00:19',180,385,21,RED,True)
 elif kind=='phone':
  rr((83,149,280,450),'#1c202f',22,'#72858d',3);rr((95,171,268,430),'#263541',13)
  txt('00:00',181,201,39,GOLD,True);txt('НОВЫЙ ПОДХОД',181,280,21,RED,True)
  txt('ТЫ НЕ ВКЛЮЧАЛ ТАЙМЕР',181,335,12,CREAM,True)
  for i in range(3):line([(116,382+i*8),(246,382+i*8)],'#50636b',1)
 elif kind in ['bathroom','message']:
  reflection(t,3,True)
  # fogged, written message; intentionally no explanation of a physical cause
  rr((55,273,306,374),'#254047',12)
  a.textlines(['ЕЩЁ ОДИН','ПОДХОД'],180,282,29,CREAM,36)
  if kind=='message':txt('ТЫ ЖИВЁШЬ ОДИН.',180,436,23,RED,True)
 elif kind in ['empty','door']:
  rr((173,156,336,455),'#383447',5,'#747380',3);rr((186,171,323,439),'#272f3d',2);ell((193,314,201,322),GOLD)
  rr((12,331,160,411),'#654b54',5,INK);txt('РЕСЕПШЕН',86,351,16,CREAM,True)
  foreground(t,5,True)
  if kind=='door':txt('ЩЁЛК.',246,257,30,RED,True)
  else:txt('НИКОГО.',248,208,23,RED,True)

def horror_audio(sections,duration):
 sr=a.SR;n=round(duration*sr);mix=np.zeros((n,2),dtype=np.float64);rng=np.random.default_rng(777)
 def sound(at,dur,f=55,vol=.03,end=None,noise=False,pan=0):
  count=int(dur*sr);tt=np.arange(count)/sr
  if noise:v=rng.uniform(-1,1,count)*np.exp(-tt*9)
  else:
   phase=np.cumsum(np.linspace(f,f if end is None else end,count))/sr
   v=np.sin(2*np.pi*phase)+.25*np.sin(2*np.pi*phase*2.01)
  v*=np.minimum(tt/.02,1)*np.minimum((dur-tt)/.08,1)*vol;i=int(at*sr);count=min(count,n-i)
  if count>0:mix[i:i+count,0]+=v[:count]*(1-pan*.4);mix[i:i+count,1]+=v[:count]*(1+pan*.4)
 # Quiet original low drones, slow dissonant shimmer, no cheerful melody.
 for at in np.arange(0,duration,3.0):
  sound(float(at),3.5,48,.019,end=47);sound(float(at),3.2,73.4,.01,pan=.5)
 for s in sections:
  for sh in s['shots']:
   sound(sh['start'],.21,vol=.025,noise=True,pan=-.4)
  v=s['audio'].astype(np.float64);i=int(s['start']*sr);count=min(len(v),n-i);mix[i:i+count]+=v[:count,None]*.97
 # Metal knocks, self-starting timer, locked door and a crystalline crossing.
 for off in [.1,.42,.85]:sound(sections[3]['start']+off,.28,490,.045,end=190)
 sound(sections[4]['start']+4,.20,vol=.12,noise=True);sound(sections[4]['start']+4,.4,80,.055,end=42)
 for k in range(7):sound(sections[5]['start']+4+k*.055,.43,1400+k*173,.025,pan=(-1)**k*.6)
 sound(sections[5]['start']+7,2.3,90,.04,end=37)
 sound(sections[6]['end']-.55,1.15,54,.065,end=33)
 mix*=np.minimum(np.arange(n)/(sr*.08),1)[:,None];mix*=np.minimum((n-np.arange(n))/(sr*.8),1)[:,None]
 mix*=min(1,.93/max(np.max(np.abs(mix)),1e-6))
 path=OUT/'soundtrack.wav'
 with wave.open(str(path),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes((mix*32767).astype('<i2').tobytes())
 return path

def frame(t,sections,total):
 s=next((s for s in sections if s['start']<=t<s['end']+.22),sections[0] if t<.3 else sections[-1]);sh=next((sh for sh in s['shots'] if sh['start']<=t<sh['end']),s['shots'][-1]);local=max(0,t-sh['start'])
 a.im=Image.new('RGB',(720,1280),'#171d2a');a.d=ImageDraw.Draw(a.im)
 scene(sh['kind'],t,s,local,(t-s['start'])/(s['end']-s['start']))
 zoom=1+min(.045,local*.013);nw=int(720*zoom);nh=int(1280*zoom)
 if nw>720:
  a.im=a.im.resize((nw,nh),Image.Resampling.BICUBIC);a.im=a.im.crop(((nw-720)//2,(nh-1280)//2,(nw-720)//2+720,(nh-1280)//2+1280))
 a.im=Image.composite(a.DARK,a.im,a.VIGNETTE);a.d=ImageDraw.Draw(a.im)
 txt('ЕЩЁ ОДИН ПОДХОД',18,18,15,GOLD);a.badge(s['tag'],18,54,RED if s['index']>2 else '#9db8ad',9)
 a.caption(t,s,keywords=r'зеркал|отраж|слаб|силь|подход|трещин|настоящ|абонемент|друг|секунд|полночь')
 txt('МИСТИЧЕСКАЯ ИСТОРИЯ · ВСЕ СОБЫТИЯ ВЫМЫШЛЕНЫ',180,594,7,a.MUTED,True)
 rr((18,619,342,621),'#443a52',1);rr((18,619,18+324*min(1,t/total),621),RED,1)
 return a.im

DESCRIPTIONS={
 'entrance':'Необычная вывеска нового зала на месте вчерашней аптеки',
 'contract':'Дешёвый абонемент с условием последнего подхода перед зеркалом',
 'gym':'Герой и отражение ещё движутся почти синхронно',
 'mirror':'Зеркало в полный рост, холодные блики и самостоятельная мимика',
 'lift':'Гантель в руке героя начинает казаться тяжелее',
 'weak':'Герой уменьшается в кадре, отражение становится крупнее',
 'bottle':'Бутылка воды, которую герой не может открыть',
 'mirrorclose':'Отражение крупным планом: оно сильнее и смотрит прямо на зрителя',
 'friend':'Друг в жёлтой кепке замечает, что герой стал меньше',
 'video':'Запись с телефона: движения человека и отражения не совпадают',
 'delay':'Человек остановился; отражение продолжает держать гантель',
 'phone':'Таймер на телефоне запускается сам в полночь',
 'bathroom':'Запотевшее зеркало в пустой ванной, металлический стук',
 'message':'На стекле проступает надпись «Ещё один подход»',
 'empty':'Пустой ресепшен, герой пришёл отменять абонемент',
 'door':'За спиной героя захлопывается дверь',
 'thanks':'Сильное отражение улыбается и благодарит героя',
 'throw':'Гантель летит из руки героя в зеркало',
 'crack':'Трещина растёт; стекло остаётся на месте',
 'cross':'Двойник выходит из зеркала в реальную комнату',
 'trapped':'Настоящий герой заперт внутри стекла, ладонь прижата изнутри',
 'outside':'Друг встречает улыбающегося двойника возле зала',
 'ticket':'Новый абонемент уже оформлен на друга',
 'end':'Финальная карточка: теперь очередь друга'
}

def save(sections,total):
 public=[];content=[f"# {STORY['title']}\n\nОригинальная вымышленная мистическая история. Русский язык, {total:.2f} с,\n9:16, 720×1280, 30 fps. Это сверхъестественный сюжет, не объяснение\nфизиологии и не утверждение, что спорт отнимает силу.\n\nГерой — бирюзовый костюм; друг — жёлтая кепка; двойник сначала внутри\nзеркала, затем снаружи. Никаких сцен с врачом или объяснений перегрузкой.\nОзвучка выбранным рассказчиком, оригинальный тревожный эмбиент,\nметалл, щелчок замка и стеклянный переход. Пословные титры используют\nоценочную фонетическую разметку по активности речи.\n"]
 cues=[];i=1
 for s in sections:
  public.append({k:v for k,v in s.items() if k not in ['audio','groups']});content.append(f"## {a.stamp(s['start'])} — {a.stamp(s['end'])}\n\n**{s['tag']}**\n\n{s['text']}\n\nПланы:")
  for sh in s['shots']:content.append(f"- {a.stamp(sh['start'])}–{a.stamp(sh['end'])}: {DESCRIPTIONS[sh['kind']]}")
  content.append('')
  for group in s['groups']:
   cues.append(f"{i}\n{a.stamp(group[0]['start'],True)} --> {a.stamp(group[-1]['end'],True)}\n{' '.join(w['word'] for w in group)}");i+=1
 (OUT/'script-ru.md').write_text('\n'.join(content));(OUT/'captions.srt').write_text('\n\n'.join(cues)+'\n')
 (OUT/'timeline.json').write_text(json.dumps(dict(title=STORY['title'],duration=total,sections=public),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
 sections,total,_=a.prepare_audio(reveal_index=4,final_index=6);audio=horror_audio(sections,total);save(sections,total)
 print(f'Rendering {total:.2f}s',flush=True);video=OUT/'one-more-rep-mystery-ru.mp4'
 cmd=[a.FF,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','30','-i','-','-i',str(audio),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-t',str(total),'-movflags','+faststart',str(video)]
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=(OUT/'encode.log').open('w'))
 for i in range(round(total*30)):
  image=frame(i/30,sections,total)
  if i==2100:image.save(OUT/'poster.png')
  if i in [60,1200,2100,round(total*30)-90]:image.save(OUT/f'frame-{i}.png')
  if i%600==0:print(f'{i/30:.0f}s / {total:.0f}s',flush=True)
  p.stdin.write(image.tobytes())
 p.stdin.close()
 if p.wait():raise RuntimeError('Encoding failed')
 print(video,flush=True)
