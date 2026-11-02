"""Render a new contemporary 2D short about fatigue and inadequate recovery.
Reuses the vector cast and narration/caption pipeline, not the historical plot.
Run: .venv/bin/python tools/make_training.py
"""
import json,math,subprocess
from PIL import Image,ImageDraw
import make_history as a
ROOT=a.ROOT;AS=ROOT/'assets/training';OUT=ROOT/'exports/training';OUT.mkdir(parents=True,exist_ok=True)
STORY=json.loads((AS/'story.json').read_text())
a.AS=AS;a.OUT=OUT;a.STORY=STORY
# Shared drawing calls address the shared canvas, preserving identical cast proportions.
rr,rect,ell,line,poly,txt,card=a.rr,a.rect,a.ell,a.line,a.poly,a.txt,a.card
TEAL,GOLD,RED,CREAM,INK=a.TEAL,a.GOLD,a.RED,a.CREAM,a.INK

def gym(t):
 rect((0,100,360,455),'#343247');rect((0,455,360,640),'#555064')
 for x in range(-60,420,60):line([(x,457),(x-45,640)],'#6b5c74',2)
 for y in range(465,640,35):line([(0,y),(360,y)],'#6b5c74',2)
 # mirror with a moving reflected stripe, shelves and warm overhead lighting
 rr((24,142,242,333),'#829ca6',8,INK,3);rr((30,148,236,327),'#425b70',5)
 x=48+math.sin(t*.5)*7;poly([(x,151),(x+30,151),(x+125,325),(x+95,325)],'#526c80',None)
 line([(251,173),(334,173)],'#b99b91',4)
 for i in range(3):dumbbell(267+i*25,161,0,.5)
 line([(259,209),(329,209)],'#b99b91',4)
 for i,c in enumerate([TEAL,RED,GOLD]):rr((267+i*22,183,279+i*22,207),c,4,INK,1)
 # light halos are a fixed overlay, not a hard white background
 for x in [70,285]:
  rr((x-30,112,x+30,122),GOLD,5,INK);line([(x,100),(x,111)],'#bca191',2)
 ell((14,454,346,514),'#234d57',INK,2);ell((30,464,332,503),'#376f73')
 # a towel and water bottle, not historical props
 rr((260,373,330,389),'#ad7864',5,INK);line([(270,390),(270,453)],INK,4);line([(320,390),(320,453)],INK,4)
 rr((282,345,297,372),TEAL,4,INK,1);rr((286,339,294,347),GOLD,2)

def dumbbell(x,y,angle=0,scale=1):
 def point(xx,yy):
  return(x+(xx*math.cos(angle)-yy*math.sin(angle))*scale,y+(xx*math.sin(angle)+yy*math.cos(angle))*scale)
 line([point(-22,0),point(22,0)],INK,max(2,round(7*scale)))
 line([point(-22,0),point(22,0)],'#9aabc1',max(2,round(4*scale)))
 for xx in [-29,19]:
  poly([point(xx,-15),point(xx+11,-15),point(xx+11,15),point(xx,15)],'#a98fba',INK,max(1,round(2*scale)))

def battery(percent,x=60,y=207,w=240):
 rr((x,y,x+w,y+121),'#25283d',15,'#a2acbd',4);rr((x+w,y+38,x+w+11,y+80),'#a2acbd',3)
 color=TEAL if percent>45 else RED
 rr((x+10,y+10,x+11+(w-22)*percent/100,y+111),color,8)
 txt(f'{percent}%',x+w/2,y+27,41,CREAM,True)
 txt('УСЛОВНАЯ ШКАЛА СИЛ',180,y+145,14,GOLD,True)

def pushup(t,weak=False):
 # Dynamic side-on pushup, with jointed arms and body motion rather than a static pose.
 p=(math.sin(t*(2.2 if weak else 4))+1)/2;hy=380+p*(10 if weak else 28)
 line([(62,468),(210,hy+14),(272,hy+10)],INK,31)
 line([(62,468),(210,hy+14),(272,hy+10)],TEAL,25)
 line([(62,468),(47,475)],INK,17)
 line([(246,hy+26),(221,430),(266,472)],INK,13)
 line([(246,hy+26),(221,430),(266,472)],'#e8ac83',9)
 ell((246,hy-32,311,hy+31),'#e8ac83',INK,3)
 poly([(247,hy-15),(249,hy-35),(277,hy-43),(303,hy-25),(305,hy-15),(281,hy-25)],'#4b3341')
 ell((282,hy-9,304,hy+12),CREAM,INK,1);ell((294,hy-3,301,hy+7),INK)
 if weak:ell((298,hy+16,306,hy+25),'#783849')
 else:line([(293,hy+18),(305,hy+16)],INK,2)
 if weak:
  for i in range(2):poly([(321+i*11,hy-4+i*10),(317+i*11,hy+6+i*10),(324+i*11,hy+6+i*10)],'#83c4d4',None,1)

def bag(x,y,t):
 wiggle=math.sin(t*8)*2
 rr((x,y+25,x+83,y+113),'#c29a6d',9,INK,3)
 line([(x+16,y+33),(x+21,y+wiggle),(x+62,y+wiggle),(x+68,y+33)],INK,5)
 for dx,dy in [(14,21),(39,28),(23,47),(47,47)]:ell((x+dx,y+dy,x+dx+25,y+dy+22),'#d6b77e',INK,1)
 txt('БОСС',x+41,y+83,16,INK,True)

def coach(t):
 a.char('boy',99,303,t,1.06,mood='shock');a.char('vendor',273,286,t,1.03,gesture=True)
 a.badge('ТРЕНЕР',228,450,TEAL,12)

def scene(kind,t,s,local,progress):
 gym(t)
 if kind in ['hero','lift']:
  a.char('boy',156,255,t,1.43,mood='shock' if s['index']>=2 else 'normal',gesture=True)
  dumbbell(234,373+math.sin(t*4)*(12 if s['index']<2 else 3),math.sin(t*4)*.08,1.15 if s['index']<2 else .8)
  if kind=='hero':a.badge('ЦЕЛЬ: СТАТЬ СИЛЬНЕЕ',35,173,GOLD,17)
  else:a.badge('ЛЕГЧЕ ГАНТЕЛЬ. ТЯЖЕЛЕЕ ЖИТЬ.',21,174,RED,12)
 elif kind=='pushup':
  pushup(t,s['index']>=2)
  card(35,176,290,91,'#393549');txt('ОТЖИМАНИЯ',180,187,20,GOLD,True)
  txt('10 → 6 → 2' if s['index']>=2 else 'ПЕРВЫЙ ПОДХОД: 10',180,220,24,CREAM,True)
 elif kind=='battery':
  a.char('boy',178,319,t,1.05,mood='shock',gesture=True)
  battery(18 if s['index'] in [0,3] else 45)
  if s['index']==6:txt('ДАЖЕ МАШИНАМ НУЖНА ЗАРЯДКА',180,415,14,GOLD,True)
 elif kind=='calendar':
  a.char('boy',94,331,t,.96,gesture=True)
  card(30,170,300,211,'#3a354d');txt('НИ ДНЯ БЕЗ НАГРУЗКИ',180,186,20,RED,True)
  for i,day in enumerate(['ПН','ВТ','СР','ЧТ','ПТ','СБ','ВС']):
   x=48+(i%4)*72;y=236+(i//4)*62;rr((x,y,x+51,y+45),'#704b64',6);txt(day,x+25,y+5,13,CREAM,True);txt('×',x+25,y+18,21,RED,True)
 elif kind=='coffee':
  a.char('boy',91,323,t,.97,mood='shock')
  card(107,164,225,230);txt('СОН?',220,181,28,RED,True);txt('ПОТОМ.',220,216,24,CREAM,True)
  rr((151,280,270,360),'#ecbf7e',15,INK,3);ell((244,294,290,341),'#ecbf7e',INK,3);ell((258,307,280,330),'#43384e')
  ell((153,270,268,295),'#5a3837',INK)
  for i in range(3):line([(173+i*24,262),(168+i*24+math.sin(t*3+i)*5,250),(176+i*24,235)],'#c7b1b5',3)
 elif kind=='friend':
  a.char('boy',91,309,t,1.05,mood='shock');a.char('friend',267,292,t,1.08,gesture=True)
  a.speech('Ты разряжаешься?',148,211,197)
 elif kind=='choice':
  a.char('boy',83,319,t,1.03)
  card(23,161,314,246,'#302e45',GOLD);txt('Ты устал. Что дальше?',180,176,22,GOLD,True)
  for i,label in enumerate(['A  Сон и восстановление','B  Ещё один подход','C  Кофе вместо сна']):
   yy=221+i*54;rr((36,yy,324,yy+44),RED if i==1 else '#494359',8,GOLD if i==1 else None,2);txt(label,48,yy+10,16,CREAM)
  px=309;py=290+math.sin(t*3)*3;poly([(px,py),(px,py+23),(px+7,py+15),(px+15,py+14)],GOLD,INK,1)
 elif kind=='counter':
  pushup(t,True);card(23,171,314,153);txt('БОЛЬШЕ ТРЕНИРУЕШЬСЯ',180,190,19,GOLD,True)
  txt('10 → 6 → 2',180,229,39,RED,True);txt('вымышленный пример, не прогноз',180,289,12,CREAM,True)
 elif kind=='phone':
  a.char('boy',75,328,t,.95,mood='shock')
  rr((135,150,308,448),'#1c1d30',22,'#b1a0bd',3);rr((146,169,297,427),'#39344d',12)
  txt('ОГОНЁК ГОРИТ',222,190,18,GOLD,True);txt('7',222,223,42,GOLD,True);txt('ДНЕЙ ПОДРЯД',222,276,16,CREAM,True)
  poly([(220,305),(206,328),(201,348),(213,366),(234,366),(245,348),(234,323),(232,343)],RED,None)
  txt('А ТЫ — НЕТ',222,393,18,RED,True)
 elif kind=='bag':
  rect((0,138,360,449),'#3a374d');rr((23,162,338,228),'#6c5476',9,INK);txt('МАГАЗИН «У ДОМА»',180,180,23,GOLD,True)
  a.char('boy',120,287,t,1.23,mood='shock',gesture=True);bag(237,350,t)
  a.badge('ТЫ 0 : 1 КАРТОШКА',60,252,RED,19)
 elif kind=='coach':
  coach(t);a.speech('Нагрузка — только часть.',67,202,244)
 elif kind=='diagram':
  coach(t);card(24,151,312,187)
  txt('НЕ ХВАТАЕТ ВТОРОЙ ПОЛОВИНЫ',180,168,16,GOLD,True)
  for i,(title,c) in enumerate([('НАГРУЗКА',RED),('ВОССТАНОВЛЕНИЕ',TEAL)]):
   yy=208+i*55;rr((40,yy,320,yy+42),c,8);txt(title,180,yy+9,18,CREAM,True)
  txt('СОН + ПИТАНИЕ + ПЛАН',180,359,19,GOLD,True)
 elif kind=='plan':
  a.char('boy',94,325,t,1.03)
  card(30,159,300,224);txt('ПЛАН БЕЗ ГЕРОИЗМА',180,177,23,GOLD,True)
  for i,s in enumerate(['✓ Обсудить нагрузку','✓ Оставить время на отдых','✓ Не соревноваться с усталостью']):txt(s,46,224+i*41,15,CREAM)
 elif kind=='bed':
  rect((0,138,360,457),'#37334e');rect((0,457,360,640),'#50465e')
  rr((238,168,331,297),'#a77d7a',8,INK);rr((245,175,324,290),'#263e61',5);ell((286,185,312,211),GOLD)
  rr((31,345,321,447),'#a16d69',11,INK,3);rr((42,333,313,388),'#d6a889',10,INK)
  rr((48,331,142,365),CREAM,11,INK)
  # sleeping head and blanket; slow breathing rather than an instant strength gain
  yy=328+math.sin(t*1.5)*1.2;ell((77,yy-28,140,yy+25),'#e8ac83',INK,3)
  poly([(79,yy-7),(79,yy-28),(105,yy-41),(136,yy-24),(136,yy-10),(107,yy-20)],'#4b3341')
  line([(114,yy-3),(127,yy-3)],INK,2)
  rr((133,328+math.sin(t*1.5),309,389),TEAL,12,INK,3)
  txt('z',165,292+math.sin(t*2)*4,21,GOLD);txt('Z',191,273+math.sin(t*2+.5)*4,27,GOLD)
  txt('НЕ МАГИЯ ЗА ОДНУ НОЧЬ',180,197,21,GOLD,True);txt('Восстановление — часть плана',180,239,17,CREAM,True)
 elif kind=='summary':
  a.char('boy',98,314,t,1.1);card(25,159,310,157);txt('БОЛЬШЕ ≠ ЛУЧШЕ',180,179,30,GOLD,True)
  txt('Сила — не серия в приложении',180,237,17,CREAM,True);txt('Нагрузка должна быть посильной',180,273,15,TEAL,True)
 elif kind=='doctor':
  card(27,164,306,249,'#3b344d',RED);rr((149,185,211,247),CREAM,14);rect((174,195,186,237),RED);rect((158,210,202,222),RED)
  a.textlines(['СТОЙКАЯ ИЛИ','НЕОЖИДАННАЯ СЛАБОСТЬ?'],180,268,21,CREAM,28)
  txt('Обратись к врачу.',180,350,27,GOLD,True)
 elif kind=='end':
  card(24,158,312,288);txt('ТЕЛО — НЕ ПАУЭРБАНК',180,180,24,GOLD,True)
  txt('Но зарядка нужна.',180,230,25,CREAM,True)
  battery(42,73,281,211)
  txt('ДАЛЬШЕ: МЕНЬШЕ СНА,',180,463,17,GOLD,True);txt('БОЛЬШЕ ПРОБЛЕМ?',180,487,20,CREAM,True)

def frame(t,sections,total):
 s=next((s for s in sections if s['start']<=t<s['end']+.22),sections[0] if t<.3 else sections[-1]);shot=next((sh for sh in s['shots'] if sh['start']<=t<sh['end']),s['shots'][-1])
 local=max(0,t-shot['start']);a.im=Image.new('RGB',(720,1280),a.BG);a.d=ImageDraw.Draw(a.im)
 scene(shot['kind'],t,s,local,(t-s['start'])/(s['end']-s['start']))
 zoom=1+min(.033,local*.01);nw=int(720*zoom);nh=int(1280*zoom)
 if nw>720:
  a.im=a.im.resize((nw,nh),Image.Resampling.BICUBIC);a.im=a.im.crop(((nw-720)//2,(nh-1280)//2,(nw-720)//2+720,(nh-1280)//2+1280))
 a.im=Image.composite(a.DARK,a.im,a.VIGNETTE);a.d=ImageDraw.Draw(a.im)
 txt('КАЧАЕШЬСЯ ИЛИ РАЗРЯЖАЕШЬСЯ?',18,18,12,GOLD);a.badge(s['tag'],18,52,GOLD if s['index']<4 else TEAL,9)
 a.caption(t,s)
 txt('ВЫМЫШЛЕННАЯ ИСТОРИЯ · НЕ ИНДИВИДУАЛЬНАЯ ПРОГРАММА',180,594,7,a.MUTED,True)
 rr((18,619,342,621),'#57485f',1);rr((18,619,18+324*min(1,t/total),621),GOLD,1)
 return a.im

DESCRIPTIONS={
 'hero':'Герой в бирюзовом спортивном костюме уверенно входит в зал',
 'lift':'Анимированный подъём гантели; амплитуда уменьшается по мере усталости',
 'pushup':'Отжимания с движением корпуса и сгибанием локтей',
 'battery':'Условная шкала энергии, явно не медицинское измерение',
 'calendar':'Календарь без выходных: все дни заняты тренировками',
 'coffee':'Гигантская кружка кофе вместо сна, пар и усталое лицо',
 'friend':'Друг в жёлтой кепке спрашивает, не разряжается ли герой',
 'choice':'Выбор A/B/C; курсор выбирает ошибочный вариант «Ещё один подход»',
 'counter':'Иллюстративный спад 10 → 6 → 2, пометка о вымышленном примере',
 'phone':'Телефон хвалит серию тренировок; горящий значок контрастирует с усталостью',
 'bag':'Герой проигрывает пакету картошки: условный счёт 0:1',
 'coach':'Тренер в фиолетовом обсуждает план с героем',
 'diagram':'Нагрузка и восстановление; сон, питание, план',
 'plan':'Новый список действий: обсудить нагрузку, отдыхать, не соревноваться с усталостью',
 'bed':'Ночная комната, медленное дыхание спящего героя, предупреждение «Не магия за одну ночь»',
 'summary':'Крупный вывод «Больше ≠ лучше»',
 'doctor':'При стойкой или неожиданной слабости — обратиться к врачу',
 'end':'Финальная метафора зарядки и тизер следующей истории о недосыпе'
}

def script(sections,total):
 content=[f"# {STORY['title']}\n\nРусский, {total:.2f} с; 9:16, 720×1280, 30 fps.\nОригинальная комедийная история, не диагноз и не программа тренировок.\nЧисла 10 → 6 → 2 и шкалы энергии вымышлены. Ролик показывает возможный\nэффект накопившейся усталости, а не утверждает, что тренировки всегда ослабляют.\n\nОзвучка: выбранный рассказчик voice-02, темп 1,35×. Музыка и эффекты\nсинтезированы кодом, встроены в MP4. Пословные метки оценены по паузам\nи фонетическим весам; исходные WAV и монтажный JSON включены.\n"]
 cues=[];public=[];idx=1
 for s in sections:
  content.append(f"## {a.stamp(s['start'])} — {a.stamp(s['end'])}\n\n**{s['tag']}**\n\n{s['text']}\n\nПланы:")
  for sh in s['shots']:content.append(f"- {a.stamp(sh['start'])}–{a.stamp(sh['end'])}: {DESCRIPTIONS[sh['kind']]}")
  content.append('');public.append({k:v for k,v in s.items() if k not in ['audio','groups']})
  for group in s['groups']:
   cues.append(f"{idx}\n{a.stamp(group[0]['start'],True)} --> {a.stamp(group[-1]['end'],True)}\n{' '.join(w['word'] for w in group)}");idx+=1
 content.append((AS/'sources.md').read_text())
 (OUT/'script-ru.md').write_text('\n'.join(content))
 (OUT/'captions.srt').write_text('\n\n'.join(cues)+'\n')
 (OUT/'timeline.json').write_text(json.dumps(dict(title=STORY['title'],duration=total,sections=public),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
 sections,total,audio=a.prepare_audio(reveal_index=4,final_index=6);script(sections,total)
 print(f'Rendering {total:.2f}s',flush=True)
 video=OUT/'training-but-weaker-ru.mp4'
 cmd=[a.FF,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','30','-i','-','-i',str(audio),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-t',str(total),'-movflags','+faststart',str(video)]
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=(OUT/'encode.log').open('w'))
 for i in range(round(total*30)):
  im=frame(i/30,sections,total)
  if i==1320:im.save(OUT/'poster.png')
  if i in [60,600,1700,round(total*30)-30]:im.save(OUT/f'frame-{i}.png')
  if i%600==0:print(f'{i/30:.0f}s / {total:.0f}s',flush=True)
  p.stdin.write(im.tobytes())
 p.stdin.close()
 if p.wait():raise RuntimeError('Encoding failed')
 print(video,flush=True)
