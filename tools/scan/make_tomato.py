"""Cut one slice out of the Commons photo 'Sliced Tomatoes.jpg' (CC0) and unwarp its ellipse to a round texture."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage as ndi
src, out = sys.argv[1], sys.argv[2]
A = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
H, W, _ = A.shape; k = W / 500.0
R, G, B = A[..., 0], A[..., 1], A[..., 2]
red = (R > 110) & (R - G > 45) & (R - B > 45)
cy, cx, ry, rx = 120 * k, 160 * k, 92 * k, 120 * k            # rough position of the top-left slice
Y, X = np.mgrid[0:H, 0:W]
win = ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 < 1
m = ndi.binary_fill_holes(ndi.binary_opening(red & win, iterations=3))
lab, n = ndi.label(m); m = lab == (1 + np.argmax(ndi.sum(m, lab, range(1, n + 1))))
ys, xs = np.nonzero(m); c = np.array([xs.mean(), ys.mean()])
ev, evec = np.linalg.eigh(np.cov(np.vstack([xs - c[0], ys - c[1]])))
M = evec @ np.diag(2 * np.sqrt(ev)) @ evec.T                    # unit disc -> the slice's ellipse
S = 1024; v, u = np.mgrid[0:S, 0:S]; u = (u / (S - 1) * 2 - 1) * 1.02; v = (v / (S - 1) * 2 - 1) * 1.02
px = c[0] + M[0, 0] * u + M[0, 1] * v; py = c[1] + M[1, 0] * u + M[1, 1] * v
img = np.dstack([ndi.map_coordinates(A[..., i], [py, px], order=1, mode='nearest') for i in range(3)])
Image.fromarray(img.clip(0, 255).astype(np.uint8)).save(out)
print('centre', c / k, 'axes', 2 * np.sqrt(ev) / k)
