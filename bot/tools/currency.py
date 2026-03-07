import httpx

def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount between currencies."""
    try:
        resp = httpx.get(
            f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}"
        ).json()
        rate = resp["rates"][to_currency.upper()]
        result = round(amount * rate, 2)
        return f"{amount} {from_currency.upper()} = {result} {to_currency.upper()}"
    except Exception as e:
        return f"Currency conversion unavailable: {e}"
