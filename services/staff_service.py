"""
Answers for NTU staff and faculty (Staff / Faculty on the home page).

Staff trips are short work trips, so these answers use past NTU staff trips
(data/staff_trips.csv) and NTU's claim limits (data/staff_claim_limits.csv)
instead of student exchange records.
"""
from datetime import date

import numpy as np

from services.data_loader import (
    STAFF_TRIPS, SENIORS,
    resolve, unknown_place_reply, matches, split_count, money,
    claim_limits_for, claim_line,
)
from services import flight_service, senior_service


BOOKING_PARTNER = "Trip.com, NTU's travel partner"


# =========================================================
# FIND THE RIGHT STAFF TRIPS
# =========================================================

def _staff_trips_for(result):
    """Past staff trips for the place asked about. Returns (rows, label, place)."""
    place = resolve(result.get("university"), result.get("destination"),
                    result.get("city"), result.get("country"))
    if place is None:
        return None, None, None

    if place["uni"] is not None:
        rows = STAFF_TRIPS[matches(STAFF_TRIPS["partner_university"], place["uni"]["match_key"])]
        label = place["uni"]["name"]
    elif place["city"]:
        rows = STAFF_TRIPS[STAFF_TRIPS["destination_city"] == place["city"]]
        label = place["city"]
    else:
        rows = STAFF_TRIPS[STAFF_TRIPS["destination_country"] == place["country"]]
        label = place["country"]

    if rows.empty:
        rows = STAFF_TRIPS[STAFF_TRIPS["destination_country"] == place["country"]]
        label = place["country"]

    return rows, label, place


def _main_city(rows, place):
    """The city most staff stayed in for this place."""
    if len(rows):
        return rows["destination_city"].mode().iloc[0]
    return place["city"]


# =========================================================
# WHERE CAN I STAY (hotels within NTU's limit)
# =========================================================

def answer_stay(result, user_type="staff"):
    rows, label, place = _staff_trips_for(result)
    if rows is None:
        return unknown_place_reply()
    if rows.empty:
        return f"We don't have any past NTU staff trips to {label} yet."

    hotels = (
        rows.groupby("hotel_name")
        .agg(trips=("trip_id", "count"),
             city=("destination_city", "first"),
             area=("hotel_area", "first"),
             stars=("hotel_stars", "first"),
             rate=("nightly_rate_sgd", "median"),
             cap=("hotel_cap_sgd", "first"),
             rating=("hotel_rating", "mean"),
             safety=("safety_rating", "mean"),
             km=("distance_to_partner_km", "first"),
             partner=("partner_university", "first"))
        .reset_index()
    )
    hotels["within"] = hotels["rate"] <= hotels["cap"]
    within = hotels[hotels["within"]].sort_values(["rating", "trips"], ascending=False).head(3)
    over = hotels[~hotels["within"]].sort_values("trips", ascending=False).head(1)

    lines = [f"🏨 Hotels NTU staff used near {label}",
             f"Based on {len(rows)} past NTU staff trips.", ""]

    for city in within["city"].unique():
        line = claim_line(claim_limits_for(city, place["country"]))
        if line:
            lines.append(line)
    lines.append("")

    for i, h in enumerate(within.itertuples(), 1):
        lines += [
            f"{i}. {h.hotel_name} ({h.stars}★)",
            f"📍 {h.area}, {h.city} · {h.km:g} km from {h.partner}",
            f"⭐ {h.rating:.1f}/10 · 🛡️ Safety {h.safety:.1f}/10 · {h.trips} staff trip{'s' if h.trips > 1 else ''}",
            f"💰 About {money(h.rate)} a night ✅ within the {money(h.cap)} limit",
            "",
        ]

    for h in over.itertuples():
        lines += [f"⚠️ Over the limit: {h.hotel_name} is about {money(h.rate)} a night "
                  f"(limit {money(h.cap)}). You'd pay the difference yourself.", ""]

    lines.append(f"Book on {BOOKING_PARTNER}, so it can be claimed. [Policy POL012]")
    return "\n".join(lines)


# =========================================================
# IS IT SAFE / WHAT DID STAFF SAY
# =========================================================

def answer_experience(result, user_type="staff"):
    rows, label, place = _staff_trips_for(result)
    if rows is None:
        return unknown_place_reply()
    if rows.empty:
        return f"We don't have any past NTU staff trips to {label} yet."

    lines = [f"🏛️ What NTU staff said about {label}",
             f"Based on {len(rows)} past NTU staff trips.", "",
             f"⭐ Overall rating: {rows['overall_rating'].mean():.1f}/10",
             f"🛡️ Safety rating: {rows['safety_rating'].mean():.1f}/10",
             f"🏨 Hotel rating: {rows['hotel_rating'].mean():.1f}/10",
             "",
             "Tips from staff:"]
    lines += [f"• {t}" for t in split_count(rows["tips"], 4)]
    lines += ["", "Watch out for:"]
    lines += [f"• {t}" for t in split_count(rows["issues"], 2)]

    # students who lived there for months, as a second opinion on safety
    seniors = SENIORS[SENIORS["destination_country"] == place["country"]]
    if place["city"]:
        in_city = SENIORS[SENIORS["destination_city"] == place["city"]]
        seniors = in_city if len(in_city) else seniors
    if len(seniors):
        lines += ["", f"NTU students who lived there rated safety {seniors['safety_rating'].mean():.1f}/10 "
                      f"({len(seniors)} students)."]
    return "\n".join(lines)


# =========================================================
# HOW MUCH WILL THE TRIP COST / HOW MUCH CAN I CLAIM
# =========================================================

def _nights(result, rows):
    try:
        n = int(float(result.get("nights")))
        if 1 <= n <= 60:
            return n, True
    except (TypeError, ValueError):
        pass
    return int(rows["nights"].median()) if len(rows) else 4, False


def _flight_estimate(result, place):
    """Full-service fare: the model's estimate if we know the date, else a typical fare."""
    if result.get("departure_date") or result.get("month") or result.get("semester"):
        r = flight_service.recommend_flight(result, "staff")
        if "error" not in r:
            return r["pick"]["fare"], f"{r['pick']['airline']}, departing {r['departure']:%d %b %Y}"
    fares = flight_service.FARES
    typical = fares[(fares["route"] == place["route"]) & (~fares["budget_airline"])
                    & fares["days_before_departure"].between(28, 90)]["price_sgd"].median()
    return typical, "typical full-service fare booked 4–13 weeks ahead"


def answer_cost(result, user_type="staff"):
    rows, label, place = _staff_trips_for(result)
    if rows is None:
        return unknown_place_reply()

    city = _main_city(rows, place)
    limit = claim_limits_for(city, place["country"])
    nights, given = _nights(result, rows)

    in_city = rows[rows["destination_city"] == city]
    ok_rates = in_city[in_city["within_hotel_cap"] == "Yes"]["nightly_rate_sgd"]
    hotel_rate = ok_rates.median() if len(ok_rates) else limit["hotel_cap_sgd_per_night"]
    allowance = limit["daily_allowance_sgd"]
    flight, flight_note = _flight_estimate(result, place)

    hotel_total = hotel_rate * nights
    allowance_total = allowance * (nights + 1)
    total = flight + hotel_total + allowance_total

    lines = [f"💼 Trip budget: {city}, {nights} night{'s' if nights > 1 else ''}", ""]
    if not given:
        lines += [f"(I used {nights} nights, the usual length of NTU staff trips here. "
                  f"Tell me your number of nights for an exact estimate.)", ""]
    lines += [
        f"✈️ Return flight: about {money(flight)}",
        f"   {flight_note}",
        f"🏨 Hotel: {nights} × {money(hotel_rate)} = {money(hotel_total)}",
        f"   NTU limit: {money(limit['hotel_cap_sgd_per_night'])} a night",
        f"🍽️ Daily allowance: {nights + 1} days × {money(allowance)} = {money(allowance_total)}",
        "",
        f"💰 Total you can claim: about {money(total)}",
    ]
    if len(rows):
        lines += ["", f"Past NTU staff trips to {label} claimed a median of {money(rows['total_claim_sgd'].median())} "
                      f"for {int(rows['nights'].median())} nights ({len(rows)} trips)."]
    lines += ["", "Claims follow NTU staff travel policy. [Policy POL011–POL014]"]
    return "\n".join(lines)


# =========================================================
# WHAT TO DO IN FREE TIME (from students who lived there)
# =========================================================

def answer_attractions(result, user_type="staff"):
    reply = senior_service.answer_attractions(result, user_type)
    reply = reply.replace("📍 Places seniors visited near",
                          "📍 For free time between meetings: places NTU students who lived there recommend near", 1)
    # the students' whole-exchange spending isn't relevant to a short work trip
    return "\n".join(line for line in reply.split("\n") if not line.startswith("Seniors spent")).rstrip()


# =========================================================
# FLIGHT EXTRAS FOR STAFF
# =========================================================

def flight_context(route, city, country):
    """Lines added to a staff flight answer: past staff trips and claim limits."""
    lines = []
    rows = STAFF_TRIPS[STAFF_TRIPS["route"] == route]
    if len(rows) >= 3:
        lines.append(f"👥 {len(rows)} past NTU staff trips on this route: median fare "
                     f"{money(rows['flight_cost_sgd'].median())}, booked a median of "
                     f"{rows['booking_lead_days'].median():.0f} days ahead.")
    line = claim_line(claim_limits_for(city, country))
    if line:
        lines.append(line)
    return lines
