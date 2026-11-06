import bpy, math, os
from mathutils import Vector
# Reuse the earlier Blender set and materials, then replace its animation.
base=open('claudefilm/scene.py').read().split('# slow curved orbit')[0]
exec(compile(base,'scene.py','exec'))
scene.cycles.samples=4;scene.render.resolution_x=576;scene.render.resolution_y=324
scene.render.fps=12;scene.frame_end=480
# Character models: beveled heads, pupils, open mouths, torsos, arms and legs.
green=mat('zombie skin',(.25,.39,.19),rough=.7);green2=mat('zombie highlights',(.40,.53,.25));shirt=mat('torn indigo shirt',(.07,.12,.20));pants=mat('dark trousers',(.07,.08,.11));red=mat('glowing zombie eyes',(1,.09,.025),emission=4);mouth=mat('mouth',(.02,.015,.013));coffee=mat('coffee projectile',(.32,.12,.035),emission=.4)
zombies=[]
for i in range(3):
 r=bpy.data.objects.new('Zombie '+str(i+1),None);scene.collection.objects.link(r);zombies.append(r)
 box('zombie torso',(0,0,.61),(.47,.30,.55),shirt,.07,r)
 box('zombie head',(0,-.015,1.03),(.44,.34,.36),green,.08,r)
 box('zombie jaw',(0,-.03,.83),(.34,.32,.09),green2,.025,r)
 for x in [-.11,.11]:box('red eye',(x,-.195,1.08),(.07,.025,.065),red,.01,r)
 box('open mouth',(0,-.198,.92),(.17,.023,.045),mouth,.01,r)
 for x in [-.15,.15]:box('zombie leg',(x,0,.19),(.16,.22,.37),pants,.03,r)
 for x in [-.33,.33]:box('outstretched arm',(x,-.18,.70),(.15,.55,.14),green,.04,r)
 # Approach from the far side, stumble back after the coffee projectile.
 x=[-.05,1.7,2.35][i]; y=[1.6,1.75,1.9][i]
 for f,loc,ry in [(1,(x,y,-2),0),(79,(x,y,-2),0),(91,(x,y,0),0),(190,(x-.12,y-1.0,0),.08),(265,(x-.15,y-1.25,0),-.08),(330,(x-.15,y-1.25,0),0),(355,(x+.20,y-.8,0),-.8),(380,(x+.45,y-.5,-.27),-1.5),(480,(x+.45,y-.5,-.27),-1.5)]:
  r.location=loc;r.rotation_euler.y=ry;r.keyframe_insert('location',frame=f);r.keyframe_insert('rotation_euler',frame=f)
# Claude hops and gestures at danger, then hurls an improvised coffee charge.
for f,z,rot in [(1,0,0),(65,.04,0),(110,.15,-.12),(130,0,.12),(165,.13,-.08),(190,0,0),(225,-.05,.16),(260,-.05,.12),(300,.08,-.08),(335,.2,-.15),(355,0,0),(410,.06,-.05),(480,0,0)]:
 root.location.z=z;root.rotation_euler.y=rot;root.keyframe_insert('location',frame=f);root.keyframe_insert('rotation_euler',frame=f)
for f,a in [(1,0),(95,0),(120,-.9),(145,.15),(160,-1),(185,0),(300,-.2),(330,-1.2),(345,.3),(370,0),(480,0)]:
 arm.rotation_euler.y=a;arm.keyframe_insert('rotation_euler',frame=f)
ball=sphere('coffee charge',(1,-.1,1.3),(.14,.14,.14),coffee)
for f,loc,scale in [(1,(1,-.1,1.3),0),(320,(1,-.1,1.3),0),(330,(1,-.1,1.3),1),(350,(1.5,.6,1.1),1),(356,(1.7,.8,.9),0),(480,(1.7,.8,.9),0)]:
 ball.location=loc;ball.scale=(.14*scale,)*3;ball.keyframe_insert('location',frame=f);ball.keyframe_insert('scale',frame=f)
# Red warning light washes the room as the horde arrives.
ld=bpy.data.lights.new('alarm','POINT');ld.color=(1,.045,.02);ld.energy=0;lo=bpy.data.objects.new('alarm',ld);scene.collection.objects.link(lo);lo.location=(0,1,2.5)
for f,power in [(1,0),(80,0),(90,120),(100,15),(110,140),(120,15),(130,140),(140,15),(150,140),(170,20),(190,140),(210,20),(230,140),(250,20),(270,140),(290,20),(310,140),(330,30),(360,0),(480,0)]:ld.energy=power;ld.keyframe_insert('energy',frame=f)
# Orbit, push-ins, and a quick retreat during the charge.
for f,loc,aim in [(1,(4,-9,4.1),(.2,0,1)),(80,(2,-7.5,3.3),(.35,0,1)),(120,(4,-6.8,3),(.65,.1,1)),(190,(1.9,-6.5,2.5),(.7,.1,1)),(265,(-.6,-6.8,2.8),(.55,.1,1)),(330,(2.0,-6,2.8),(.7,.2,1)),(360,(3.2,-8,3.6),(.7,.3,.9)),(480,(2,-8.2,3.7),(.4,.1,.9))]:
 cam.location=loc;point(cam,aim);cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_euler',frame=f)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath('claudefilm/zombie_apocalypse.blend'))
os.makedirs('/home/user/zombie_frames',exist_ok=True)
for i,f in enumerate(range(1,481,3),1):
 scene.frame_set(f);scene.render.filepath=f'/home/user/zombie_frames/{i:04d}.png';bpy.ops.render.render(write_still=True);print('FRAME',i,flush=True)
