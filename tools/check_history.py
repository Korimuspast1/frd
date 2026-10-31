"""Technical QA for the finished historical video, script, captions and edit list."""
from pathlib import Path
import json,re,subprocess
import numpy as np
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'exports/history';FF=imageio_ffmpeg.get_ffmpeg_exe()
timeline=json.loads((OUT/'timeline.json').read_text());duration=timeline['duration']
assert 90<=duration<=140
sections=timeline['sections'];assert len(sections)==10
shots=[shot for section in sections for shot in section['shots']]
assert all(2<=s['end']-s['start']<=4 for s in shots)
for i,s in enumerate(sections):
 assert s['start']<s['end']<=duration
 if i:assert sections[i-1]['end']<=s['start']
 assert s['words'] and s['words'][0]['start']>=s['start']-1e-4
 assert s['words'][-1]['end']<=s['end']+.02
 assert all(w['start']<=w['end'] for w in s['words'])
 assert ' '.join(w['word'] for w in s['words'])==s['text']
assert sections[0]['shots'][0]['kind']=='street'
assert any(s['kind']=='choice' for s in shots)
assert shots[-1]['kind']=='part2'
assert '$6 000 000' in (ROOT/'tools/make_history.py').read_text()
p=subprocess.run([FF,'-i',str(OUT/'ten-cents-history-ru.mp4'),'-f','null','-'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
for token in ['720x1280','30 fps','Audio: aac','stereo']:
 assert token in p.stderr,token
match=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',p.stderr)
assert match
h,m,s=map(float,match.groups());assert abs(h*3600+m*60+s-duration)<.05
match=re.findall(r'frame=\s*(\d+)',p.stderr);assert int(match[-1])==round(duration*30)
a=subprocess.run([FF,'-v','error','-i',str(OUT/'ten-cents-history-ru.mp4'),'-vn','-f','f32le','-ac','2','-ar','48000','-'],capture_output=True,check=True)
audio=np.frombuffer(a.stdout,dtype='<f4').reshape(-1,2)
assert abs(len(audio)/48000-duration)<.05
assert np.max(np.abs(audio))<1
for section in sections:
 samples=audio[int(section['start']*48000):int(section['end']*48000)]
 assert np.sqrt(np.mean(samples*samples))>.03
for file in ['script-ru.md','captions.srt','poster.png']:
 assert (OUT/file).stat().st_size>500
print(f"PASS: {duration:.2f}s / 720x1280 / 30fps / {len(shots)} shots, each 2–4s / AAC stereo")
print(f"PASS: {sum(len(s['words']) for s in sections)} word cues; all narration sections audible; full script + sources + SRT")
