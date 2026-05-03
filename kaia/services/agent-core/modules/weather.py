import logging
import os

import httpx

from core.profile import load_profile
from llm.client import ask_llm
from modules.base import BaseModule, ModuleResult

logger = logging.getLogger("module.weather")

API_KEY = os.getenv("OPENWEATHER_API_KEY", "")


class WeatherModule(BaseModule):
    name = "weather_outfit"
    schedule = "every day 07:25"
    catchup = False

    def run(self, profile: dict) -> ModuleResult:
        if not profile:
            profile = load_profile()

        location = profile.get("location", "Izmir,TR")
        if "," not in location:
            location = f"{location},TR"

        try:
            resp = httpx.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "q": location,
                    "appid": API_KEY,
                    "lang": "tr",
                    "units": "metric",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            temp   = data["main"]["temp"]
            feels  = data["main"]["feels_like"]
            desc   = data["weather"][0]["description"]
            humid  = data["main"]["humidity"]
            wind   = data["wind"]["speed"]

            weather_summary = f"{temp:.0f}°C (hissedilen {feels:.0f}°C), {desc}, nem %{humid}, rüzgar {wind:.1f} m/s"

            style = profile.get("clothing", {}).get("style", "casual")
            suggestion = ask_llm(
                f"Hava durumu: {weather_summary}. Kullanıcının stili: {style}. "
                f"2 cümlede ne giymeli?",
                temperature=0.6,
            )

            message = f"🌤 {location.split(',')[0]}: {weather_summary}\n{suggestion}"

            import redis, json
            r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
            r.setex("latest:weather", 3600 * 4, message)

            return ModuleResult(success=True, message=message)

        except httpx.TimeoutException:
            logger.warning("OpenWeatherMap timeout")
            return ModuleResult(success=False, message="Hava durumu alınamadı (timeout).")
        except Exception as e:
            logger.error(f"Weather module error: {e}")
            return ModuleResult(success=False, message="Hava durumu alınamadı.")
