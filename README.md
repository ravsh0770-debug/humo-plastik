# HUMO PLASTIK — sayt + Telegram bot

## Ishga tushirish
1. Python 3.9+ o'rnatilgan bo'lsin (qo'shimcha kutubxona kerak emas).
2. `start.bat` ni ikki marta bosing yoki: `python server.py`
3. Brauzerda oching: http://localhost:8000

## Botni ulash (bir marta)
1. Telegramda **@humoplastik_bot** ni oching va **/start** yuboring.
2. Birinchi /start yuborgan odam avtomatik **admin** bo'ladi — buyurtmalar unga keladi.
3. Yana admin qo'shish: yangi odam botga `/admin <ADMIN_KEY>` yuboradi (kalit `.env` faylida).

Bot buyruqlari: `/orders` — oxirgi 5 buyurtma, `/stats` — statistika.
Har bir buyurtma ostida tugmalar bor: ✅ Qabul / 🚚 Yetkazildi / ❌ Bekor.

## Telefon ilovasi (PWA)
- Telefonda sayt ilova ko'rinishida: pastki menyu, pastdan chiqadigan oynalar, 2 ustunli katalog.
- "O'rnatish" paneli orqali bosh ekranga qo'shiladi (Android: Chrome; iPhone: Safari → Ulashish → Bosh ekranga).
- Internet bo'lmasa ham katalog ochiladi (buyurtma yuborish uchun internet kerak).
- Muhim: telefonga o'rnatish faqat **HTTPS** domenda ishlaydi (yoki kompyuterda localhost).

## Tillar
- UZ / RU / EN — yuqoridagi globus tugmasi. Tanlov eslab qolinadi.
- Havola orqali: `/?lang=ru` yoki `/?lang=en`.
- Matnlar: `static/js/i18n.js`, mahsulot tarjimalari: `data/products.json`.
- Botga buyurtma doim o'zbek tilida keladi, mijoz tili alohida ko'rsatiladi.

## Tahrirlash
- **Narxlar, mahsulotlar, telefon, manzil:** `data/products.json`
- **Matnlar, raqamlar (10+ yil va h.k.):** `static/index.html`
- **Rasmlar:** `static/img/` (Unsplash/Pexels bepul litsenziyali fotolar — o'z mahsulot rasmlaringiz bilan almashtirish tavsiya etiladi)
- **Bot tokeni:** `.env`

## Fayllar
- `server.py` — web-server, API (`/api/products`, `/api/order`, `/api/callback`) va Telegram bot
- `data/orders.json` — barcha buyurtmalar (avtomatik yaratiladi)
- `data/admins.json` — bot adminlari

## Internetga chiqarish
Har qanday VPS (Ubuntu) da: `python3 server.py` (yoki systemd xizmati), oldiga Nginx + HTTPS qo'ying.
Narx har doim serverda `products.json` dan qayta hisoblanadi — brauzerdan narxni soxtalashtirib bo'lmaydi.
