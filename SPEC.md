# FlyCheapVN - Telegram Bot Săn Vé Máy Bay Giá Rẻ

**Status:** Draft SPEC  
**Last Updated:** 22/06/2026  
**Author:** Hermes (on behalf of Jack Tran)

---

## 1. Tổng Quan

Telegram bot cho phép người dùng hỏi đáp bằng tiếng Việt tự nhiên để tìm vé máy bay giá rẻ. Bot sử dụng AI (DeepSeek Flash v4) để hiểu ý định người dùng, xoay vòng nhiều nguồn API free để lấy dữ liệu, và trả kết quả gọn gàng.

**Model mặc định:** DeepSeek Flash v4 (cho phân tích + sinh response)  
**Platform:** Telegram  
**Target users:** Người Việt Nam, public (multi-user)

---

## 2. Use Cases

Bot hỗ trợ 12 loại câu hỏi tự nhiên + 2 tính năng mở rộng:

### 2.1 Tìm vé (search_flight)
- "tìm vé HN-SG cuối tuần này dưới 1tr"
- "vé đi Đà Lạt từ SG tháng 7 giá rẻ nhất"
- "có chuyến nào từ Hải Phòng ra Huế không?"
- Multi-city: "tìm vé HN-SG-DN tuần sau"

### 2.2 Khuyến mãi & Flash Sale (promo_check)
- "hãng nào đang giảm giá?"
- "VietJet có khuyến mãi gì tháng này không?"
- "săn vé 0 đồng có thật không?"
- "có deal nào từ SG đi Phú Quốc không?"
- "vé rẻ nhất hôm nay từ HN đi đâu?"
- "sale dịp 2/9 có gì hot?"

### 2.3 Xem ngày giờ xuất hành tốt (lucky_date) — ⭐ ĐIỂM MẠNH VN
- "mình sinh 1995, xem ngày tốt đi Đà Nẵng tháng 7"
- "ngày nào đẹp để xuất hành từ HN tuần này?"
- "xem giờ hoàng đạo cho chuyến bay SG-HN thứ 6"
- Tính Can Chi, giờ Hoàng Đạo, xung hợp tuổi
- Luôn kèm disclaimer: tham khảo truyền thống, không khoa học

### 2.4 Xem ngày cho nhóm (group_lucky_date) — ⭐ ĐIỂM MẠNH
- "cả nhà 4 người tuổi Thân, Dần, Tỵ, Hợi — ngày nào OK?"
- "nhóm 3 đứa sinh 1990, 1993, 1998 đi chung"
- Loại ngày xung với bất kỳ ai, tìm ngày an toàn chung

### 2.5 Dự đoán giá (price_predict) — ⭐ NHƯ AIRTRACK
- "nên mua vé HN-SG ngay hay chờ thêm?"
- "vé HN-DN hôm nay 1.2tr, có nên mua không?"
- Dựa trên price trend, so sánh với historical data

### 2.6 So sánh hãng (compare)
- "VietJet hay Bamboo rẻ hơn đường HN-DN?"
- "Vietnam Airlines với VietJet chênh bao nhiêu?"
- "nên đi hãng nào từ SG ra Phú Quốc?"
- "Bamboo với Vietravel Airlines hãng nào ổn hơn?"

### 2.7 Tư vấn (advice)
- "nên đặt vé trước bao lâu để rẻ nhất?"
- "tháng nào rẻ nhất đi Bangkok từ HN?"
- "thời điểm nào trong tuần/ngày giá rẻ nhất?"
- "mách em mẹo săn vé rẻ"
- "nên bay thẳng hay 1 stop để tiết kiệm?"

### 2.8 Lịch trình (schedule)
- "có chuyến thẳng từ SG ra Phú Quốc không?"
- "lịch bay VietJet HN-SG ngày mai"
- "giờ bay sớm nhất từ Hải Phòng đi SG"
- "chuyến bay nào ngắn nhất từ HN đi Nha Trang?"

### 2.9 Theo dõi giá (set_alert)
- "/theodoi HAN-DAD duoi 800k"
- "báo em khi vé HN-SG xuống dưới 500k"

### 2.10 Kiểm tra alert (check_alerts)
- "/check-alerts"
- "có tin gì mới cho tuyến HAN-DAD không?"

### 2.11 Memory trong session
- LLM nhớ lịch sử chat — hỏi tiếp không cần nhắc lại
- Ví dụ: "cho vé đấy luôn đi" → bot hiểu là đặt vé của kết quả vừa tìm

### 2.12 Khác (general_chat)
- Chitchat, FAQ, chào hỏi
- "/start", "/help", "/uptime"

### 2.13 Mở rộng sau (Phase 4+)
- **So sánh giá sản phẩm** (Google Shopping) — như Tara Bot
- **Hotel deals** (Booking.com affiliate) — như AirTrack
- **Price history chart** — xu hướng giá 7/30 ngày
- **Daily deal summary** — GitHub Actions mỗi sáng 9AM cho user active

---

## 3. Architecture

```
┌──────────────┐     ┌────────────────────────────────────────────┐
│  Telegram    │────▶│  FlyCheapVN Bot (Python)                   │
│  Users       │     │                                            │
│              │◀────│  - python-telegram-bot (python-telegram-bot│
└──────────────┘     │  - AI Classifier (DeepSeek Flash v4)      │
                     │  - API Router (xoay vòng nguồn free)      │
                     │  - Response Builder (LLM format)           │
                     │  - SQLite store                            │
                     └────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼──────────────────┐
                    ▼                 ▼                  ▼
              ┌──────────┐    ┌──────────┐    ┌──────────────┐
              │ Kiwi API  │    │ Amadeus  │    │ Skyscanner   │
              │ Tequila   │    │ Self-Svc │    │ (RapidAPI)   │
              └──────────┘    └──────────┘    └──────────────┘
                    │                 │                │
              ┌──────────┐    ┌──────────┐    ┌──────────────┐
              │ Aviasales│    │ SerpAPI  │    │ Cache SQLite  │
              │ Jetradar │    │ G.Flight │    │ (15p TTL)     │
              └──────────┘    └──────────┘    └──────────────┘
```

### 3.1 Data Flow

```
User msg → Telegram Bot Handler
        → AI Classifier (DeepSeek): classify intent + parse entities
        → Nếu search: gọi API Router → cache → kết quả
        → Nếu alert: lưu SQLite
        → Response Builder: LLM format kết quả đẹp
        → Nếu có alerts active: check nhân tiện, đính kèm nếu có deal
        → Reply Telegram
```

---

## 4. Core Components

### 4.1 Telegram Bot Handler
- File: `bot.py`
- python-telegram-bot v20+ (async)
- Handlers: CommandHandler (/start, /help, /uptime, /theodoi, /check-alerts) + MessageHandler (text)
- Rate limit: 5 req/phút/user (user_rate_limits table)
- Markdown fallback: nếu ParseMode.MARKDOWN lỗi → tự động retry không format

### 4.2 AI Classifier & Entity Parser
- File: `ai_router.py`
- Dùng **DeepSeek Flash v4** (env: DEEPSEEK_API_KEY, DEEPSEEK_MODEL)
- 11 intents: search_flight | promo_check | compare | advice | schedule | set_alert | check_alerts | lucky_date | group_lucky_date | price_predict | general_chat
- Extract entities: origin, destination, date_from, date_to, max_price, airline, trip_type, birth_year, group_birth_years
- **Session memory:** Lưu lịch sử chat (max 10 turn) → LLM nhớ context
- **Fallback:** Nếu DeepSeek lỗi → `regex_parse_intent()` trong utils.py (đầy đủ intent + route + price + date)

**System Prompt:**
```
Bạn là trợ lý săn vé máy bay FlyCheapVN. Nhiệm vụ:
1. Phân loại ý định người dùng vào MỘT trong các intent:
   search_flight | promo_check | compare | advice | schedule | set_alert |
   check_alerts | lucky_date | group_lucky_date | price_predict | general_chat
2. Trích xuất thông tin cần thiết (mã sân bay, ngày, budget, hãng...)
3. Trả về JSON thuần, không markdown

Schema JSON:
{
  "intent": "search_flight",
  "origin": "HAN",
  "destination": "SGN",
  "date_from": "2026-06-27",
  "date_to": null,
  "max_price": 1000000,
  "airline": null,
  "trip_type": "one_way",
  "birth_year": null,
  "group_birth_years": null,
  "confidence": 0.95
}
```

### 4.3 API Router (Core Engine)
- File: `api_router.py`
- **Parallel-first strategy:**

```
search(origin, dest, date, params):
    sources = sorted by priority + health_score (circuit breaker check)
    Phase 1: Gọi song song top 2 nguồn (asyncio.gather)
             → merge kết quả, dedupe
    Phase 2: Nếu < 3 kết quả, gọi tuần tự các nguồn còn lại
             → dừng khi đủ limit
    Fallback: stale cache nếu tất cả nguồn đều fail
```

**Nguồn ưu tiên:**
| Ưu tiên | Nguồn | Key | Rate/h |
|---------|-------|-----|--------|
| 1 | Fly Scraper (RapidAPI) | `RAPIDAPI_KEY` | 50 |
| 2 | Kiwi/Tequila | `KIWI_API_KEY` (sandbox: `picky`) | 500 |
| 3 | Amadeus Self-Service | `AMADEUS_CLIENT_ID/SECRET` | 100 |
| 4 | Skyscanner (RapidAPI) | `RAPIDAPI_KEY` | 50 |
| 5 | Aviasales | `TRAVELPAYOUTS_TOKEN` | 200 |
| 6 | SerpAPI | `SERPAPI_KEY` | 10 |

**Tính năng nâng cao:**
- **Circuit Breaker:** Nếu 1 nguồn fail → bị chặn 5 phút (source_health table)
- **Health Score:** Tự động ưu tiên nguồn có tỷ lệ thành công cao
- **Stale Cache Fallback:** Nếu cache hết hạn, vẫn có thể dùng nếu không nguồn nào hoạt động
- **Rate Limit Tracking:** Đếm số request mỗi giờ, không vượt max_per_hour
- **quick_price():** Lightweight check ưu tiên price-calendar, không gọi full search

**Normalized output format:**
```python
{
    "success": True,
    "source": "kiwi",
    "flights": [
        {
            "airline": "VJ",
            "airline_name": "VietJet Air",
            "flight_number": "VJ123",
            "price": 599000,
            "currency": "VND",
            "price_usd": 25.82,
            "departure": "2026-06-27T06:00:00",
            "arrival": "2026-06-27T07:30:00",
            "origin": "HAN",
            "dest": "SGN",
            "stops": 0,
            "duration_minutes": 90,
            "booking_url": "https://..."
        }
    ],
    "cached": False
}
```

### 4.4 Cache Layer
- File: `database.py` (functions: get_cache, set_cache, get_stale_cache, cleanup_expired_cache)
- SQLite: `cache` table
- TTL: 15 phút cho cùng 1 query
- Key: SHA256 hash(origin + dest + date_from + date_to + max_price + currency + limit)
- **Stale cache:** Nếu cache hết hạn nhưng không có API nào hoạt động, vẫn trả về cache cũ

```sql
CREATE TABLE cache (
    query_hash TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
```

### 4.5 Alert Manager
- File: `alert_manager.py`
- **Trigger-based:** Không có background cron
- Alert được lưu trong SQLite (alerts table)
- Chỉ check khi user:
  - Gõ `/check-alerts`
  - Hỏi "có gì mới cho tuyến X-Y không?"
  - Bất kỳ câu hỏi nào → `incidental_check()` kiểm tra max 3 alert active, cooldown 1h

**Check logic:**
```
check_alert(alert, force=False):
    if force or last_checked > 1h ago:
        price = quick_price(alert.origin, alert.dest)  # lightweight
        if price and price <= alert.max_price:
            if not last_notified or price < last_notified:
                notify_user()
                update last_notified_price
        update last_checked, last_price
```

### 4.6 Response Builder
- File: `response_builder.py`
- Dùng DeepSeek Flash v4 để format (optional — fallback sang template)
- Templates cho từng intent:
  - search_flight: top 5 flights với medal, time, stops, link
  - set_alert: xác nhận + chi tiết alert
  - check_alerts: danh sách alert + deal mới
  - promo_check: hardcoded deal hiện tại
  - compare: group theo hãng, sắp xếp giá
  - price_predict: so sánh giá user vs thị trường → khuyên mua/chờ
  - lucky_date: ngày đẹp theo can chi (hardcoded cho MVP)
  - group_lucky_date: như trên nhưng cho nhóm

**Format output (search_flight - LLM format nếu có DeepSeek, fallback template):**
```
✈️ HAN → SGN | 27/06/2026
─────────────────────────
🥇 VietJet VJ 1.2tr
   🕐 06:00→07:30 | Bay thẳng 1h30m
   🔗 Đặt ngay: [link]

🥈 Bamboo QH 1.5tr
   🕐 08:00→09:25 | Bay thẳng 1h25m
   🔗 Đặt ngay: [link]

💡 Mẹo: Đặt trước 3 tuần để có giá tốt nhất!
```

---

## 5. Database Schema

File: `database.py` — SQLite (single file: `flycheapvn.db`)

```sql
-- Users
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    chat_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT,
    lang TEXT DEFAULT 'vi',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);

-- Alerts
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    origin TEXT NOT NULL,
    dest TEXT NOT NULL,
    max_price INTEGER NOT NULL,
    currency TEXT DEFAULT 'VND',
    date_from TEXT,
    date_to TEXT,
    last_checked TIMESTAMP,
    last_price INTEGER,
    last_notified_price INTEGER,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Cache
CREATE TABLE cache (
    query_hash TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Rate limit tracking (per source per hour)
CREATE TABLE rate_limits (
    source TEXT PRIMARY KEY,
    last_reset TIMESTAMP,
    count INTEGER DEFAULT 0,
    max_per_hour INTEGER
);

-- User rate limit (chống spam)
CREATE TABLE user_rate_limits (
    telegram_id INTEGER PRIMARY KEY,
    window_start TIMESTAMP NOT NULL,
    count INTEGER DEFAULT 0
);

-- Source health + circuit breaker
CREATE TABLE source_health (
    source TEXT PRIMARY KEY,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    last_success TIMESTAMP,
    last_failure TIMESTAMP,
    circuit_open_until TIMESTAMP
);
```

---

## 6. File Structure

```
/Volumes/SSD_1TB/PROJECT/san_ve_gia_re/
├── SPEC.md                    # This file
├── .env                       # API keys (not in git)
├── requirements.txt
├── README.md                  # Project README
├── flycheapvn.db              # SQLite database
├── bot.py                     # Main entry: Telegram bot handler
├── ai_router.py               # LLM classify + entity parser + session memory
├── api_router.py              # API rotation (parallel) + cache + circuit breaker
├── alert_manager.py           # Trigger-based alert system
├── response_builder.py        # Format kết quả (LLM + templates)
├── database.py                # SQLite init + all CRUD helpers
├── utils.py                   # Mã sân bay, currency, date parsing, regex fallback
├── sources/
│   ├── __init__.py            # Exports all source classes
│   ├── fly_scraper.py         # Priority 1 — RapidAPI Skyscanner
│   ├── kiwi.py                # Priority 2 — Kiwi/Tequila API
│   ├── amadeus.py             # Priority 3 — Amadeus Self-Service
│   ├── skyscanner.py          # Priority 4 — Skyscanner RapidAPI
│   ├── aviasales.py           # Priority 5 — Aviasales/Travelpayouts
│   └── serpapi.py             # Priority 6 — SerpAPI Google Flights
└── tests/
    ├── __init__.py
    ├── test_ai_router.py      # Tests for regex parser
    ├── test_api_router.py     # Tests for cache logic
    ├── test_alert_manager.py
    ├── test_response_builder.py
    └── test_fly_scraper.py
```

---

## 7. API Key Requirements

| API | Sign Up | Free Tier | Ghi chú |
|-----|---------|-----------|---------|
| Kiwi/Tequila | https://docs.kiwi.com/ | sandbox key 'picky' hoặc đăng ký key riêng | Priority 1 |
| Amadeus | https://developers.amadeus.com/ | 2,000 req/tháng | Priority 2 |
| Skyscanner | https://rapidapi.com/skyscanner | 50 req/min, unlimited | Priority 3 |
| Aviasales | https://www.travelpayouts.com/ | Cached 48h free, live cần apply | Priority 4 |
| SerpAPI | https://serpapi.com/ | 100 req/tháng free | Priority 5 (fallback) |
| DeepSeek | https://platform.deepseek.com/ | API key cho Flash v4 | AI classification |

---

## 8. Implementation Phases

### Phase 1: MVP (Priority)
- Telegram bot handler + /start /help
- AI Classifier + entity parser (DeepSeek Flash v4)
- 1 API source: Kiwi/Tequila
- Response Builder cơ bản
- 3 use case: search_flight, general_chat, set_alert

**File cần code:**
- bot.py, ai_router.py, api_router.py (kiwi wrapper), response_builder.py, database.py, utils.py

### Phase 2: Mở rộng
- Thêm API sources: Amadeus, Skyscanner, Aviasales
- API rotation + cache
- Thêm use case: promo_check, compare, schedule
- Rate limit tracking

### Phase 3: Alert + Hoàn thiện
- Alert Manager trigger-based
- Use case: check_alerts, advice
- Cache cleanup
- Error handling + logging
- Testing

---

## 9. Code Standards

- Python 3.11+
- Async (asyncio) cho Telegram handler
- httpx cho API calls
- python-telegram-bot v20+
- openai-compatible client cho DeepSeek API
- SQLite3 (stdlib)
- Logging via logging module

---

## 10. Open Questions

1. Cơ chế affiliate/referral để bot có thể kiếm tiền? (Travelpayouts, Skyscanner affiliate)
2. Có cần hỗ trợ tiếng Anh không?
3. Deploy lên server sau này hay chỉ local?
4. Có cần web dashboard quản lý không?
