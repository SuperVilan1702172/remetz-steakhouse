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
  // the drop is a rendered frame sequence (tools/burger_3d.py); scroll picks the frame
  const N = 48, frames = [], cx = burger.getContext('2d');
  let want = 0, shown = null;
  const draw = () => {   // nearest frame that has finished loading, so a slow network never shows a blank
    for (let d = 0; d < N; d++) {
      const f = [frames[want - d], frames[want + d]].find(im => im && im.complete && im.naturalWidth);
      if (!f) continue;
      if (f !== shown) { cx.clearRect(0, 0, burger.width, burger.height); cx.drawImage(f, 0, 0); shown = f; }
      return;
    }
  };
  for (let i = 0; i < N; i++) { const im = new Image(); im.onload = draw; im.src = `assets/burger3d/f${String(i + 1).padStart(3, '0')}.webp`; frames.push(im); }
  const fire = makeFire($('#fire'));
  let landed = false, queued = false;

  function scrub() {
    queued = false;
    const range = hero.offsetHeight - innerHeight;
    const p = clamp(-hero.getBoundingClientRect().top / range);
    const q = clamp(p / 0.72); // the rest of the scroll is a hold with the button on screen
    want = Math.round(q * (N - 1)); draw();
    const s = stage.style, panel = smooth(q, 0.82, 1);
    s.setProperty('--q', q.toFixed(4));
    s.setProperty('--pm', smooth(q, 0.3, 0.92).toFixed(4));
    s.setProperty('--title', (1 - smooth(q, 0.08, 0.66)).toFixed(4));
    s.setProperty('--panel', panel.toFixed(4));
    s.setProperty('--intro', (1 - smooth(q, 0, 0.14)).toFixed(4));
    stage.classList.toggle('panel-on', panel > 0.02);
    fire.level = 0.32 + 0.5 * q;
    const now = q >= 0.73; // frame 35, where the top bun hits
    if (now !== landed) {
      landed = now; stage.classList.toggle('landed', now);
      if (now) { const b = burger.getBoundingClientRect(), st = stage.getBoundingClientRect(); fire.burst(b.left + b.width / 2 - st.left, b.top + b.height * 0.8 - st.top); }
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
  $$('.fire-sec, .room, .rv, .course').forEach(el => seen.observe(el));
  $$('.dishes').forEach(ul => $$('li', ul).forEach((li, i) => li.style.setProperty('--i', i)));

  /* ---------- menu: hovering or focusing a dish shows its photo ---------- */
  $$('.course').forEach(course => {
    const imgs = $$('[data-swap] img', course);
    const show = key => imgs.forEach(im => im.classList.toggle('on', im.dataset.key === key));
    $$('.dishes li', course).forEach(li => li.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') show(li.dataset.img); }));
  });

  /* ---------- booking: a board of free hours, then a sheet that grows out of the button ---------- */
  const pad = n => String(n).padStart(2, '0');
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const fmt = (d, o) => d.toLocaleDateString('en-GB', o);
  const HOURS = Array.from({ length: 12 }, (_, i) => 12 + i);
  const DAYS = [0, 1, 2, 3, 4].map(n => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + n); return d; });
  // shortcut: availability is invented from a hash of date and hour, replace free() with the booking service's answer when one exists
  const free = (d, h) => {
    if (iso(d) === iso(new Date()) && h <= new Date().getHours()) return false;
    let x = 7; for (const c of iso(d) + h) x = (x * 31 + c.charCodeAt(0)) % 997;
    return x % 10 < 6;
  };
  const best = (d, first) => [first, 20, 21, 19, ...HOURS].find(h => h != null && free(d, h));
  const daysEl = $('#days'), slotsEl = $('#slots'), note = $('#boardNote');
  let day = DAYS.find(d => best(d) != null) || DAYS[0], hour = best(day);
  const label = () => `${fmt(day, { weekday: 'long', day: 'numeric', month: 'long' })} at ${pad(hour)}:00`;
  const button = (cls, html) => { const b = document.createElement('button'); b.type = 'button'; b.className = cls; b.innerHTML = html; return b; };

  function paint() {
    $$('.day', daysEl).forEach((b, i) => b.setAttribute('aria-pressed', DAYS[i] === day));
    $$('.slot', slotsEl).forEach((b, i) => b.setAttribute('aria-pressed', HOURS[i] === hour));
    note.textContent = hour == null ? 'That day is fully booked. Pick another day.' : `Your table: ${label()}.`;
  }
  function slots() {
    slotsEl.replaceChildren(...HOURS.map((h, i) => {
      const b = button('slot', `${pad(h)}:00`);
      b.style.setProperty('--i', i);
      if (!free(day, h)) { b.disabled = true; b.setAttribute('aria-label', `${pad(h)}:00, fully booked`); }
      b.addEventListener('click', () => { hour = h; paint(); });
      return b;
    }));
    paint();
  }
  daysEl.append(...DAYS.map((d, i) => {
    const b = button('day', `<small>${i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : fmt(d, { weekday: 'short' })}</small><b>${d.getDate()}</b>`);
    b.setAttribute('aria-label', fmt(d, { weekday: 'long', day: 'numeric', month: 'long' }));
    b.addEventListener('click', () => { if (d !== day) { day = d; hour = best(d, hour); slots(); } });
    return b;
  }));
  slots();
  $('#heroNote').textContent = hour == null ? '' : `Next table: ${label()}`;

  const sheet = $('#sheet'), book = $('#book'), booked = $('#booked'), err = $('#bookError'), go = $('#go');
  const flash = $('.sheet-flash', sheet), inner = $('.sheet-in', sheet);
  $('#guestRow').innerHTML = [1, 2, 3, 4, 5, 6, 7, 8].map(g => `<label><input type="radio" name="guests" value="${g}"${g === 2 ? ' checked' : ''}><span>${g}</span></label>`).join('');
  // sample names shown greyed in the empty name field; real guests' names must never be shown here
  const NAMES = ['Noa Cohen', 'Yossi Levi', 'Maya Friedman', 'Daniel Mizrahi', 'Tamar Katz', 'Omer Peretz'];
  let origin = null, nameTimer = 0, closing = false;

  // the sheet starts as the button (same box, same red) and grows into place; closing plays it backwards
  function morph(back) {
    if (reduced || !origin) return Promise.resolve();
    const a = origin.getBoundingClientRect(), b = sheet.getBoundingClientRect();
    const o = { duration: back ? 320 : 480, easing: 'cubic-bezier(.32,.72,0,1)', direction: back ? 'reverse' : 'normal', fill: 'both' };
    const runs = [
      sheet.animate([{ transform: `translate(${a.left - b.left}px,${a.top - b.top}px) scale(${a.width / b.width},${a.height / b.height})` }, { transform: 'none' }], o),
      flash.animate([{ opacity: 1 }, { opacity: 1, offset: 0.2 }, { opacity: 0 }], o),
      inner.animate([{ opacity: 0 }, { opacity: 0, offset: 0.4 }, { opacity: 1 }], o),
    ];
    return Promise.all(runs.map(r => r.finished)).then(() => runs.forEach(r => r.cancel()));
  }
  function openSheet(btn) {
    if (hour == null) { paint(); $('#reserve').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' }); return; }
    origin = btn;
    $('#sheetWhen').textContent = label();
    book.hidden = false; booked.hidden = true; err.hidden = true;
    sheet.classList.remove('closing');
    sheet.showModal();
    origin.style.visibility = 'hidden';
    morph(false);
    let n = 0; const name = book.elements.name;
    name.placeholder = NAMES[0];
    nameTimer = setInterval(() => { name.placeholder = NAMES[++n % NAMES.length]; }, 1800);
  }
  function closeSheet() {
    if (closing) return Promise.resolve();
    closing = true; sheet.classList.add('closing');
    return morph(true).then(() => sheet.close());
  }
  sheet.addEventListener('close', () => { closing = false; clearInterval(nameTimer); if (origin) origin.style.visibility = ''; });
  sheet.addEventListener('cancel', e => { e.preventDefault(); closeSheet(); });
  sheet.addEventListener('click', e => { if (e.target === sheet || e.target.closest('[data-close]')) closeSheet(); });
  $$('[data-open-book]').forEach(b => b.addEventListener('click', () => openSheet(b)));
  $('#sheetChange').addEventListener('click', () => closeSheet().then(() => $('#reserve').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' })));

  function problem(f) {
    if (f.name.value.trim().length < 2) return [f.name, 'Tell us the name for the booking.'];
    if (f.phone.value.replace(/\D/g, '').length < 9) return [f.phone, 'Enter a phone number we can text, at least 9 digits.'];
    return null;
  }
  book.addEventListener('input', e => {
    e.target.removeAttribute('aria-invalid'); err.hidden = true;
    go.classList.toggle('ready', !problem(book.elements)); // the button lights up once nothing is missing
  });
  book.addEventListener('submit', e => {
    e.preventDefault();
    const f = book.elements, bad = problem(f);
    if (bad) { bad[0].setAttribute('aria-invalid', 'true'); err.textContent = bad[1]; err.hidden = false; bad[0].focus(); return; }
    const g = +f.guests.value;
    $('#bookedTitle').textContent = `See you soon, ${f.name.value.trim().split(/\s+/)[0]}.`;
    $('#bookedText').textContent = `Table for ${g === 1 ? 'one' : g}, ${label()}. We will text ${f.phone.value.trim()} to confirm. The grill will be hot.`;
    book.hidden = true; booked.hidden = false; booked.focus();
  });

  // self-check: the validator rejects a missing name and a short number, and passes a real booking
  console.assert(problem({ name: { value: ' ' }, phone: { value: '0541234567' } })[1].startsWith('Tell'), 'name check');
  console.assert(problem({ name: { value: 'Dana' }, phone: { value: '12-34' } })[1].startsWith('Enter'), 'phone check');
  console.assert(problem({ name: { value: 'Dana' }, phone: { value: '054-123-4567' } }) === null, 'valid booking');
  console.assert(DAYS.length === 5 && !free(DAYS[0], new Date().getHours()), 'no slots in the past');
})();
