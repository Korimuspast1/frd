"""QA of the final one-minute personal nostalgia short."""
from pathlib import Path
import json,re,subprocess
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'exports/nostalgia';FF=imageio_ffmpeg.get_ffmpeg_exe()
t=json.loads((OUT/'timeline.json').read_text())
assert t['duration']==60 and t['age']==8 and t['date']=='10 июня 2021'
assert len(t['shots'])==15 and len(t['dialogue'])==6
for i,s in enumerate(t['shots']):assert s['start']==i*4 and s['end']==(i+1)*4
for i,c in enumerate(t['dialogue']):
 assert 0<=c['start']<c['end']<=60
 if i:assert t['dialogue'][i-1]['end']<c['start']
 assert ' '.join(w['word'] for w in c['words'])==c['text']
text=' '.join(c['text'] for c in t['dialogue'])
assert 'Мне восемь.' in text and 'Комсомольск-на-Амуре' in text and 'Гагарина' in text
assert 'семнадцать' not in text
video=OUT/'mne-snova-8-2021-komsomolsk.mp4'
p=subprocess.run([FF,'-i',str(video),'-f','null','-'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
for token in ['Duration: 00:01:00.00','720x1280','30 fps','Audio: aac','stereo']:assert token in p.stderr,token
assert int(re.findall(r'frame=\s*(\d+)',p.stderr)[-1])==1800
p=subprocess.run([FF,'-hide_banner','-i',str(video),'-vn','-af','astats=metadata=0:reset=0','-f','null','-'],capture_output=True,text=True,check=True)
levels=re.findall(r'RMS level dB:\s*(-?[\d.]+)',p.stderr);assert levels and float(levels[-1])>-35
for file in ['script-ru.md','captions.srt','poster.png']:assert (OUT/file).stat().st_size>500
sources=(ROOT/'assets/nostalgia/sources.md').read_text()
assert '2016' in sources and '2017' in sources and 'не хроника' in (ROOT/'tools/make_nostalgia.py').read_text()
print('PASS: exactly 60 seconds / 1800 frames / 720x1280 / 30 fps / AAC stereo')
print('PASS: 8 years old, 10 June 2021, six non-overlapping voiced lines, real park photo credits and date limitations')
