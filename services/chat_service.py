import os
import json

from dotenv import load_dotenv
from google import genai


# =========================================================
# LOAD GEMINI
# =========================================================

load_dotenv()


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# =========================================================
# UNDERSTAND USER MESSAGE
# =========================================================

def understand_message(message):

    try:

        # -------------------------------------------------
        # Ask Gemini to classify the user's message
        # -------------------------------------------------

        prompt = f"""
You are the intent classifier for a student exchange chatbot.

The chatbot helps university students planning for exchange.

You MUST choose exactly ONE of these intents:

1. current_weather
   - User wants the weather right now.
   - Example:
     "What's the weather in Tokyo?"
     "Is it raining in Seoul?"

2. historical_weather
   - User wants typical, historical, seasonal or monthly weather.
   - Example:
     "What's Seoul usually like in December?"
     "How cold is Tokyo in January?"
     "Singapore weather in June"

3. senior_experience
   - User asks about previous exchange students' experiences,
     advice, opinions, challenges or recommendations.

4. senior_attractions
   - User asks what attractions, places or activities previous
     exchange students recommend.

5. senior_accommodation
   - User asks about accommodation used or recommended by
     previous exchange students.

6. senior_cost
   - User asks about spending, living costs, budgets or expenses
     reported by previous exchange students.

7. flight_price
   - User asks about flight prices or typical flight costs.

8. cheapest_flight_day
   - User asks which day or day of the week is historically
     cheapest to fly.

9. cheapest_flight_month
   - User asks which month or period is historically cheapest
     to fly.

10. country_comparison
    - User asks to compare two or more exchange destinations.

11. unknown
    - The request does not match any of the above.


Extract information when available:

- city
- country
- countries
- month
- origin
- destination

Use "country" when the user is referring to one country.

Use "countries" when the user is comparing two or more countries.
"countries" must be a JSON list.

For flight-related intents, locations should primarily be placed in
"origin" and "destination", not "city".

Do not put the flight destination into "city" unless the question
separately refers to that city for a non-flight purpose.

IMPORTANT RULES:

- Return ONLY valid JSON.
- Do not include markdown.
- Do not include ```json.
- Do not explain your answer.
- Do not invent missing information.
- Missing values must be null.
- Month must be a number from 1 to 12.
- Use the intent names exactly as provided above.


Return exactly this structure:

{{
    "intent": "intent_name",
    "city": null,
    "country": null,
    "month": null,
    "origin": null,
    "destination": null
}}


USER MESSAGE:

{message}
"""


        # -------------------------------------------------
        # Send request to Gemini
        # -------------------------------------------------

        interaction = client.interactions.create(
            model="gemini-3.6-flash",
            input=prompt
        )


        response_text = (
            interaction.output_text.strip()
        )


        # -------------------------------------------------
        # Convert Gemini response into Python dictionary
        # -------------------------------------------------

        result = json.loads(
            response_text
        )


        # -------------------------------------------------
        # Validate intent
        # -------------------------------------------------

        valid_intents = [
            "current_weather",
            "historical_weather",
            "senior_experience",
            "senior_attractions",
            "senior_accommodation",
            "senior_cost",
            "flight_price",
            "cheapest_flight_day",
            "cheapest_flight_month",
            "country_comparison",
            "unknown"
        ]


        if result.get("intent") not in valid_intents:

            return {
                "intent": "unknown"
            }


        # -------------------------------------------------
        # Add full month name for app.py
        # -------------------------------------------------

        month_names = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December"
        }


        month = result.get(
            "month"
        )


        if month in month_names:

            result["month_name"] = (
                month_names[month]
            )


        return result


    # =====================================================
    # GEMINI / JSON ERROR
    # =====================================================

    except Exception as error:

        print(
            "Gemini error:",
            error
        )


        return {
            "intent": "unknown"
        }


# =========================================================
# TESTING
# =========================================================

if __name__ == "__main__":

    tests = [

        "What's the weather in Tokyo?",

        "What's Seoul usually like in December?",

        "I'm going to Tokyo in Jan. How cold is it usually?",

        "What attractions do seniors recommend in Korea?",

        "How much did students spend during exchange in Japan?",

        "Where did seniors stay in Seoul?",

        "Which day is cheapest to fly from Singapore to Seoul?",

        "Which month is cheapest to fly to Tokyo?",

        "Should I go to Japan or Korea for exchange?"
    ]


    for test in tests:

        print(
            "\nUSER:",
            test
        )


        result = understand_message(
            test
        )


        print(
            "RESULT:",
            result
        )