"""Cut the exploded-burger photo into transparent ingredient layers.
Coordinates are in a 1333x2000 preview space; work happens at 2x."""
import json, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

SRC = sys.argv[1]; OUT = sys.argv[2]
K = 2
im = Image.open(SRC).convert('RGB').resize((1333*K, 2000*K), Image.LANCZOS)
A = np.asarray(im).astype(np.float32)
R, G, B = A[..., 0], A[..., 1], A[..., 2]
mx = A.max(-1); lum = 0.3*R + 0.59*G + 0.11*B
H, W = mx.shape
Y, X = np.mgrid[0:H, 0:W] / K          # preview-space coords
gr = G / np.maximum(R, 1)

fg = mx > 34
# name: (box, extra keep-rule)
layers = {
 'bun-top': ((505, 580, 880, 768), None),
 'veg':     ((435, 772, 910, 897), None),
 'bacon':   ((478, 895, 895, 1042), ((Y < 1005) | (G - B < 45)) & ((Y < 1012) | (X > 745))),
 'cheese':  ((455, 1003, 895, 1218), (lum > 120) & ~((X > 560) & (Y > 1192)) & ~((X > 610) & (Y > 1183)) & ((Y > 1040) | (G - B > 45))),
 'patty':   ((498, 1178, 865, 1312), ~((lum > 125) & (gr > 0.62) & (Y < 1218)) & ~((R - B > 105) & (Y > 1278)) & ~((R > 185) & (Y > 1278)) & ~((Y > 1296) & (X < 550))),
 'tomato':  ((430, 1278, 865, 1432), ((R - B > 105) | (R > 185)) & ((gr < 0.8) | (Y < 1395))),
 'lettuce': ((455, 1398, 915, 1612), gr > 0.8),
 'bun-bottom': ((455, 1596, 915, 1725), (Y > 1603) & (X > 490) & (Y < 1704 - (X - 480) * 0.03) & (gr < 0.92)),
}
meta = {}
for name, ((x0, y0, x1, y1), rule) in layers.items():
    m = fg.copy()
    if rule is not None: m &= rule
    box = np.zeros_like(m); box[y0*K:y1*K, x0*K:x1*K] = True
    m &= box
    m = ndi.binary_opening(m, iterations=2)
    m = ndi.binary_closing(m, iterations=6)
    m = ndi.binary_fill_holes(m)
    if name in ('lettuce', 'bun-bottom'): m &= ~((gr < 0.62) & (B / np.maximum(G, 1) > 0.72) & (Y < 1624) & (X < 560))  # palm showing through the lettuce gap
    lab, n = ndi.label(m)
    if n:
        sizes = ndi.sum(m, lab, range(1, n+1))
        m = np.isin(lab, [i+1 for i, s in enumerate(sizes) if s > 0.02*sizes.max()])
    m = ndi.binary_erosion(m, iterations=1)
    alpha = np.clip(ndi.gaussian_filter(m.astype(np.float32), 1.2), 0, 1)
    ys, xs = np.where(alpha > 0.02)
    ya, yb, xa, xb = ys.min(), ys.max()+1, xs.min(), xs.max()+1
    rgba = np.dstack([A[ya:yb, xa:xb], alpha[ya:yb, xa:xb]*255]).astype(np.uint8)
    Image.fromarray(rgba, 'RGBA').save(f'{OUT}/{name}.webp', quality=88, method=6)
    meta[name] = dict(x=xa/K, y=ya/K, w=(xb-xa)/K, h=(yb-ya)/K)
    print(name, meta[name])
json.dump(meta, open(f'{OUT}/layers.json', 'w'), indent=1)
