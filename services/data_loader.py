import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd


# =========================================================
# FILE LOCATIONS
# =========================================================

DATA = Path(__file__).resolve().parent.parent / "data"

UNIVERSITIES = pd.read_csv(DATA / "universities.csv").fillna("")
SENIORS = pd.read_csv(DATA / "seniors.csv")
ELIGIBILITY = pd.read_csv(DATA / "eligibility.csv")
MODULES = pd.read_csv(DATA / "modules.csv")
POLICIES = pd.read_csv(DATA / "ntu_travel_policies.csv")
STAFF_TRIPS = pd.read_csv(DATA / "staff_trips.csv")
CLAIM_LIMITS = pd.read_csv(DATA / "staff_claim_limits.csv")


# =========================================================
# CITIES AND COUNTRIES WE COVER
# =========================================================

# city or nickname -> (city, country, flight route)
CITIES = {
    "helsinki": ("Helsinki", "Finland", "SIN-HEL"),
    "espoo": ("Espoo", "Finland", "SIN-HEL"),
    "otaniemi": ("Espoo", "Finland", "SIN-HEL"),
    "mikkeli": ("Mikkeli", "Finland", "SIN-HEL"),
    "budapest": ("Budapest", "Hungary", "SIN-BUD"),
    "eschsuralzette": ("Esch-sur-Alzette", "Luxembourg", "SIN-LUX"),
    "belval": ("Esch-sur-Alzette", "Luxembourg", "SIN-LUX"),
    "zagreb": ("Zagreb", "Croatia", "SIN-ZAG"),
    "hanoi": ("Hanoi", "Vietnam", "SIN-HAN"),
    "hochiminh": ("Ho Chi Minh City", "Vietnam", "SIN-SGN"),
    "saigon": ("Ho Chi Minh City", "Vietnam", "SIN-SGN"),
    "bandarseribegawan": ("Bandar Seri Begawan", "Brunei", "SIN-BWN"),
    "gadong": ("Bandar Seri Begawan", "Brunei", "SIN-BWN"),
    "yogyakarta": ("Yogyakarta", "Indonesia", "SIN-YIA"),
    "jogja": ("Yogyakarta", "Indonesia", "SIN-YIA"),
    "jakarta": ("Jakarta", "Indonesia", "SIN-CGK"),
    "depok": ("Jakarta", "Indonesia", "SIN-CGK"),
    "bandung": ("Bandung", "Indonesia", "SIN-CGK"),
    "luxembourgcity": ("Luxembourg City", "Luxembourg", "SIN-LUX"),
    "kirchberg": ("Luxembourg City", "Luxembourg", "SIN-LUX"),
}

# country -> main flight route
COUNTRIES = {
    "Finland": "SIN-HEL",
    "Hungary": "SIN-BUD",
    "Luxembourg": "SIN-LUX",
    "Croatia": "SIN-ZAG",
    "Vietnam": "SIN-HAN",
    "Brunei": "SIN-BWN",
    "Indonesia": "SIN-CGK",
}

ROUTE_CITY = {
    "SIN-HEL": "Helsinki", "SIN-BUD": "Budapest", "SIN-LUX": "Luxembourg",
    "SIN-ZAG": "Zagreb", "SIN-HAN": "Hanoi", "SIN-SGN": "Ho Chi Minh City",
    "SIN-BWN": "Bandar Seri Begawan", "SIN-YIA": "Yogyakarta", "SIN-CGK": "Jakarta",
}


# =========================================================
# TEXT HELPERS
# =========================================================

def norm(text):
    """Lowercase, remove accents and anything that isn't a letter or number."""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def matches(series, key):
    """True for rows whose text contains the university's match key."""
    return series.map(norm).str.contains(key, regex=False)


def split_count(series, top=5):
    """Count items in 'a; b; c' columns and return the most common ones."""
    items = (
        series.dropna()
        .str.split(";")
        .explode()
        .str.strip()
    )
    items = items[items != ""]
    return items.value_counts().head(top).index.tolist()


def money(value):
    return f"S${value:,.0f}"


# =========================================================
# FIND THE DESTINATION THE USER MEANS
# =========================================================

def resolve(*texts):
    """
    Work out which university, city or country the user means.

    Returns a dict with keys: uni (row or None), city, country, route.
    Returns None if nothing matches one of our 7 countries.
    """
    joined = " ".join(str(t) for t in texts if t)
    text = norm(joined)
    if not text:
        return None

    # 1. A university name or nickname (most specific)
    best, best_len = None, 0
    for _, row in UNIVERSITIES.iterrows():
        for alias in row["aliases"].split(";"):
            a = norm(alias)
            # short nicknames like "uh" or "itb" must match the whole word
            if len(a) <= 4:
                words = {norm(w) for w in re.split(r"\W+", joined)}
                hit = a in words
            else:
                hit = a in text
            if hit and len(a) > best_len:
                best, best_len = row, len(a)
    if best is not None:
        return {"uni": best, "city": best["city"], "country": best["country"], "route": best["route"]}

    # 2. A city
    for key, (city, country, route) in CITIES.items():
        if key in text:
            return {"uni": None, "city": city, "country": country, "route": route}

    # 3. A country (Luxembourg and Brunei have one university each)
    for country, route in COUNTRIES.items():
        if norm(country) in text:
            unis = UNIVERSITIES[UNIVERSITIES["country"] == country]
            uni = unis.iloc[0] if len(unis) == 1 else None
            return {"uni": uni, "city": None, "country": country, "route": route}

    return None


def place_name(place):
    if place["uni"] is not None:
        return place["uni"]["name"]
    return place["city"] or place["country"]


def unknown_place_reply():
    return (
        "I can help with our 7 exchange destinations: Finland, Hungary, Luxembourg, "
        "Croatia, Vietnam, Brunei and Indonesia.\n\n"
        "Try naming a university or city, e.g. \"Aalto\", \"Hanoi\" or \"ELTE in Budapest\"."
    )


# =========================================================
# DATES
# =========================================================

def term_start(uni, semester, year):
    """Approximate start of teaching for 'Semester 1' or 'Semester 2'."""
    mmdd = uni["sem1_start"] if semester == 1 else uni["sem2_start"]
    if not mmdd:
        return None
    return date.fromisoformat(f"{year}-{mmdd}")


def next_term_start(uni, today=None):
    """The next term start after today, as (date, semester number)."""
    today = today or date.today()
    options = []
    for year in (today.year, today.year + 1):
        for sem in (1, 2):
            start = term_start(uni, sem, year)
            if start and start > today:
                options.append((start, sem))
    return min(options) if options else (None, None)


def policies_for(user_type):
    """Policy rows that apply to students or to staff."""
    who = POLICIES["applicable_to"].str.lower()
    if user_type == "staff":
        return POLICIES[who.str.contains("staff")]
    return POLICIES[~who.str.contains("staff")]


def claim_limits_for(city=None, country=None):
    """NTU's hotel limit and daily allowance for a city (or the country's first city)."""
    rows = CLAIM_LIMITS[CLAIM_LIMITS["city"] == city]
    if rows.empty and country:
        rows = CLAIM_LIMITS[CLAIM_LIMITS["country"] == country]
    return rows.iloc[0] if len(rows) else None


def claim_line(limit):
    if limit is None:
        return None
    return (f"🏛️ NTU limits in {limit['city']}: hotel up to {money(limit['hotel_cap_sgd_per_night'])} a night, "
            f"daily allowance {money(limit['daily_allowance_sgd'])}. [Policy POL013, POL014]")
