# PRD — KAIA (Personal AI Assistant)

**Version:** 1.0 — Final  
**Date:** April 2026  
**User:** Single user, Izmir

---

## 1. Vision

KAIA is a personal AI assistant that runs silently in the background, gets to know you over time, and can hold a genuinely real conversation with you. Not a bot that fetches morning news, suggests outfits, tracks events, and monitors prices — it does all of those things, but it is also an entity you can turn to at any moment and say "what should I eat today?" or "I'm bored, suggest something," and it will know you, make connections, and respond in context.

**Operating model:** While the computer is on, Docker runs automatically in the background. The user never sees a terminal. Everything is managed through Telegram.

---

## 2. Core Principles

| Principle | Description |
|-----------|-------------|
| AI-first | Every response goes through the LLM — it thinks, it doesn't behave like a script |
| Conversation memory | Remembers the last 3 days, builds context |
| Adaptive tone | Default is warm/friendly; say "be serious" and it stays serious until told otherwise |
| Proactive | Writes on its own if it finds something important |
| Missed task | Tasks skipped while the computer was off are run when it turns back on |
| Local-first | LLM runs entirely on-device, no data leaves the machine |
| Modular | New module = single Python file |
| Secure | Actions requiring approval are never performed automatically |
| Resource-friendly | ~5–6 GB RAM in the background, near-zero CPU when idle |

---

## 3. System Architecture (Detailed)

### 3.1 General Layer Structure

    ┌─────────────────────────────────────────────────────────────┐
    │                    Docker Network (isolated)                │
    │                                                             │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │                  INTERFACE LAYER                    │   │
    │  │                                                     │   │
    │  │   Telegram Bot Service                              │   │
    │  │   ┌──────────────────────────────────────────────┐  │   │
    │  │   │ • Forwards incoming messages to Agent Core   │  │   │
    │  │   │ • Formats and sends outgoing messages        │  │   │
    │  │   │ • Chat ID filter (rejects unknown senders)   │  │   │
    │  │   │ • Inline keyboard / button management        │  │   │
    │  │   │ • Photo/file reception                       │  │   │
    │  │   └──────────────────────────────────────────────┘  │   │
    │  └─────────────────────────────────────────────────────┘   │
    │                           │                                │
    │                           ▼                                │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │                  BRAIN LAYER                        │   │
    │  │                                                     │   │
    │  │   Agent Core (Python + FastAPI)                     │   │
    │  │   ┌──────────────────────────────────────────────┐  │   │
    │  │   │                                              │  │   │
    │  │   │  Intent Detector                             │  │   │
    │  │   │  "What does the user want?" → chat / task / tone │  │
    │  │   │         │                                    │  │   │
    │  │   │         ▼                                    │  │   │
    │  │   │  Conversation Engine                         │  │   │
    │  │   │  Memory + Tone + Profile → LLM call          │  │   │
    │  │   │         │                                    │  │   │
    │  │   │         ▼                                    │  │   │
    │  │   │  Module Dispatcher                           │  │   │
    │  │   │  Triggers the right module, formats result   │  │   │
    │  │   │         │                                    │  │   │
    │  │   │         ▼                                    │  │   │
    │  │   │  Proactive Engine                            │  │   │
    │  │   │  Decides "should this be sent to the user?"  │  │   │
    │  │   │                                              │  │   │
    │  │   └──────────────────────────────────────────────┘  │   │
    │  └─────────────────────────────────────────────────────┘   │
    │                           │                                │
    │            ┌──────────────┼──────────────┐                 │
    │            ▼              ▼              ▼                 │
    │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐      │
    │  │  LLM LAYER  │  │ QUEUE LAYER  │  │ DATA LAYER   │      │
    │  │             │  │              │  │              │      │
    │  │  Ollama     │  │  Celery      │  │  Redis       │      │
    │  │  Mistral 7B │  │  Worker      │  │  · conversation  │  │
    │  │  (local,    │  │              │  │    history   │      │
    │  │  no internet│  │  Celery      │  │  · profile   │      │
    │  │  access)    │  │  Beat        │  │  · tone/mode │      │
    │  │             │  │  (scheduling)│  │  · job state │      │
    │  │             │  │              │  │  · feedback  │      │
    │  └─────────────┘  └──────────────┘  └──────────────┘      │
    │                           │                                │
    │                           ▼                                │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │                  MODULE LAYER                       │   │
    │  │                                                     │   │
    │  │  [clothing] [article] [news] [weather] [food]       │   │
    │  │  [events] [price_tracker] [+ new modules]           │   │
    │  │                                                     │   │
    │  │  Every module inherits from BaseModule.             │   │
    │  │  The system auto-discovers modules.                 │   │
    │  └─────────────────────────────────────────────────────┘   │
    │                           │                                │
    │                           ▼                                │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │               SCRAPER SANDBOX LAYER                 │   │
    │  │                                                     │   │
    │  │  Playwright (Chromium headless)                     │   │
    │  │  · Each task runs in a separate subprocess          │   │
    │  │  · Access restricted to the target domain only      │   │
    │  │  · robots.txt check is mandatory                    │   │
    │  │  · Rate limit: per-minute per site                  │   │
    │  │  · Task ends → process is terminated                │   │
    │  └─────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────┘
                                │
                         ┌──────▼──────┐
                         │  Telegram   │
                         │  (single    │
                         │  interface) │
                         └─────────────┘

### 3.2 Component Details

**Telegram Bot Service**
- python-telegram-bot library
- Chat ID check on every incoming message — silently rejected if there is no match
- Text, photo, and button clicks are processed
- Communicates with Agent Core via Redis queue (not HTTP — because async)
- Makes no decisions on its own, acts as a pure carrier

**Agent Core**
- FastAPI: to accept HTTP calls from internal services
- Intent Detector: categorizes incoming text using the LLM
- Conversation Engine: makes LLM calls with memory + tone + profile information
- Module Dispatcher: adds the correct module to the Celery queue based on intent
- Proactive Engine: evaluates module results and decides whether to send a notification

**Ollama**
- Completely internal network — no internet access
- Mistral 7B Q4 model (~4.5 GB RAM)
- All LLM calls go here: responses, summaries, intent detection, tone analysis

**Redis**
- All state lives here
- Conversation history (TTL: 3 days)
- User profile (persistent)
- Tone mode (persistent)
- Job state — which task ran when (for the missed-task system)
- Feedback history

**Celery Worker + Beat**
- Worker: Executes tasks (2 concurrent workers, resource-friendly)
- Beat: Manages scheduling, reads from schedule.yaml
- Records "last_run" to Redis after each task execution

### 3.3 Services and Network Isolation

    Service             | kaia-internal | kaia-external | Description
    --------------------|---------------|---------------|----------------------------------
    ollama              | ✅            | ❌            | No internet access
    redis               | ✅            | ❌            | Completely isolated
    agent-core          | ✅            | ✅            | Telegram API + OpenWeather
    telegram-bot        | ❌            | ✅            | Telegram API only
    celery-worker       | ✅            | ✅            | External access needed for scraper
    celery-beat         | ✅            | ❌            | Scheduling only, no outbound access
    playwright-scraper  | ❌            | ✅ (limited)  | Target domain only

### 3.4 Data Flow — User Sends a Message

    1. User writes in Telegram
    2. Telegram Bot → Chat ID check (stop if unknown)
    3. Telegram Bot → place message in Redis queue
    4. Agent Core → retrieve message from queue
    5. Agent Core → Intent Detector (LLM call)
    6. Intent = "chat":
       a. Pull conversation history from Redis
       b. Pull tone mode from Redis
       c. Pull profile from Redis
       d. Add everything to the system prompt
       e. Send to Ollama → receive response
       f. Save response to Redis (memory)
       g. Send to Telegram Bot → deliver to user
    7. Intent = "task" (clothing, food, etc.):
       a. Add module to Celery queue
       b. Send "Looking into it..." message
       c. Module runs → result written to Redis
       d. Agent Core → format result → send to Telegram

### 3.5 Data Flow — Scheduled Task

    1. Celery Beat → "Tuesday 10:00, clothing module should run"
    2. Write to Redis: job_state["clothing"]["scheduled"] = "2026-04-22T10:00"
    3. Celery Worker → run the module
    4. Module completes → write to Redis: job_state["clothing"]["last_run"] = "2026-04-22T10:02"
    5. Result → Proactive Engine → Telegram notification

---

## 4. Missed Task System

Tasks that were scheduled while the computer was off are not lost. They are caught when the computer turns back on.

### 4.1 How It Works

The runtime of each module is stored in Redis:

    job_state:{module_name} → {
        "scheduled_at": "2026-04-22T10:00:00",
        "last_run":     "2026-04-20T10:03:00",
        "status":       "completed"
    }

When Docker starts (i.e., when the computer turns on), the **Catch-Up Service** runs automatically:

    Catch-Up Service starts
    → Fetch job_state of all modules from Redis
    → For each module: "Was this module supposed to have run by now but didn't?"
    → If yes: add to Celery queue as a "catch-up" task
    → If no: continue normally

### 4.2 Missed Task Rules

| Situation | Behavior |
|-----------|----------|
| Computer was off < 6 hours | Missed tasks are run immediately |
| Computer was off > 6 hours | Only the most recent period's task runs (no old backlog) |
| News module was missed | Skipped — news older than 24 hours is not sent |
| Clothing/event scan was missed | Waits for the next normal cycle |
| Price tracker was missed | Runs immediately (price may have changed) |
| Morning briefing was missed | Skipped — morning briefing is not sent that day |
| Passive discovery was missed | Runs immediately |

### 4.3 Notification Stacking

If the computer was off for 3+ days and multiple periods have accumulated:

    → Only the most recent period's data is processed
    → A single "Welcome back" summary message is sent:
       "We haven't spoken in 3 days. Here's the latest: [summary]"
    → No flood of separate notifications

### 4.4 Catch-Up Service Code (Structure)

    class CatchUpService:
        def run(self):
            modules = load_all_modules()
            for module in modules:
                state = redis.get(f"job_state:{module.name}")
                if self.should_catchup(module, state):
                    celery.send_task(module.name, kwargs={"catchup": True})
    
        def should_catchup(self, module, state) -> bool:
            if not module.schedule:
                return False  # On-demand modules (like food) are skipped
            if module.name in NO_CATCHUP_MODULES:
                return False  # Time-sensitive modules like news and morning briefing
            last_run = state.get("last_run")
            next_expected = calculate_next_run(module.schedule, last_run)
            offline_duration = now() - last_run
            return next_expected < now() and offline_duration < timedelta(hours=6)

---

## 5. AI Assistant Core

### 5.1 Conversation Loop

    User sends a message
           │
           ▼
    Intent Detector (LLM)
    "What do they want? Chat, task, or tone change?"
           │
           ├── chat         → LLM response with memory + tone + profile
           ├── clothing     → Trigger clothing module
           ├── food         → Trigger food module
           ├── news         → Trigger news module
           ├── article      → Trigger article module
           ├── events       → Trigger events module
           ├── price        → Trigger price module
           ├── tone_change  → Update tone, write to Redis
           └── unclear      → LLM decides, asks if needed

### 5.2 Conversation Memory

The last **3 days** of conversation is stored in Redis (TTL: 3 days). It is added as context to every LLM call.

    Memory structure:
    · Last 20 messages: Stored as full text
    · Older than 20, newer than 3 days: Compressed by summarizing with the LLM
    · Older than 3 days: Deleted

### 5.3 Adaptive Tone System

Tone is stored in Redis. It is persistent and carries across conversations.

    Tones:
    · casual       — Friendly, can be informal (default)
    · serious      — Professional but not cold
    · professional — Formal, brief, precise

    Changing tone: Natural language, no commands required
    · "be a bit more serious"    → switch to serious mode
    · "relax now"                → return to casual mode
    · "be normal"                → revert to default

    The LLM detects tone-change requests from the message text itself.

### 5.4 Proactive Messaging

KAIA writes on its own in two situations:

1. **Scheduled modules** — Morning briefing, evening reading, etc. (expected)
2. **AI decision** — If it decides "the user should know this" while a module runs

    Proactive decision:
    relevance_score = calculate_relevance(item, profile)
    urgency         = item.get("urgency", 0)
    
    if relevance_score > 0.88 or urgency > 0.95:
        telegram.send(user_id, format_proactive(item))

    Examples:
    KAIA: "Hey, that Sony headset dropped 24% — it's now ₺1,860."
    KAIA: "There's a concert tonight at AASSM that you might find interesting."
    KAIA: "There's something on Ars Technica right now that I think you'll really like."

### 5.5 System Prompt

    You are KAIA — a personal AI assistant, not a bot.
    
    PERSONALITY:
    - Default tone: casual, friendly. Can be informal.
    - If the tone is changed, stay in the new tone until told otherwise.
    - Be concise. Don't elaborate unless necessary.
    
    LANGUAGE:
    - Respond in Turkish to Turkish messages, in English to English messages.
    
    MEMORY:
    - You remember previous conversations. Reference them.
    - You know the profile: interests, style, budget.
    
    TASK DETECTION:
    - "what should I eat" → food module
    - "suggest something" → decide based on profile
    - If unclear, ask — but don't ask too many questions.
    
    LIMITS:
    - Payment, account creation, passwords — never.
    - For actions requiring approval, send a button.

---

## 6. Onboarding (Initial Setup)

When the system first runs, it sends the user an empty profile template.

    KAIA: Hello! Please fill out this template
          and send it back so I can get to know you:
    
    [template.yaml file is attached]

The user fills it out and sends it back. KAIA parses it, writes it to Redis. System is ready.

Template content (to be filled in by the user):

    # KAIA Profile Template
    
    location: "Izmir"
    
    clothing:
      style: ""           # e.g.: oversized, minimal, streetwear
      budget_min: 0
      budget_max: 0
    
    interests:
      - ""               # e.g.: technology, architecture, photography, music
    
    reading:
      morning: "short_news"    # short_news / deep_article / mixed
      evening: "deep_article"
      max_minutes: 20
    
    events:
      categories:
        - theater
        - cinema
        - concert
    
    modules:
      food: false       # Starts disabled, enable with /module food on

---

## 7. Scheduling System

    # schedule.yaml
    
    tasks:
      morning_briefing:
        time: "07:30"
        days: every_day
        content: [weather, news_summary, article_of_the_day]
        catchup: false       # Skip if missed
    
      evening_reading:
        time: "21:00"
        days: every_day
        content: [article_recommendations]
        catchup: false
    
      weekly_events:
        time: "09:00"
        day: monday
        content: [izmir_events]
        catchup: false       # Waits for the next cycle
    
      clothing_scan:
        time: "10:00"
        days: [tuesday, friday]
        content: [clothing_recommendations]
        catchup: false       # Waits for the next cycle
    
      price_check:
        time: "12:00"
        days: every_day
        content: [price_tracker]
        catchup: true        # Run immediately if missed
    
      passive_discovery:
        time: "14:00"
        days: every_day
        content: [proactive_discovery]
        catchup: true        # Run immediately if missed

---

## 8. Modules

### 8.1 Clothing Module

At initial setup, reference photos are converted to embeddings using the CLIP model and saved to the profile.

During regular scans (Tuesday & Friday):
- Playwright scrapes known sites + newly discovered sites
- Each product image is embedded with CLIP
- Cosine similarity is computed against reference embeddings
- Budget filter applied + top 8 products selected
- Sent to Telegram

Site discovery: 1–2 new sites are discovered on each search. Sites that yield good results are saved to the profile. Sites are prioritized as the user likes more results.

Learning:
- Like → embedding added to liked pool, site score +0.05
- Skip → added to disliked pool, site score -0.02

### 8.2 Article / Reading Module

RSS + web scraping. Sources are selected based on interests and language preference.
(Technology → English, current affairs/culture → Turkish)

Evening at 21:00: 3 article recommendations, each with title + reading time + 2-sentence teaser.

Natural language: "I don't want anything heavy" → LLM analyzes tone, returns lighter suggestions.

### 8.3 News Summary Module

Delivered as part of the morning briefing. Primarily Turkish sources, with selected English technology sources.
Each news item: Headline + 2-sentence summary + source link.
News older than 24 hours is not sent (skipped during catch-up).

### 8.4 Price Tracker Module

User provides a link or product name and sets a target price. Checked once per day.
Instant Telegram notification when the price drops. Catch-up active: checks immediately when the computer turns on.

### 8.5 Weather + Outfit Suggestion

OpenWeatherMap free API. Izmir weather data + profile style → LLM outfit suggestion.
Delivered as part of the morning briefing.

### 8.6 Food Recipe Module

On-demand, disabled by default. Enable with: /module food on

User writes a list of ingredients → LLM suggests 3 recipes → if not satisfied, "suggest something else" loop →
user can add constraints like "keep it light" → loop continues until satisfied.
Conversation state is stored in Redis.

### 8.7 Events Module (Izmir)

Sources: Biletix, Passo, AASSM, Izmir Metropolitan Municipality, Akademik Müzik

Weekly summary: Monday 09:00, events with profile interest score > 0.75.
Instant notification: Proactive message for events with score > 0.88.
Reservation: Level 2 action — the form is not opened until the user presses the confirm button.

---

## 9. Logging

Each service writes to its own log file. The user can read it whenever they want.

    ~/.kaia/logs/
    ├── agent-core.log     # Intent, conversation, decisions
    ├── telegram-bot.log   # Incoming/outgoing messages, rejections
    ├── celery-worker.log  # Task start/end, errors
    ├── celery-beat.log    # Scheduling events
    ├── scraper.log        # Site scraping, rate limits, errors
    └── catchup.log        # Missed task detection and execution

Log format:

    2026-04-22 10:02:34 [INFO]  [clothing] Scan started — 3 sites
    2026-04-22 10:04:12 [INFO]  [clothing] 8 products found, sent to Telegram
    2026-04-22 10:04:12 [INFO]  [catchup] price_tracker missed, added to queue
    2026-04-22 10:05:01 [WARN]  [scraper] trendyol.com slow response — 8.2s
    2026-04-22 10:05:45 [ERROR] [scraper] zara.com connection error — will retry

Logs are retained for 30 days, then automatically cleaned up.

Can be monitored live with the make logs command:

    make logs              # All services
    make logs s=scraper    # Scraper only

---

## 10. Security Model

### 10.1 Telegram Security

Chat ID filter: every message that does not match the TELEGRAM_CHAT_ID value defined in .env is silently rejected. It is logged but receives no response.

### 10.2 Action Permission Levels

    Level 0 — AUTOMATIC:
      Web scraping, sending notifications, updating profile, logging
    
    Level 1 — INFORM (does it, tells you):
      Clothing/article/news recommendations, sharing links, updating profile scores
    
    Level 2 — CONFIRM (Telegram button required):
      Filling forms, initiating a reservation, adding a product to tracking
    
    Level 3 — FORBIDDEN (even if the user approves):
      Payment, account creation, entering passwords, sharing financial data

### 10.3 Network Isolation

    Ollama:     NO internet access
    Redis:      Completely closed to the outside
    Scraper:    Target domain only, process terminated after task
    Agent Core: Telegram API + OpenWeatherMap API only

### 10.4 Rate Limiting

Per site: max requests per minute, random wait (3–12 s), mandatory robots.txt check.

---

## 11. Updates

    git pull
    make build
    make restart

Profile and Redis data are unaffected. Logs are preserved.

---

## 12. Backup

    Every night at 03:00:
    → ~/.kaia/backups/profile_YYYY-MM-DD.yaml
    → ~/.kaia/backups/job_state_YYYY-MM-DD.json
    Last 30 days retained, older files deleted.

---

## 13. Success Criteria

- Docker starts automatically when the computer turns on; the user never sees a terminal
- Background RAM < 6 GB, CPU < 2% when idle
- Meaningful, contextual responses to freely written messages
- "Yesterday we talked about..." references are correctly resolved
- Tone change is detected from the message text, no command required
- Proactive messages genuinely make the user say "this is exactly what I wanted"
- Critical missed tasks (price tracker) run at startup
- No Level 3 action ever occurs
- Messages from unknown chat IDs are rejected
- Logs are readable and meaningful
- Adding a new module takes < 1 hour (single Python file)
- Recommendations after 4 weeks are noticeably better than in the first week


## 14. After MVP 
- After all the success criteria's reached the additions that we can:
-> Song Selecter from spotify or youtube for users mood 