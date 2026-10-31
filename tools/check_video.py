"""Decode the deliverable and check duration, dimensions, frames and audio."""
from pathlib import Path
import subprocess, wave
import numpy as np
import imageio_ffmpeg
root=Path(__file__).resolve().parents[1]
video=root/'exports/claude-code-pixel-40s-voiced.mp4'
ff=imageio_ffmpeg.get_ffmpeg_exe()
p=subprocess.run([ff,'-i',str(video),'-f','null','-'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
for token in ['Duration: 00:00:40.00','720x1280','30 fps','Audio: aac','stereo','frame= 1200']:
 assert token in p.stderr,token
# Inspect audio decoded from the final MP4, not just the source WAV.
a=subprocess.run([ff,'-v','error','-i',str(video),'-vn','-f','f32le','-ac','2','-ar','44100','-'],capture_output=True,check=True)
s=np.frombuffer(a.stdout,dtype='<f4').reshape(-1,2)
assert abs(len(s)/44100-40)<.05
assert np.sqrt(np.mean(s*s))>.02
for start in [0,4,9.5,13,18,22,27,30,34.5,39]:
 chunk=s[int(start*44100):int((start+1)*44100)]
 assert np.sqrt(np.mean(chunk*chunk))>.005,f'Silent scene at {start}'
import json
clips=json.loads((root/'exports/dialogue-40s.json').read_text())
assert len(clips)==8
assert len({c['speaker'] for c in clips})==2
for i,c in enumerate(clips):
 assert 0<=c['start']<c['end']<=40
 if i:assert clips[i-1]['end']<c['start']
print('PASS: 40 s / 720x1280 / 30 fps / 1200 frames / AAC stereo; all scenes have audio')
