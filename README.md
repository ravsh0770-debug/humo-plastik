# HUMO PLASTIK — sayt + Telegram bot

Selofan paketlar ishlab chiqaruvchisi uchun sayt: katalog, kalkulyator, savat, buyurtmalar Telegram botga keladi.
Telefonda ilova (PWA) ko'rinishida ishlaydi, UZ / RU / EN tillari bor.

## Tuzilma
```
public/          sayt (HTML, CSS, JS, rasmlar, manifest, service worker)
api/index.py     API + Telegram bot (Vercel serverless funksiyasi)
data/products.json   mahsulotlar, narxlar, kontaktlar (3 tilda)
server.py        lokal server (kompyuterda sinash uchun)
vercel.json      Vercel sozlamalari
```

---

## Vercel'ga joylash

### 1. Loyihani ulash
1. https://vercel.com/new → **Import Git Repository** → `humo-plastik` ni tanlang.
2. **Framework Preset:** `Other`. Boshqa sozlamalarga tegmang (`vercel.json` hammasini belgilaydi).

### 2. Environment Variables (Deploy dan oldin)
| Nomi | Qiymati |
|---|---|
| `BOT_TOKEN` | BotFather bergan token |
| `ADMIN_KEY` | o'zingiz o'ylab topgan maxfiy so'z (masalan `humo2026xyz`) |
| `ADMIN_CHAT_IDS` | hozircha bo'sh qoldiring (3-qadamda to'ldiriladi) |

**Deploy** ni bosing.

### 3. Botni ulash (bir marta)
1. Brauzerda oching: `https://SAYTINGIZ.vercel.app/api/setup?key=ADMIN_KEY`
   → `"ok": true` chiqsa, webhook o'rnatildi.
2. Telegramda botga **/start** yuboring → bot sizning **chat ID** raqamingizni yozadi.
3. Vercel → Settings → Environment Variables → `ADMIN_CHAT_IDS` = shu raqam
   (bir nechta admin: `12345, 67890`) → **Deployments → Redeploy**.
4. Tayyor! Saytdan buyurtma bering — botga keladi.

### 4. (Ixtiyoriy) Buyurtmalar tarixi — Upstash Redis
Redis'siz ham buyurtmalar botga keladi va ✅/🚚/❌ tugmalari ishlaydi.
`/orders`, `/stats` buyruqlari va admin avtomatik qo'shilishi uchun:
Vercel → **Storage** → **Upstash for Redis** (bepul) → loyihaga ulang → Redeploy.
`KV_REST_API_URL` va `KV_REST_API_TOKEN` avtomatik qo'shiladi.

Tekshirish: `https://SAYTINGIZ.vercel.app/api/health`

---

## Lokal ishga tushirish
1. `.env.example` dan nusxa olib `.env` yarating va tokenni yozing.
2. `start.bat` ni bosing yoki `python server.py` → http://localhost:8000
3. Lokal rejimda buyurtmalar `data/orders.json` ga saqlanadi, birinchi /start yuborgan admin bo'ladi.

> Agar bot Vercel'ga ulangan bo'lsa (webhook), lokal server botni ishga tushirmaydi —
> Vercel'dagi bot ishlashda davom etadi.

## Bot buyruqlari
`/start` — boshlash · `/id` — chat ID · `/orders` — oxirgi buyurtmalar · `/stats` — statistika ·
`/admin KALIT` — admin bo'lish (Redis yoki lokal rejimda)

## Telefon ilovasi (PWA)
- Pastki menyu, pastdan chiqadigan oynalar, 2 ustunli katalog, oflayn ishlash.
- "O'rnatish" paneli: Android (Chrome) — bir bosishda; iPhone (Safari) — Ulashish → Bosh ekranga.
- Vercel avtomatik HTTPS beradi, shuning uchun o'rnatish u yerda ishlaydi.

## Tillar
- UZ / RU / EN — yuqoridagi globus tugmasi; havola orqali `/?lang=ru`, `/?lang=en`.
- Matnlar: `public/js/i18n.js`, mahsulotlar: `data/products.json`.
- Botga buyurtma o'zbek tilida keladi, mijoz tili alohida ko'rsatiladi.

## Tahrirlash
- Narxlar, mahsulotlar, telefon, manzil: `data/products.json`
- Raqamlar (20+ yil va h.k.) va matnlar: `public/index.html` + `public/js/i18n.js`
- Rasmlar: `public/img/` (Unsplash/Pexels bepul fotolar — o'z rasmlaringizga almashtirish tavsiya etiladi)
- Narx har doim serverda `products.json` dan qayta hisoblanadi — brauzerdan soxtalashtirib bo'lmaydi.
