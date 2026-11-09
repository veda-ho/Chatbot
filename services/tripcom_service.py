"""
"Book on Trip.com" buttons.

NTU pays Trip.com for this chatbot, so after the bot gives its advice, the
user can jump straight to Trip.com with the search already filled in
(route and dates for flights, city and dates for hotels).

The buttons go through our own /go page first, which writes a line to the
logs and then sends the user on to Trip.com. That way we can count how many
people the bot sends to Trip.com.
"""
from datetime import date, timedelta
from urllib.parse import quote

from services.data_loader import resolve, ROUTE_CITY


SITE = "https://sg.trip.com"   # Singapore site, prices in S$

# Trip.com city codes for our routes (Jakarta and Yogyakarta use city codes, not airport codes)
FLIGHT_CITY = {
    "SIN-HEL": "hel", "SIN-BUD": "bud", "SIN-LUX": "lux", "SIN-ZAG": "zag",
    "SIN-HAN": "han", "SIN-SGN": "sgn", "SIN-BWN": "bwn", "SIN-YIA": "jog", "SIN-CGK": "jkt",
}

# Trip.com hotel city ids, taken from Trip.com's own hotel list pages
HOTEL_CITY = {
    "Helsinki": ("helsinki", 277), "Espoo": ("espoo", 38173), "Tampere": ("tampere", 1796),
    "Mikkeli": ("mikkeli", 7467), "Budapest": ("budapest", 637),
    "Luxembourg City": ("luxembourg", 665), "Luxembourg": ("luxembourg", 665),
    "Esch-sur-Alzette": ("esch-sur-alzette", 38996), "Zagreb": ("zagreb", 1418),
    "Hanoi": ("hanoi", 286), "Ho Chi Minh City": ("ho-chi-minh-city", 301),
    "Bandar Seri Begawan": ("bandar-seri-begawan", 4048), "Yogyakarta": ("yogyakarta", 741),
    "Jakarta": ("jakarta", 524), "Depok": ("depok", 77066), "Bandung": ("bandung", 740),
}

STUDENT_STAY_DAYS = 140   # about one semester, used as the return date for students
STAFF_NIGHTS = 4          # usual length of an NTU staff trip


# =========================================================
# LINKS
# =========================================================

def flight_link(route, departure=None, return_date=None):
    """Trip.com flight search from Singapore, with dates if we know them."""
    code = FLIGHT_CITY.get(route)
    if code is None:
        return None
    if departure is None:
        return f"{SITE}/flights/showfarefirst?dcity=sin&acity={code}&class=y&quantity=1&locale=en-SG&curr=SGD"
    url = (f"{SITE}/flights/showfarefirst?dcity=sin&acity={code}&ddate={departure:%Y-%m-%d}"
           f"&class=y&quantity=1&locale=en-SG&curr=SGD")
    if return_date:
        return url + f"&rdate={return_date:%Y-%m-%d}&triptype=rt"
    return url + "&triptype=ow"


def hotel_link(city, checkin=None, nights=None):
    """Trip.com hotel list for a city, with dates if we know them."""
    if city not in HOTEL_CITY:
        return None
    slug, city_id = HOTEL_CITY[city]
    if checkin is None:
        return f"{SITE}/hotels/{slug}-hotels-list-{city_id}/"
    checkout = checkin + timedelta(days=nights or 1)
    return (f"{SITE}/hotels/list?city={city_id}&checkin={checkin:%Y/%m/%d}"
            f"&checkout={checkout:%Y/%m/%d}&adult=1&crn=1&curr=SGD&locale=en-SG")


def tracked(url, kind):
    """Send the click through our /go page so it's counted, then on to Trip.com."""
    return f"/go?kind={kind}&to={quote(url, safe='')}"


def is_tripcom(url):
    """Only ever send people on to Trip.com (stops /go being used for other sites)."""
    from urllib.parse import urlparse
    parts = urlparse(url)
    host = parts.hostname or ""
    return parts.scheme == "https" and (host == "trip.com" or host.endswith(".trip.com"))


# =========================================================
# WHICH BUTTONS GO UNDER AN ANSWER
# =========================================================

def _date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _nights(result):
    try:
        n = int(float(result.get("nights")))
        return n if 1 <= n <= 60 else STAFF_NIGHTS
    except (TypeError, ValueError):
        return STAFF_NIGHTS


def _flight_button(result, user_type):
    from services import flight_service   # imported here to avoid a loop at start-up

    r = flight_service.recommend_flight(result, user_type)
    if "error" in r:
        place = resolve(result.get("destination"), result.get("university"),
                        result.get("city"), result.get("country"))
        if place is None:
            return None
        url = flight_link(place["route"])
    else:
        dep = r["departure"]
        back = dep + timedelta(days=_nights(result) if user_type == "staff" else STUDENT_STAY_DAYS)
        url = flight_link(r["route"], dep, back)
    if url is None:
        return None
    return {"label": "✈️ Search this flight on Trip.com", "href": tracked(url, "flight")}


def _hotel_button(result, user_type):
    place = resolve(result.get("university"), result.get("destination"),
                    result.get("city"), result.get("country"))
    if place is None:
        return None
    city = place["city"] or ROUTE_CITY.get(place["route"])
    if user_type == "staff":
        # same city as the staff hotel list (e.g. Jakarta for University of Indonesia)
        from services import staff_service
        rows, _, _ = staff_service._staff_trips_for(result)
        if rows is not None and len(rows):
            city = staff_service._main_city(rows, place)
    checkin = _date(result.get("departure_date")) if user_type == "staff" else None
    url = hotel_link(city, checkin, _nights(result))
    if url is None:
        return None
    return {"label": f"🏨 Hotels in {city} on Trip.com", "href": tracked(url, "hotel")}


def buttons_for(intent, result, user_type="student"):
    """Trip.com buttons for one answered question (can be empty)."""
    makers = []
    if intent in ("flight_price", "cheapest_flight_day", "cheapest_flight_month"):
        makers = [_flight_button]
    elif intent == "senior_accommodation":
        makers = [_hotel_button]
    elif intent == "senior_cost" and user_type == "staff":
        makers = [_flight_button, _hotel_button]

    buttons = []
    for make in makers:
        try:
            b = make(result, user_type)
        except Exception as error:      # a button must never break the answer
            print("Trip.com button error:", error)
            b = None
        if b:
            buttons.append(b)
    return buttons
