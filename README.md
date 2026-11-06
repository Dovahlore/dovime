# dovime · Dovahzul IME (Dragon Language Input Method)

English | [简体中文](README_CN.md)

A Dragon Language (Dovahzul) learning & translation web app for *The Elder Scrolls V: Skyrim* — offline dictionary + AI two-way translation + rune typewriter + endless quizzes.

This is the **standalone edition** of the "Dovahzul IME" page on [dovahwall.cn](https://www.dovahwall.cn): it no longer depends on the original Django site and runs from just a few Python files.

**Live demo**: <https://www.dovahwall.cn/s/ime>

## Features

- **Offline conversion** — Chinese ↔ Dovahzul word-by-word translation with the full 4,227-entry [thuum.org](https://thuum.org) lexicon (canon level / part of speech / word-building notes); click any word to switch candidates
- **AI direct translation** — Chinese translated straight into grammatical Dovahzul transliteration (streaming; the model's reasoning and dictionary lookups stream live into the "thinking" panel)
- **AI polishing** — Dovahzul text rendered into natural Chinese (unlisted words such as names / pinyin transliterations get restored)
- **Dictionary tool** — while translating, the AI can call `dict_lookup` to query/verify the lexicon (batched queries with a call budget)
- **Rune typewriter** — type Latin letters and see Dragon Alphabet runes instantly (digraphs like `aa` / `ah` / `ii` auto-compose into single runes)
- **Endless quiz** — letters / word meanings / full sentences, three tiers, unlimited streaks with instant explanations when you miss
- Grammar crash course, a gallery of 27 + 5 Shouts, an inflection tool, and a local AI history (stored in your browser, never uploaded)

## Quick start

```bash
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:8000
```

The page itself (dictionary / two-way conversion / runes / quiz) works fully offline. **AI features** need an OpenAI-compatible API key:

```bash
# option 1: environment variable
export IME_AI_KEY=your-key      # Windows: set IME_AI_KEY=your-key

# option 2: copy .env.example to .env and fill in IME_AI_KEY=your-key
```

> The key is only read on the server side; the browser never sees it. `.env` is excluded by `.gitignore` and will never be committed.

## Configuration (environment variables)

| Variable | Default | Description |
| --- | --- | --- |
| `IME_AI_KEY` | — | API key (required for AI; `DEEPSEEK_KEY` / `DASHSCOPE_API_KEY` also accepted) |
| `IME_AI_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Any OpenAI-compatible endpoint |
| `IME_AI_MODEL` | `deepseek-v4-pro` | Model name |
| `IME_AI_TIMEOUT` | `15` | Upstream timeout (seconds) |
| `IME_HOST` / `IME_PORT` | `127.0.0.1` / `8000` | Bind address / port |

Defaults match the live dovahwall.cn deployment. Switching providers takes two variables, e.g. the official DeepSeek API:

```bash
IME_AI_BASE_URL=https://api.deepseek.com/v1
IME_AI_MODEL=deepseek-chat
```

## Production deployment

```bash
pip install gunicorn
gunicorn -w 1 -b 0.0.0.0:8000 app:app --timeout 120
```

The AI endpoint streams its response (and already sends `X-Accel-Buffering: no`). If nginx sits in front, disable buffering for that path:

```nginx
location /ime/ai {
    proxy_pass http://127.0.0.1:8000;
    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

## Repository layout

```
app.py                  # Flask entry: the page + streaming /ime/ai endpoint (with the dict_lookup tool)
dovzul_lexicon.py       # Server-side lexicon: parses the full thuum.org dictionary from data.js / ref.js
templates/ime.html      # Single-page app: convert / dictionary / shouts / grammar / runes / quiz
static/ime/js/          # core.js engine + app.js UI + data.js/ref.js dictionary data + font.js loader
static/ime/font/        # Dragon Alphabet font (thuum.org)
static/ime/img/         # Icons
.env.example            # AI config template (copy to .env; never committed)
```

## Security notes

- No API keys in this repository; keys are read only from environment variables / `.env`
- AI requests are proxied by the server, so the frontend never touches the key — safe for public deployments
- AI calls are budget-limited (≤10 tool calls & ≤3 tool rounds per request, input truncated to 2,000 characters) to prevent abuse

## Acknowledgements & disclaimer

- Lexicon data (4,227 entries) and the Dragon Alphabet font come from the [thuum.org](https://thuum.org) community dictionary
- Shout data compiled from [UESP](https://en.uesp.net)
- This is an **unofficial fan work**. The Elder Scrolls and all related rights belong to Bethesda Softworks / ZeniMax Media; this project is not affiliated with them and is non-commercial.

## License

[MIT](LICENSE) © Dovahlore
