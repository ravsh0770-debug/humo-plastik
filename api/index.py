"""
HUMO PLASTIK — API va Telegram bot (Vercel serverless funksiyasi).

Yo'llar (vercel.json orqali /api/* shu faylga yo'naltiriladi):
  GET  /api/products   — katalog va sozlamalar
  POST /api/order      — buyurtma
  POST /api/callback   — qayta qo'ng'iroq so'rovi
  POST /api/telegram   — Telegram webhook
  GET  /api/setup?key= — webhookni o'rnatish (bir marta)
  GET  /api/health     — holatni tekshirish

Faqat Python standart kutubxonasi ishlatiladi. Lokal server (server.py) ham shu faylni ishlatadi.
"""

import hashlib
import html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRODUCTS_FILE = DATA / "products.json"
TZ = timezone(timedelta(hours=5))  # Toshkent vaqti (Vercel serverlari UTC da)


# ---------------------------------------------------------------- sozlamalar
def _load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
ON_VERCEL = bool(os.environ.get("VERCEL"))
# Telegram webhook so'rovlarini tekshirish uchun maxfiy kalit (tokendan hosil qilinadi)
WEBHOOK_SECRET = hashlib.sha256(("humo:" + BOT_TOKEN).encode()).hexdigest()[:40]
LOGO_EXTRA = 0.15


def env_admins():
    raw = os.environ.get("ADMIN_CHAT_IDS", "")
    return {int(x) for x in re.findall(r"-?\d+", raw)}


def now():
    return datetime.now(TZ)


def catalog():
    try:
        return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"settings": {}, "products": []}


def fmt_sum(n):
    return f"{int(round(n)):,}".replace(",", " ") + " so'm"


def uz(v):
    return v.get("uz", "") if isinstance(v, dict) else (v or "")


class ApiError(ValueError):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


# ---------------------------------------------------------------- saqlash
class RedisStore:
    """Upstash / Vercel KV (REST). Vercel'da buyurtmalar tarixi uchun."""
    kind = "redis"

    def __init__(self, url, token):
        self.url, self.token = url.rstrip("/"), token

    def cmd(self, *args):
        req = urllib.request.Request(self.url, data=json.dumps([str(a) for a in args]).encode(),
                                     headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read()).get("result")

    def admins(self):
        return {int(x) for x in (self.cmd("SMEMBERS", "humo:admins") or [])}

    def add_admin(self, cid):
        self.cmd("SADD", "humo:admins", cid)

    def next_id(self):
        return 1000 + int(self.cmd("INCR", "humo:seq"))

    def save(self, o):
        self.cmd("SET", f"humo:order:{o['id']}", json.dumps(o, ensure_ascii=False))
        self.cmd("LPUSH", "humo:orders", o["id"])
        self.cmd("LTRIM", "humo:orders", 0, 1999)

    def get(self, oid):
        v = self.cmd("GET", f"humo:order:{oid}")
        return json.loads(v) if v else None

    def recent(self, n):
        ids = self.cmd("LRANGE", "humo:orders", 0, n - 1) or []
        if not ids:
            return []
        vals = self.cmd("MGET", *[f"humo:order:{i}" for i in ids]) or []
        return [json.loads(v) for v in vals if v][::-1]

    def hit(self, ip, window=600):
        k = f"humo:rl:{ip}"
        c = int(self.cmd("INCR", k))
        if c == 1:
            self.cmd("EXPIRE", k, window)
        return c


class FileStore:
    """Lokal kompyuterda: data/*.json fayllari."""
    kind = "file"
    lock = threading.Lock()

    def __init__(self):
        self.orders_f, self.admins_f = DATA / "orders.json", DATA / "admins.json"
        self.hits = {}

    def _r(self, f, d):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return d

    def _w(self, f, d):
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(f)

    def admins(self):
        return set(self._r(self.admins_f, []))

    def add_admin(self, cid):
        with self.lock:
            a = self._r(self.admins_f, [])
            if cid not in a:
                a.append(cid)
                self._w(self.admins_f, a)

    def next_id(self):
        o = self._r(self.orders_f, [])
        return (o[-1]["id"] + 1) if o else 1001

    def save(self, order):
        with self.lock:
            o = self._r(self.orders_f, [])
            o.append(order)
            self._w(self.orders_f, o)

    def get(self, oid):
        return next((x for x in self._r(self.orders_f, []) if str(x["id"]) == str(oid)), None)

    def update(self, order):
        with self.lock:
            o = self._r(self.orders_f, [])
            for i, x in enumerate(o):
                if x["id"] == order["id"]:
                    o[i] = order
            self._w(self.orders_f, o)

    def recent(self, n):
        return self._r(self.orders_f, [])[-n:]

    def hit(self, ip, window=600):
        t = time.time()
        h = [x for x in self.hits.get(ip, []) if t - x < window] + [t]
        self.hits[ip] = h
        return len(h)


class NoStore:
    """Vercel'da Redis ulanmagan bo'lsa: buyurtmalar faqat Telegramga yuboriladi."""
    kind = "none"
    hits = {}

    def admins(self): return set()
    def add_admin(self, cid): raise RuntimeError("no storage")
    def next_id(self): return int(now().strftime("%d%H%M%S")) % 1000000
    def save(self, o): pass
    def get(self, oid): return None
    def recent(self, n): return []

    def hit(self, ip, window=600):
        t = time.time()
        h = [x for x in self.hits.get(ip, []) if t - x < window] + [t]
        self.hits[ip] = h
        return len(h)


def make_store():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    tok = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if url and tok:
        return RedisStore(url, tok)
    if not ON_VERCEL:
        DATA.mkdir(exist_ok=True)
        return FileStore()
    return NoStore()


store = make_store()


def admins():
    try:
        return env_admins() | store.admins()
    except Exception as e:
        print(f"[store] admins xato: {e}")
        return env_admins()


# ---------------------------------------------------------------- Telegram
def tg(method, **params):
    if not BOT_TOKEN:
        return None
    req = urllib.request.Request(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
                                 data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=params.get("timeout", 0) + 10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[telegram] {method} xato: {e}")
        return None


STATUS = {
    "new": "🆕 Yangi",
    "accepted": "✅ Qabul qilindi",
    "delivered": "🚚 Yetkazildi",
    "canceled": "❌ Bekor qilindi",
}


def order_keyboard(oid):
    return {"inline_keyboard": [[
        {"text": "✅ Qabul", "callback_data": f"st:{oid}:accepted"},
        {"text": "🚚 Yetkazildi", "callback_data": f"st:{oid}:delivered"},
        {"text": "❌ Bekor", "callback_data": f"st:{oid}:canceled"},
    ]]}


def order_text(o):
    e = html.escape
    c = o["customer"]
    lines = [
        f"🛒 <b>Yangi buyurtma #{o['id']}</b>",
        f"🕒 {o['created']}",
        f"📌 Holat: <b>{STATUS.get(o['status'], o['status'])}</b>",
        f"🌐 Mijoz tili: {o.get('lang', 'uz').upper()}",
        "",
        f"👤 <b>{e(c['name'])}</b>",
        f"📞 <code>{e(c['phone'])}</code>",
    ]
    if c.get("company"):
        lines.append(f"🏢 {e(c['company'])}")
    if c.get("address"):
        lines.append(f"📍 {e(c['address'])}")
    lines.append(f"🚚 {e(c.get('delivery', ''))}   💳 {e(c.get('payment', ''))}")
    lines += ["", "<b>Mahsulotlar:</b>"]
    for i, it in enumerate(o["items"], 1):
        opts = [v for v in (it.get("size"), it.get("thickness"), it.get("color")) if v]
        if it.get("logo"):
            opts.append("logotip pechati")
        lines.append(f"{i}. <b>{e(it['name'])}</b> — {it['qty']} {e(it['unit'])}")
        if opts:
            lines.append(f"    <i>{e(', '.join(opts))}</i>")
        lines.append(f"    = {fmt_sum(it['sum'])}")
    lines += ["", f"💰 <b>Jami: {fmt_sum(o['total'])}</b>"]
    if c.get("comment"):
        lines += ["", f"💬 {e(c['comment'])}"]
    return "\n".join(lines)


def notify_admins(text, keyboard=None):
    ids = admins()
    if not ids:
        print("[telegram] Admin yo'q! Botga /start yuboring.")
    for cid in ids:
        p = {"chat_id": cid, "text": text, "parse_mode": "HTML"}
        if keyboard:
            p["reply_markup"] = keyboard
        tg("sendMessage", **p)


def relabel(msg, new_label):
    """Xabardagi holat yozuvini almashtiradi (formatlash saqlanadi). Saqlash bo'lmasa ham ishlaydi."""
    text, ents = msg.get("text", ""), [dict(x) for x in msg.get("entities", [])]
    for old in STATUS.values():
        i = text.find(old)
        if i >= 0:
            break
    else:
        return None, None
    u16 = lambda s: len(s.encode("utf-16-le")) // 2
    pos, delta = u16(text[:i]), u16(new_label) - u16(old)
    for en in ents:
        if en["offset"] > pos:
            en["offset"] += delta
        elif en["offset"] <= pos < en["offset"] + en["length"]:
            en["length"] += delta
    return text[:i] + new_label + text[i + len(old):], ents


HELP = "/orders — oxirgi buyurtmalar\n/stats — statistika\n/id — chat ID"


def handle_update(u):
    if "callback_query" in u:
        q = u["callback_query"]
        msg = q.get("message") or {}
        cid = msg.get("chat", {}).get("id")
        if cid not in admins():
            tg("answerCallbackQuery", callback_query_id=q["id"], text="Ruxsat yo'q")
            return
        try:
            _, oid, status = q["data"].split(":")
        except ValueError:
            return
        if status not in STATUS:
            return
        try:
            o = store.get(oid)
            if o:
                o["status"] = status
                if isinstance(store, FileStore):
                    store.update(o)
                else:
                    store.cmd("SET", f"humo:order:{oid}", json.dumps(o, ensure_ascii=False))
        except Exception as e:
            print(f"[store] status xato: {e}")
        text, ents = relabel(msg, STATUS[status])
        if text:
            tg("editMessageText", chat_id=cid, message_id=msg["message_id"], text=text, entities=ents,
               reply_markup=order_keyboard(oid))
        tg("answerCallbackQuery", callback_query_id=q["id"], text=STATUS[status])
        return

    msg = u.get("message") or {}
    text = (msg.get("text") or "").strip()
    if not text:
        return
    cid = msg["chat"]["id"]
    name = html.escape(msg.get("from", {}).get("first_name", ""))
    cmd, _, arg = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
    is_admin = cid in admins()
    send = lambda t: tg("sendMessage", chat_id=cid, text=t, parse_mode="HTML")
    how_env = (f"Sizning chat ID: <code>{cid}</code>\n\nVercel → Settings → Environment Variables → "
               f"<b>ADMIN_CHAT_IDS</b> ga shu raqamni yozing va <b>Redeploy</b> qiling.")

    if cmd == "/start":
        if is_admin:
            send(f"Salom, {name}! Siz adminsiz ✅\n{HELP}")
        elif not admins() and store.kind != "none":
            store.add_admin(cid)
            send(f"Salom, {name}! 👋\nSiz <b>admin</b> sifatida ro'yxatdan o'tdingiz.\n"
                 f"Endi saytdagi barcha buyurtmalar shu yerga keladi.\n\n{HELP}")
        elif not admins():
            send(f"Salom, {name}! 👋\nBuyurtmalar shu chatga kelishi uchun:\n\n{how_env}")
        else:
            send("Assalomu alaykum! HUMO PLASTIK botiga xush kelibsiz.\nBuyurtma berish uchun saytimizdan foydalaning.")
    elif cmd == "/id":
        send(f"Chat ID: <code>{cid}</code>")
    elif cmd == "/admin":
        if not (ADMIN_KEY and arg.strip() == ADMIN_KEY):
            send("❌ Kalit noto'g'ri.")
        elif store.kind == "none":
            send(how_env)
        else:
            store.add_admin(cid)
            send("✅ Siz admin sifatida qo'shildingiz.")
    elif cmd == "/orders" and is_admin:
        orders = store.recent(5)
        if not orders:
            send("Hozircha saqlangan buyurtmalar yo'q." + ("\n(Tarix uchun Upstash Redis ulang — README)" if store.kind == "none" else ""))
        for o in orders:
            tg("sendMessage", chat_id=cid, text=order_text(o), parse_mode="HTML", reply_markup=order_keyboard(o["id"]))
    elif cmd == "/stats" and is_admin:
        orders = store.recent(2000)
        today = now().strftime("%d.%m.%Y")
        t = [o for o in orders if o["created"].startswith(today)]
        send(f"📊 <b>Statistika</b>\nBugun: {len(t)} ta ({fmt_sum(sum(o['total'] for o in t))})\n"
             f"Jami: {len(orders)} ta ({fmt_sum(sum(o['total'] for o in orders))})\n"
             f"Ko'rib chiqilmagan: {sum(1 for o in orders if o['status'] == 'new')} ta")


# ---------------------------------------------------------------- buyurtmalar
PHONE_RE = re.compile(r"^\+998\d{9}$")


def clean(s, n=200):
    return str(s or "").strip()[:n]


def clean_phone(p):
    d = re.sub(r"\D", "", str(p or ""))
    if len(d) == 9:
        d = "998" + d
    return "+" + d


def get_lang(data):
    return data.get("lang") if data.get("lang") in ("uz", "ru", "en") else "uz"


def create_order(data):
    c = data.get("customer") or {}
    customer = {
        "name": clean(c.get("name"), 80),
        "phone": clean_phone(c.get("phone")),
        "company": clean(c.get("company"), 120),
        "address": clean(c.get("address"), 200),
        "delivery": clean(c.get("delivery"), 40) or "Yetkazib berish",
        "payment": clean(c.get("payment"), 40) or "Naqd",
        "comment": clean(c.get("comment"), 600),
    }
    if len(customer["name"]) < 2:
        raise ApiError("name", "Ismingizni kiriting")
    if not PHONE_RE.match(customer["phone"]):
        raise ApiError("phone", "Telefon raqami noto'g'ri")

    products = {p["id"]: p for p in catalog()["products"]}
    extra = catalog()["settings"].get("logo_extra_percent", LOGO_EXTRA * 100) / 100
    items = []
    for it in (data.get("items") or [])[:30]:
        p = products.get(it.get("id"))
        if not p:
            continue
        try:
            qty = int(it.get("qty", 0))
        except (TypeError, ValueError):
            continue
        if qty < p["min"] or qty > 10_000_000:
            raise ApiError("min", f"{uz(p['name'])}: minimal {p['min']} {p['unit']}")
        logo = bool(it.get("logo")) and p.get("logo", False)
        price = p["price"] * (1 + extra if logo else 1)  # narx doim serverda hisoblanadi
        items.append({
            "id": p["id"], "name": uz(p["name"]), "unit": p["unit"], "qty": qty,
            "price": round(price), "sum": round(price * qty), "logo": logo,
            "size": clean(it.get("size"), 40), "thickness": clean(it.get("thickness"), 40),
            "color": clean(it.get("color"), 40),
        })
    if not items:
        raise ApiError("empty", "Savat bo'sh")

    order = {
        "id": store.next_id(),
        "created": now().strftime("%d.%m.%Y %H:%M"),
        "status": "new",
        "lang": get_lang(data),
        "customer": customer,
        "items": items,
        "total": sum(i["sum"] for i in items),
    }
    try:
        store.save(order)
    except Exception as e:
        print(f"[store] saqlash xato: {e}")
    notify_admins(order_text(order), order_keyboard(order["id"]))
    return order


def create_callback(data):
    name, phone = clean(data.get("name"), 80), clean_phone(data.get("phone"))
    if len(name) < 2:
        raise ApiError("name", "Ismingizni kiriting")
    if not PHONE_RE.match(phone):
        raise ApiError("phone", "Telefon raqami noto'g'ri")
    e = html.escape
    text = (f"📞 <b>Qayta qo'ng'iroq so'rovi</b>\n🕒 {now():%d.%m.%Y %H:%M}\n🌐 Mijoz tili: {get_lang(data).upper()}\n\n"
            f"👤 {e(name)}\n📞 <code>{e(phone)}</code>")
    if data.get("message"):
        text += f"\n💬 {e(clean(data.get('message'), 600))}"
    notify_admins(text)


def setup_webhook(host, key):
    if not ADMIN_KEY or key != ADMIN_KEY:
        return {"ok": False, "error": "key noto'g'ri"}, 403
    url = f"https://{host}/api/telegram"
    r = tg("setWebhook", url=url, secret_token=WEBHOOK_SECRET, allowed_updates=["message", "callback_query"],
           drop_pending_updates=True)
    me = tg("getMe") or {}
    return {"ok": bool(r and r.get("ok")), "webhook": url, "telegram": r,
            "bot": (me.get("result") or {}).get("username"), "storage": store.kind,
            "admins": len(admins())}, 200


# ---------------------------------------------------------------- HTTP
class handler(BaseHTTPRequestHandler):
    """Vercel shu klassni chaqiradi. Lokal server.py undan meros oladi."""

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} {fmt % args}")

    def send_json(self, obj, code=200, cache=None):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache or "no-store")
        self.end_headers()
        self.wfile.write(body)

    def route(self):
        u = urllib.parse.urlparse(self.path)
        return u.path.rstrip("/").rsplit("/", 1)[-1], urllib.parse.parse_qs(u.query)

    def do_GET(self):
        name, qs = self.route()
        if name == "products":
            return self.send_json(catalog(), cache="public, s-maxage=60, stale-while-revalidate=600")
        if name == "health":
            return self.send_json({"ok": True, "bot": bool(BOT_TOKEN), "storage": store.kind,
                                   "admins": len(admins()), "time": now().isoformat(timespec="seconds")})
        if name == "setup":
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
            obj, code = setup_webhook(host, (qs.get("key") or [""])[0])
            return self.send_json(obj, code)
        return self.send_json({"ok": False, "error": "Topilmadi"}, 404)

    def do_POST(self):
        name, _ = self.route()
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 100_000:
                return self.send_json({"ok": False, "error": "Juda katta"}, 413)
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.send_json({"ok": False, "error": "Noto'g'ri so'rov"}, 400)

        if name == "telegram":
            if self.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
                return self.send_json({"ok": False}, 403)
            try:
                handle_update(data)
            except Exception as e:
                print(f"[telegram] update xato: {e}")
            return self.send_json({"ok": True})

        if name not in ("order", "callback"):
            return self.send_json({"ok": False, "error": "Topilmadi"}, 404)
        ip = (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()
        try:
            if store.hit(ip) > 6:
                return self.send_json({"ok": False, "code": "rate", "error": "Juda ko'p so'rov"}, 429)
        except Exception as e:
            print(f"[store] rate limit xato: {e}")
        try:
            if name == "order":
                o = create_order(data)
                return self.send_json({"ok": True, "order_id": o["id"], "total": o["total"]})
            create_callback(data)
            return self.send_json({"ok": True})
        except ApiError as e:
            return self.send_json({"ok": False, "code": e.code, "error": str(e)}, 400)


# ---------------------------------------------------------------- lokal bot (polling)
def bot_polling():
    """Faqat lokal kompyuterda. Agar Vercel webhook o'rnatilgan bo'lsa, polling yoqilmaydi."""
    if not BOT_TOKEN:
        print("[telegram] BOT_TOKEN yo'q — bot o'chirilgan.")
        return
    info = (tg("getWebhookInfo") or {}).get("result") or {}
    if info.get("url"):
        print(f"[telegram] Webhook o'rnatilgan ({info['url']}) — bot Vercel'da ishlaydi, lokal polling o'chirildi.")
        return
    me = tg("getMe")
    if me and me.get("ok"):
        print(f"[telegram] Bot ulandi (lokal): @{me['result']['username']}")
    offset = 0
    while True:
        res = tg("getUpdates", offset=offset, timeout=30, allowed_updates=["message", "callback_query"])
        if not res or not res.get("ok"):
            time.sleep(5)
            continue
        for u in res["result"]:
            offset = u["update_id"] + 1
            try:
                handle_update(u)
            except Exception as e:
                print(f"[telegram] update xato: {e}")
