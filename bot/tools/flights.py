from datetime import datetime
from urllib.parse import quote


def search_flights(origin: str, destination: str, date: str, return_date: str = "") -> str:
    """Build direct search links for cheapest flights between two airports.

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

    # Google Flights deep link
    # Format: /flights/search?tfs=CBwQARooEgoyMDI2LTA0LTEyagcIARIDQklPcgcIARIDTEVE
    # Easier to use the simple URL format
    gf_date = dt.strftime("%Y-%m-%d")
    google = f"https://www.google.com/travel/flights/search?tfs=CBwQARooagcIARID{orig}cgcIARID{dest}SAQwAQ&q=flights+{orig}+to+{dest}"

    # Kayak
    kayak_date = dt.strftime("%Y-%m-%d")
    if return_date:
        try:
            rt = datetime.strptime(return_date.strip(), "%Y-%m-%d")
            kayak_rt = rt.strftime("%Y-%m-%d")
            kayak = f"https://www.kayak.com/flights/{orig}-{dest}/{kayak_date}/{kayak_rt}"
        except ValueError:
            kayak = f"https://www.kayak.com/flights/{orig}-{dest}/{kayak_date}"
    else:
        kayak = f"https://www.kayak.com/flights/{orig}-{dest}/{kayak_date}"

    # Skyscanner
    sky_date = dt.strftime("%Y%m%d")
    if return_date:
        try:
            rt = datetime.strptime(return_date.strip(), "%Y-%m-%d")
            sky_rt = rt.strftime("%Y%m%d")
            skyscanner = f"https://www.skyscanner.com/transport/flights/{orig.lower()}/{dest.lower()}/{sky_date}/{sky_rt}/"
        except ValueError:
            skyscanner = f"https://www.skyscanner.com/transport/flights/{orig.lower()}/{dest.lower()}/{sky_date}/"
    else:
        skyscanner = f"https://www.skyscanner.com/transport/flights/{orig.lower()}/{dest.lower()}/{sky_date}/"

    # Momondo
    momondo = f"https://www.momondo.com/flight-search/{orig}-{dest}/{gf_date}"
    if return_date:
        try:
            rt = datetime.strptime(return_date.strip(), "%Y-%m-%d")
            momondo += f"/{rt.strftime('%Y-%m-%d')}"
        except ValueError:
            pass

    trip_type = "round trip" if return_date else "one way"
    lines = [
        f"**Flights {orig} → {dest}** | {dt.strftime('%d %b %Y')} | {trip_type}",
        "",
        f"- [Google Flights]({google})",
        f"- [Kayak]({kayak})",
        f"- [Skyscanner]({skyscanner})",
        f"- [Momondo]({momondo})",
        "",
        "Note: I cannot retrieve live prices directly — open the links to compare fares.",
    ]
    return "\n".join(lines)
