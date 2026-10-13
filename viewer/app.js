/* UI плеера .kvs: галерея, drag&drop, управление воспроизведением, инспектор. */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const canvas = $("#canvas");
  const placeholder = $("#placeholder");
  let player = null;

  // ------------------------------------------------------------------ //
  async function loadBytes(bytes, name) {
    let file;
    try {
      file = await KVS.decode(bytes);
    } catch (err) {
      alert("Не удалось открыть файл: " + err.message);
      return;
    }
    player = new KVS.Player(file);
    player.attach(canvas);
    player.onframe = updateSeek;
    placeholder.style.display = "none";
    canvas.style.display = "block";
    fitCanvas();
    fillMeta(file, name);
    player.seek(0);
    player.play();
    document.title = (file.scene.nm || name) + " — KVS Studio";
  }

  function fitCanvas() {
    const f = player.file;
    const wrap = canvas.parentElement;
    const maxW = wrap.clientWidth - 4;
    const ratio = f.height / f.width;
    canvas.style.width = Math.min(maxW, 620) + "px";
    canvas.style.height = Math.min(maxW, 620) * ratio + "px";
    const seek = $("#seek");
    seek.max = f.frames - 1;
  }

  function updateSeek(frame) {
    const seek = $("#seek");
    if (document.activeElement !== seek) seek.value = frame;
    $("#timecode").textContent =
      Math.floor(frame) + " / " + player.file.frames + "  (" +
      player.file.fps + " fps, " + (frame / player.file.fps).toFixed(2) + " c)";
  }

  function fillMeta(file, name) {
    const rows = [
      ["имя файла", name],
      ["название сцены", file.scene.nm || "—"],
      ["версия контейнера", file.version],
      ["кодек сжатия", file.codec],
      ["холст", file.width + "×" + file.height + " px"],
      ["кадров / fps", file.frames + " / " + file.fps],
      ["длительность", file.duration.toFixed(2) + " c"],
      ["слоёв / ассетов", (file.scene.l || []).length + " / " + Object.keys(file.scene.a || {}).length],
      ["тело в файле", file.rawSize + " Б → " + file.fileSize + " Б (×" + (file.rawSize / file.fileSize).toFixed(2) + ")"],
      ["превью встроено", file.preview ? "да" : "нет"],
    ];
    $("#meta-grid").innerHTML = rows
      .map(([k, v]) => `<div class="kv"><span>${k}</span><b>${v}</b></div>`)
      .join("");
    $("#json").textContent = JSON.stringify(file.scene, null, 1);

    const GEOM = { p: "path", r: "rect", rr: "round-rect", e: "ellipse", ci: "circle", pg: "polygon", st: "star" };
    const BLEND = ["normal", "multiply", "screen", "overlay", "add"];
    $("#layers").innerHTML =
      "<tr><th>#</th><th>имя</th><th>геометрия</th><th>fill</th><th>stroke</th><th>blend</th><th>анимация</th></tr>" +
      (file.scene.l || []).map((l) => {
        const tr = l.t || {};
        const anim = [];
        const names = { p: "position", a: "anchor", s: "scale", r: "rotation", o: "opacity", k: "skew" };
        for (const key in names) if (KVS.isAnimated(tr[key])) anim.push(names[key]);
        if (l.g && l.g.t === "p" && KVS.isAnimated(l.g.s)) anim.push("path.morph");
        if (l.f && KVS.isAnimated(l.f.c)) anim.push("fill.color");
        if (l.s && KVS.isAnimated(l.s.c)) anim.push("stroke.color");
        return `<tr><td>${l.i}</td><td>${l.nm || ""}</td><td>${typeof l.g === "string" ? "ref:" + l.g : GEOM[l.g.t] || "?"}</td>` +
          `<td>${l.f ? "✓" : ""}</td><td>${l.s ? "✓" : ""}</td><td>${BLEND[l.b || 0]}</td>` +
          `<td>${anim.join(", ") || "—"}</td></tr>`;
      }).join("");
  }

  // ------------------------------------------------------------------ //
  async function buildGallery() {
    let manifest = [];
    try {
      manifest = await (await fetch("/samples/manifest.json")).json();
    } catch (e) { /* нет примеров */ }
    const cards = $("#cards");
    cards.innerHTML = "";
    for (const item of manifest) {
      const card = document.createElement("button");
      card.className = "card";
      card.innerHTML = `<div class="thumb"><img alt=""></div>
        <div class="card-name">${item.name}</div>
        <div class="card-sub">${item.width}×${item.height} · ${item.frames}f · ${item.size} Б</div>`;
      card.onclick = async () => {
        const buf = await (await fetch("/samples/" + item.file)).arrayBuffer();
        loadBytes(new Uint8Array(buf), item.file);
      };
      cards.appendChild(card);
      // превью берём прямо из контейнера -- оно вшито в файл
      fetch("/samples/" + item.file)
        .then((r) => r.arrayBuffer())
        .then(async (buf) => {
          const f = await KVS.decode(new Uint8Array(buf), { skipCrc: true });
          if (f.preview) {
            const blob = new Blob([f.preview], { type: "image/png" });
            card.querySelector("img").src = URL.createObjectURL(blob);
          }
        })
        .catch(() => {});
    }
  }

  // ------------------------------------------------------------------ //
  $("#play").onclick = () => {
    if (!player) return;
    if (player.playing) { player.pause(); $("#play").textContent = "▶"; }
    else { player.play(); $("#play").textContent = "⏸"; }
  };
  $("#step-back").onclick = () => player && (player.pause(), $("#play").textContent = "▶", player.seek(player.frame - 1));
  $("#step-fwd").onclick = () => player && (player.pause(), $("#play").textContent = "▶", player.seek(player.frame + 1));
  $("#seek").oninput = (e) => player && (player.pause(), $("#play").textContent = "▶", player.seek(+e.target.value));
  $("#speed").onchange = (e) => player && (player.speed = +e.target.value);

  $("#file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    loadBytes(new Uint8Array(await f.arrayBuffer()), f.name);
  };

  ["dragover", "dragenter"].forEach((ev) =>
    window.addEventListener(ev, (e) => { e.preventDefault(); document.body.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    window.addEventListener(ev, (e) => { e.preventDefault(); document.body.classList.remove("drag"); }));
  window.addEventListener("drop", async (e) => {
    const f = e.dataTransfer.files[0];
    if (!f) return;
    loadBytes(new Uint8Array(await f.arrayBuffer()), f.name);
  });

  window.addEventListener("keydown", (e) => {
    if (!player) return;
    if (e.code === "Space") { e.preventDefault(); $("#play").onclick(); }
    if (e.code === "ArrowLeft") $("#step-back").onclick();
    if (e.code === "ArrowRight") $("#step-fwd").onclick();
  });

  buildGallery();
})();
