"""Validate the supernatural mirror short and its exported edit list."""
from pathlib import Path
import json,re,subprocess
import numpy as np
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'exports/mirror';FF=imageio_ffmpeg.get_ffmpeg_exe()
t=json.loads((OUT/'timeline.json').read_text());duration=t['duration']
assert 90<=duration<=110
assert len(t['sections'])==7
text=' '.join(s['text'] for s in t['sections']).lower()
assert 'отражение' in text and 'зеркале' in text
assert all(term not in text for term in ['перегрузка','восстановление','тренер объясняет'])
shots=[sh for s in t['sections'] for sh in s['shots']]
assert all(2<=sh['end']-sh['start']<=4 for sh in shots)
assert any(sh['kind']=='delay' for sh in shots)
assert any(sh['kind']=='trapped' for sh in shots)
assert any(sh['kind']=='end' for sh in shots)
for i,s in enumerate(t['sections']):
 assert s['start']<s['end']<=duration
 if i:assert t['sections'][i-1]['end']<=s['start']
 assert ' '.join(w['word'] for w in s['words'])==s['text']
p=subprocess.run([FF,'-i',str(OUT/'one-more-rep-mystery-ru.mp4'),'-f','null','-'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
for token in ['720x1280','30 fps','Audio: aac','stereo']:
 assert token in p.stderr,token
m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',p.stderr);assert m
h,mi,s=map(float,m.groups());assert abs(h*3600+mi*60+s-duration)<.05
assert int(re.findall(r'frame=\s*(\d+)',p.stderr)[-1])==round(duration*30)
a=subprocess.run([FF,'-v','error','-i',str(OUT/'one-more-rep-mystery-ru.mp4'),'-vn','-f','f32le','-ac','2','-ar','48000','-'],capture_output=True,check=True)
samples=np.frombuffer(a.stdout,dtype='<f4').reshape(-1,2)
assert abs(len(samples)/48000-duration)<.05
assert np.max(np.abs(samples))<1
for s in t['sections']:
 chunk=samples[int(s['start']*48000):int(s['end']*48000)]
 assert np.sqrt(np.mean(chunk*chunk))>.03
for name in ['script-ru.md','poster.png','captions.srt']:assert (OUT/name).stat().st_size>500
print(f'PASS: {duration:.2f}s / 720x1280 / 30fps / AAC stereo / {len(shots)} shots / 7 narration sections')
