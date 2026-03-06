from datetime import datetime


def search_flights(origin: str, destination: str, date: str, return_date: str = "") -> str:
    """Search for flights between two airports. Returns direct booking links for Google Flights, Kayak, Skyscanner, and Momondo.

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

    gf_date = dt.strftime("%Y-%m-%d")
    date_str = dt.strftime("%d %b %Y")
    trip_type = "round trip" if return_date else "one way"

    google = f"https://www.google.com/travel/flights/search?tfs=CBwQARooagcIARID{orig}cgcIARID{dest}SAQwAQ&q=flights+{orig}+to+{dest}"
    kayak_date = dt.strftime("%Y-%m-%d")

    if return_date:
        try:
            rt = datetime.strptime(return_date.strip(), "%Y-%m-%d")
            kayak = f"https://www.kayak.com/flights/{orig}-{dest}/{kayak_date}/{rt.strftime('%Y-%m-%d')}"
            skyscanner = f"https://www.skyscanner.com/transport/flights/{orig.lower()}/{dest.lower()}/{dt.strftime('%Y%m%d')}/{rt.strftime('%Y%m%d')}/"
            momondo = f"https://www.momondo.com/flight-search/{orig}-{dest}/{gf_date}/{rt.strftime('%Y-%m-%d')}"
        except ValueError:
            kayak = f"https://www.kayak.com/flights/{orig}-{dest}/{kayak_date}"
            skyscanner = f"https://www.skyscanner.com/transport/flights/{orig.lower()}/{dest.lower()}/{dt.strftime('%Y%m%d')}/"
            momondo = f"https://www.momondo.com/flight-search/{orig}-{dest}/{gf_date}"
    else:
        kayak = f"https://www.kayak.com/flights/{orig}-{dest}/{kayak_date}"
        skyscanner = f"https://www.skyscanner.com/transport/flights/{orig.lower()}/{dest.lower()}/{dt.strftime('%Y%m%d')}/"
        momondo = f"https://www.momondo.com/flight-search/{orig}-{dest}/{gf_date}"

    lines = [
        f"**Flights {orig} → {dest}** | {date_str} | {trip_type}",
        "",
        f"- [Google Flights]({google})",
        f"- [Kayak]({kayak})",
        f"- [Skyscanner]({skyscanner})",
        f"- [Momondo]({momondo})",
        "",
        "I cannot fetch live prices — click a link above to see real-time fares and book.",
    ]
    return "\n".join(lines)
