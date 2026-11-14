"""Pack the Blender PNG frames as WebP with alpha for the site: python tools/frames_to_webp.py <png_dir> <out_dir>"""
import sys, glob, os
from PIL import Image
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for p in sorted(glob.glob(os.path.join(src, 'f*.png'))):
    Image.open(p).save(os.path.join(out, os.path.basename(p)[:-4] + '.webp'), quality=80, method=6)
print(len(glob.glob(os.path.join(out, '*.webp'))), 'frames')
