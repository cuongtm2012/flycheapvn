"""Flight API source adapters."""

from .kiwi import KiwiSource
from .fly_scraper import FlyScraperSource
from .amadeus import AmadeusSource
from .skyscanner import SkyscannerSource
from .aviasales import AviasalesSource
from .serpapi import SerpAPISource
from .google_flights_scraper import GoogleFlightsScraper

__all__ = [
    "KiwiSource",
    "FlyScraperSource",
    "AmadeusSource",
    "SkyscannerSource",
    "AviasalesSource",
    "SerpAPISource",
    "GoogleFlightsScraper",
]
