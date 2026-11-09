/* HUMO PLASTIK — frontend */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  };

  /* ================= TIL (i18n) ================= */
  const LANGS = ["uz", "ru", "en"];
  const DICT = window.I18N;
  // O'zbekcha matnlarni HTML ning o'zidan yig'ib olamiz
  $$("[data-i18n]").forEach(el => { DICT.uz[el.dataset.i18n] ??= el.textContent.trim(); });
  $$("[data-i18n-html]").forEach(el => { DICT.uz[el.dataset.i18nHtml] ??= el.innerHTML.trim(); });
  $$("[data-i18n-ph]").forEach(el => { DICT.uz[el.dataset.i18nPh] ??= el.placeholder; });

  let lang = new URLSearchParams(location.search).get("lang") || store.get("humo_lang");
  if (!LANGS.includes(lang)) {
    const nav = (navigator.language || "uz").slice(0, 2);
    lang = nav === "ru" ? "ru" : nav === "en" ? "en" : "uz";
  }
  const t = (key, vars = {}) => {
    let s = DICT[lang]?.[key] ?? DICT.uz[key] ?? key;
    for (const k in vars) s = s.replaceAll(`{${k}}`, vars[k]);
    return s;
  };
  // ko'p tilli maydon: {uz,ru,en} yoki oddiy matn
  const L = (v, lg = lang) => (v && typeof v === "object" ? v[lg] ?? v.uz : v ?? "");
  // "30x55 sm", "15 mkm", "50 sm rulon" kabi o'lchov birliklarini tarjima qiladi
  const unitize = s => String(s).replace(/(\d)\s?(sm|mkm|kg|L)\b/g, (m, d, u) => `${d} ${t("u." + u)}`).replace(/\brulon\b/g, t("u.rulon"));
  const num = n => Number(n).toLocaleString(lang === "en" ? "en-US" : "ru-RU").replace(/ /g, " ");
  const money = n => num(Math.round(n)) + " " + t("money");
  const unit = u => t("unit." + u);

  function applyLang() {
    document.documentElement.lang = lang;
    document.title = t("meta.title");
    $('meta[name="description"]').content = t("meta.desc");
    $$("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-html]").forEach(el => { el.innerHTML = t(el.dataset.i18nHtml); });
    $$("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
    $("#langCur").textContent = lang.toUpperCase();
    $$("[data-lang]").forEach(b => b.classList.toggle("is-active", b.dataset.lang === lang));
    if (PRODUCTS.length) {
      renderProducts(curCat); renderMarquee(); calcFill(true); renderCart(); applySettings(SETTINGS);
      if (current) openProduct(current.id, true);
    }
  }
  function setLang(lg) { lang = lg; store.set("humo_lang", lg); applyLang(); }

  const langBox = $("#lang");
  $("#langBtn").addEventListener("click", e => {
    e.stopPropagation();
    const open = langBox.classList.toggle("open");
    $("#langBtn").setAttribute("aria-expanded", open);
  });
  $$("[data-lang]").forEach(b => b.addEventListener("click", () => { setLang(b.dataset.lang); langBox.classList.remove("open"); }));
  document.addEventListener("click", e => { if (!langBox.contains(e.target)) langBox.classList.remove("open"); });

  /* ================= MA'LUMOTLAR ================= */
  let PRODUCTS = [];
  let SETTINGS = {};
  let curCat = "all";
  const byId = id => PRODUCTS.find(p => p.id === id);
  const qtyText = (q, p) => `${num(q)} ${unit(p.unit)}`;
  const optText = (p, field, i, lg) => unitize(L(p[field][i], lg));
  const optUz = (p, field, i) => L(p[field][i], "uz");

  /* ================= SAVAT ================= */
  let cart = [];
  try { cart = JSON.parse(store.get("humo_cart2") || "[]"); } catch { cart = []; }
  const saveCart = () => store.set("humo_cart2", JSON.stringify(cart));
  const stepOf = p => (p.min >= 1000 ? 500 : p.min >= 100 ? 50 : 10);

  function addToCart(item) {
    const key = [item.id, item.si, item.ti, item.ci, item.logo].join("|");
    const ex = cart.find(c => c.key === key);
    if (ex) ex.qty += item.qty; else cart.push({ ...item, key });
    saveCart(); renderCart();
    $$(".cart-btn, .tabbar__cart").forEach(b => { b.classList.remove("bump"); void b.offsetWidth; b.classList.add("bump"); });
    if (navigator.vibrate) navigator.vibrate(15);
    toast(t("toast.added"));
  }

  function renderCart() {
    cart = cart.filter(c => byId(c.id));
    $("#cartItems").innerHTML = cart.map((c, i) => {
      const p = byId(c.id);
      const opts = [optText(p, "sizes", c.si), optText(p, "thickness", c.ti), optText(p, "colors", c.ci), c.logo ? t("cart.logo") : ""]
        .filter(Boolean).join(" · ");
      return `<div class="ci-row">
        <img src="${p.img}" alt="">
        <div><h4>${L(p.name)}</h4><small>${opts}</small>
          <div class="stepper"><button type="button" data-ci="${i}" data-d="-1">−</button>
          <input type="number" inputmode="numeric" value="${c.qty}" data-ciq="${i}" min="${p.min}"><button type="button" data-ci="${i}" data-d="1">+</button></div>
          <small>${t("cart.minLabel", { u: unit(p.unit), n: num(p.min) })}</small></div>
        <div class="ci-row__right"><b>${qtyText(c.qty, p)}</b><button class="ci-del" data-del="${i}">${t("cart.remove")}</button></div>
      </div>`;
    }).join("");
    $("#cartTotal").textContent = t("cart.items", { n: cart.length });
    $$("[data-cart-count]").forEach(el => { el.textContent = cart.length; el.classList.toggle("is-zero", !cart.length); });
    $("#cart").classList.toggle("is-empty", cart.length === 0);
  }

  $("#cartItems").addEventListener("click", e => {
    const tg = e.target;
    if (tg.dataset.del != null) { cart.splice(+tg.dataset.del, 1); saveCart(); renderCart(); }
    if (tg.dataset.ci != null) {
      const c = cart[+tg.dataset.ci], p = byId(c.id);
      c.qty = Math.max(p.min, c.qty + stepOf(p) * +tg.dataset.d);
      saveCart(); renderCart();
    }
  });
  $("#cartItems").addEventListener("change", e => {
    const i = e.target.dataset.ciq; if (i == null) return;
    const c = cart[+i], p = byId(c.id);
    c.qty = Math.max(p.min, parseInt(e.target.value) || p.min);
    saveCart(); renderCart();
  });

  /* ================= KATALOG ================= */
  function renderProducts(cat = "all") {
    curCat = cat;
    const list = PRODUCTS.filter(p => cat === "all" || p.cat === cat);
    $("#products").innerHTML = list.map((p, i) => {
      const th = p.thickness.length > 1 ? `${optText(p, "thickness", 0)} – ${optText(p, "thickness", p.thickness.length - 1)}` : optText(p, "thickness", 0);
      return `
      <article class="card product" style="animation-delay:${i * 50}ms">
        <div class="product__img" data-open="${p.id}">
          <img src="${p.img}" alt="${L(p.name)}" loading="lazy">
          ${p.badge ? `<span class="badge">${t("badge." + p.badge)}</span>` : ""}
        </div>
        <div class="product__body">
          <h3 data-open="${p.id}">${L(p.name)}</h3>
          <p>${L(p.desc)}</p>
          <div class="tags"><span>${t("card.sizes", { n: p.sizes.length })}</span><span>${th}</span></div>
          <div class="product__foot">
            <div class="price"><small>${t("pm.qty")}</small><b>${t("card.min", { n: num(p.min), u: unit(p.unit) })}</b></div>
            <button class="add-btn" data-open="${p.id}" aria-label="${t("card.order")}">
              <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg><span>${t("card.order")}</span></button>
          </div>
        </div>
      </article>`;
    }).join("");
  }

  function renderMarquee() {
    const names = PRODUCTS.map(p => `<span>${L(p.name)}</span>`).join("");
    $("#marquee").innerHTML = names + names;
  }

  $("#tabs").addEventListener("click", e => {
    const b = e.target.closest(".tab"); if (!b) return;
    $$(".tab").forEach(x => x.classList.toggle("is-active", x === b));
    b.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
    renderProducts(b.dataset.cat);
  });
  $("#products").addEventListener("click", e => {
    const el = e.target.closest("[data-open]");
    if (el) openProduct(el.dataset.open);
  });

  /* ================= MAHSULOT OYNASI ================= */
  let current = null;
  const opts = (p, field) => p[field].map((_, i) => `<option value="${i}">${optText(p, field, i)}</option>`).join("");

  function openProduct(id, keep = false) {
    const p = current = byId(id);
    const prev = keep ? { s: $("#pmSize").value, th: $("#pmThick").value, c: $("#pmColor").value, q: $("#pmQty").value, l: $("#pmLogo").checked } : null;
    $("#pmImg").src = p.img; $("#pmImg").alt = L(p.name);
    $("#pmName").textContent = L(p.name);
    $("#pmDesc").textContent = L(p.desc);
    $("#pmQtyUnit").textContent = unit(p.unit);
    $("#pmSize").innerHTML = opts(p, "sizes");
    $("#pmThick").innerHTML = opts(p, "thickness");
    $("#pmColor").innerHTML = opts(p, "colors");
    $("#pmQty").min = p.min;
    $("#pmMin").textContent = t("pm.min", { n: num(p.min), u: unit(p.unit) });
    $("#pmLogoWrap").style.display = p.logo ? "" : "none";
    if (prev) {
      $("#pmSize").value = prev.s; $("#pmThick").value = prev.th; $("#pmColor").value = prev.c; $("#pmQty").value = prev.q; $("#pmLogo").checked = prev.l;
    } else {
      $("#pmQty").value = p.min; $("#pmLogo").checked = false; $("#pmMin").classList.remove("err");
      openModal("#productModal");
    }
    pmTotal();
  }
  function pmTotal() {
    const q = parseInt($("#pmQty").value) || 0;
    $("#pmTotal").textContent = qtyText(q, current);
  }
  $("#pmQty").addEventListener("input", pmTotal);
  $("#pmLogo").addEventListener("change", pmTotal);
  $$("#productModal [data-step]").forEach(b => b.addEventListener("click", () => {
    const q = parseInt($("#pmQty").value) || current.min;
    $("#pmQty").value = Math.max(current.min, q + stepOf(current) * +b.dataset.step);
    pmTotal();
  }));
  $("#pmAdd").addEventListener("click", () => {
    const q = parseInt($("#pmQty").value) || 0;
    if (q < current.min) { $("#pmMin").classList.add("err"); return; }
    addToCart({ id: current.id, qty: q, si: +$("#pmSize").value, ti: +$("#pmThick").value, ci: +$("#pmColor").value,
      logo: $("#pmLogo").checked && current.logo });
    closeAll();
  });

  /* ================= KALKULYATOR ================= */
  function calcFill(keep = false) {
    const sel = $("#calcProduct"), was = sel.value;
    sel.innerHTML = PRODUCTS.map(p => `<option value="${p.id}">${L(p.name)}</option>`).join("");
    if (keep && was) { sel.value = was; calcLabels(); calc(); } else calcSet();
  }
  function calcLabels() {
    const p = byId($("#calcProduct").value);
    $("#calcUnit").textContent = unit(p.unit);
    $("#calcMin").textContent = t("calc.min", { n: num(p.min), u: unit(p.unit) });
    $("#calcLogoWrap").style.display = p.logo ? "" : "none";
  }
  function calcSet() {
    const p = byId($("#calcProduct").value);
    $("#calcQty").value = p.min * 2; $("#calcQty").min = p.min;
    $("#calcLogo").checked = false;
    calcLabels(); calc();
  }
  function calc() {
    const p = byId($("#calcProduct").value);
    const q = parseInt($("#calcQty").value) || 0;
    $("#calcTotal").textContent = qtyText(q, p);
    $("#calcPer").textContent = L(p.name) + ($("#calcLogo").checked && p.logo ? " · " + t("calc.logo").toLowerCase() : "");
    $("#calcMin").classList.toggle("err", q < p.min);
  }
  $("#calcProduct").addEventListener("change", calcSet);
  $("#calcQty").addEventListener("input", calc);
  $("#calcLogo").addEventListener("change", calc);
  $("#calcAdd").addEventListener("click", () => {
    const p = byId($("#calcProduct").value);
    const q = parseInt($("#calcQty").value) || 0;
    if (q < p.min) { $("#calcMin").classList.add("err"); toast(t("toast.min", { n: num(p.min), u: unit(p.unit) }), true); return; }
    addToCart({ id: p.id, qty: q, si: 0, ti: 0, ci: 0, logo: $("#calcLogo").checked && p.logo });
  });

  /* ================= OYNALAR ================= */
  function openModal(sel) {
    const m = $(sel); m.classList.add("is-open"); m.setAttribute("aria-hidden", "false");
    document.body.classList.add("lock");
  }
  function closeAll() {
    $$(".modal.is-open, .drawer.is-open").forEach(m => { m.classList.remove("is-open"); m.setAttribute("aria-hidden", "true"); });
    document.body.classList.remove("lock");
    current = null;
  }
  document.addEventListener("click", e => { if (e.target.closest("[data-close]")) closeAll(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeAll(); });
  $("#cartOpen").addEventListener("click", () => openModal("#cart"));
  $("#tabCart").addEventListener("click", () => openModal("#cart"));

  // Pastga surib yopish (telefonda bottom-sheet)
  $$(".modal__box").forEach(box => {
    let y0 = null, dy = 0;
    box.addEventListener("touchstart", e => { if (box.scrollTop <= 0) { y0 = e.touches[0].clientY; dy = 0; } }, { passive: true });
    box.addEventListener("touchmove", e => {
      if (y0 == null) return;
      dy = e.touches[0].clientY - y0;
      if (dy > 0) { box.style.transition = "none"; box.style.transform = `translateY(${dy}px)`; }
    }, { passive: true });
    box.addEventListener("touchend", () => {
      box.style.transition = ""; box.style.transform = "";
      if (y0 != null && dy > 110) closeAll();
      y0 = null;
    });
  });

  /* ================= TELEFON MASKASI ================= */
  function maskPhone(v) {
    let d = v.replace(/\D/g, "");
    if (!d.startsWith("998")) d = "998" + d.replace(/^998/, "");
    d = d.slice(0, 12);
    const p = [d.slice(0, 3), d.slice(3, 5), d.slice(5, 8), d.slice(8, 10), d.slice(10, 12)].filter(Boolean);
    return "+" + p.join(" ");
  }
  $$("[data-mask]").forEach(i => {
    i.addEventListener("focus", () => { if (!i.value) i.value = "+998 "; });
    i.addEventListener("input", () => { i.value = maskPhone(i.value); });
    i.addEventListener("blur", () => { if (i.value.replace(/\D/g, "").length <= 3) i.value = ""; });
  });
  const phoneOk = v => v.replace(/\D/g, "").length === 12;

  function validate(form) {
    let ok = true;
    $$("[required]", form).forEach(el => {
      const bad = el.dataset.mask != null ? !phoneOk(el.value) : el.value.trim().length < 2;
      el.classList.toggle("invalid", bad);
      if (bad) ok = false;
    });
    return ok;
  }

  async function post(url, data) {
    let r;
    try {
      r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...data, lang }) });
    } catch { throw new Error(t("toast.net")); }
    const j = await r.json().catch(() => ({ ok: false }));
    if (!j.ok) throw new Error(j.code ? t("err." + j.code) : (j.error || t("toast.net")));
    return j;
  }

  /* ================= BUYURTMA ================= */
  $("#orderForm").addEventListener("submit", async e => {
    e.preventDefault();
    const f = e.target;
    if (!validate(f)) { toast(t("toast.fill"), true); return; }
    const btn = $("#orderSubmit");
    btn.disabled = true; btn.textContent = t("cart.sending");
    try {
      const customer = Object.fromEntries(new FormData(f));
      // Admin uchun variantlar o'zbek tilida yuboriladi
      const items = cart.map(c => {
        const p = byId(c.id);
        return { id: c.id, qty: c.qty, logo: c.logo, size: optUz(p, "sizes", c.si), thickness: optUz(p, "thickness", c.ti), color: optUz(p, "colors", c.ci) };
      });
      const r = await post("/api/order", { customer, items });
      cart = []; saveCart(); renderCart(); f.reset(); closeAll();
      $("#okTitle").textContent = t("ok.order", { id: r.order_id });
      $("#okText").textContent = t("ok.orderText");
      openModal("#successModal");
      if (navigator.vibrate) navigator.vibrate([20, 40, 20]);
    } catch (err) {
      toast(err.message, true);
    } finally {
      btn.disabled = false; btn.textContent = t("cart.submit");
    }
  });

  $("#callbackForm").addEventListener("submit", async e => {
    e.preventDefault();
    const f = e.target;
    if (!validate(f)) { toast(t("toast.fill"), true); return; }
    const btn = $("button[type=submit]", f); btn.disabled = true;
    try {
      await post("/api/callback", Object.fromEntries(new FormData(f)));
      f.reset();
      $("#okTitle").textContent = t("ok.thanks");
      $("#okText").textContent = t("ok.cbText");
      openModal("#successModal");
    } catch (err) { toast(err.message, true); }
    finally { btn.disabled = false; }
  });

  /* ================= YORDAMCHILAR ================= */
  let tt;
  function toast(msg, err = false, ms = 2600) {
    const el = $("#toast"); el.textContent = msg; el.classList.toggle("err", err); el.classList.add("show");
    clearTimeout(tt); tt = setTimeout(() => el.classList.remove("show"), ms);
  }

  function applySettings(s) {
    const tel = v => "tel:" + String(v).replace(/[^\d+]/g, "");
    if (s.phone) $$("[data-phone]").forEach(a => { a.textContent = s.phone; a.href = tel(s.phone); });
    $$("[data-phone2]").forEach(a => { a.hidden = !s.phone2; if (s.phone2) { a.textContent = s.phone2; a.href = tel(s.phone2); } });
    if (s.address) $$("[data-address]").forEach(a => a.textContent = L(s.address));
    if (s.hours) $$("[data-hours]").forEach(a => a.textContent = L(s.hours));
    if (s.telegram) $$("[data-tg]").forEach(a => a.href = s.telegram);
    if (s.map && $("#map").src === "about:blank") $("#map").src = s.map;
  }

  addEventListener("scroll", () => $("#header").classList.toggle("is-scrolled", scrollY > 10), { passive: true });
  $("#year").textContent = new Date().getFullYear();

  // Pastki menyuda joriy bo'limni belgilash
  const tabLinks = $$("#tabbar [data-tab]");
  const sections = [[".hero", "top"], ["#katalog", "katalog"], ["#ishlab-chiqarish", "katalog"], ["#kalkulyator", "kalkulyator"], ["#savollar", "kalkulyator"], ["#aloqa", "aloqa"]];
  const secObs = new IntersectionObserver(entries => entries.forEach(en => {
    if (!en.isIntersecting) return;
    const tab = en.target.dataset.tabFor;
    tabLinks.forEach(a => a.classList.toggle("is-active", a.dataset.tab === tab));
  }), { rootMargin: "-45% 0px -50% 0px" });
  sections.forEach(([sel, tab]) => { const el = $(sel); if (el) { el.dataset.tabFor = tab; secObs.observe(el); } });

  // raqamlar animatsiyasi va paydo bo'lish effekti
  const io = new IntersectionObserver(entries => entries.forEach(en => {
    if (!en.isIntersecting) return;
    const el = en.target; io.unobserve(el);
    if (el.dataset.count) {
      const end = +el.dataset.count, t0 = performance.now();
      const tick = tm => { const k = Math.min(1, (tm - t0) / 1400); el.textContent = num(Math.round(end * (1 - Math.pow(1 - k, 3)))); if (k < 1) requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
    } else el.classList.add("in");
  }), { threshold: .15 });
  $$("[data-count]").forEach(el => io.observe(el));
  $$(".section__head, .banner, .step, .feature, .flow li, .faq, .contact > *, .calc > *").forEach(el => { el.classList.add("reveal"); io.observe(el); });

  /* ================= ILOVA (PWA) ================= */
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (standalone) document.documentElement.classList.add("is-app");

  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
  }

  let deferred = null;
  const bar = $("#installBar");
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const dismissed = () => +store.get("humo_install_x") > Date.now();
  const showBar = () => { if (!standalone && !dismissed() && innerWidth < 900) bar.hidden = false; };

  addEventListener("beforeinstallprompt", e => { e.preventDefault(); deferred = e; showBar(); });
  if (isIOS && !standalone) setTimeout(showBar, 2500);

  $("#installBtn").addEventListener("click", async () => {
    if (deferred) {
      deferred.prompt();
      const r = await deferred.userChoice.catch(() => null);
      deferred = null;
      if (r && r.outcome === "accepted") bar.hidden = true;
    } else if (isIOS) {
      toast(t("install.ios"), false, 6000);
    }
  });
  $("#installX").addEventListener("click", () => { bar.hidden = true; store.set("humo_install_x", Date.now() + 3 * 864e5); });
  addEventListener("appinstalled", () => { bar.hidden = true; toast(t("install.done")); });

  addEventListener("offline", () => toast(t("toast.offline"), true, 4000));

  /* ================= START ================= */
  applyLang();
  fetch("/api/products").then(r => r.json()).then(d => {
    PRODUCTS = d.products || []; SETTINGS = d.settings || {};
    applySettings(SETTINGS);
    renderProducts(); renderMarquee(); calcFill(); renderCart();
  }).catch(() => toast(t("toast.load"), true));
})();
