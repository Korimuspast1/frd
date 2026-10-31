"""Validate both new shorts by decoding their final MP4 video and audio streams."""
from pathlib import Path
import json, subprocess
import numpy as np
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];FF=imageio_ffmpeg.get_ffmpeg_exe()
for name in ['one-small-fix-25s','friday-deploy-25s']:
 p=ROOT/'exports'/(name+'.mp4')
 r=subprocess.run([FF,'-i',str(p),'-f','null','-'],capture_output=True,text=True)
 assert r.returncode==0,r.stderr
 for token in ['Duration: 00:00:25.00','720x1280','30 fps','Audio: aac','stereo','frame=  750']:
  assert token in r.stderr,(name,token)
 a=subprocess.run([FF,'-v','error','-i',str(p),'-vn','-f','f32le','-ac','2','-ar','44100','-'],capture_output=True,check=True)
 samples=np.frombuffer(a.stdout,dtype='<f4').reshape(-1,2)
 assert abs(len(samples)/44100-25)<.05
 assert np.sqrt(np.mean(samples*samples))>.025
 clips=json.loads((ROOT/'exports'/(name+'.json')).read_text())
 assert len(clips)==5 and len({c['speaker'] for c in clips})==2
 for i,c in enumerate(clips):
  assert 0<=c['start']<c['end']<=25
  if i:assert clips[i-1]['end']<c['start']
  audio=samples[int(c['start']*44100):int(c['end']*44100)]
  assert np.sqrt(np.mean(audio*audio))>.025
 print(f'PASS {name}: 25 seconds, 750 frames, 720x1280, AAC stereo, five non-overlapping voiced lines')
