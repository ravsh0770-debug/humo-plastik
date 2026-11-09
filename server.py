"""
HUMO PLASTIK — sayt serveri va Telegram bot.

Faqat Python standart kutubxonasi ishlatiladi (pip install shart emas).
Ishga tushirish:  python server.py
"""

import html
import json
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)  # loglar darhol chiqsin

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)

ORDERS_FILE = DATA / "orders.json"
ADMINS_FILE = DATA / "admins.json"
PRODUCTS_FILE = DATA / "products.json"


# ---------------------------------------------------------------- sozlamalar
def load_env():
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
LOGO_EXTRA = 0.15  # logotip pechati narxga +15%

lock = threading.Lock()


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def catalog():
    return read_json(PRODUCTS_FILE, {"settings": {}, "products": []})


def fmt_sum(n):
    return f"{int(round(n)):,}".replace(",", " ") + " so'm"


def uz(v):
    """Ko'p tilli maydondan o'zbekcha matnni oladi (admin uchun)."""
    return v.get("uz", "") if isinstance(v, dict) else (v or "")


class ApiError(ValueError):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


# ---------------------------------------------------------------- Telegram
API = f"https://api.telegram.org/bot{BOT_TOKEN}/"


def tg(method, **params):
    if not BOT_TOKEN:
        return None
    body = json.dumps(params).encode()
    req = urllib.request.Request(API + method, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read())
    except Exception as e:  # tarmoq xatosi bo'lsa sayt to'xtamasin
        print(f"[telegram] {method} xato: {e}")
        return None


def admins():
    return read_json(ADMINS_FILE, [])


def add_admin(chat_id):
    with lock:
        ids = admins()
        if chat_id not in ids:
            ids.append(chat_id)
            write_json(ADMINS_FILE, ids)


STATUS = {
    "new": "🆕 Yangi",
    "accepted": "✅ Qabul qilindi",
    "delivered": "🚚 Yetkazildi",
    "canceled": "❌ Bekor qilindi",
}


def order_keyboard(order_id):
    return {"inline_keyboard": [[
        {"text": "✅ Qabul", "callback_data": f"st:{order_id}:accepted"},
        {"text": "🚚 Yetkazildi", "callback_data": f"st:{order_id}:delivered"},
        {"text": "❌ Bekor", "callback_data": f"st:{order_id}:canceled"},
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
    for chat_id in ids:
        params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if keyboard:
            params["reply_markup"] = keyboard
        tg("sendMessage", **params)


def handle_update(u):
    if "callback_query" in u:
        q = u["callback_query"]
        chat_id = q["message"]["chat"]["id"]
        if chat_id not in admins():
            tg("answerCallbackQuery", callback_query_id=q["id"], text="Ruxsat yo'q")
            return
        try:
            _, oid, status = q["data"].split(":")
        except ValueError:
            return
        with lock:
            orders = read_json(ORDERS_FILE, [])
            o = next((x for x in orders if str(x["id"]) == oid), None)
            if o and status in STATUS:
                o["status"] = status
                write_json(ORDERS_FILE, orders)
        if o:
            tg("editMessageText", chat_id=chat_id, message_id=q["message"]["message_id"],
               text=order_text(o), parse_mode="HTML", reply_markup=order_keyboard(o["id"]))
        tg("answerCallbackQuery", callback_query_id=q["id"], text=STATUS.get(status, "OK"))
        return

    msg = u.get("message") or {}
    text = (msg.get("text") or "").strip()
    if not text:
        return
    chat_id = msg["chat"]["id"]
    name = msg.get("from", {}).get("first_name", "")
    cmd, _, arg = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
    is_admin = chat_id in admins()

    if cmd == "/start":
        if not admins():
            add_admin(chat_id)
            tg("sendMessage", chat_id=chat_id, parse_mode="HTML",
               text=f"Salom, {html.escape(name)}! 👋\nSiz <b>admin</b> sifatida ro'yxatdan o'tdingiz.\n"
                    "Endi saytdagi barcha buyurtmalar shu yerga keladi.\n\n"
                    "/orders — oxirgi buyurtmalar\n/stats — statistika")
        elif is_admin:
            tg("sendMessage", chat_id=chat_id, text="Siz allaqachon adminsiz ✅\n/orders — oxirgi buyurtmalar\n/stats — statistika")
        else:
            tg("sendMessage", chat_id=chat_id,
               text="Assalomu alaykum! HUMO PLASTIK botiga xush kelibsiz.\nBuyurtma berish uchun saytimizdan foydalaning.")
    elif cmd == "/admin":
        if ADMIN_KEY and arg.strip() == ADMIN_KEY:
            add_admin(chat_id)
            tg("sendMessage", chat_id=chat_id, text="✅ Siz admin sifatida qo'shildingiz.")
        else:
            tg("sendMessage", chat_id=chat_id, text="❌ Kalit noto'g'ri.")
    elif cmd == "/orders" and is_admin:
        orders = read_json(ORDERS_FILE, [])[-5:]
        if not orders:
            tg("sendMessage", chat_id=chat_id, text="Hozircha buyurtmalar yo'q.")
        for o in orders:
            tg("sendMessage", chat_id=chat_id, text=order_text(o), parse_mode="HTML",
               reply_markup=order_keyboard(o["id"]))
    elif cmd == "/stats" and is_admin:
        orders = read_json(ORDERS_FILE, [])
        today = datetime.now().strftime("%d.%m.%Y")
        t = [o for o in orders if o["created"].startswith(today)]
        new = sum(1 for o in orders if o["status"] == "new")
        tg("sendMessage", chat_id=chat_id, parse_mode="HTML",
           text=f"📊 <b>Statistika</b>\nBugun: {len(t)} ta ({fmt_sum(sum(o['total'] for o in t))})\n"
                f"Jami: {len(orders)} ta ({fmt_sum(sum(o['total'] for o in orders))})\n"
                f"Ko'rib chiqilmagan: {new} ta")


def bot_polling():
    if not BOT_TOKEN:
        print("[telegram] BOT_TOKEN yo'q — bot o'chirilgan.")
        return
    tg("deleteWebhook")
    me = tg("getMe")
    if me and me.get("ok"):
        print(f"[telegram] Bot ulandi: @{me['result']['username']}")
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


# ---------------------------------------------------------------- buyurtmalar
PHONE_RE = re.compile(r"^\+?998\d{9}$")
recent = {}  # ip -> [vaqtlar], spamdan himoya


def too_many(ip, limit=5, window=600):
    now = time.time()
    hits = [t for t in recent.get(ip, []) if now - t < window]
    hits.append(now)
    recent[ip] = hits
    return len(hits) > limit


def clean(s, n=200):
    return str(s or "").strip()[:n]


def clean_phone(p):
    digits = re.sub(r"\D", "", str(p or ""))
    if len(digits) == 9:
        digits = "998" + digits
    return "+" + digits


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
        raise ApiError("phone", "Telefon raqami noto'g'ri (+998 XX XXX XX XX)")
    lang = data.get("lang") if data.get("lang") in ("uz", "ru", "en") else "uz"

    products = {p["id"]: p for p in catalog()["products"]}
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
            raise ApiError("min", f"{uz(p['name'])}: minimal buyurtma {p['min']} {p['unit']}")
        logo = bool(it.get("logo")) and p.get("logo", False)
        price = p["price"] * (1 + LOGO_EXTRA if logo else 1)  # narx doim serverda hisoblanadi
        items.append({
            "id": p["id"], "name": uz(p["name"]), "unit": p["unit"], "qty": qty,
            "price": round(price), "sum": round(price * qty), "logo": logo,
            "size": clean(it.get("size"), 40), "thickness": clean(it.get("thickness"), 40),
            "color": clean(it.get("color"), 40),
        })
    if not items:
        raise ApiError("empty", "Savat bo'sh")

    with lock:
        orders = read_json(ORDERS_FILE, [])
        order = {
            "id": (orders[-1]["id"] + 1) if orders else 1001,
            "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "status": "new",
            "lang": lang,
            "customer": customer,
            "items": items,
            "total": sum(i["sum"] for i in items),
        }
        orders.append(order)
        write_json(ORDERS_FILE, orders)

    threading.Thread(target=notify_admins, args=(order_text(order), order_keyboard(order["id"])), daemon=True).start()
    return order


def create_callback(data):
    name = clean(data.get("name"), 80)
    phone = clean_phone(data.get("phone"))
    if len(name) < 2:
        raise ApiError("name", "Ismingizni kiriting")
    if not PHONE_RE.match(phone):
        raise ApiError("phone", "Telefon raqami noto'g'ri")
    lang = data.get("lang") if data.get("lang") in ("uz", "ru", "en") else "uz"
    e = html.escape
    text = (f"📞 <b>Qayta qo'ng'iroq so'rovi</b>\n🕒 {datetime.now():%d.%m.%Y %H:%M}\n🌐 Mijoz tili: {lang.upper()}\n\n"
            f"👤 {e(name)}\n📞 <code>{e(phone)}</code>")
    if data.get("message"):
        text += f"\n💬 {e(clean(data.get('message'), 600))}"
    threading.Thread(target=notify_admins, args=(text,), daemon=True).start()


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "HumoPlastik/1.0"

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} {fmt % args}")

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/products":
            return self.send_json(catalog())
        if path == "/":
            path = "/index.html"
        file = (STATIC / path.lstrip("/")).resolve()
        if not file.is_file() or STATIC not in file.parents:
            file = STATIC / "index.html" if "." not in path.rsplit("/", 1)[-1] else None
            if file is None:
                return self.send_error(404)
        ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400" if "/img/" in path else "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 50_000:
                return self.send_json({"ok": False, "error": "So'rov juda katta"}, 413)
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.send_json({"ok": False, "error": "Noto'g'ri so'rov"}, 400)

        if path not in ("/api/order", "/api/callback"):
            return self.send_json({"ok": False, "error": "Topilmadi"}, 404)
        if too_many(ip):
            return self.send_json({"ok": False, "code": "rate", "error": "Juda ko'p so'rov. Birozdan so'ng urinib ko'ring."}, 429)
        try:
            if path == "/api/order":
                o = create_order(data)
                return self.send_json({"ok": True, "order_id": o["id"], "total": o["total"]})
            create_callback(data)
            return self.send_json({"ok": True})
        except ApiError as e:
            return self.send_json({"ok": False, "code": e.code, "error": str(e)}, 400)


if __name__ == "__main__":
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("image/svg+xml", ".svg")
    mimetypes.add_type("application/manifest+json", ".webmanifest")
    threading.Thread(target=bot_polling, daemon=True).start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[web] Sayt ishga tushdi: http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nTo'xtatildi.")
