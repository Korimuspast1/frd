import bpy, math, os, sys
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=4; scene.cycles.use_denoising=True
scene.render.resolution_x=640;scene.render.resolution_y=360;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.world.color=(.03,.03,.03)
scene.view_settings.view_transform='AgX'
scene.render.threads_mode='FIXED';scene.render.threads=6

def mat(name,color,metal=0,rough=.45,emission=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
 if emission:p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=emission
 return m
def box(name,loc,scale,m, bevel=.04,parent=None):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object;o.name=name;o.dimensions=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m)
 if bevel:
  mod=o.modifiers.new('Soft machined edges','BEVEL');mod.width=bevel;mod.segments=3
  o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 if parent:o.parent=parent
 return o
def sphere(name,loc,scale,m):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(m);bpy.ops.object.shade_smooth();return o
def cylinder(name,loc,r,depth,m):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc);o=bpy.context.object;o.name=name;o.data.materials.append(m);mod=o.modifiers.new('Edge bevel','BEVEL');mod.width=.025;mod.segments=3;o.modifiers.new('Normals','WEIGHTED_NORMAL');return o
def point(o,xyz):o.rotation_euler=(Vector(xyz)-o.location).to_track_quat('-Z','Y').to_euler()
def area(name,loc,power,color,size,aim):
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.color=color;data.shape='DISK';data.size=size;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=loc;point(o,aim)
orange=mat('warm coral',(.66,.25,.13),rough=.38); eye=mat('dark glossy eyes',(.008,.013,.018),rough=.18);desk=mat('walnut desk',(.13,.065,.045),rough=.4); dark=mat('graphite',(.025,.033,.045),metal=.3); screen=mat('screen',(.015,.075,.085),emission=.65);mint=mat('code mint',(.17,.7,.57),emission=2);amber=mat('code amber',(.95,.42,.2),emission=2); mug=mat('ceramic',(.78,.76,.65)); wall=mat('midnight',(.018,.026,.045));keys=mat('keycaps',(.15,.17,.2));light=mat('lamplight',(1,.57,.26),emission=4)
# room, tabletop, monitor and props
box('table',(0,0,-.16),(8,5,.3),desk,.08);box('back wall',(0,2.5,2.4),(10,.18,5),wall,.02)
box('monitor base',(-1.5,.7,.07),(1.1,.7,.14),dark);box('monitor stem',(-1.5,.95,.55),(.16,.14,.95),dark)
box('monitor housing',(-1.5,.88,1.48),(2.55,.18,1.55),dark,.08);box('screen',(-1.5,.775,1.48),(2.36,.025,1.35),screen,.025)
for row in range(8):
 for j in range(2 if row%3 else 3):
  x=-2.45+j*.46+(row%2)*.12; box('code', (x,.754,1.95-row*.12),(.32 if j!=1 else .21,.012,.025),mint if j!=1 else amber,.007)
box('keyboard',(-1.5,-.55,.10),(2.0,.78,.15),dark,.06)
for i in range(11):
 for j in range(4):box('key',(-2.33+i*.165,-.81+j*.16,.195),(.13,.12,.05),keys,.012)
cylinder('mug', (2.35,.3,.29),.27,.55,mug);cylinder('coffee',(2.35,.3,.575),.205,.012,desk)
bpy.ops.mesh.primitive_torus_add(major_radius=.18,minor_radius=.055,location=(2.60,.30,.31),rotation=(math.pi/2,0,0));bpy.context.object.data.materials.append(mug)
# character is a 3D reinterpretation of Claude Code pixel mascot
root=bpy.data.objects.new('Clawd animated rig',None);scene.collection.objects.link(root);root.location=(.75,-.05,0)
box('body',(0,0,1.04),(1.42,.72,.92),orange,.095,root)
box('pixel crown',(0,0,1.55),(1.08,.72,.15),orange,.035,root)
for x in [-.52,-.18,.18,.52]:box('foot',(x,0,.38),(.23,.62,.50),orange,.055,root)
for x in [-.28,.28]:box('eye',(x,-.37,1.19),(.13,.06,.18),eye,.025,root)
arm=box('waving arm',(.78,0,.94),(.20,.56,.38),orange,.05,root)
box('left pixel arm',(-.78,0,1.05),(.18,.56,.30),orange,.04,root)
# background practical lamp
cylinder('lamp foot',(3,1.4,.07),.35,.14,dark);cylinder('lamp stem',(3,1.4,.8),.045,1.5,dark);sphere('lamp shade',(3,1.4,1.62),(.37,.37,.22),dark);sphere('lamp bulb',(3,1.4,1.51),(.23,.23,.10),light)
area('large warm key',(-3,-4,5),500,(1,.63,.43),4,(0,0,0));area('blue rim',(2,2.1,4),700,(.35,.56,1),3,(.6,0,1));area('soft frontal',(2,-4,3),250,(.8,.9,1),3,(.5,0,1));area('monitor bounce',(-1.5,.4,1.4),30,(.35,1,.8),1,(0,-1,1))
camdata=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camdata);scene.collection.objects.link(cam);scene.camera=cam;camdata.type='PERSP';camdata.lens=38
# slow curved orbit and camera push-in
for f,loc,aim in [(1,(4,-9,4.1),(.1,0,1)),(90,(2,-8,3.25),(.1,0,1)),(160,(-.6,-7.4,3),(.0,0,1)),(216,(.8,-8,3.5),(.1,0,1))]:
 cam.location=loc;point(cam,aim);cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_euler',frame=f)
for f,z,rot in [(1,0,0),(30,.06,-.04),(60,0,.03),(90,.06,-.03),(120,0,0),(145,-.08,.10),(175,-.08,.10),(200,.06,-.04),(216,0,0)]:
 root.location.z=z;root.rotation_euler.y=rot;root.keyframe_insert('location',frame=f);root.keyframe_insert('rotation_euler',frame=f)
for f,angle in [(1,0),(55,0),(65,-.8),(75,.2),(85,-.7),(95,0),(180,0),(195,-.7),(205,.1),(216,0)]:arm.rotation_euler.y=angle;arm.keyframe_insert('rotation_euler',frame=f)
scene.frame_end=216;scene.render.fps=12
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath('claudefilm/claude_scene.blend'))
if '--still' in sys.argv:
 scene.frame_set(60);scene.render.filepath='/home/user/test_claude.png';bpy.ops.render.render(write_still=True)
else:
 os.makedirs('/home/user/claude_frames',exist_ok=True)
 for i, f in enumerate(range(1,217,2), 1):
  scene.frame_set(f);scene.render.filepath=f'/home/user/claude_frames/{i:04d}.png';bpy.ops.render.render(write_still=True);print('FRAME',f,flush=True)
