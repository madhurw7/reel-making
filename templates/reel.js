/* Shared animation runtime. compose.py inlines this into each reel's index.html.
   It reads the timing that compose.py wrote into the HTML (data-start, data-duration, data-at ...) and builds ONE
   paused GSAP timeline. HyperFrames seeks that timeline frame by frame, so nothing here may depend on real time,
   randomness or the network. To restyle a single reel, edit that reel's index.html; to change every future reel,
   edit templates/reel.js. */
(function () {
  const root = document.getElementById("root");
  const D = parseFloat(root.dataset.duration);
  const tl = gsap.timeline({ paused: true });
  const num = (el, key) => parseFloat(el.dataset[key]);
  const all = (el, sel) => Array.from(el.querySelectorAll(sel));

  // backdrop drift + progress bar run for the whole reel
  tl.fromTo(".g1", { x: 0, y: 0, scale: 1 }, { x: 190, y: 260, scale: 1.18, duration: D, ease: "sine.inOut" }, 0);
  tl.fromTo(".g2", { x: 0, y: 0, scale: 1 }, { x: -260, y: -220, scale: 1.12, duration: D, ease: "sine.inOut" }, 0);
  tl.fromTo(".g3", { x: 0, y: 0, opacity: 0.6 }, { x: -320, y: 380, opacity: 1, duration: D, ease: "sine.inOut" }, 0);
  tl.fromTo(".r1", { x: 0, y: 0, scale: 1 }, { x: 90, y: -70, scale: 1.12, duration: D, ease: "sine.inOut" }, 0);
  tl.fromTo(".r2", { x: 0, y: 0, scale: 1 }, { x: -130, y: -50, scale: 0.9, duration: D, ease: "sine.inOut" }, 0);
  tl.fromTo(".r3", { x: 0, y: 0 }, { x: 110, y: 90, duration: D, ease: "sine.inOut" }, 0);
  tl.fromTo("#progress-fill", { scaleX: 0, transformOrigin: "left center" }, { scaleX: 1, duration: D, ease: "none" }, 0);

  const popIn = (el, at, o = {}) => el && tl.fromTo(el,
    { scale: 0, rotation: o.rot ?? -18, opacity: 0 },
    { scale: 1, rotation: 0, opacity: 1, duration: o.dur ?? 0.5, ease: "back.out(2)" }, at);
  const rise = (el, at, o = {}) => el && tl.fromTo(el,
    { y: o.y ?? 60, opacity: 0 }, { y: 0, opacity: 1, duration: o.dur ?? 0.4, ease: "power3.out" }, at);
  const words = (sc, sel, at, gap = 0.07) => all(sc, sel + " .w").forEach((w, i) => tl.fromTo(w,
    { y: 70, opacity: 0 }, { y: 0, opacity: 1, duration: 0.42, ease: "back.out(1.5)" }, at + i * gap));

  const SCENES = {
    hook(sc, s) {
      // The hook sits in its final layout at frame 0 (the first frame is the thumbnail on social players),
      // then bounces instead of fading in.
      const e = sc.querySelector(".emoji span");
      tl.fromTo(e, { scale: 1, rotation: 0 },
        { scale: 1.3, rotation: -12, duration: 0.17, yoyo: true, repeat: 1, ease: "power2.out" }, s + 0.04);
      all(sc, ".headline .w").forEach((w, i) => tl.fromTo(w,
        { y: 0 }, { y: -22, duration: 0.14, yoyo: true, repeat: 1, ease: "power2.out" }, s + 0.1 + i * 0.07));
      tl.to(e, { rotation: 9, duration: 0.2, yoyo: true, repeat: 3, ease: "sine.inOut" }, s + 1.3);
    },
    statement(sc, s) {
      popIn(sc.querySelector(".emoji span"), s + 0.08);
      words(sc, ".title", s + 0.24, 0.06);
      tl.fromTo(sc.querySelector(".rule"), { scaleX: 0 }, { scaleX: 1, duration: 0.45, ease: "power3.out" }, s + 0.55);
    },
    bullets(sc, s) {
      rise(sc.querySelector(".chip"), s + 0.05, { y: 30 });
      words(sc, ".title", s + 0.12, 0.05);
      all(sc, ".item").forEach((it) => {
        const at = num(it, "at");
        tl.fromTo(it, { x: -90, opacity: 0 }, { x: 0, opacity: 1, duration: 0.42, ease: "power3.out" }, at);
        tl.fromTo(it.querySelector(".idx"), { scale: 0 }, { scale: 1, duration: 0.4, ease: "back.out(2.4)" }, at + 0.1);
      });
    },
    stat(sc, s) {
      popIn(sc.querySelector(".emoji span"), s + 0.05);
      const big = sc.querySelector(".big"), n = sc.querySelector(".num");
      const end = num(sc, "countEnd");
      tl.fromTo(big, { scale: 0.5, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.45, ease: "back.out(1.8)" }, s + 0.2);
      if (n) {
        const to = num(n, "to"), dec = parseInt(n.dataset.dec || "0", 10), c = { v: 0 };
        const show = () => { n.textContent = c.v.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec }); };
        tl.fromTo(c, { v: 0 }, { v: to, duration: Math.max(0.3, end - (s + 0.25)), ease: "power2.out", onUpdate: show }, s + 0.25);
      }
      tl.to(big, { scale: 1.12, duration: 0.14, yoyo: true, repeat: 1, ease: "power2.out" }, end);
      words(sc, ".title", s + 0.5, 0.05);
    },
    compare(sc, s) {
      words(sc, ".title", s + 0.08, 0.05);
      const sides = all(sc, ".side");
      tl.fromTo(sides[0], { x: -260, opacity: 0 }, { x: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, num(sides[0], "at"));
      tl.fromTo(sides[1], { x: 260, opacity: 0 }, { x: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, num(sides[1], "at"));
      popIn(sc.querySelector(".vs"), num(sides[1], "at") - 0.15, { rot: -40 });
    },
    quiz(sc, s) {
      popIn(sc.querySelector(".chip"), s + 0.05, { rot: -6 });
      words(sc, ".title", s + 0.2, 0.05);
      all(sc, ".item").forEach((it) => rise(it, num(it, "at"), { y: 50 }));
      tl.fromTo(sc.querySelector(".ring-bg"), { opacity: 0 }, { opacity: 1, duration: 0.2 }, s + 0.1);
      const timer = sc.querySelector(".timer"), ring = sc.querySelector(".ring");
      const hs = num(timer, "holdStart"), hold = num(timer, "hold"), C = 2 * Math.PI * 80;
            tl.fromTo(ring, { strokeDasharray: C, strokeDashoffset: 0 }, { strokeDashoffset: C, duration: hold, ease: "none" }, hs);
      all(timer, ".count span").forEach((c, i, arr) => {
        const step = hold / arr.length, at = hs + i * step;
        tl.fromTo(c, { opacity: 0, scale: 1.5 }, { opacity: 1, scale: 1, duration: 0.16, ease: "power2.out" }, at);
        if (i < arr.length - 1) tl.to(c, { opacity: 0, duration: 0.06 }, at + step - 0.07);
      });
    },
    answer(sc, s) {
      const at = num(sc, "revealAt");
      popIn(sc.querySelector(".chip"), s + 0.05, { rot: -6 });
      all(sc, ".item").forEach((it, i) => rise(it, s + 0.08 + i * 0.05, { y: 30, dur: 0.3 }));
      all(sc, ".item.wrong").forEach((it) => tl.to(it, { opacity: 0.32, duration: 0.3 }, at));
      const ok = sc.querySelector(".item.correct");
      if (ok) {
        tl.to(ok, { backgroundColor: "rgba(52, 211, 153, 0.95)", borderColor: "#ffffff", color: "#0b0f1c", duration: 0.25 }, at);
        tl.to(ok, { scale: 1.06, duration: 0.18, yoyo: true, repeat: 1, ease: "power2.out" }, at);
        popIn(ok.querySelector(".mark"), at + 0.05, { dur: 0.4 });
      }
      words(sc, ".title", at + 0.3, 0.05);
    },
    story(sc, s, d) {
      tl.fromTo(sc.querySelector(".spot"), { scale: 0.7, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.6, ease: "power3.out" }, s + 0.05);
      const e = sc.querySelector(".emoji span");
      popIn(e, s + 0.2, { rot: 0, dur: 0.55 });
      tl.to(e, { y: -22, duration: Math.max(0.6, (d - 0.9) / 2), yoyo: true, repeat: 1, ease: "sine.inOut" }, s + 0.8);
      words(sc, ".title", s + 0.4, 0.09);
    },
    outro(sc, s) {
      popIn(sc.querySelector(".emoji span"), s + 0.08);
      tl.to(sc.querySelector(".emoji span"), { rotation: 14, duration: 0.12, yoyo: true, repeat: 5, ease: "sine.inOut" }, s + 0.7);
      words(sc, ".headline", s + 0.25);
      popIn(sc.querySelector(".follow"), s + 0.6, { rot: 0 });
      tl.to(sc.querySelector(".follow"), { scale: 1.09, duration: 0.22, yoyo: true, repeat: 3, ease: "sine.inOut" }, s + 1.25);
      rise(sc.querySelector(".handle"), s + 0.85, { y: 20 });
    },
  };

  const scenes = all(root, ".scene");
  scenes.forEach((sc, i) => {
    const s = num(sc, "start"), d = num(sc, "duration");
    (SCENES[sc.dataset.scene] || SCENES.statement)(sc, s, d);
    const stage = sc.querySelector(".stage");
    tl.fromTo(stage, { scale: 1 }, { scale: 1.035, duration: d, ease: "none" }, s);          // slow push-in
    if (i < scenes.length - 1)                                                                 // quick exit before the cut
      tl.to(stage, { opacity: 0, y: -46, duration: 0.2, ease: "power2.in" }, s + d - 0.21);
  });

  all(root, ".cap").forEach((c) => tl.fromTo(c.querySelector(".cap-text"),
    { scale: 0.84, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.13, ease: "power2.out" }, num(c, "start")));

  window.__timelines = window.__timelines || {};
  window.__timelines["main"] = tl;
  tl.seek(0);
})();
