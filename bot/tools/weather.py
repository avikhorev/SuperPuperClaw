import httpx

def get_weather(location: str) -> str:
    """Get current weather for a location."""
    try:
        geo = httpx.get(
            f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
        ).json()
        if not geo.get("results"):
            return f"Location '{location}' not found."
        r = geo["results"][0]
        lat, lon = r["latitude"], r["longitude"]
        data = httpx.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,weathercode,windspeed_10m&timezone=auto"
        ).json()
        c = data["current"]
        return f"Weather in {location}: {c['temperature_2m']}°C, wind {c['windspeed_10m']} km/h"
    except Exception as e:
        return f"Weather unavailable: {e}"
