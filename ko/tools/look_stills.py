"""Cycles CPU look-check stills of a character.blend: front, 3/4, side, back; full body + torso close-up.
    python tools/look_stills.py CHARACTER.blend OUT_PREFIX [--samples 16] [--res 480]"""
import sys, math, bpy
from mathutils import Vector
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
src, out = args[0], args[1]
samples = int(args[args.index('--samples') + 1]) if '--samples' in args else 16
res = int(args[args.index('--res') + 1]) if '--res' in args else 480
bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = samples
sc.cycles.use_denoising = False
sc.render.use_compositing = False; sc.render.use_sequencer = False; sc.render.use_freestyle = False
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 1.5)
sc.render.film_transparent = False
for o in bpy.data.objects:     # physics helpers never render
    if o.type == 'MESH' and (o.name.endswith('Phys') or 'collision' in o.name.lower() or 'Phys ' in o.name or o.name.startswith('WGT')):
        o.hide_render = True
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.55, 0.56, 0.6, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.6
for name, rot, e in (('key', (50, 0, 30), 3.0), ('fill', (60, 0, -120), 1.2), ('rim', (70, 0, 170), 2.0)):
    ld = bpy.data.lights.new(name, 'SUN'); ld.energy = e
    lo = bpy.data.objects.new(name, ld); sc.collection.objects.link(lo)
    lo.rotation_euler = [math.radians(a) for a in rot]
cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render and o.visible_get()]
zs = [ (o.matrix_world @ Vector(c))[2] for o in meshes for c in o.bound_box]
top = max(zs)
def shot(tag, az, z, dist, lens):
    a = math.radians(az)
    tgt = Vector((0, 0, z))
    cam.location = tgt + Vector((math.sin(a) * dist, -math.cos(a) * dist, 0.05))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cd.lens = lens
    sc.render.filepath = f'{out}_{tag}.png'
    bpy.ops.render.render(write_still=True)
for az in (() if ('--check-only' in args or '--face-only' in args) else (0, 35, 90, 180)):
    shot(f'full_{az:03d}', az, top * 0.5, 3.2, 50)
for az in (() if ('--check-only' in args or '--face-only' in args) else (0, 35, 90)):
    shot(f'torso_{az:03d}', az, top * 0.68, 1.5, 50)
if '--check' in args:      # coverage look check: low angles at the hips and the bust
    for tag, az, z, el in (('hips_low_front', 0, 0.62, -0.35), ('hips_low_back', 180, 0.62, -0.35), ('hips_side_low', 90, 0.62, -0.3), ('bust_side', 70, 1.2, 0.0)):
        a = math.radians(az); tgt = Vector((0, 0, z + (0.25 if 'hips' in tag else 0)))
        cam.location = tgt + Vector((math.sin(a) * 1.1, -math.cos(a) * 1.1, el))
        cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler(); cd.lens = 50
        sc.render.filepath = f'{out}_check_{tag}.png'; bpy.ops.render.render(write_still=True)
if '--gaze' in args:       # up_deg,side_deg (+side = her left) on KO_eye_* objects
    up_, side_ = [float(x) for x in args[args.index('--gaze') + 1].split(',')]
    from mathutils import Matrix
    for a_ in [o for o in bpy.data.objects if o.type == 'ARMATURE']:
        for nm in ('eye.L', 'eye.R'):
            pb = a_.pose.bones.get(nm)
            if pb is None:
                continue
            # world-rest rotation (up = -X, her left = +Z) expressed in the bone's rest frame
            Rw = Matrix.Rotation(math.radians(side_), 3, 'Z') @ Matrix.Rotation(math.radians(-up_), 3, 'X')
            B = (a_.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()).normalized()
            pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (B.inverted() @ Rw @ B).to_quaternion()
if '--keys' in args:       # name=val,name=val on Face shape keys
    kb = bpy.data.objects['Face'].data.shape_keys.key_blocks
    for kv in args[args.index('--keys') + 1].split(','):
        k, v = kv.split('='); kb[k].value = float(v)
if '--face' in args:
    hz = top - 0.13
    for tag, az in (('face_000', 0), ('face_030', 30)):
        a = math.radians(az); tgt = Vector((0, 0, hz))
        cam.location = tgt + Vector((math.sin(a) * 0.55, -math.cos(a) * 0.55, 0.02))
        cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler(); cd.lens = 85
        sc.render.resolution_x = sc.render.resolution_y = res
        sc.render.filepath = f'{out}_{tag}.png'; bpy.ops.render.render(write_still=True)
print('done', out)
