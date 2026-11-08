from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    redirect,
    url_for
)

from services.weather_service import (
    get_weather,
    get_historical_weather
)

from services.chat_service import (
    understand_message
)

from services import (
    flight_service,
    senior_service,
    eligibility_service
)

from services.data_loader import (
    resolve,
    ROUTE_CITY
)


app = Flask(__name__)


# Which function answers each intent (weather is handled below)
HANDLERS = {
    "flight_price": flight_service.answer_flight_price,
    "cheapest_flight_day": flight_service.answer_cheapest_day,
    "cheapest_flight_month": flight_service.answer_cheapest_month,
    "senior_experience": senior_service.answer_experience,
    "senior_attractions": senior_service.answer_attractions,
    "senior_accommodation": senior_service.answer_accommodation,
    "senior_cost": senior_service.answer_cost,
    "country_comparison": senior_service.answer_comparison,
    "eligibility": eligibility_service.answer_eligibility,
    "modules": eligibility_service.answer_modules,
}


MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


# =========================================================
# CONVERSATION MEMORY
# The browser sends back what we remembered last time, so a
# follow-up like "Which modules can I take?" still knows the
# university from an earlier message.
# =========================================================

PLACE_KEYS = [
    "university", "destination", "city", "country", "countries"
]

MEMORY_KEYS = PLACE_KEYS + [
    "month", "departure_date", "school", "cgpa", "semester"
]


def remember(result, context):

    context = context or {}

    # The user named a new place: forget the old one
    if any(result.get(k) for k in PLACE_KEYS):

        context = {
            k: v for k, v in context.items()
            if k not in PLACE_KEYS
        }


    # New details win; missing ones come from memory
    merged = dict(result)

    for key in MEMORY_KEYS:

        if merged.get(key) in (None, "", []):

            if context.get(key) not in (None, "", []):

                merged[key] = context[key]


    # Tidy the month so the weather code always gets a number
    try:

        if merged.get("month") is not None:

            month = str(merged["month"]).strip().lower()

            # accept "1", 1, "January" or "jan"
            merged["month"] = next(
                (n for n, name in MONTH_NAMES.items()
                 if name.lower().startswith(month[:3])),
                None
            ) if not month.isdigit() else int(month)

            merged["month_name"] = MONTH_NAMES[merged["month"]]

    except (ValueError, KeyError):

        merged["month"] = None


    new_context = {
        k: merged[k] for k in MEMORY_KEYS
        if merged.get(k) not in (None, "", [])
    }

    return merged, new_context


def weather_city(result):
    """The city to look up weather for, even if the user named a university."""

    if result.get("city"):

        return result["city"]


    place = resolve(
        result.get("destination"),
        result.get("university"),
        result.get("country")
    )

    if place:

        return place["city"] or ROUTE_CITY[place["route"]]


    return (
        result.get("destination")
        or result.get("country")
    )


# =========================================================
# HOME PAGE: choose Student or Staff / Faculty
# =========================================================

@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# =========================================================
# CHAT PAGE: /student or /staff
# =========================================================

@app.route("/<role>")
def chat_page(role):

    # Anything other than student or staff goes back home
    if role not in ("student", "staff"):

        return redirect(
            url_for("home")
        )


    return render_template(
        "index.html",
        role=role
    )


# =========================================================
# CHATBOT
# =========================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    # -----------------------------------
    # Get user's message
    # -----------------------------------

    data = request.get_json()


    if (
        not data
        or "message" not in data
    ):

        return jsonify({
            "reply":
                "Please enter a message."
        }), 400


    user_message = (
        data["message"]
    )


    # "student" or "staff", chosen on the home page
    user_type = (
        "staff" if data.get("user_type") == "staff"
        else "student"
    )


    # Everything said so far in this sitting
    history = data.get("history") or []


    # -----------------------------------
    # Understand user's request
    # (Gemini also sees the conversation so far)
    # -----------------------------------

    result = understand_message(
        user_message,
        history
    )


    old_context = data.get("context") or {}

    # Did this message give a new detail (date, cGPA, school, place...)?
    gave_detail = any(
        result.get(key) not in (None, "", [])
        for key in MEMORY_KEYS
    )


    # Did this message itself name a place? (used for the "Got it" reply)
    named_place = any(
        result.get(key) not in (None, "", [])
        for key in PLACE_KEYS
    )


    result, context = remember(
        result,
        old_context
    )

    result["named_place"] = named_place


    # A reply like "12 jan" or "3.4" on its own has no question in it.
    # If the bot just asked for that detail, carry on with the last question.
    if (
        result.get("intent") == "unknown"
        and gave_detail
        and old_context.get("last_intent")
    ):

        result["intent"] = old_context["last_intent"]

        result["intents"] = [old_context["last_intent"]]


    # -----------------------------------
    # Answer every question in the message
    # e.g. "Where should I stay and how much does it cost?"
    # -----------------------------------

    intents = (
        result.get("intents")
        or [result.get("intent", "unknown")]
    )

    replies = []

    for intent in intents:

        try:

            replies.append(
                answer(
                    dict(result, intent=intent),
                    user_type
                )
            )

        except Exception as error:

            print(
                f"Error answering {intent}:",
                error
            )

            replies.append(
                "Sorry, something went wrong while I was looking that up. "
                "Please try asking in a different way."
            )


    reply = "\n\n━━━━━━━━━━━━━━━━\n\n".join(
        replies
    )


    # Remember the last real question for the next message
    answered = [i for i in intents if i != "unknown"]

    if answered:

        context["last_intent"] = answered[-1]

    elif old_context.get("last_intent"):

        context["last_intent"] = old_context["last_intent"]


    return jsonify({
        "reply": reply,
        "context": context
    })


def answer(result, user_type):

    intent = result["intent"]


    # =====================================================
    # CURRENT WEATHER
    # =====================================================

    if intent == "current_weather":

        city = weather_city(result)


        if not city:

            return "Which city do you want the weather for?"


        weather = get_weather(
            city
        )


        if weather is None:

            return (
                f"Sorry, I couldn't find weather information for {city}. "
                f"Please check the location and try again."
            )


        return (
            f"🌤️ Current Weather in "
            f"{weather['city']}, "
            f"{weather['country']}\n\n"

            f"🌡️ Temperature: "
            f"{weather['temperature']}°C\n"

            f"💧 Humidity: "
            f"{weather['humidity']}%\n"

            f"🌧️ Precipitation: "
            f"{weather['precipitation']} mm\n"

            f"💨 Wind speed: "
            f"{weather['wind_speed']} km/h"
        )


    # =====================================================
    # HISTORICAL WEATHER
    # =====================================================

    elif intent == "historical_weather":

        city = weather_city(result)

        month = result.get("month")


        if not city:

            return "Which city do you want typical weather for?"


        if not month:

            return f"Which month do you want typical weather for in {city}?"


        month_name = (
            result["month_name"]
        )


        historical = (
            get_historical_weather(
                city,
                month
            )
        )


        if historical is None:

            return (
                f"Sorry, I couldn't find historical weather information "
                f"for {city}. Please check the location and try again."
            )


        return (
            f"📊 Typical Weather in "
            f"{historical['city']} — "
            f"{month_name}\n\n"

            f"Based on historical data from "
            f"{historical['years']}\n\n"

            f"🌡️ Average temperature: "
            f"{historical['average_temperature']}°C\n"

            f"⬆️ Average high: "
            f"{historical['average_high']}°C\n"

            f"⬇️ Average low: "
            f"{historical['average_low']}°C\n"

            f"🌧️ Monthly rainfall: "
            f"{historical['average_monthly_rainfall']} mm\n"

            f"☔ Average rainy days: "
            f"{historical['average_rainy_days']} days"
        )


    # =====================================================
    # FLIGHTS, SENIOR ADVICE, ELIGIBILITY, MODULES
    # =====================================================

    elif intent in HANDLERS:

        return HANDLERS[intent](
            result,
            user_type
        )


    # =====================================================
    # UNKNOWN REQUEST
    # =====================================================

    else:

        # The user named a place but not a question: say what we can do there
        place = resolve(
            result.get("university"),
            result.get("destination"),
            result.get("city"),
            result.get("country")
        )

        if place and result.get("named_place"):

            name = (
                place["uni"]["name"] if place["uni"] is not None
                else place["city"] or place["country"]
            )

            when = (
                f" in {result['month_name']}"
                if result.get("month_name") else ""
            )

            return (
                f"Got it: {name}{when}. 👍 I can help with:\n\n"
                "• Am I eligible? (tell me your school and cGPA)\n"
                "• Which modules can I take?\n"
                "• When should I book my flight?\n"
                "• Where did seniors stay? Is it safe?\n"
                "• What does exchange there cost?\n"
                "• What's the weather like?\n\n"
                "What would you like to know?"
            )


        return (
            "I'm not sure what you're asking yet.\n\n"
            "You can ask me things like:\n"
            "• When should I book my flight to Aalto in January?\n"
            "• Where did seniors stay near VinUni?\n"
            "• I'm in NBS with a 3.6 cGPA. Can I go to Aalto?\n"
            "• Which modules can I take at Tampere?\n"
            "• How cold is Helsinki in January?"
        )


# =========================================================
# START APP
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
