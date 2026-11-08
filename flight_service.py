from datetime import date, timedelta

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import OrdinalEncoder

from services.data_loader import (
    DATA, UNIVERSITIES, SENIORS, ROUTE_CITY,
    resolve, place_name, unknown_place_reply, term_start, next_term_start, money,
)


# =========================================================
# FARE DATA AND MODEL
# =========================================================

MODEL_FILE = DATA / "fare_model.joblib"
FARES = pd.read_csv(DATA / "flight_fares.csv", parse_dates=["departure_date"])

FEATURES = [
    "route_c", "airline_c", "budget_airline", "stops", "days_before_departure",
    "departure_month", "dep_dow", "days_to_term_start", "cohort_ntu_spots", "dep_doy",
]
WAIT_THRESHOLD = 0.03   # only say "wait" if the fare should drop by 3% or more
MAX_LEAD = 180          # the model was trained on bookings up to 180 days out


def _add_date_features(df):
    df["departure_month"] = df["departure_date"].dt.month
    df["dep_dow"] = df["departure_date"].dt.dayofweek
    df["dep_doy"] = df["departure_date"].dt.dayofyear
    return df


def _train():
    """Train the fare model once and save it to data/fare_model.joblib."""
    print("Training fare model (first run only, about 1 minute)...")
    df = _add_date_features(FARES.copy())
    enc = OrdinalEncoder()
    df[["route_c", "airline_c"]] = enc.fit_transform(df[["route", "airline"]])
    X = df[FEATURES].astype(float).to_numpy()
    y = df["price_sgd"].to_numpy()
    kw = dict(max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
              categorical_features=[0, 1], random_state=0)
    bundle = {
        "model": HistGradientBoostingRegressor(**kw).fit(X, np.log(y)),
        # 5th and 95th percentile models: a wider range than the notebook's 10th-90th
        "low": HistGradientBoostingRegressor(loss="quantile", quantile=0.05, **kw).fit(X, y),
        "high": HistGradientBoostingRegressor(loss="quantile", quantile=0.95, **kw).fit(X, y),
        "encoder": enc,
    }
    joblib.dump(bundle, MODEL_FILE)
    print("Fare model saved to", MODEL_FILE)
    return bundle


def _load():
    if MODEL_FILE.exists():
        try:
            return joblib.load(MODEL_FILE)
        except Exception as error:
            print("Could not load saved fare model, retraining:", error)
    return _train()


BUNDLE = _load()


# =========================================================
# TERM-START COHORTS (same logic as the notebook)
# =========================================================

def _term_events():
    rows = []
    for _, uni in UNIVERSITIES.iterrows():
        for year in range(2024, 2031):
            for sem, col in ((1, "ntu_spots_sem1"), (2, "ntu_spots_sem2")):
                start = term_start(uni, sem, year)
                if start:
                    rows.append((uni["route"], pd.Timestamp(start), int(uni[col])))
    ev = pd.DataFrame(rows, columns=["route", "start", "spots"])
    ev["week"] = ev["start"].dt.to_period("W")
    return ev.groupby(["route", "week"]).agg(start=("start", "min"), spots=("spots", "sum")).reset_index()


EVENTS = _term_events()


def _nearest_term(route, dep):
    ev = EVENTS[EVENTS["route"] == route]
    gap = (ev["start"] - dep).dt.days.to_numpy()
    i = int(np.argmin(np.abs(gap)))
    days = int(np.clip(gap[i], -60, 60))
    spots = int(ev["spots"].iloc[i]) if abs(gap[i]) <= 60 else 0
    return days, spots


# =========================================================
# PREDICTION
# =========================================================

def _airlines(route):
    """Airlines on a route with their budget flag and number of stops."""
    return (
        FARES[FARES["route"] == route]
        .groupby("airline")[["budget_airline", "stops"]]
        .first()
        .reset_index()
    )


def predict_curve(route, airline, budget, stops, departure):
    """Predicted fare (and range) for every booking day from 180 to 1 day out."""
    dep = pd.Timestamp(departure)
    leads = np.arange(1, MAX_LEAD + 1)
    days_to_term, spots = _nearest_term(route, dep)
    df = pd.DataFrame({
        "route": route, "airline": airline, "budget_airline": budget, "stops": stops,
        "days_before_departure": leads, "departure_date": dep,
        "days_to_term_start": days_to_term, "cohort_ntu_spots": spots,
    })
    df = _add_date_features(df)
    df[["route_c", "airline_c"]] = BUNDLE["encoder"].transform(df[["route", "airline"]])
    X = df[FEATURES].astype(float).to_numpy()
    return pd.DataFrame({
        "lead": leads,
        "fare": np.exp(BUNDLE["model"].predict(X)),
        "low": BUNDLE["low"].predict(X),
        "high": BUNDLE["high"].predict(X),
    }).set_index("lead")


def _pick_departure(result, place, today):
    """Turn the user's date or month into a departure date. Returns (date, note)."""
    if result.get("departure_date"):
        try:
            return date.fromisoformat(str(result["departure_date"])[:10]), None
        except ValueError:
            pass

    # "Semester 1" or "Semester 2" with no date: the next start of that semester
    semester = str(result.get("semester") or "")
    if semester in ("1", "2") and not result.get("month") and place["uni"] is not None:
        starts = [term_start(place["uni"], int(semester), y) for y in (today.year, today.year + 1)]
        starts = [s for s in starts if s and s > today]
        if starts:
            dep = starts[0] - timedelta(days=7)
            return dep, (f"I used Semester {semester} at {place['uni']['name']} (starting around "
                         f"{starts[0]:%d %b %Y}) and a flight on {dep:%d %b %Y}.")

    month = result.get("month")
    if month:
        month = int(month)
        year = today.year if month > today.month else today.year + 1
        # flying for a term that starts that month: arrive about a week early
        if place["uni"] is not None:
            for sem in (1, 2):
                start = term_start(place["uni"], sem, year)
                if start and start.month == month:
                    dep = start - timedelta(days=7)
                    return dep, f"I assumed you fly on {dep:%d %b %Y}, about a week before term starts."
        dep = date(year, month, 15)
        return dep, f"I assumed you fly mid-month, on {dep:%d %b %Y}."

    if place["uni"] is not None:
        start, sem = next_term_start(place["uni"], today)
        if start:
            dep = start - timedelta(days=7)
            return dep, (f"You didn't give a date, so I used the next term at {place['uni']['name']} "
                         f"(Semester {sem}, starting around {start:%d %b %Y}) and a flight on {dep:%d %b %Y}.")
    return None, None


def recommend_flight(result, user_type="student", today=None):
    """Best fare to book now, the book-now-or-wait advice and senior context."""
    today = today or date.today()
    place = resolve(result.get("destination"), result.get("university"),
                    result.get("city"), result.get("country"))
    if place is None:
        return {"error": unknown_place_reply()}

    dep, note = _pick_departure(result, place, today)
    if dep is None:
        return {"error": f"When do you plan to fly to {place_name(place)}? "
                         f"Give me a date or a month, e.g. \"3 January\"."}
    lead = (dep - today).days
    if lead < 1:
        return {"error": f"{dep:%d %b %Y} has already passed. Which date do you want to fly?"}

    route = place["route"]
    lead_now = min(lead, MAX_LEAD)
    options = []
    for _, a in _airlines(route).iterrows():
        curve = predict_curve(route, a["airline"], bool(a["budget_airline"]), int(a["stops"]), dep)
        now = curve.loc[lead_now]
        later = curve.loc[(curve.index < lead_now) & (curve.index >= 7)]
        options.append({
            "airline": a["airline"], "budget": bool(a["budget_airline"]), "stops": int(a["stops"]),
            "fare": now["fare"], "low": now["low"], "high": now["high"],
            "best_later": later["fare"].min() if len(later) else now["fare"],
            "best_later_lead": int(later["fare"].idxmin()) if len(later) else lead_now,
            "in_3_weeks": curve.loc[lead_now - 21, "fare"] if lead_now - 21 >= 1 else None,
            "two_weeks_out": curve.loc[14, "fare"],
        })
    options = sorted(options, key=lambda o: o["fare"])

    # wanted airline, if the user named one
    if result.get("airline"):
        named = [o for o in options if result["airline"].lower() in o["airline"].lower()]
        options = named + [o for o in options if o not in named] if named else options

    allowed = [o for o in options if not (user_type == "staff" and o["budget"])]
    pick = allowed[0]
    cheapest_budget = next((o for o in options if o["budget"]), None)

    return {
        "place": place, "route": route, "departure": dep, "lead": lead, "note": note,
        "pick": pick, "cheapest_budget": cheapest_budget, "user_type": user_type,
        "wait": pick["best_later"] < pick["fare"] * (1 - WAIT_THRESHOLD),
        "too_early": lead > MAX_LEAD,
    }


def _senior_flight_context(route, semester=None):
    s = SENIORS[SENIORS["route"] == route]
    if semester:
        s = s[s["exchange_period"] == f"Semester {semester}"]
    if len(s) < 5:
        return None
    early = s[s["booking_lead_days"] >= 56]["flight_cost_sgd"].median()
    late = s[s["booking_lead_days"] < 28]["flight_cost_sgd"].median()
    when = f" for Semester {semester}" if semester else ""
    line = (f"👥 {len(s)} past NTU students flew this route{when}. They booked a median of "
            f"{s['booking_lead_days'].median():.0f} days ahead.")
    if not np.isnan(early) and not np.isnan(late):
        line += f" Those who booked 8+ weeks ahead paid {money(early)}; under 4 weeks, {money(late)}."
    return line


def answer_flight_price(result, user_type="student"):
    r = recommend_flight(result, user_type)
    if "error" in r:
        return r["error"]

    p, dep, city = r["pick"], r["departure"], ROUTE_CITY[r["route"]]
    stops = "direct" if p["stops"] == 0 else f"{p['stops']} stop"
    where = place_name(r["place"])
    where = "" if where == city else f" ({where})"
    lines = [f"✈️ Singapore → {city}{where}, departing {dep:%a %d %b %Y}"]
    if r["note"]:
        lines.append(r["note"])
    lines.append("")

    if r["too_early"]:
        lines += [
            f"That's {r['lead']} days away, which is earlier than fares usually move.",
            f"Estimated return fare on {p['airline']} ({stops}): about {money(p['fare'])} "
            f"(likely {money(p['low'])}–{money(p['high'])}).",
            f"➡️ No rush. Check again around {dep - timedelta(days=84):%d %b %Y} (12 weeks before you fly).",
        ]
    else:
        lines.append(f"Best option now: {p['airline']} ({stops}), about {money(p['fare'])} return "
                     f"(likely {money(p['low'])}–{money(p['high'])}).")
        # only show "in 3 weeks" if that is still more than 2 weeks before the flight
        if p["in_3_weeks"] is not None and r["lead"] - 21 > 14:
            lines.append(f"In 3 weeks: about {money(p['in_3_weeks'])}")
        if r["lead"] > 14:
            lines.append(f"2 weeks before you fly: about {money(p['two_weeks_out'])}")
        if r["wait"]:
            wait_until = dep - timedelta(days=p["best_later_lead"])
            lines.append(f"➡️ WAIT: likely to drop to about {money(p['best_later'])} around {wait_until:%d %b}.")
        else:
            lines.append("➡️ BOOK NOW: it's not expected to get cheaper.")

    budget = r["cheapest_budget"]
    if r["user_type"] == "staff":
        lines.append("")
        lines.append("🏛️ Showing only flights you can claim as NTU staff: full-service airlines, "
                     "booked through an approved agent (CWT Singapore, BCD Travel or Flight Centre). "
                     "[Policy POL011, POL012]")
        if budget:
            lines.append(f"Budget fares from about {money(budget['fare'])} ({budget['airline']}) "
                         f"are hidden because NTU won't reimburse them.")
    elif p["budget"]:
        lines.append("")
        lines.append("ℹ️ This is a budget airline. NTU allows these for regional flights under 4 hours, "
                     "but check baggage and refund rules. [Policy POL008]")

    sem = None
    if r["place"]["uni"] is not None:
        for year in (dep.year, dep.year + 1):
            for s in (1, 2):
                start = term_start(r["place"]["uni"], s, year)
                if start and 0 <= (start - dep).days <= 30:
                    sem = s
    context = _senior_flight_context(r["route"], sem)
    if context:
        lines += ["", context]

    lines += ["", "Fares are estimates from our model on synthetic data."]
    return "\n".join(lines)


# =========================================================
# CHEAPEST DAY AND MONTH
# =========================================================

def _route_from(result):
    place = resolve(result.get("destination"), result.get("university"),
                    result.get("city"), result.get("country"))
    return place


def _typical(route, user_type):
    """Fares booked 4-13 weeks out, the window most people book in."""
    f = FARES[(FARES["route"] == route) & FARES["days_before_departure"].between(28, 90)]
    if user_type == "staff":
        f = f[~f["budget_airline"]]
    return f


def answer_cheapest_day(result, user_type="student"):
    place = _route_from(result)
    if place is None:
        return unknown_place_reply()
    f = _typical(place["route"], user_type)
    by_day = f.groupby(f["departure_date"].dt.day_name())["price_sgd"].median().sort_values()
    city = ROUTE_CITY[place["route"]]
    lines = [f"📅 Cheapest days to fly Singapore → {city}", ""]
    for i, (day, fare) in enumerate(by_day.items()):
        tag = " ← cheapest" if i == 0 else (" ← most expensive" if i == len(by_day) - 1 else "")
        lines.append(f"{day}: {money(fare)}{tag}")
    gap = by_day.iloc[-1] - by_day.iloc[0]
    lines += ["", f"Flying on a {by_day.index[0]} instead of a {by_day.index[-1]} saves about {money(gap)}.",
              "Median return fares booked 4–13 weeks ahead (synthetic data)."]
    return "\n".join(lines)


def answer_cheapest_month(result, user_type="student"):
    place = _route_from(result)
    if place is None:
        return unknown_place_reply()
    f = _typical(place["route"], user_type)
    by_month = f.groupby(f["departure_date"].dt.month)["price_sgd"].median()
    names = {m: date(2000, m, 1).strftime("%b") for m in range(1, 13)}
    order = by_month.sort_values()
    city = ROUTE_CITY[place["route"]]
    lines = [f"📅 Cheapest months to fly Singapore → {city}", ""]
    lines.append("Cheapest: " + ", ".join(f"{names[m]} ({money(v)})" for m, v in order.head(3).items()))
    lines.append("Most expensive: " + ", ".join(f"{names[m]} ({money(v)})" for m, v in order.tail(3)[::-1].items()))
    lines += ["", "Fares also rise in the 3 weeks before partner-university terms start, "
                  "when many exchange students fly.",
              "Median return fares booked 4–13 weeks ahead (synthetic data)."]
    return "\n".join(lines)
