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
    # UNKNOWN REQUEST
    # =====================================================

    else:

        return jsonify({
            "reply": (
                "I'm not sure what you're asking yet.\n\n"
                "You can ask me things like:\n"
                "• What's the weather in Tokyo?\n"
                "• What's Seoul usually like in December?\n"
                "• Singapore weather in June"
            )
        })


# =========================================================
# START APP
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )