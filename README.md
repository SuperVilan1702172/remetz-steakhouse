# Remetz

Single-page site for Remetz, a live-fire steak and burger house in Dizengoff Center, Tel Aviv.

Static files, no build step. Open `index.html`, or serve the folder:

```bash
python -m http.server 8765
```

- `index.html`, `css/styles.css`, `js/main.js`: the whole site.
- `assets/burger/`: the seven transparent burger layers the hero assembles on scroll.
- `tools/cut_layers.py`: regenerates those layers from the source photo (needs Pillow, numpy, scipy).

The restaurant, menu, prices, phone number and bookings are placeholders. The booking form confirms on screen only and sends nothing.

Photos are from Unsplash (Pablo Merchán Montes, Joshua Kantarges, Eiliv Aceron, Engin Akyurt, Jenn Kosar, Adrien Olichon, Patrick Tomasso, Shio Yang and others). Map data © OpenStreetMap contributors.

## The 3D burger

The hero burger is rendered in Blender (`tools/burger_3d.py`, Blender 2.90, Cycles) as 48 frames with alpha, packed to WebP by
`tools/frames_to_webp.py` into `assets/burger3d/`, and scrubbed by scroll on a canvas.
The bun is Poly Haven's scanned "Hamburger Buns" (CC0). Tomato and lettuce use photographs from Wikimedia Commons
(CC0 and public domain). Sources are listed in `tools/scan/README.md`. Patty, cheese, bacon, onion and plate are procedural.
The reservation button is adapted from a Uiverse.io design by barisdogansutcu.
Table availability on the booking board is invented in `js/main.js`; nothing is sent anywhere.
