"""Decode the deliverable and check duration, dimensions, frames and audio."""
from pathlib import Path
import subprocess, wave
import numpy as np
import imageio_ffmpeg
root=Path(__file__).resolve().parents[1]
video=root/'exports/claude-code-pixel-25s.mp4'
ff=imageio_ffmpeg.get_ffmpeg_exe()
p=subprocess.run([ff,'-i',str(video),'-f','null','-'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
for token in ['Duration: 00:00:25.00','720x1280','30 fps','Audio: aac','stereo','frame=  750']:
 assert token in p.stderr,token
# Inspect audio decoded from the final MP4, not just the source WAV.
a=subprocess.run([ff,'-v','error','-i',str(video),'-vn','-f','f32le','-ac','2','-ar','44100','-'],capture_output=True,check=True)
s=np.frombuffer(a.stdout,dtype='<f4').reshape(-1,2)
assert abs(len(s)/44100-25)<.05
assert np.sqrt(np.mean(s*s))>.02
for start in [0,4,7,9,11,16,21,23]:
 chunk=s[int(start*44100):int((start+1)*44100)]
 assert np.sqrt(np.mean(chunk*chunk))>.005,f'Silent scene at {start}'
print('PASS: 25 s / 720x1280 / 30 fps / 750 frames / AAC stereo; all scenes have audio')
