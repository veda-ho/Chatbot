from flask import (
    Flask,
    render_template,
    jsonify,
    request
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


app = Flask(__name__)


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
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


    # "student" or "staff", from the switch on the chat page
    user_type = data.get(
        "user_type",
        "student"
    )


    # -----------------------------------
    # Understand user's request
    # -----------------------------------

    result = understand_message(
        user_message
    )


    intent = result["intent"]


    # =====================================================
    # CURRENT WEATHER
    # =====================================================

    if intent == "current_weather":

        city = result["city"]


        weather = get_weather(
            city
        )


        if weather is None:

            return jsonify({
                "reply":
                    f"Sorry, I couldn't find weather information for {city}. "
                    f"Please check the location and try again."
            })


        reply = (
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


        return jsonify({
            "reply": reply
        })


    # =====================================================
    # HISTORICAL WEATHER
    # =====================================================

    elif intent == "historical_weather":

        city = result["city"]

        month = result["month"]

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

            return jsonify({
                "reply":
                    f"Sorry, I couldn't find historical weather information "
                    f"for {city}. Please check the location and try again."
            })


        reply = (
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


        return jsonify({
            "reply": reply
        })


    # =====================================================
    # FLIGHTS, SENIOR ADVICE, ELIGIBILITY, MODULES
    # =====================================================

    elif intent in HANDLERS:

        try:

            reply = HANDLERS[intent](
                result,
                user_type
            )

        except Exception as error:

            print(
                f"Error answering {intent}:",
                error
            )

            reply = (
                "Sorry, something went wrong while I was looking that up. "
                "Please try asking in a different way."
            )


        return jsonify({
            "reply": reply
        })


    # =====================================================
    # UNKNOWN REQUEST
    # =====================================================

    else:

        return jsonify({
            "reply": (
                "I'm not sure what you're asking yet.\n\n"
                "You can ask me things like:\n"
                "• When should I book my flight to Aalto in January?\n"
                "• Where did seniors stay near VinUni?\n"
                "• I'm in NBS with a 3.6 cGPA. Can I go to Aalto?\n"
                "• Which modules can I take at Tampere?\n"
                "• How cold is Helsinki in January?"
            )
        })


# =========================================================
# START APP
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )