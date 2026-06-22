# flycheapvn

Telegram bot săn vé máy bay giá rẻ cho người Việt — hỏi đáp tiếng Việt tự nhiên.

## Tính năng

- Tìm vé máy bay (xoay vòng nhiều nguồn API)
- Theo dõi giá (alert trigger-based)
- AI phân loại câu hỏi (DeepSeek)
- Khuyến mãi, so sánh hãng, tư vấn, ngày tốt...

## Cài đặt

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Điền TELEGRAM_BOT_TOKEN, DEEPSEEK_API_KEY, RAPIDAPI_KEY
python bot.py
```

## API sources (xoay vòng tự động)

| Ưu tiên | Nguồn | Key |
|---------|-------|-----|
| 1 | Fly Scraper (RapidAPI) | `RAPIDAPI_KEY` |
| 2 | Kiwi/Tequila | `KIWI_API_KEY` (sandbox: `picky`) |
| 3 | Amadeus | `AMADEUS_CLIENT_ID/SECRET` |
| 4 | Skyscanner | `RAPIDAPI_KEY` |
| 5 | Aviasales | `TRAVELPAYOUTS_TOKEN` |
| 6 | SerpAPI | `SERPAPI_KEY` |

Bot tự: gọi song song top 2 nguồn → merge kết quả rẻ nhất → fallback tuần tự → circuit breaker khi lỗi.

## Bot

[t.me/flycheapvn_bot](https://t.me/flycheapvn_bot)

## License

MIT
