# ROADMAP — KAIA

**PRD:** v1.0  
**Total:** ~10 Weeks  
**Rule:** At the end of every week, there is something working and testable in hand.

---

## Overview

    Week 1  → Docker + security foundation
    Week 2  → Ollama + local LLM
    Week 3  → AI assistant core (conversation + memory + tone)
    Week 4  → Web scraping with Playwright
    Week 5  → Celery + module system + missed tasks
    Week 6  → Telegram bot + onboarding + security
    Week 7  → First real modules: news + weather + morning briefing
    Week 8  → Clothing module (visual search)
    Week 9  → Food + events + price tracker
    Week 10 → Learning + logging + production

---

## Week 1 — Docker Foundation and Security

**Goal:** An isolated, secure environment. Everything comes up with make start.

### What to Learn This Week
- What is Docker, what is the difference between a container and an image?
- How does docker-compose.yml work?
- Container networking: internal vs external network
- Secrets management: .env file, why passwords don't belong in code
- restart: always — the service restarts itself if it crashes

### Recommended Resources
- Docker official "Get Started" (sections 1–3): docs.docker.com/get-started
- YouTube: "Docker Compose in 12 Minutes" — TechWorld with Nana

### Tasks

**1.1 — Installation**
- Install Docker Desktop (Windows: with WSL2 backend)
- Verify that docker --version and docker compose version work
- Install the VS Code Docker extension

**1.2 — Folder structure**

    kaia/
    ├── docker-compose.yml
    ├── .env.example
    ├── .env                    ← NEVER committed to git
    ├── .gitignore
    ├── Makefile
    ├── schedule.yaml
    └── services/
        ├── agent-core/
        │   └── Dockerfile
        ├── telegram-bot/
        │   └── Dockerfile
        └── scraper/
            └── Dockerfile

**1.3 — docker-compose.yml**

    version: '3.9'
    
    networks:
      kaia-internal:
        internal: true
      kaia-external:
        internal: false
    
    services:
      redis:
        image: redis:7-alpine
        networks: [kaia-internal]
        restart: always
        volumes: [redis-data:/data]
    
      ollama:
        image: ollama/ollama
        networks: [kaia-internal]     # No internet access
        restart: always
        volumes: [ollama-data:/root/.ollama]
    
      agent-core:
        build: ./services/agent-core
        networks: [kaia-internal, kaia-external]
        restart: always
        env_file: .env
        depends_on: [redis, ollama]
        volumes:
          - ~/.kaia:/data/kaia        # For profile and logs
    
      telegram-bot:
        build: ./services/telegram-bot
        networks: [kaia-external]
        restart: always
        env_file: .env
        depends_on: [agent-core]
    
      celery-worker:
        build: ./services/agent-core
        command: celery -A core.celery_app worker --loglevel=info --concurrency=2
        networks: [kaia-internal, kaia-external]
        restart: always
        env_file: .env
        depends_on: [redis, ollama]
    
      celery-beat:
        build: ./services/agent-core
        command: celery -A core.celery_app beat --loglevel=info
        networks: [kaia-internal]
        restart: always
        env_file: .env
        depends_on: [redis]
    
    volumes:
      redis-data:
      ollama-data:

**1.4 — .env.example**

    TELEGRAM_TOKEN=
    TELEGRAM_CHAT_ID=
    OPENWEATHER_API_KEY=
    KAIA_DATA_DIR=/data/kaia

**1.5 — Makefile**

    start:
        docker compose up -d
    
    stop:
        docker compose down
    
    restart:
        docker compose restart
    
    build:
        docker compose build --no-cache
    
    logs:
        docker compose logs -f $(s)
    
    health:
        docker compose ps

**1.6 — .gitignore**

    .env
    *.pyc
    __pycache__/
    .DS_Store
    ~/.kaia/backups/

### Week 1 End Test

    make start    → All services show "running"
    make health   → All green
    make logs     → Log stream is visible
    make stop     → Everything stops

### Common Issues

    WSL2 not installed     → PowerShell: wsl --install
    Port conflict          → Change the ports section in docker-compose
    Permission denied      → sudo usermod -aG docker $USER

---

## Week 2 — Ollama + Local LLM

**Goal:** LLM runs entirely locally. Responses can be retrieved from Python.

### What to Learn This Week
- LLM quantization: what is Q4, why do we choose Q4?
- Using the Ollama REST API
- The difference between a system prompt and a user prompt
- What do temperature and context window mean?
- Why Mistral 7B? (speed, quality, Turkish language support)

### Recommended Resources
- Ollama docs: ollama.ai/docs
- Prompt Engineering Guide: promptingguide.ai (Sections 1–2)

### Tasks

**2.1 — Download the model**

    docker exec -it kaia-ollama-1 ollama pull mistral:7b-instruct-q4_K_M
    # ~4 GB, downloaded once

**2.2 — Python Ollama client**

    # services/agent-core/llm/client.py
    import httpx
    
    OLLAMA_URL = "http://ollama:11434"
    
    def ask_llm(prompt, system=None, history=None, temperature=0.7):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
    
        response = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": "mistral:7b-instruct-q4_K_M",
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature}
            },
            timeout=60.0
        )
        return response.json()["message"]["content"]

**2.3 — System prompt**

    # services/agent-core/llm/prompts.py
    
    KAIA_SYSTEM = """
    You are KAIA — a personal AI assistant, not a bot.
    
    PERSONALITY:
    - Default tone: casual, friendly. Can be informal.
    - If the tone is changed, stay in the new tone until told otherwise.
    - Be concise.
    
    LANGUAGE:
    - Respond in Turkish to Turkish messages, in English to English messages.
    
    MEMORY:
    - You remember previous conversations. Reference them.
    - You know the profile: interests, style, budget.
    
    LIMITS:
    - Payment, account creation, passwords — never.
    - For actions requiring approval, send a button, don't do it yourself.
    """

**2.4 — RAM measurement**

    docker stats    # Compare model loaded vs idle

### Week 2 End Test

    python -c "
    from llm.client import ask_llm
    from llm.prompts import KAIA_SYSTEM
    print(ask_llm('It is 28 degrees today. What should I wear?', system=KAIA_SYSTEM))
    "
    # → Should return a short, casual, sensible response

---

## Week 3 — AI Assistant Core (THE MOST CRITICAL WEEK)

**Goal:** Conversation memory, intent detection, and the tone system all work.
This is what turns KAIA into a real assistant.

### What to Learn This Week
- Stateful conversation: context window management
- Storing JSON data in Redis with TTL
- Intent detection: using the LLM as a classifier
- State machine: managing tone modes

### File Structure (End of Week 3)

    services/agent-core/
    ├── llm/
    │   ├── client.py
    │   └── prompts.py
    ├── memory/
    │   └── conversation.py     ← Memory system
    ├── core/
    │   ├── intent.py           ← Intent detector
    │   ├── tone_manager.py     ← Tone management
    │   └── conversation_loop.py ← Main loop
    └── requirements.txt

### Tasks

**3.1 — Conversation Memory**

    # memory/conversation.py
    import redis, json
    from datetime import datetime
    
    r = redis.Redis(host="redis", port=6379, decode_responses=True)
    
    class ConversationMemory:
        def __init__(self, user_id, window_days=3):
            self.key = f"conversation:{user_id}"
            self.ttl = window_days * 86400
    
        def add(self, role, content):
            msg = {
                "role": role,
                "content": content,
                "ts": datetime.now().isoformat()
            }
            r.rpush(self.key, json.dumps(msg))
            r.expire(self.key, self.ttl)
    
        def get_recent(self, last_n=20):
            """Last N messages — full text"""
            all_msgs = r.lrange(self.key, 0, -1)
            return [json.loads(m) for m in all_msgs[-last_n:]]
    
        def get_summary(self):
            """Older messages — LLM summary"""
            old = r.lrange(self.key, 0, -21)
            if not old:
                return ""
            text = "\n".join([json.loads(m)["content"] for m in old])
            return ask_llm(f"Summarize this conversation in 3 sentences:\n{text}",
                           temperature=0.3)

**3.2 — Intent Detector**

    # core/intent.py
    
    INTENT_PROMPT = """
    Analyze the user message. Which category does it belong to?
    
    Categories:
    chat | clothing | food | news | article | events
    price | tone_change | module | unclear
    
    Message: "{message}"
    
    Write only the category name, nothing else.
    """
    
    def detect_intent(message: str) -> str:
        result = ask_llm(
            INTENT_PROMPT.format(message=message),
            temperature=0.1    # Low temperature = consistent output
        )
        return result.strip().lower()

**3.3 — Tone Manager**

    # core/tone_manager.py
    
    INSTRUCTIONS = {
        "casual":       "Speak casually and in a friendly way. Can be informal.",
        "serious":      "Be serious and professional. Not cold.",
        "professional": "Use formal language. Be brief and precise.",
    }
    
    class ToneManager:
        def __init__(self, user_id):
            self.key = f"tone:{user_id}"
    
        def get(self):
            return r.hget(self.key, "current") or "casual"
    
        def set(self, tone):
            r.hset(self.key, mapping={"current": tone})
    
        def instruction(self):
            return INSTRUCTIONS.get(self.get(), INSTRUCTIONS["casual"])

**3.4 — Main Conversation Loop**

    # core/conversation_loop.py
    
    MODULE_INTENTS = {"clothing", "food", "news", "article", "events", "price"}
    
    async def handle_message(user_id: str, message: str) -> str:
        memory = ConversationMemory(user_id)
        tone   = ToneManager(user_id)
    
        intent = detect_intent(message)
    
        # Tone change
        if intent == "tone_change":
            new_tone = extract_tone_from_message(message)  # Via LLM
            tone.set(new_tone)
            response = "Understood." if new_tone == "serious" else "Sure :)"
            memory.add("user", message)
            memory.add("assistant", response)
            return response
    
        # Trigger module
        if intent in MODULE_INTENTS:
            return await trigger_module(intent, message, user_id)
    
        # Chat — LLM call with memory + tone
        recent  = memory.get_recent(last_n=20)
        summary = memory.get_summary()
    
        system = KAIA_SYSTEM + f"\nTone: {tone.instruction()}"
        if summary:
            system += f"\nPrevious conversation summary: {summary}"
    
        response = ask_llm(message, system=system, history=recent)
    
        memory.add("user", message)
        memory.add("assistant", response)
    
        return response

### Week 3 End Test

    # Terminal simulation with test_conversation.py (Telegram not yet connected)
    
    You: hello
    KAIA: Hey, what's up?
    
    You: be a bit more serious
    KAIA: Understood.
    
    You: what will the weather be like tomorrow
    KAIA: [Response in serious tone]
    
    You: relax now
    KAIA: Sure :)
    
    You: what did we talk about yesterday
    KAIA: [Summarizes from memory]

---

## Week 4 — Web Scraping with Playwright

**Goal:** Be able to browse any website safely and extract data.

### What to Learn This Week
- What is a headless browser? Playwright vs Selenium
- How to write CSS Selectors and XPath
- robots.txt and ethical scraping
- Rate limiting: how to avoid getting banned
- Why JS-heavy sites need a dedicated scraper

### Recommended Resources
- Playwright Python docs: playwright.dev/python

### Tasks

**4.1 — Base Scraper**

    # scraper/base.py
    import asyncio, random
    from playwright.async_api import async_playwright
    
    class BaseScraper:
        def __init__(self, base_url, rate_limit_rpm=10):
            self.base_url = base_url
            self.delay_min = 60 / rate_limit_rpm
            self.delay_max = self.delay_min * 2
    
        async def _wait(self):
            await asyncio.sleep(random.uniform(self.delay_min, self.delay_max))
    
        async def _check_robots(self, url) -> bool:
            # Fetch robots.txt, check if scraping is allowed
            pass
    
        async def scrape(self, url) -> dict:
            raise NotImplementedError

**4.2 — Trendyol Scraper**

    # scraper/trendyol.py
    
    class TrendyolScraper(BaseScraper):
        def __init__(self):
            super().__init__("https://trendyol.com", rate_limit_rpm=8)
    
        async def search(self, query, max_items=20):
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(f"{self.base_url}/sr?q={query}")
                await page.wait_for_selector(".product-card")
    
                items = []
                for card in (await page.query_selector_all(".product-card"))[:max_items]:
                    await self._wait()
                    items.append({
                        "title":     await card.inner_text(),  # real selectors will differ
                        "price":     ...,
                        "link":      ...,
                        "image_url": ...
                    })
    
                await browser.close()
                return items

**4.3 — Write Zara + H&M scrapers (same pattern)**

**4.4 — Site discovery scraper**
New site discovery via Google Shopping — scrape search engine results, detect new domains.

### Week 4 End Test

    results = asyncio.run(TrendyolScraper().search("oversize tshirt", 10))
    print(f"{len(results)} products — first: {results[0]['title']}")
    # → Delays between requests should be visible in the log

---

## Week 5 — Celery + Module System + Missed Tasks

**Goal:** Tasks run in the background. Missed tasks are caught. New module = single file.

### What to Learn This Week
- What is a task queue and why is it needed?
- Celery + Redis connection
- Celery Beat: cron-style scheduling
- Plugin system with abstract base class
- Automatic module discovery with importlib
- TTL and job state management in Redis

### Tasks

**5.1 — BaseModule**

    # modules/base.py
    from abc import ABC, abstractmethod
    from dataclasses import dataclass, field
    
    @dataclass
    class ModuleResult:
        success: bool
        items: list = field(default_factory=list)
        message: str = ""
        requires_approval: bool = False
        proactive: bool = False
    
    class BaseModule(ABC):
        name: str = ""
        schedule: str = ""       # If empty, on-demand only
        catchup: bool = False    # Should it run if missed?
        enabled: bool = True
    
        @abstractmethod
        def run(self, profile: dict) -> ModuleResult:
            pass
    
        def on_feedback(self, item_id: str, feedback: str):
            pass
    
        def should_notify_proactively(self, item: dict, profile: dict) -> bool:
            return False

**5.2 — Module Loader**

    # core/module_loader.py
    import importlib, pkgutil
    from modules.base import BaseModule
    
    def load_all_modules() -> list:
        modules = []
        for _, name, _ in pkgutil.iter_modules(["modules"]):
            mod = importlib.import_module(f"modules.{name}")
            for attr in dir(mod):
                cls = getattr(mod, attr)
                if (isinstance(cls, type) and
                    issubclass(cls, BaseModule) and
                    cls != BaseModule):
                    modules.append(cls())
        return [m for m in modules if m.enabled]

**5.3 — Missed Task Service (Catch-Up)**

    # core/catchup.py
    from datetime import datetime, timedelta
    import json
    
    NO_CATCHUP = {"news", "morning_briefing", "clothing", "events"}
    # These modules wait for the next cycle if missed
    
    class CatchUpService:
        def run(self, modules):
            for module in modules:
                if module.name in NO_CATCHUP:
                    continue
                if not module.catchup or not module.schedule:
                    continue
    
                state = self._get_state(module.name)
                if self._should_catchup(module, state):
                    self._enqueue(module.name)
                    log(f"[catchup] {module.name} missed, added to queue")
    
        def _should_catchup(self, module, state) -> bool:
            last_run = state.get("last_run")
            if not last_run:
                return True
            last_run_dt = datetime.fromisoformat(last_run)
            offline = datetime.now() - last_run_dt
            # If offline for more than 6 hours, run only once
            if offline > timedelta(hours=6):
                already_queued = r.get(f"catchup_done:{module.name}:{datetime.today().date()}")
                return not already_queued
            return True
    
        def _get_state(self, name):
            raw = r.get(f"job_state:{name}")
            return json.loads(raw) if raw else {}
    
        def _enqueue(self, name):
            celery.send_task(f"tasks.run_module", args=[name],
                             kwargs={"catchup": True})
            # Prevent re-triggering today
            r.setex(f"catchup_done:{name}:{datetime.today().date()}", 86400, "1")

**5.4 — Job state update**
After each module runs:

    def record_run(module_name, success):
        r.set(f"job_state:{module_name}", json.dumps({
            "last_run": datetime.now().isoformat(),
            "status": "completed" if success else "failed"
        }))

**5.5 — Test module: HelloKAIA**

    # modules/hello_kaia.py
    from .base import BaseModule, ModuleResult
    from datetime import datetime
    
    class HelloKAIA(BaseModule):
        name = "hello_kaia"
        schedule = "every 1 minutes"
        catchup = False
    
        def run(self, profile):
            return ModuleResult(
                success=True,
                message=f"KAIA is running — {datetime.now():%H:%M:%S}"
            )

### Week 5 End Test

    make start
    → Every minute in the log: "KAIA is running — 14:23:01"
    
    # Missed task test:
    make stop
    # Wait 10 minutes
    make start
    → catchup.log: "price_tracker missed, added to queue"
    
    # Adding a new module:
    touch services/agent-core/modules/test2.py
    # Implement BaseModule
    make restart
    → System auto-discovers it

---

## Week 6 — Telegram Bot + Onboarding + Security

**Goal:** Writing a message in Telegram gets a response from KAIA with memory and tone awareness.
Messages from unknown chat IDs are rejected. Onboarding works.

### What to Learn This Week
- Telegram Bot API and BotFather
- python-telegram-bot library
- Inline keyboard / button system
- Config management with YAML
- Designing an approval mechanism

### Tasks

**6.1 — Get a bot token**

    @BotFather → /newbot → get token
    Add to .env:
    TELEGRAM_TOKEN=...
    TELEGRAM_CHAT_ID=...  ← Your own chat ID

**6.2 — Chat ID filter**

    # telegram-bot/security.py
    import os
    
    ALLOWED_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
    
    def is_allowed(update) -> bool:
        return update.effective_chat.id == ALLOWED_CHAT_ID

**6.3 — Main message handler**

    # telegram-bot/bot.py
    from telegram.ext import Application, MessageHandler, filters
    
    async def handle_text(update, context):
        if not is_allowed(update):
            # Reject silently, write to log, do not reply
            logger.warning(f"Unknown chat ID: {update.effective_chat.id}")
            return
    
        user_id = str(update.effective_user.id)
        message = update.message.text
    
        # Forward to Agent Core via Redis queue
        response = await agent_core.handle_message(user_id, message)
        await update.message.reply_text(response)

**6.4 — Approval mechanism (Level 2)**

    async def ask_approval(chat_id, description, action_id):
        keyboard = [[
            InlineKeyboardButton("✅ Confirm", callback_data=f"approve_{action_id}"),
            InlineKeyboardButton("❌ Cancel",  callback_data="cancel")
        ]]
        await bot.send_message(
            chat_id,
            f"⚠️ Approval required:\n{description}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

**6.5 — Onboarding flow**

    # On first startup:
    if not profile_exists(user_id):
        template = load_template("profile_template.yaml")
        await bot.send_document(chat_id, template,
            caption="Hello! Fill this out and send it back so I can get to know you.")
    
    # If the user sends back a filled .yaml:
    async def handle_document(update, context):
        if update.message.document.file_name.endswith(".yaml"):
            file = await update.message.document.get_file()
            content = await file.download_as_bytearray()
            profile = parse_profile(content)
            save_profile(user_id, profile)
            await update.message.reply_text("Profile saved! I'm ready now.")

**6.6 — Profile YAML service**

    # core/profile.py
    import yaml
    
    PROFILE_PATH = "/data/kaia/user_profile.yaml"
    
    def load_profile():
        with open(PROFILE_PATH) as f:
            return yaml.safe_load(f)
    
    def save_profile(profile):
        with open(PROFILE_PATH, "w") as f:
            yaml.dump(profile, f, allow_unicode=True)

### Week 6 End Test

    In Telegram: "hello"               → casual response
    "be a bit more serious"            → tone changes
    "what did we talk about yesterday" → response from memory
    Message from unknown number        → no reply, logged
    
    On first startup:
    → Template.yaml arrives via Telegram
    → Profile is saved when filled out and sent back

---

## Week 7 — News + Weather + Morning Briefing

**Goal:** Morning briefing arrives in Telegram every day at 07:30.

### Tasks

**7.1 — OpenWeatherMap API**
openweathermap.org → free account → OPENWEATHER_API_KEY → .env

**7.2 — Weather Module**

    # modules/weather.py
    class WeatherModule(BaseModule):
        name = "weather_outfit"
        schedule = "every day 07:25"
        catchup = False    # Skip if morning briefing is missed
    
        def run(self, profile):
            data = httpx.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": "Izmir,TR", "appid": API_KEY,
                        "lang": "en", "units": "metric"}
            ).json()
    
            weather = f"{data['main']['temp']:.0f}°C, {data['weather'][0]['description']}"
            suggestion = ask_llm(f"Weather: {weather}. Profile style: {profile['clothing']['style']}. "
                                 f"In 2 sentences, what should I wear?")
    
            return ModuleResult(success=True, message=f"🌤 {weather}\n{suggestion}")

**7.3 — News Module**

    # modules/news.py
    RSS_SOURCES = {
        "en":   ["https://feeds.arstechnica.com/arstechnica/index"],
        "tr":   ["https://bianet.org/rss", "https://t24.com.tr/rss"]
    }
    
    class NewsModule(BaseModule):
        name = "news"
        schedule = "every day 07:20"
        catchup = False    # News older than 24 hours is not sent
    
        def run(self, profile):
            articles = []
            for category, sources in RSS_SOURCES.items():
                for url in sources:
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:3]:
                        summary = ask_llm(f"Summarize in 2 sentences: {entry.title}. {entry.summary[:300]}")
                        articles.append({
                            "title":    entry.title,
                            "summary":  summary,
                            "link":     entry.link,
                            "category": category
                        })
            return ModuleResult(success=True, items=articles)

**7.4 — Morning Briefing Orchestrator**

    # modules/morning_brief.py
    class MorningBriefModule(BaseModule):
        name = "morning_briefing"
        schedule = "every day 07:30"
        catchup = False
    
        def run(self, profile):
            weather = redis.get("latest:weather")    # Left by WeatherModule
            news    = redis.get("latest:news")       # Left by NewsModule
    
            briefing = self._format(weather, news, profile)
            return ModuleResult(success=True, message=briefing)
    
        def _format(self, weather, news, profile):
            return f"""☀️ Good morning!
    
    {weather}
    
    📰 Today's News
    {news}
    """

### Week 7 End Test

    At 07:30 → arrives in Telegram:
    ☀️ Good morning! Tuesday, April 22
    
    🌤 Izmir: 22°C, sunny
       A light top is enough.
    
    📰 4 news summaries

---

## Week 8 — Clothing Module (Visual Search)

**Goal:** Send a reference photo → similar clothes arrive in Telegram.

### What to Learn This Week
- What is an embedding? How does the CLIP model work?
- Cosine similarity: how is the similarity between two vectors calculated?
- Coordinating multiple scrapers

### Tasks

**8.1 — CLIP installation**

    pip install sentence-transformers pillow
    # Model: clip-ViT-B-32, ~600 MB

**8.2 — Visual Embedder**

    # vision/embedder.py
    from sentence_transformers import SentenceTransformer
    from PIL import Image
    import numpy as np
    
    class VisualEmbedder:
        def __init__(self):
            self.model = SentenceTransformer("clip-ViT-B-32")
    
        def embed(self, image_path):
            return self.model.encode(Image.open(image_path))
    
        def similarity(self, e1, e2):
            return float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2)))

**8.3 — Reference photo registration flow**

    # When a photo arrives via Telegram:
    async def handle_photo(update, context):
        file = await update.message.photo[-1].get_file()
        path = f"~/.kaia/photos/ref_{timestamp}.jpg"
        await file.download_to_drive(path)
    
        emb = embedder.embed(path)
        profile["clothing"]["reference_photos"].append({
            "path":      path,
            "embedding": emb.tolist()
        })
        save_profile(profile)
    
        count = len(profile["clothing"]["reference_photos"])
        await update.message.reply_text(f"Reference added ({count}/5)")

**8.4 — Clothing Module**

    # modules/clothing.py
    class ClothingModule(BaseModule):
        name = "clothing"
        schedule = "every tuesday,friday 10:00"
        catchup = False    # Waits for the next cycle
    
        def run(self, profile):
            refs = [np.array(r["embedding"])
                    for r in profile["clothing"]["reference_photos"]]
            if not refs:
                return ModuleResult(success=False, message="No reference photos found.")
    
            budget_min = profile["clothing"]["budget"]["min"]
            budget_max = profile["clothing"]["budget"]["max"]
    
            results = []
            for scraper in [TrendyolScraper(), ZaraScraper(), HMScraper()]:
                items = asyncio.run(scraper.search("", max_items=50))
                for item in items:
                    emb = embedder.embed_from_url(item["image_url"])
                    score = float(np.mean([embedder.similarity(emb, r) for r in refs]))
                    if score > 0.75 and budget_min <= item["price"] <= budget_max:
                        item["score"] = score
                        results.append(item)
    
            results.sort(key=lambda x: x["score"], reverse=True)
            return ModuleResult(success=True, items=results[:8])
    
        def on_feedback(self, item_id, feedback):
            item = json.loads(r.get(f"item:{item_id}"))
            if feedback == "like":
                # Add embedding to liked pool
                # Increase site score
                pass
            elif feedback == "dislike":
                # Add to disliked pool
                # Decrease site score
                pass

### Week 8 End Test

    You: [Send 5 t-shirt photos]
    KAIA: 5 references saved! Suggestions will arrive on Friday.
    
    [Friday 10:00 automatic]:
    👕 Clothing Suggestions
    1. Oversized White T-Shirt — Trendyol, ₺349, 91% match
    [🔗 Go] [❤️ Like] [👎 Skip]

---

## Week 9 — Food + Events + Price Tracker

### 9.1 Food Recipe Module

On-demand, disabled by default. Enable with /module food on.

    Conversation flow:
    You: what should I eat
    KAIA: What do you have at home?
    You: tomatoes, eggs, cheese
    KAIA: 3 suggestions: Menemen / Caprese Toast / Sauté
          [1] [2] [3] [Suggest something else]
    You: keep it light
    KAIA: [same ingredients, lighter recipes]
    
    State stored in Redis:
    conversation_state:{user_id} = {
        "module": "food",
        "ingredients": ["tomatoes", "eggs", "cheese"],
        "step": "recipe_suggestion"
    }

### 9.2 Events Module

    # modules/events.py
    IZMIR_SOURCES = [
        "https://www.biletix.com/bolge/IZMIR/",
        "https://www.passo.com.tr/tr/etkinlik/izmir",
        "https://www.aassm.gov.tr/",
    ]
    
    class EventsModule(BaseModule):
        name = "events"
        schedule = "every monday 08:30"
        catchup = False    # Waits for the next cycle
    
        def run(self, profile):
            events = []
            for url in IZMIR_SOURCES:
                items = asyncio.run(generic_scraper(url))
                for item in items:
                    score = self._relevance_score(item, profile)
                    if score > profile["events"]["min_interest_score"]:
                        item["score"] = score
                        events.append(item)
            return ModuleResult(success=True, items=events)
    
        def should_notify_proactively(self, item, profile):
            return item.get("score", 0) > 0.88

### 9.3 Price Tracker Module

    # modules/price_tracker.py
    class PriceTrackerModule(BaseModule):
        name = "price_tracker"
        schedule = "every day 12:00"
        catchup = True     # Check immediately when computer turns on
    
        def run(self, profile):
            notifications = []
            for product in profile["price_tracker"]["products"]:
                current = self._fetch_price(product["link"])
                if current < product["target_price"]:
                    notifications.append({
                        "name":      product["name"],
                        "old":       product["current_price"],
                        "new":       current,
                        "link":      product["link"],
                        "proactive": True
                    })
                    product["current_price"] = current
            save_profile(profile)
            return ModuleResult(success=True, items=notifications)

---

## Week 10 — Learning + Logging + Production

**Goal:** System is stable, learning, logs are readable, and it auto-starts when the computer turns on.

### 10.1 Learning Engine

    # core/learning.py
    class LearningEngine:
        def process_feedback(self, item_id, feedback, profile):
            item = json.loads(r.get(f"item:{item_id}") or "{}")
            category = item.get("category", "general")
    
            delta = 0.02 if feedback == "like" else -0.01
            current = profile["interests"].get(category, 0.5)
            profile["interests"][category] = max(0.0, min(1.0, current + delta))
            save_profile(profile)
    
        def weekly_normalize(self, profile):
            """Weekly: normalize so all interest weights sum to 1.0"""
            total = sum(profile["interests"].values()) or 1
            for key in profile["interests"]:
                profile["interests"][key] /= total
            save_profile(profile)
            backup_profile(profile)

### 10.2 Logging

    # core/logger.py
    import logging
    from pathlib import Path
    
    LOG_DIR = Path("/data/kaia/logs")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    def get_logger(name):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
    
        # Write to file
        handler = logging.FileHandler(LOG_DIR / f"{name}.log")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        ))
        logger.addHandler(handler)
        return logger

Log files:

    ~/.kaia/logs/
    ├── agent-core.log
    ├── telegram-bot.log
    ├── celery-worker.log
    ├── celery-beat.log
    ├── scraper.log
    └── catchup.log

Retained for 30 days. Can be monitored live with make logs s=scraper.

### 10.3 Error Handling

In every module:

    def run(self, profile):
        try:
            # main code
        except httpx.TimeoutException:
            logger.warning(f"{self.name}: timeout")
            return ModuleResult(success=False, message="Site did not respond.")
        except Exception as e:
            logger.error(f"{self.name}: {e}")
            return ModuleResult(success=False, message="An error occurred.")

### 10.4 Auto-Start on Computer Boot

Windows — Task Scheduler:

    Trigger: At log on
    Action: docker compose -f C:\kaia\docker-compose.yml up -d

macOS — launchd:

    # ~/Library/LaunchAgents/com.kaia.startup.plist
    RunAtLoad: true
    Program: docker compose -f /Users/.../kaia/docker-compose.yml up -d

Linux:

    Docker restart: always + systemd docker service is sufficient.

### 10.5 Updates

    git pull
    make build
    make restart
    # Profile and Redis data are unaffected

### 10.6 Backup (Automatic, via Celery Beat)

    Every night at 03:00:
    ~/.kaia/backups/profile_YYYY-MM-DD.yaml
    ~/.kaia/backups/job_state_YYYY-MM-DD.json
    Last 30 days retained.

---

## Module Addition Guide (from Week 5 onwards)

    # 1. Create the file
    touch services/agent-core/modules/new_module.py
    
    # 2. Fill in the template:
    from .base import BaseModule, ModuleResult
    
    class NewModule(BaseModule):
        name = "new_module"
        schedule = "every day 10:00"
        catchup = False
        enabled = True
    
        def run(self, profile):
            # do your work
            return ModuleResult(success=True, items=[...])
    
        def should_notify_proactively(self, item, profile):
            return False
    
    # 3. make restart → system auto-discovers it, done

---

## Version Plan

    Version | Content                              | Week
    --------|--------------------------------------|-------
    v0.1    | Docker + LLM running                 | 2
    v0.2    | Conversation memory + tone system    | 3
    v0.3    | Scraping working                     | 4
    v0.4    | Module system + Celery + Catch-Up    | 5
    v0.5    | Telegram + Security + Onboarding     | 6
    v0.6    | Morning briefing arriving daily      | 7
    v0.7    | Clothing module active               | 8
    v0.9    | All modules working                  | 9
    v1.0    | Learning + Logging + Production      | 10

---

## Risk Table

    Risk                             | Mitigation
    ---------------------------------|------------------------------------------
    Trendyol bot detection           | User-agent rotation + slow requests
    Mistral slow response            | Q4 quant, timeout=60, fallback message
    RAM overflow                     | Celery concurrency=2, lazy model load
    Event site structure changes     | Add fallback parser to each scraper
    Telegram rate limit              | Queue at 1 message/sec
    LLM intent detection error       | Fallback: ask "What did you mean?"
    Catch-up stacks too many tasks   | NO_CATCHUP list + 6-hour threshold

---

## Conclusion

    You set it up once (10 weeks, learning as you go)
              ↓
    You turn on your computer
              ↓
    Docker starts automatically in the background
    Catch-Up service checks for missed tasks
              ↓
    07:30  → Morning briefing
    21:00  → Evening reading
    Tue/Fri → Clothing recommendations
    Mon    → Izmir events
    12:00  → Price check (runs at startup if missed)
    14:00  → Passive discovery (runs at startup if missed)
    Live   → Price drops, important events, KAIA's own discoveries
              ↓
    You can write on Telegram at any time.
    KAIA responds with memory, knowing your style, knowing you.
    Every week it knows you a little better.
