import re
import urllib.parse
import urllib.request
from datetime import datetime


def search_flights(origin: str, destination: str, date: str, return_date: str = "") -> str:
    """Search for flights between two airports. Returns prices and flight info when available, plus booking links.

    Args:
        origin: IATA airport code (e.g. BIO, MAD, JFK)
        destination: IATA airport code (e.g. LED, BCN, LHR)
        date: Departure date in YYYY-MM-DD format
        return_date: Return date in YYYY-MM-DD format (optional, for round trips)
    """
    orig = origin.strip().upper()
    dest = destination.strip().upper()

    try:
        dt = datetime.strptime(date.strip(), "%Y-%m-%d")
    except ValueError:
        return f"Invalid date format: '{date}'. Use YYYY-MM-DD (e.g. 2026-04-15)."

    date_str = dt.strftime("%d %b %Y")
    month_str = dt.strftime("%B %Y")
    trip_type = "round trip" if return_date else "one way"

    # Try to get real price info via web search
    price_info = _search_prices(orig, dest, date_str, month_str)

    # Build booking links
    kayak_date = dt.strftime("%Y-%m-%d")
    if return_date:
        try:
            rt = datetime.strptime(return_date.strip(), "%Y-%m-%d")
            kayak = f"https://www.kayak.com/flights/{orig}-{dest}/{kayak_date}/{rt.strftime('%Y-%m-%d')}"
            skyscanner = f"https://www.skyscanner.com/transport/flights/{orig.lower()}/{dest.lower()}/{dt.strftime('%Y%m%d')}/{rt.strftime('%Y%m%d')}/"
            momondo = f"https://www.momondo.com/flight-search/{orig}-{dest}/{kayak_date}/{rt.strftime('%Y-%m-%d')}"
        except ValueError:
            kayak = f"https://www.kayak.com/flights/{orig}-{dest}/{kayak_date}"
            skyscanner = f"https://www.skyscanner.com/transport/flights/{orig.lower()}/{dest.lower()}/{dt.strftime('%Y%m%d')}/"
            momondo = f"https://www.momondo.com/flight-search/{orig}-{dest}/{kayak_date}"
    else:
        kayak = f"https://www.kayak.com/flights/{orig}-{dest}/{kayak_date}"
        skyscanner = f"https://www.skyscanner.com/transport/flights/{orig.lower()}/{dest.lower()}/{dt.strftime('%Y%m%d')}/"
        momondo = f"https://www.momondo.com/flight-search/{orig}-{dest}/{kayak_date}"

    lines = [f"**Flights {orig} → {dest}** | {date_str} | {trip_type}", ""]

    if price_info:
        lines.append(price_info)
        lines.append("")

    lines += [
        "**Book:**",
        f"- [Kayak]({kayak})",
        f"- [Skyscanner]({skyscanner})",
        f"- [Momondo]({momondo})",
    ]
    return "\n".join(lines)


def _search_prices(orig: str, dest: str, date_str: str, month_str: str) -> str:
    """Try to get real price data via DDG web search."""
    try:
        query = f"{orig} {dest} flights {month_str} price EUR cheap"
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query, "kl": "us-en"})
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")

        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        snippets = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets]

        # Keep snippets that mention prices or fare info
        price_snippets = []
        for s in snippets:
            if re.search(r'[\$€£]\s*\d+|\d+\s*(?:EUR|USD|GBP)|from\s+\$?\d+|cheap|price|fare', s, re.IGNORECASE):
                if len(s) > 20:
                    price_snippets.append(s[:220])
            if len(price_snippets) >= 3:
                break

        if price_snippets:
            return "**From web search:**\n" + "\n".join(f"- {s}" for s in price_snippets)
    except Exception:
        pass
    return ""
