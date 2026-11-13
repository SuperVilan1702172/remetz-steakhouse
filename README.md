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
