(() => {
  'use strict';
  document.documentElement.classList.add('js');
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const smooth = (v, a, b) => { const x = clamp((v - a) / (b - a)); return x * x * (3 - 2 * x); };
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- fire: additive flame blobs + rising embers on one canvas ---------- */
  function makeFire(canvas) {
    const ctx = canvas.getContext('2d');
    const RES = 0.5; // half-resolution: flames are soft anyway, and it keeps phones cool
    let W = 0, H = 0, flames = [], embers = [], last = 0, raf = 0, level = 0.35, boost = 0;
    const sprite = (r, g, b) => {
      const c = document.createElement('canvas'); c.width = c.height = 64;
      const x = c.getContext('2d'), grd = x.createRadialGradient(32, 32, 0, 32, 32, 32);
      grd.addColorStop(0, `rgba(${r},${g},${b},1)`); grd.addColorStop(0.4, `rgba(${r},${g},${b},.45)`); grd.addColorStop(1, `rgba(${r},${g},${b},0)`);
      x.fillStyle = grd; x.fillRect(0, 0, 64, 64); return c;
    };
    const hot = sprite(255, 190, 80), mid = sprite(255, 90, 24), cool = sprite(150, 16, 4), spark = sprite(255, 214, 140);
    const resize = () => { W = canvas.clientWidth; H = canvas.clientHeight; canvas.width = Math.ceil(W * RES); canvas.height = Math.ceil(H * RES); };
    const rnd = (a, b) => a + Math.random() * (b - a);
    const ember = (x, y, vx, vy) => embers.push({ x, y, vx, vy, life: 0, max: rnd(2.2, 5.5), size: rnd(0.9, 2.4), ph: rnd(0, 6.28) });

    function tick(now) {
      raf = requestAnimationFrame(tick);
      const dt = Math.min(0.05, (now - last) / 1000 || 0.016); last = now;
      boost *= Math.pow(0.12, dt);
      const lv = level + boost, wide = W / 1440;
      // spawn
      let n = 300 * wide * lv * dt; n = Math.floor(n) + (Math.random() < n % 1 ? 1 : 0);
      while (n--) { const r = rnd(22, 64) * (0.55 + lv * 0.6); flames.push({ x: rnd(-40, W + 40), y: H + r * 0.8, vx: rnd(-14, 14), vy: -rnd(90, 260) * (0.5 + lv), r, life: 0, max: rnd(0.8, 1.7) }); }
      if (Math.random() < 14 * wide * lv * dt + 0.02) ember(rnd(0, W), H + 6, rnd(-18, 18), -rnd(40, 130));

      ctx.setTransform(RES, 0, 0, RES, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'lighter';
      for (let i = flames.length - 1; i >= 0; i--) {
        const f = flames[i]; f.life += dt; const k = f.life / f.max;
        if (k >= 1) { flames.splice(i, 1); continue; }
        f.x += (f.vx + Math.sin(now / 240 + f.y / 40) * 16) * dt; f.y += f.vy * dt;
        const r = f.r * (1 - 0.62 * k);
        ctx.globalAlpha = Math.sin(Math.PI * Math.min(1, k * 1.15)) * 0.3;
        ctx.drawImage(k < 0.28 ? hot : k < 0.62 ? mid : cool, f.x - r, f.y - r * 2.4, r * 2, r * 4.8); // tall blobs read as tongues of flame
      }
      for (let i = embers.length - 1; i >= 0; i--) {
        const e = embers[i]; e.life += dt; const k = e.life / e.max;
        if (k >= 1 || e.y < -20) { embers.splice(i, 1); continue; }
        e.vy += 26 * dt * (e.vy > -40 ? -1 : 0.2); // settle into a slow drift
        e.x += (e.vx + Math.sin(now / 520 + e.ph) * 22) * dt; e.y += e.vy * dt;
        const s = e.size * 3.2;
        ctx.globalAlpha = (1 - k) * (0.55 + 0.45 * Math.sin(now / 90 + e.ph * 7));
        ctx.drawImage(spark, e.x - s, e.y - s, s * 2, s * 2);
      }
    }
    return {
      start() { if (!raf && !reduced) { resize(); last = performance.now(); raf = requestAnimationFrame(tick); } },
      stop() { cancelAnimationFrame(raf); raf = 0; },
      resize,
      set level(v) { level = v; },
      burst(x, y) { boost = 0.9; for (let i = 0; i < 70; i++) { const a = rnd(-Math.PI * 0.95, -Math.PI * 0.05), v = rnd(60, 380); ember(x + rnd(-60, 60), y, Math.cos(a) * v, Math.sin(a) * v * 0.9); } },
    };
  }

  /* ---------- hero: scroll scrubs the burger from exploded to plated ---------- */
  const hero = $('#hero'), stage = $('#stage'), burger = $('#burger'), nav = $('#nav');
  const layers = $$('.layer[data-drop]'); // DOM order = bottom to top, so the lowest lands first
  layers.forEach(l => l.style.setProperty('--drop', l.dataset.drop));
  const fire = makeFire($('#fire'));
  let landed = false, queued = false;

  function scrub() {
    queued = false;
    const range = hero.offsetHeight - innerHeight;
    const p = clamp(-hero.getBoundingClientRect().top / range);
    const q = clamp(p / 0.8); // the last fifth of the scroll is a hold with the form on screen
    layers.forEach((l, i) => { const x = clamp((q - i * 0.06) / 0.5); l.style.setProperty('--t', (x * x).toFixed(4)); });
    const s = stage.style, panel = smooth(q, 0.82, 1);
    s.setProperty('--q', q.toFixed(4));
    s.setProperty('--pm', smooth(q, 0.3, 0.92).toFixed(4));
    s.setProperty('--title', (1 - smooth(q, 0.08, 0.66)).toFixed(4));
    s.setProperty('--plate', smooth(q, 0.42, 0.78).toFixed(4));
    s.setProperty('--panel', panel.toFixed(4));
    s.setProperty('--intro', (1 - smooth(q, 0, 0.14)).toFixed(4));
    stage.classList.toggle('panel-on', panel > 0.02);
    fire.level = 0.32 + 0.5 * q;
    const now = q >= 0.8;
    if (now !== landed) {
      landed = now; stage.classList.toggle('landed', now);
      if (now) { const b = burger.getBoundingClientRect(), st = stage.getBoundingClientRect(); fire.burst(b.left + b.width / 2 - st.left, b.bottom - st.top); }
    }
    nav.classList.toggle('solid', p >= 1);
  }
  const onScroll = () => { if (!queued) { queued = true; requestAnimationFrame(scrub); } };
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', () => { fire.resize(); onScroll(); });
  scrub();

  new IntersectionObserver(([e]) => (e.isIntersecting && !document.hidden ? fire.start() : fire.stop())).observe(hero);
  document.addEventListener('visibilitychange', () => { if (document.hidden) fire.stop(); else if (hero.getBoundingClientRect().bottom > 0) fire.start(); });

  /* ---------- one-shot reveals ---------- */
  const seen = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('seen'); seen.unobserve(e.target); } }), { threshold: 0.15 });
  $$('.fire-sec, .room').forEach(el => seen.observe(el));

  /* ---------- menu: hovering or focusing a dish shows its photo ---------- */
  $$('.course').forEach(course => {
    const imgs = $$('[data-swap] img', course);
    const show = key => imgs.forEach(im => im.classList.toggle('on', im.dataset.key === key));
    $$('.dishes li', course).forEach(li => li.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') show(li.dataset.img); }));
  });

  /* ---------- booking ---------- */
  const pad = n => String(n).padStart(2, '0');
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const today = new Date(), tomorrow = new Date(Date.now() + 864e5);
  $$('[data-times]').forEach(sel => { for (let m = 12 * 60; m <= 23 * 60; m += 30) sel.add(new Option(`${pad(m / 60 | 0)}:${pad(m % 60)}`)); sel.value = '20:00'; });
  $$('[data-guests]').forEach(sel => { for (let g = 1; g <= 8; g++) sel.add(new Option(g)); sel.value = '2'; });
  $$('input[type="date"]').forEach(d => { d.min = iso(today); d.value = iso(tomorrow); });

  const quick = $('#quick'), book = $('#book'), booked = $('#booked'), err = $('#bookError');
  quick.addEventListener('submit', e => {
    e.preventDefault();
    ['date', 'time', 'guests'].forEach(n => { if (quick.elements[n].value) book.elements[n].value = quick.elements[n].value; });
    $('#reserve').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
    book.elements.name.focus({ preventScroll: true });
  });

  function problem(f) {
    if (!f.date.value || f.date.value < iso(new Date())) return [f.date, 'Pick a date from today onwards.'];
    if (f.name.value.trim().length < 2) return [f.name, 'Tell us the name for the booking.'];
    if (f.phone.value.replace(/\D/g, '').length < 9) return [f.phone, 'Enter a mobile number we can text, at least 9 digits.'];
    return null;
  }
  book.addEventListener('submit', e => {
    e.preventDefault();
    const f = book.elements, bad = problem(f);
    $$('[aria-invalid]', book).forEach(el => el.removeAttribute('aria-invalid'));
    if (bad) { bad[0].setAttribute('aria-invalid', 'true'); err.textContent = bad[1]; err.hidden = false; bad[0].focus(); return; }
    err.hidden = true;
    const [y, m, d] = f.date.value.split('-').map(Number);
    const when = new Date(y, m - 1, d).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
    const g = +f.guests.value;
    $('#bookedTitle').textContent = `See you ${when}, ${f.name.value.trim().split(/\s+/)[0]}.`;
    $('#bookedText').textContent = `Table for ${g === 1 ? 'one' : g} at ${f.time.value}. We will text ${f.phone.value.trim()} to confirm. The grill will be hot.`;
    book.hidden = true; booked.hidden = false; booked.focus();
  });
  $('#bookAgain').addEventListener('click', () => { booked.hidden = true; book.hidden = false; book.elements.date.focus(); });
  book.addEventListener('input', e => { e.target.removeAttribute('aria-invalid'); err.hidden = true; });

  // self-check: the form validator rejects the three ways a booking can be wrong
  console.assert(problem({ date: { value: '' }, name: { value: 'Dana' }, phone: { value: '0541234567' } })[1].startsWith('Pick'), 'date check');
  console.assert(problem({ date: { value: '2999-01-01' }, name: { value: ' ' }, phone: { value: '0541234567' } })[1].startsWith('Tell'), 'name check');
  console.assert(problem({ date: { value: '2999-01-01' }, name: { value: 'Dana' }, phone: { value: '12-34' } })[1].startsWith('Enter'), 'phone check');
  console.assert(problem({ date: { value: '2999-01-01' }, name: { value: 'Dana' }, phone: { value: '054-123-4567' } }) === null, 'valid booking');
})();
