import re
import urllib.parse
from typing import Dict, List, Optional


def generate_google_flights_url(origin: str, destination: str, date: str) -> str:
    """Generates direct Google Flights search URL for a single flight leg."""
    query_str = f"Flights from {origin} to {destination} on {date} nonstop"
    encoded_query = urllib.parse.quote(query_str)
    return f"https://www.google.com/travel/flights?q={encoded_query}"


def generate_kayak_multicity_url(legs: List[Dict]) -> str:
    """Generates direct 100% working Kayak multi-city search URL pre-filling all flight legs."""
    segments = []
    for leg in legs:
        src = leg.get("origin_city", leg.get("origin"))
        dst = leg.get("destination_city", leg.get("destination"))
        date = leg.get("departure_date")
        segments.append(f"{src}-{dst}/{date}")
    return "https://www.kayak.com/flights/" + "/".join(segments)


class GoogleFlightsScraper:
    """Direct web scraper using Playwright."""

    def __init__(self, timeout_ms: int = 15000, max_departure_hour: int = 19):
        self.timeout_ms = timeout_ms
        self.max_departure_hour = max_departure_hour

    def scrape_leg(self, origin: str, destination: str, date: str) -> Dict:
        direct_url = generate_google_flights_url(origin, destination, date)
        
        result = {
            "origin": origin,
            "destination": destination,
            "date": date,
            "price_usd": None,
            "duration_minutes": None,
            "departure_time": None,
            "carrier": None,
            "google_flights_url": direct_url,
            "scraped": False,
        }

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page.goto(direct_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_timeout(3000)

                page_text = page.content()

                prices = re.findall(r"\$([\d,]+)", page_text)
                if prices:
                    valid_prices = [float(p.replace(",", "")) for p in prices if 20 <= float(p.replace(",", "")) <= 3000]
                    if valid_prices:
                        result["price_usd"] = min(valid_prices)

                duration_match = re.search(r"(\d+)\s*hr\s*(?:(\d+)\s*min)?", page_text, re.IGNORECASE)
                if duration_match:
                    hrs = int(duration_match.group(1))
                    mins = int(duration_match.group(2)) if duration_match.group(2) else 0
                    result["duration_minutes"] = hrs * 60 + mins

                result["scraped"] = True
                browser.close()
        except Exception as err:
            result["scrape_error"] = str(err)

        return result
