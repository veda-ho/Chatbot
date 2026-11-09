import pandas as pd

from services.data_loader import (
    SENIORS, UNIVERSITIES, COUNTRIES,
    resolve, place_name, unknown_place_reply, matches, split_count, money,
)


# =========================================================
# FIND THE RIGHT SENIORS
# =========================================================

def _seniors_for(result):
    """
    Seniors who went to the place the user asked about.
    Returns (rows, label, note). rows is None if the place isn't one of ours.
    """
    place = resolve(result.get("university"), result.get("destination"),
                    result.get("city"), result.get("country"))
    if place is None:
        return None, None, None

    note = None
    if place["uni"] is not None:
        rows = SENIORS[matches(SENIORS["partner_university_name"], place["uni"]["match_key"])]
        label = place["uni"]["name"]
        if rows.empty:
            # no seniors at this university: fall back to the country
            rows = SENIORS[SENIORS["destination_country"] == place["country"]]
            note = (f"We have no senior records for {label} yet, so this uses "
                    f"other NTU students in {place['country']}.")
            label = place["country"]
    elif place["city"]:
        rows = SENIORS[SENIORS["destination_city"] == place["city"]]
        label = place["city"]
        if rows.empty:
            rows = SENIORS[SENIORS["destination_country"] == place["country"]]
            label = place["country"]
    else:
        rows = SENIORS[SENIORS["destination_country"] == place["country"]]
        label = place["country"]

    if rows.empty:
        note = (f"We don't have any senior records for {place_name(place)} yet "
                f"(no NTU students in our data went there).")
    return rows, label, note


def _no_data(rows, label, note):
    if rows is None:
        return unknown_place_reply()
    if rows.empty:
        return note
    return None


def _header(emoji, title, rows, note):
    lines = [f"{emoji} {title}", f"Based on {len(rows)} past NTU exchange students."]
    if note:
        lines.append(note)
    lines.append("")
    return lines


# =========================================================
# ANSWERS
# =========================================================

def answer_experience(result, user_type="student"):
    rows, label, note = _seniors_for(result)
    missing = _no_data(rows, label, note)
    if missing:
        return missing

    recommend = (rows["would_recommend"] == "Yes").mean() * 100
    lines = _header("🎓", f"What seniors said about {label}", rows, note)
    lines += [
        f"⭐ Overall rating: {rows['overall_rating'].mean():.1f}/10",
        f"🛡️ Safety rating: {rows['safety_rating'].mean():.1f}/10",
        f"👍 Would recommend: {recommend:.0f}%",
        "",
        "Liked: " + "; ".join(split_count(rows["likes"], 3)),
        "Disliked: " + "; ".join(split_count(rows["dislikes"], 3)),
        "",
        "Top tips:",
    ]
    lines += [f"• {tip}" for tip in split_count(rows["tips"], 4)]
    return "\n".join(lines)


def answer_attractions(result, user_type="student"):
    rows, label, note = _seniors_for(result)
    missing = _no_data(rows, label, note)
    if missing:
        return missing

    lines = _header("📍", f"Places seniors visited near {label}", rows, note)
    lines.append("Most visited:")
    lines += [f"• {a}" for a in split_count(rows["attractions_visited"], 6)]
    lines += ["", "Popular activities:"]
    lines += [f"• {a}" for a in split_count(rows["activities_done"], 4)]
    lines += ["", f"Seniors spent a median of {money(rows['total_attractions_cost_sgd'].median())} "
                  f"on attractions over the whole exchange."]
    return "\n".join(lines)


def lower_first(text):
    """'Local student housing provider' -> 'local student housing provider' (keeps names like Airbnb)."""
    text = str(text)
    common = {"local", "housing", "university", "private", "student", "direct", "campus", "online"}
    first = text.split(" ")[0]
    return text[0].lower() + text[1:] if first.lower() in common else text


def answer_accommodation(result, user_type="student"):
    rows, label, note = _seniors_for(result)
    missing = _no_data(rows, label, note)
    if missing:
        return missing

    stays = (
        rows.groupby("accommodation_used")
        .agg(students=("experience_id", "count"),
             city=("destination_city", "first"),
             type=("accommodation_type", "first"),
             platform=("accommodation_booking_platform", "first"),
             cost=("accommodation_cost_sgd", "median"),
             rating=("accommodation_rating", "mean"),
             safety=("safety_rating", "mean"))
        .reset_index()
    )
    # rank by rating and safety; places only one senior used count for less
    stays["score"] = stays["rating"] + stays["safety"] - (stays["students"] < 2) * 2
    top = stays.sort_values(["score", "students"], ascending=False).head(3)

    lines = _header("🏠", f"Where seniors stayed near {label}", rows, note)
    for i, s in enumerate(top.itertuples(), 1):
        lines += [
            f"{i}. {s.accommodation_used}",
            f"📍 {s.city} · {s.type}",
            f"⭐ {s.rating:.1f}/10 · 🛡️ Safety {s.safety:.1f}/10 · "
            f"{s.students} senior{'s' if s.students > 1 else ''}",
            f"💰 About {money(s.cost)} for the stay · booked via {lower_first(s.platform)}",
            "",
        ]
    # different campuses in different cities (e.g. Aalto in Espoo and Mikkeli)
    if top["city"].nunique() > 1:
        lines.append("Note: these are in different cities. Pick the one near your campus.")
        lines.append("")
    lines += ["Book through the university or a verified platform, and check safety ratings. [Policy POL010]"]
    if user_type == "staff":
        lines.append("🏛️ These are where past students stayed. For your claim, book your hotel on "
                     "Trip.com, NTU's travel partner. [Policy POL012]")
    return "\n".join(lines)


def answer_cost(result, user_type="student"):
    rows, label, note = _seniors_for(result)
    missing = _no_data(rows, label, note)
    if missing:
        return missing

    m = rows.median(numeric_only=True)
    lines = _header("💰", f"Cost of exchange at {label}", rows, note)
    lines += [
        f"Total for the exchange: about {money(m['total_estimated_spending_sgd'])} "
        f"(median, {m['exchange_months']:.0f}-month stay)",
        "",
        f"🏠 Accommodation (whole stay): {money(m['accommodation_cost_sgd'])}",
        f"✈️ Return flight: {money(m['flight_cost_sgd'])}",
        f"🍜 Food: {money(m['monthly_food_cost_sgd'])} a month",
        f"🚌 Transport: {money(m['monthly_transport_cost_sgd'])} a month",
        f"📍 Attractions (whole stay): {money(m['total_attractions_cost_sgd'])}",
    ]
    low, high = rows["total_estimated_spending_sgd"].quantile([0.25, 0.75])
    lines += ["", f"Most seniors spent between {money(low)} and {money(high)}."]
    return "\n".join(lines)


def answer_comparison(result, user_type="student"):
    # Gemini should give a list; fall back to any of our countries named anywhere
    names = result.get("countries") or []
    if isinstance(names, str):
        names = [names]
    places = []
    for name in names:
        p = resolve(name)
        if p and p["country"] not in [q["country"] for q in places]:
            places.append(p)
    if len(places) < 2:
        return ("Which destinations should I compare? Name two or more of: "
                + ", ".join(COUNTRIES) + ". For example: \"Hungary or Luxembourg for exchange?\"")

    lines = ["⚖️ Comparing destinations (medians from past NTU students)", ""]
    for p in places:
        country = p["country"]
        rows = SENIORS[SENIORS["destination_country"] == country]
        unis = UNIVERSITIES[UNIVERSITIES["country"] == country]
        spots = int(unis["ntu_spots_sem1"].sum() + unis["ntu_spots_sem2"].sum())
        lines.append(f"{country} ({spots} GEM spots a year: {', '.join(unis['name'])})")
        if rows.empty:
            lines.append("   No senior records yet.")
        else:
            m = rows.median(numeric_only=True)
            lines += [
                f"   Total cost {money(m['total_estimated_spending_sgd'])} · "
                f"flight {money(m['flight_cost_sgd'])}",
                f"   Overall {rows['overall_rating'].mean():.1f}/10 · safety {rows['safety_rating'].mean():.1f}/10 · "
                f"{(rows['would_recommend'] == 'Yes').mean() * 100:.0f}% would recommend "
                f"({len(rows)} students)",
                f"   Liked: {'; '.join(split_count(rows['likes'], 2))}",
            ]
        lines.append("")
    lines.append("Ask about any one of them for housing, attractions or costs.")
    return "\n".join(lines)
