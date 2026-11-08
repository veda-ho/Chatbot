import os
import json
from datetime import date

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
You are the intent classifier for an NTU (Singapore) travel and exchange chatbot.

The chatbot helps NTU students planning exchange and NTU staff planning work trips.
Our destinations: Finland, Hungary, Luxembourg, Croatia, Vietnam, Brunei and Indonesia.

Today's date is {date.today().isoformat()}.

You MUST choose exactly ONE of these intents:

1. current_weather
   - User wants the weather right now.
   - Example: "What's the weather in Helsinki?"

2. historical_weather
   - User wants typical, seasonal or monthly weather.
   - Example: "How cold is Helsinki in January?"

3. senior_experience
   - User asks about previous exchange students' experiences,
     advice, opinions, safety, challenges or tips.

4. senior_attractions
   - User asks what attractions, places or activities previous
     exchange students recommend.

5. senior_accommodation
   - User asks where to stay, or about accommodation used or
     recommended by previous exchange students.

6. senior_cost
   - User asks about spending, living costs, budgets or expenses.

7. flight_price
   - User asks about flight prices, which flight to book,
     or when to book a flight.

8. cheapest_flight_day
   - User asks which day of the week is cheapest to fly.

9. cheapest_flight_month
   - User asks which month or period is cheapest to fly.

10. country_comparison
    - User asks to compare two or more exchange destinations.

11. eligibility
    - User asks whether they can go on exchange somewhere,
      or about cGPA requirements or exchange vacancies.

12. modules
    - User asks which modules or courses they can take or map
      at a partner university.

13. unknown
    - The request does not match any of the above.


Extract information when available:

- city: a city named for a non-flight purpose
- country: one country
- countries: a JSON list, only when comparing two or more places
- university: a university name, e.g. "Aalto", "VinUni", "ELTE"
- month: a number from 1 to 12
- departure_date: the flight date as YYYY-MM-DD, using the next
  future occurrence if the user gives no year
- origin and destination: for flights
- airline: if the user names one
- cgpa: a number, e.g. 3.6
- school: the user's NTU school, e.g. "NBS", "CCDS", "EEE"
- semester: 1 or 2, if the user names a semester

For flight-related intents, put the place the user flies to in
"destination", not "city". If the user names a university,
also put it in "university".

IMPORTANT RULES:

- Return ONLY valid JSON.
- Do not include markdown.
- Do not include ```json.
- Do not explain your answer.
- Do not invent missing information.
- Missing values must be null.
- Use the intent names exactly as provided above.


Return exactly this structure:

{{
    "intent": "intent_name",
    "city": null,
    "country": null,
    "countries": null,
    "university": null,
    "month": null,
    "departure_date": null,
    "origin": null,
    "destination": null,
    "airline": null,
    "cgpa": null,
    "school": null,
    "semester": null
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
        # Remove ```json fences if Gemini adds them anyway
        # -------------------------------------------------

        if response_text.startswith("```"):

            response_text = (
                response_text
                .strip("`")
                .removeprefix("json")
                .strip()
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
            "eligibility",
            "modules",
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

        "What's the weather in Helsinki?",

        "How cold is Helsinki usually in January?",

        "I'm going to Aalto in January. When should I book my flight?",

        "What attractions do seniors recommend in Hanoi?",

        "How much did students spend during exchange in Finland?",

        "Where did seniors stay near VinUni?",

        "Which day is cheapest to fly from Singapore to Hanoi?",

        "Which month is cheapest to fly to Budapest?",

        "Should I go to Hungary or Luxembourg for exchange?",

        "I'm in NBS with a 3.4 cGPA. Can I go to Aalto?",

        "Which modules can I clear at Tampere as a CCDS student?"
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
