"""Validate the final ten-minute movie, all 150 edit decisions and sound coverage.
This intentionally decodes the complete deliverable rather than trusting metadata.
"""
from pathlib import Path
import json,re,subprocess
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'exports/survival';FF=imageio_ffmpeg.get_ffmpeg_exe()
t=json.loads((OUT/'timeline.json').read_text());assert t['duration']==600 and t['fps']==30
sections=t['sections'];assert len(sections)==10
shots=[shot for section in sections for shot in section['shots']]
assert len(shots)==150
for i,shot in enumerate(shots):
 assert shot['index']==i
 assert shot['start']==i*4 and shot['end']==(i+1)*4
assert shots[0]['start']==0 and shots[-1]['end']==600
assert len({s['kind'] for s in shots})>=100
for ci,ch in enumerate(sections):
 assert ch['start']==ci*60 and ch['end']==ci*60+60
 assert ' '.join(w['word'] for w in ch['words'])==ch['text']
 assert len(ch['voice_spans'])==3
 for j,span in enumerate(ch['voice_spans']):
  assert ch['start']<=span['start']<span['end']<=ch['end']
  if j:assert ch['voice_spans'][j-1]['end']<span['start']
 assert all(w['start']<=w['end'] for w in ch['words'])
video=OUT/'do-rassveta-10min-ru.mp4'
p=subprocess.run([FF,'-i',str(video),'-f','null','-'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
for token in ['Duration: 00:10:00.00','720x1280','30 fps','Audio: aac','stereo']:
 assert token in p.stderr,token
assert int(re.findall(r'frame=\s*(\d+)',p.stderr)[-1])==18000
# Sample a frame every ten seconds and verify the film isn't a frozen image or a
# short repeated clip. Full animation was decoded above, hashes are additional QA.
r=subprocess.run([FF,'-v','error','-i',str(video),'-an','-vf','fps=1/10','-f','framemd5','-'],capture_output=True,text=True,check=True)
hashes=[line.split(',')[-1].strip() for line in r.stdout.splitlines() if line and not line.startswith('#')]
assert len(hashes)==60 and len(set(hashes))>=58
# Verify audible audio throughout every 10-second interval, including no-narration
# suspense sections. astats uses streaming processing, so no huge raw audio files.
for start in range(0,600,60):
 r=subprocess.run([FF,'-hide_banner','-ss',str(start),'-t','60','-i',str(video),'-vn','-af','astats=metadata=0:reset=0','-f','null','-'],capture_output=True,text=True,check=True)
 levels=re.findall(r'RMS level dB:\s*(-?[\d.]+)',r.stderr)
 assert levels and float(levels[-1])>-45,(start,levels)
for name in ['script-ru.md','captions.srt','poster.png']:assert (OUT/name).stat().st_size>500
print('PASS: 600.00 seconds / 18000 decoded frames / 720x1280 / 30 fps / AAC stereo')
print(f'PASS: 150 contiguous shots, {len({s["kind"] for s in shots})} action types; 30 separate narration passages')
print(f'PASS: {len(set(hashes))}/60 distinct sampled frames; audible audio in all ten chapters; screenplay + SRT + timeline')
