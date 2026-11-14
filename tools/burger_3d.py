"""Model the Remetz burger in Blender, light it from behind, and render the drop onto the plate.

  blender -b --factory-startup -P tools/burger_3d.py -- <absolute_out_dir> <all | 1,30,64> [samples]

Every piece is released at once and falls under the same gravity, so the low pieces land first.
Written for Blender 2.90 (Cycles). Frames are RGBA PNGs; tools/frames_to_webp.py packs them for the site.
"""
import bpy, bmesh, math, os, random, sys
from mathutils import Vector, Quaternion, noise

argv = sys.argv[sys.argv.index('--') + 1:]
OUT, WHICH = argv[0], argv[1]
SAMPLES = int(argv[2]) if len(argv) > 2 else 64
N, F0, T = 48, 2, 33           # frames, release frame, frames the top bun spends falling
random.seed(11)
SCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan')   # scanned bun and source photos, see tools/scan/README.md

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
col = sc.collection

# ---------------------------------------------------------------- mesh helpers
def obj(name, bm, subsurf=0, thick=0.0):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    if thick:
        m = ob.modifiers.new('solid', 'SOLIDIFY'); m.thickness = thick; m.offset = 0
    if subsurf:
        m = ob.modifiers.new('ss', 'SUBSURF'); m.levels = m.render_levels = subsurf
    return ob

def lathe(name, prof, seg=128, subsurf=2):
    bm = bmesh.new(); rings = []
    for r, z in prof:
        if r < 1e-6: rings.append([bm.verts.new((0, 0, z))])
        else: rings.append([bm.verts.new((r * math.cos(6.28318 * i / seg), r * math.sin(6.28318 * i / seg), z)) for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            if len(a) == 1 and len(b) == 1: continue
            if len(a) == 1: bm.faces.new((a[0], b[i], b[j]))
            elif len(b) == 1: bm.faces.new((a[i], a[j], b[0]))
            else: bm.faces.new((a[i], a[j], b[j], b[i]))
    return obj(name, bm, subsurf=subsurf)

def grid(name, nx, ny, fn, subsurf=1, thick=0.0):
    """fn(u, v) with u, v in 0..1 returns a point."""
    bm = bmesh.new()
    vs = [[bm.verts.new(fn(i / nx, j / ny)) for j in range(ny + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
    return obj(name, bm, subsurf=subsurf, thick=thick)

def give(ob, m): ob.data.materials.append(m); return ob

# ---------------------------------------------------------------- shader helpers
def base(name, rough=0.5, spec=0.5, clear=0.0, sss=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    m.cycles.displacement_method = 'BOTH'      # real displaced geometry plus bump for the fine grain
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = rough; b.inputs['Specular'].default_value = spec
    b.inputs['Clearcoat'].default_value = clear; b.inputs['Clearcoat Roughness'].default_value = 0.12
    b.inputs['Subsurface'].default_value = sss; b.inputs['Subsurface Radius'].default_value = (0.10, 0.05, 0.025)
    tc = nt.nodes.new('ShaderNodeTexCoord'); geo = nt.nodes.new('ShaderNodeNewGeometry')
    return m, nt, b, tc.outputs['Object'], geo.outputs['Normal']

def put(nt, v, sock):
    if hasattr(v, 'is_linked'): nt.links.new(v, sock)
    elif isinstance(v, (int, float)): sock.default_value = v
    else: sock.default_value = (*v, 1) if len(v) == 3 and len(sock.default_value) == 4 else v

def M(nt, op, a, b=None, c=None):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op
    for i, v in enumerate((a, b, c)):
        if v is not None: put(nt, v, n.inputs[i])
    return n.outputs[0]

def axis(nt, v, ax):
    s = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(v, s.inputs[0]); return s.outputs[ax]

def length(nt, v):
    n = nt.nodes.new('ShaderNodeVectorMath'); n.operation = 'LENGTH'; nt.links.new(v, n.inputs[0]); return n.outputs['Value']

def fbm(nt, co, scale, detail=6):
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail
    nt.links.new(co, n.inputs['Vector']); return n.outputs['Fac']

def cells(nt, co, scale, feature='F1'):
    n = nt.nodes.new('ShaderNodeTexVoronoi'); n.feature = feature; n.inputs['Scale'].default_value = scale
    nt.links.new(co, n.inputs['Vector']); return n.outputs['Distance']

def step(nt, v, lo, hi):   # smoothstep
    n = nt.nodes.new('ShaderNodeMapRange'); n.interpolation_type = 'SMOOTHSTEP'
    put(nt, v, n.inputs[0]); n.inputs[1].default_value = lo; n.inputs[2].default_value = hi
    return n.outputs[0]

def remap(nt, v, lo, hi):  # 0..1 to lo..hi
    n = nt.nodes.new('ShaderNodeMapRange'); put(nt, v, n.inputs[0]); n.inputs[3].default_value = lo; n.inputs[4].default_value = hi
    return n.outputs[0]

def ramp(nt, fac, stops):
    n = nt.nodes.new('ShaderNodeValToRGB'); el = n.color_ramp.elements
    el[0].position, el[0].color = stops[0][0], (*stops[0][1], 1)
    el[1].position, el[1].color = stops[-1][0], (*stops[-1][1], 1)
    for pos, c in stops[1:-1]:
        e = el.new(pos); e.color = (*c, 1)
    put(nt, fac, n.inputs['Fac']); return n.outputs['Color']

def mix(nt, fac, a, b, mode='MIX'):
    n = nt.nodes.new('ShaderNodeMixRGB'); n.blend_type = mode
    put(nt, fac, n.inputs[0]); put(nt, a, n.inputs[1]); put(nt, b, n.inputs[2]); return n.outputs[0]

def colour(nt, b, c):
    put(nt, c, b.inputs['Base Color']); put(nt, c, b.inputs['Subsurface Color'])

def bump(nt, b, height, strength, dist=0.02):
    n = nt.nodes.new('ShaderNodeBump'); n.inputs['Strength'].default_value = strength; n.inputs['Distance'].default_value = dist
    put(nt, height, n.inputs['Height']); nt.links.new(n.outputs[0], b.inputs['Normal'])

def displace(nt, height, scale, mid=0.5):
    n = nt.nodes.new('ShaderNodeDisplacement'); n.inputs['Scale'].default_value = scale; n.inputs['Midlevel'].default_value = mid
    put(nt, height, n.inputs['Height']); nt.links.new(n.outputs[0], nt.nodes['Material Output'].inputs['Displacement'])

def glow_through(nt, b, c, fac):   # thin food lit from behind: mix in a translucent lobe
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); put(nt, c, tr.inputs['Color'])
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.inputs['Fac'].default_value = fac
    nt.links.new(b.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], nt.nodes['Material Output'].inputs['Surface'])

def photo(nt, path, vector):
    n = nt.nodes.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(path); n.extension = 'REPEAT'
    nt.links.new(vector, n.inputs['Vector']); return n.outputs['Color']

def planar(nt, co, scale, offset=0.5):   # object XY -> UV
    n = nt.nodes.new('ShaderNodeMapping'); n.inputs['Scale'].default_value = (scale, scale, 1); n.inputs['Location'].default_value = (offset, offset, 0)
    nt.links.new(co, n.inputs['Vector']); return n.outputs['Vector']

def grey(nt, c):
    n = nt.nodes.new('ShaderNodeRGBToBW'); nt.links.new(c, n.inputs[0]); return n.outputs[0]

# ---------------------------------------------------------------- materials
def mat_bun_top():
    m, nt, b, co, nrm = base('bun_top', rough=0.4, clear=0.14, sss=0.04)
    big, fine = fbm(nt, co, 2.6, 4), fbm(nt, co, 80, 8)
    fac = M(nt, 'ADD', M(nt, 'MULTIPLY', axis(nt, co, 'Z'), 1.15), M(nt, 'MULTIPLY', M(nt, 'SUBTRACT', big, 0.5), 0.34))
    c = ramp(nt, fac, [(0.0, (0.76, 0.50, 0.20)), (0.2, (0.56, 0.25, 0.06)), (0.55, (0.36, 0.13, 0.028)), (1.0, (0.21, 0.065, 0.014))])
    c = mix(nt, 1.0, c, ramp(nt, fbm(nt, co, 9, 3), [(0.60, (1, 1, 1)), (0.74, (0.62, 0.46, 0.36))]), 'MULTIPLY')   # darker blisters
    colour(nt, b, c)
    put(nt, remap(nt, fbm(nt, co, 14, 5), 0.24, 0.6), b.inputs['Roughness'])    # egg wash is patchy
    bump(nt, b, M(nt, 'ADD', M(nt, 'MULTIPLY', fine, 0.35), M(nt, 'MULTIPLY', cells(nt, co, 38), 0.65)), 0.16)
    displace(nt, big, 0.07)
    return m

def mat_bun_bot():
    m, nt, b, co, nrm = base('bun_bot', rough=0.55, sss=0.1)
    up = step(nt, axis(nt, nrm, 'Z'), 0.7, 0.95)                                # the cut face
    side = ramp(nt, fbm(nt, co, 4, 4), [(0.3, (0.52, 0.25, 0.07)), (0.7, (0.72, 0.42, 0.14))])
    pores = cells(nt, co, 34)
    crumb = mix(nt, step(nt, pores, 0.05, 0.3), (0.62, 0.42, 0.2), ramp(nt, fbm(nt, co, 7, 4), [(0.3, (0.95, 0.84, 0.62)), (0.75, (0.78, 0.55, 0.28))]))
    colour(nt, b, mix(nt, up, side, crumb))
    bump(nt, b, M(nt, 'ADD', M(nt, 'MULTIPLY', pores, 0.8), M(nt, 'MULTIPLY', fbm(nt, co, 60, 8), 0.3)), 0.45)
    displace(nt, fbm(nt, co, 3, 4), 0.04)
    return m

def mat_patty():
    m, nt, b, co, nrm = base('patty', rough=0.45, spec=0.65, clear=0.28)
    grain, grit, big = cells(nt, co, 20), fbm(nt, co, 46, 8), fbm(nt, co, 5, 5)
    c = ramp(nt, M(nt, 'ADD', M(nt, 'MULTIPLY', grit, 0.55), M(nt, 'MULTIPLY', big, 0.45)),
             [(0.30, (0.022, 0.009, 0.005)), (0.48, (0.09, 0.036, 0.016)), (0.64, (0.20, 0.08, 0.034)), (0.80, (0.33, 0.15, 0.07))])
    wave = nt.nodes.new('ShaderNodeTexWave'); wave.inputs['Scale'].default_value = 2.4; wave.inputs['Distortion'].default_value = 0.6
    nt.links.new(co, wave.inputs['Vector'])
    bars = M(nt, 'MULTIPLY', step(nt, wave.outputs['Fac'], 0.78, 0.9), step(nt, axis(nt, nrm, 'Z'), 0.3, 0.8))   # grill bars on top only
    colour(nt, b, mix(nt, bars, c, (0.012, 0.006, 0.004)))
    put(nt, remap(nt, grit, 0.22, 0.62), b.inputs['Roughness'])                 # fat glistens in patches
    bump(nt, b, M(nt, 'ADD', grit, M(nt, 'MULTIPLY', grain, 0.6)), 0.6)
    displace(nt, M(nt, 'ADD', M(nt, 'MULTIPLY', grain, 0.6), M(nt, 'MULTIPLY', grit, 0.5)), 0.085, mid=0.55)
    return m

def mat_lettuce():
    m, nt, b, co, nrm = base('lettuce', rough=0.42, spec=0.22)
    c = photo(nt, os.path.join(SCAN, 'photos', 'lettuce_src.jpg'), planar(nt, co, 0.36))   # real leaf lettuce, public domain
    c = mix(nt, 1.0, c, ramp(nt, length(nt, co), [(0.2, (1.0, 1.0, 0.9)), (1.2, (0.62, 0.72, 0.55))]), 'MULTIPLY')   # paler rib, deeper frill
    colour(nt, b, c)
    bump(nt, b, M(nt, 'ADD', grey(nt, c), M(nt, 'MULTIPLY', fbm(nt, co, 30, 6), 0.25)), 0.6, dist=0.03)
    displace(nt, fbm(nt, co, 8, 4), 0.05)
    glow_through(nt, b, mix(nt, 0.4, c, (0.55, 0.9, 0.15)), 0.45)
    return m

def mat_tomato():
    m, nt, b, co, nrm = base('tomato', rough=0.42, spec=0.25, sss=0.2)
    face = photo(nt, os.path.join(SCAN, 'photos', 'tomato_face.png'), planar(nt, co, 1 / 1.14))   # a real slice, CC0, unwarped to a disc
    cut = step(nt, M(nt, 'ABSOLUTE', axis(nt, nrm, 'Z')), 0.5, 0.85)
    face = mix(nt, 0.6, face, (1.0, 0.5, 0.4), 'MULTIPLY')        # the backlight washes pale flesh out, so deepen it
    colour(nt, b, mix(nt, cut, (0.52, 0.03, 0.012), face))
    wet = grey(nt, face)
    put(nt, remap(nt, wet, 0.3, 0.55), b.inputs['Roughness'])    # the dark seed gel is the wet part
    bump(nt, b, M(nt, 'ADD', wet, M(nt, 'MULTIPLY', fbm(nt, co, 40, 6), 0.2)), 0.5, dist=0.03)
    return m

def mat_cheese():
    m, nt, b, co, nrm = base('cheese', rough=0.34, sss=0.3)
    c = ramp(nt, fbm(nt, co, 5, 4), [(0.3, (0.95, 0.40, 0.018)), (0.7, (0.98, 0.50, 0.04))])
    colour(nt, b, c); bump(nt, b, fbm(nt, co, 26, 6), 0.05)
    glow_through(nt, b, (1.0, 0.55, 0.05), 0.22)
    return m

def mat_bacon():
    m, nt, b, co, nrm = base('bacon', rough=0.28, clear=0.5)
    wave = nt.nodes.new('ShaderNodeTexWave'); wave.bands_direction = 'Y'
    wave.inputs['Scale'].default_value = 4.6; wave.inputs['Distortion'].default_value = 3.6; wave.inputs['Detail'].default_value = 3
    nt.links.new(co, wave.inputs['Vector'])
    c = ramp(nt, wave.outputs['Fac'], [(0.16, (0.20, 0.022, 0.013)), (0.44, (0.46, 0.075, 0.038)), (0.56, (0.93, 0.70, 0.52)), (0.68, (0.86, 0.58, 0.40)), (0.82, (0.34, 0.045, 0.026))])
    c = mix(nt, 1.0, c, ramp(nt, fbm(nt, co, 13, 5), [(0.42, (1, 1, 1)), (0.8, (0.55, 0.40, 0.30))]), 'MULTIPLY')   # crisped patches
    colour(nt, b, c)
    blister = cells(nt, co, 52)
    bump(nt, b, M(nt, 'ADD', M(nt, 'MULTIPLY', blister, 0.7), M(nt, 'MULTIPLY', fbm(nt, co, 70, 8), 0.4)), 0.55)
    displace(nt, blister, 0.012)
    glow_through(nt, b, (0.95, 0.38, 0.18), 0.18)
    return m

def mat_onion():
    m, nt, b, co, nrm = base('onion', rough=0.22, sss=0.3, clear=0.2)
    fac = M(nt, 'ADD', axis(nt, nrm, 'Z'), M(nt, 'MULTIPLY', M(nt, 'SUBTRACT', fbm(nt, co, 9, 4), 0.5), 0.12))
    colour(nt, b, ramp(nt, fac, [(0.0, (0.28, 0.018, 0.15)), (0.6, (0.42, 0.04, 0.24)), (0.96, (0.64, 0.24, 0.47)), (1.0, (0.88, 0.68, 0.82))]))
    bump(nt, b, fbm(nt, co, 55, 6), 0.08)
    glow_through(nt, b, (0.9, 0.5, 0.8), 0.3)
    return m

def mat_plain(name, c, **kw):
    m, nt, b, co, nrm = base(name, **kw); colour(nt, b, c); return m

# ---------------------------------------------------------------- pieces (origin at each piece's underside)
def dome(R, H, lip=0.13, n=22):
    p = [(0, 0), (R - lip, 0)]
    p += [(R - lip + lip * math.sin(a), lip - lip * math.cos(a)) for a in (0.35, 0.7, 1.05, 1.4)]
    p += [(R * math.cos(t) ** 0.7, lip + H * math.sin(t)) for t in [1.5708 * i / n for i in range(1, n)]]
    return p + [(0, lip + H)]

plate = give(lathe('plate', [(0, 0), (0.95, 0), (1.12, 0.02), (1.36, 0.10), (1.42, 0.115), (1.43, 0.095), (1.15, -0.02), (0.75, -0.06), (0, -0.06)], subsurf=2),
             mat_plain('plate', (0.58, 0.53, 0.46), rough=0.25, spec=0.5, clear=0.25))
patty = give(lathe('patty', [(0, 0), (0.5, 0), (0.9, 0), (1.03, 0.05), (1.07, 0.15), (1.04, 0.25), (0.92, 0.3), (0.5, 0.31), (0, 0.31)], subsurf=4), mat_patty())
tex = bpy.data.textures.new('lumps', 'CLOUDS'); tex.noise_scale = 0.16
d = patty.modifiers.new('lumps', 'DISPLACE'); d.texture = tex; d.strength = 0.07; d.mid_level = 0.5
# buns: Poly Haven's scanned 'Hamburger Buns' (CC0). One whole bun, scaled up, cut in two, the cut faces capped with crumb.
had = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(SCAN, 'hamburger_buns', 'hamburger_buns_2k.gltf'))
scans = sorted([o for o in bpy.data.objects if o not in had and o.type == 'MESH'], key=lambda o: o.name)
whole = scans[0]
for o in scans[1:]: bpy.data.objects.remove(o)
bpy.context.view_layer.update()
me = whole.data; me.transform(whole.matrix_world); whole.matrix_world.identity()
xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
k = 2.16 / max(max(xs) - min(xs), max(ys) - min(ys))             # same footprint as the patty
cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
for v in me.vertices: v.co = ((v.co.x - cx) * k, (v.co.y - cy) * k, (v.co.z - min(zs)) * k)
BUN_H = (max(zs) - min(zs)) * k; CUT = BUN_H * 0.34
print('scanned bun height', round(BUN_H, 3), 'cut at', round(CUT, 3))
scan_mat = me.materials[0]
snt = scan_mat.node_tree; sb = snt.nodes['Principled BSDF']
sb.inputs['Subsurface'].default_value = 0.04; sb.inputs['Clearcoat'].default_value = 0.22; sb.inputs['Clearcoat Roughness'].default_value = 0.2
src = sb.inputs['Base Color'].links[0].from_socket
tcs = snt.nodes.new('ShaderNodeTexCoord')
toast = ramp(snt, M(snt, 'MULTIPLY', axis(snt, tcs.outputs['Object'], 'Z'), 1.0 / BUN_H), [(0.0, (1.0, 0.86, 0.66)), (0.45, (0.95, 0.66, 0.40)), (1.0, (0.78, 0.42, 0.20))])
snt.links.new(mix(snt, 1.0, src, toast, 'MULTIPLY'), sb.inputs['Base Color'])
if sb.inputs['Roughness'].links:
    snt.links.new(M(snt, 'MULTIPLY', sb.inputs['Roughness'].links[0].from_socket, 0.62), sb.inputs['Roughness'])
crumb = mat_bun_bot()

def half(name, keep_top):
    ob = whole.copy(); ob.data = whole.data.copy(); ob.name = name; col.objects.link(ob)
    ob.data.materials.append(crumb)
    bm = bmesh.new(); bm.from_mesh(ob.data)
    r = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, CUT), plane_no=(0, 0, 1), clear_inner=keep_top, clear_outer=not keep_top)
    cap = bmesh.ops.triangle_fill(bm, edges=[e for e in r['geom_cut'] if isinstance(e, bmesh.types.BMEdge)], use_beauty=True)
    for f in cap['geom']:
        if isinstance(f, bmesh.types.BMFace): f.material_index = 1; f.smooth = False
    for v in bm.verts: v.co.z -= CUT if keep_top else 0
    bm.to_mesh(ob.data); bm.free()
    return ob
bun_top, bun_bot = half('bun_top', True), half('bun_bot', False)
bpy.data.objects.remove(whole)
TOP_H = BUN_H - CUT
bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, diameter=1.0)
for v in bm.verts: v.co.y *= 1.0 + 0.45 * v.co.x; v.co.z *= 1.0 + 0.3 * v.co.x      # teardrop
seed_me = bpy.data.meshes.new('seed'); bm.to_mesh(seed_me); bm.free()
for p in seed_me.polygons: p.use_smooth = True
seed_me.materials.append(mat_plain('seed', (0.93, 0.80, 0.55), rough=0.38, sss=0.12))
bpy.context.view_layer.update()
for _ in range(150):
    a, r = random.uniform(0, 6.2832), 0.98 * math.sqrt(random.uniform(0, 1))
    hit, loc, nrm, _i = bun_top.ray_cast(Vector((r * math.cos(a), r * math.sin(a), 5)), Vector((0, 0, -1)))
    if not hit or nrm.z < 0.25: continue
    s_ = bpy.data.objects.new('seed', seed_me); col.objects.link(s_)
    kk = random.uniform(0.85, 1.15)
    s_.location = loc + nrm * 0.004; s_.scale = (0.046 * kk, 0.024 * kk, 0.012 * kk)
    s_.rotation_mode = 'QUATERNION'; s_.rotation_quaternion = nrm.to_track_quat('Z', 'Y') @ Quaternion((0, 0, 1), random.uniform(0, 6.28))
    s_.parent = bun_top

def leaf(u, v):   # ruffled disc: flat in the middle, frilled and lifted at the rim
    th = v * 6.2832; t = u
    n = noise.noise(Vector((math.cos(th) * 1.7, math.sin(th) * 1.7, t * 2.0)))
    n2 = noise.noise(Vector((math.cos(th) * 5.0, math.sin(th) * 5.0, 3.0 + t)))
    n3 = noise.noise(Vector((math.cos(th) * 14.0, math.sin(th) * 14.0, 7.0 + t * 3)))
    r = t * (1.24 + 0.16 * n + 0.06 * n2)
    z = t ** 2.4 * (0.15 * math.sin(th * 9 + 5 * n) + 0.09 * math.sin(th * 23 + 7 * n2) + 0.16 * n2 + 0.05 * n3) + 0.06 * t * n + 0.02
    return (r * math.cos(th), r * math.sin(th), z)
lettuce = give(grid('lettuce', 40, 360, leaf, subsurf=1, thick=0.010), mat_lettuce())

def slab(u, v, drape):   # cheese square; drape pulls the overhanging corners down the side of the patty
    x, y = (u - 0.5) * 2.02, (v - 0.5) * 2.02
    over = max(0.0, math.hypot(x, y) - 1.03)
    k = 1 - 0.32 * drape * over
    return (x * k, y * k, -1.9 * drape * over ** 1.5)
cheese = give(grid('cheese', 48, 48, lambda u, v: slab(u, v, 0.15), subsurf=1, thick=0.04), mat_cheese())
cheese.shape_key_add(name='Basis')
key = cheese.shape_key_add(name='drape')
for i in range(49):
    for j in range(49):
        key.data[i * 49 + j].co = slab(i / 48, j / 48, 1.0)
cheese.rotation_euler.z = math.radians(38)

m_tom = mat_tomato(); tomatoes = []
for i, (x, y, rz) in enumerate([(-0.48, -0.30, 0.3), (0.50, -0.26, 1.9), (0.02, 0.42, 4.0)]):
    tm = give(lathe('tomato%d' % i, [(0, 0), (0.3, 0), (0.50, 0), (0.555, 0.02), (0.56, 0.045), (0.555, 0.07), (0.50, 0.09), (0.3, 0.09), (0, 0.09)], seg=96, subsurf=2), m_tom)
    tm['home'] = (x, y); tm.rotation_euler.z = rz; tomatoes.append(tm)

def rasher(u, v, ph):
    x, y = (u - 0.5) * 2.5, (v - 0.5) * 0.46
    n = noise.noise(Vector((x * 1.3, ph, 0.0)))
    z = 0.042 * (0.6 + 0.9 * abs(n)) * math.sin(x * 9.5 + ph + 2 * n) + 0.03 * math.sin(v * 8 + x * 4) * (0.5 + n) + 0.05
    return (x, y + 0.05 * math.sin(x * 3.1 + ph) + 0.02 * n, z)
m_bac = mat_bacon()
bacons = [give(grid('bacon%d' % i, 120, 12, lambda u, v, ph=ph: rasher(u, v, ph), subsurf=1, thick=0.022), m_bac) for i, ph in enumerate((0.0, 2.1))]
bacons[0].rotation_euler.z, bacons[1].rotation_euler.z = math.radians(18), math.radians(-24)
bacons[0]['home'], bacons[1]['home'] = (0, -0.26), (0, 0.24)

m_on = mat_onion(); onions = []
for i, (ro, x, y) in enumerate([(0.62, -0.30, -0.22), (0.50, 0.38, -0.12), (0.40, 0.0, 0.40)]):
    on = give(lathe('onion%d' % i, [(ro - 0.09, 0), (ro, 0), (ro + 0.012, 0.035), (ro, 0.07), (ro - 0.09, 0.07), (ro - 0.102, 0.035), (ro - 0.09, 0)], seg=96, subsurf=2), m_on)
    on['home'] = (x, y); onions.append(on)

# name, objects, landed z, floating z, tilt (deg, x and y) while floating
STACK = [
    ('bun_bot', [bun_bot], 0.00, 0.55, (4, -3)),
    ('lettuce', [lettuce], CUT - 0.02, 1.40, (-6, 4)),
    ('tomato',  tomatoes,  CUT + 0.06, 2.05, (7, 5)),
    ('patty',   [patty],   CUT + 0.14, 2.60, (-4, -5)),
    ('cheese',  [cheese],  CUT + 0.49, 3.35, (8, -6)),
    ('bacon',   bacons,    CUT + 0.50, 3.85, (-7, 6)),
    ('onion',   onions,    CUT + 0.56, 4.30, (6, 7)),
    ('bun_top', [bun_top], CUT + 0.60, 4.80, (-5, -4)),
]
DMAX = STACK[-1][3] - STACK[-1][2]
TOP0, TOP1 = STACK[-1][3] + TOP_H, STACK[-1][2] + TOP_H

# ---------------------------------------------------------------- camera and light
LENS = 135.0
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = LENS; cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 36; cam_d.clip_end = 200
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 1.1    # the scene is ~20x life size, so this reads like f/22 on a real burger
cam = bpy.data.objects.new('cam', cam_d); col.objects.link(cam); sc.camera = cam
TILT = math.radians(11)
cam.rotation_euler = (math.radians(90) - TILT, 0, 0)

def area(name, loc, target, size, power, color):
    l = bpy.data.lights.new(name, 'AREA'); l.size = size; l.energy = power; l.color = color
    o = bpy.data.objects.new(name, l); col.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o
# backlit: one big warm source low behind, two ember-red rims, and just enough front fill to read the food
area('back', (0, 8, 2.4), (0, 0, 1.3), 6, 2600, (1.0, 0.62, 0.34))
area('rim_l', (-5.5, 3.5, 1.6), (0, 0, 1), 3, 1500, (1.0, 0.30, 0.10))
area('rim_r', (5.5, 3.5, 1.6), (0, 0, 1), 3, 1500, (1.0, 0.30, 0.10))
area('fill', (-3, -9, 3.2), (0, 0, 1), 7, 900, (1.0, 0.90, 0.80))
area('top', (0, 1.5, 9), (0, 0, 1), 4, 120, (1.0, 0.80, 0.60))
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.012, 0.007, 0.005, 1)

sc.render.engine = 'CYCLES'
sc.cycles.samples = SAMPLES
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 810, 1080, 100
sc.render.film_transparent = True
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'Filmic'; sc.view_settings.look = 'Medium High Contrast'
try: sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception as e: print('denoise', e)
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA', 'OPENCL'):
        try:
            prefs.compute_device_type = kind; prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type != 'CPU']
            if gpus:
                for d in prefs.devices: d.use = d.type != 'CPU'
                sc.cycles.device = 'GPU'; print('GPU', kind, [d.name for d in gpus]); break
        except Exception: pass
except Exception as e: print('gpu', e)

# ---------------------------------------------------------------- motion
smooth = lambda x: (lambda t: t * t * (3 - 2 * t))(min(1.0, max(0.0, x)))

def pose(f):
    for i, (name, obs, z1, z0, tilt) in enumerate(STACK):
        dist = z0 - z1
        dur = T * math.sqrt(dist / DMAX)                  # same gravity for all: time goes with the root of the drop
        u = (f - F0) / dur
        if u <= 0: z, k, sq = z0, 0.0, 1.0
        elif u < 1: z, k, sq = z0 - dist * u * u, u * u, 1.0
        else:
            w = (f - F0 - dur) / 7.0                       # one small rebound, then rest
            hop = 0.05 * math.sqrt(dist) * math.exp(-2.6 * w) * abs(math.sin(3.1416 * min(w, 1.0)))
            z, k = z1 + hop, 1.0
            sq = 1 - 0.07 * math.exp(-3.5 * w) * math.cos(4.5 * w)
        drift = math.sin(f * 0.16 + i * 1.7) * 0.012 * (1 - k)
        for ob in obs:
            hx, hy = ob.get('home', (0, 0))
            ob.location = (hx, hy, z + drift)
            ob.rotation_euler.x, ob.rotation_euler.y = math.radians(tilt[0]) * (1 - k), math.radians(tilt[1]) * (1 - k)
            ob.scale = (1 + (1 - sq) * 0.5, 1 + (1 - sq) * 0.5, sq)
        if name == 'cheese': key.value = smooth((u - 0.9) / 0.5)   # the slice sags over the patty as it lands
    # camera dollies in behind the top bun and keeps settling after it has landed
    top = TOP0 - (TOP0 - TOP1) * smooth((f - F0) / (T + 10.0))
    height = max(4.1, top + 1.0)
    dist = height * LENS / 36.0
    cz = max(0.80, top / 2 - 0.05)
    cam.location = (0, -dist * math.cos(TILT), cz + dist * math.sin(TILT))
    cam_d.dof.focus_distance = dist - 0.75                 # focus on the near side of the stack

frames = range(1, N + 1) if WHICH == 'all' else [int(x) for x in WHICH.split(',')]
for f in frames:
    pose(f)
    sc.render.filepath = '%s/f%03d.png' % (OUT, f)
    bpy.ops.render.render(write_still=True)
print('done')
