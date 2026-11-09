import os
import json
from datetime import date
from concurrent.futures import ThreadPoolExecutor, TimeoutError as GeminiTimeout

from dotenv import load_dotenv
from google import genai


# =========================================================
# LOAD GEMINI
# =========================================================

load_dotenv()


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# Gemini models to try, in order. If one is busy (503), over its limit (429)
# or doesn't exist, the next one is tried. Flash-Lite goes first because its
# free daily limit is much higher, and sorting questions is a simple job.
# To change them without editing code, set GEMINI_MODELS, e.g.
#   GEMINI_MODELS=gemini-3.5-flash-lite,gemini-3.6-flash
GEMINI_MODELS = [
    m.strip() for m in os.getenv(
        "GEMINI_MODELS",
        "gemini-3.5-flash-lite,gemini-3.6-flash"
    ).split(",")
    if m.strip()
]

# Give up on each model after this many seconds, so the chat never freezes
GEMINI_TIMEOUT = 15

gemini_pool = ThreadPoolExecutor(
    max_workers=4
)


# =========================================================
# UNDERSTAND USER MESSAGE
# =========================================================

def format_history(history, last=10):
    """The last few messages as plain text for Gemini (long replies shortened)."""

    lines = []

    for turn in (history or [])[-last * 2:]:

        who = "User" if turn.get("role") == "user" else "Bot"

        text = " ".join(str(turn.get("text", "")).split())

        if len(text) > 300:
            text = text[:300] + "..."

        lines.append(f"{who}: {text}")

    return "\n".join(lines) if lines else "(this is the first message)"


def understand_message(message, history=None):

    try:

        # -------------------------------------------------
        # Ask Gemini to classify the user's message
        # -------------------------------------------------

        prompt = f"""
You are the intent classifier for an NTU (Singapore) travel and exchange chatbot.

The chatbot helps NTU students planning exchange and NTU staff planning work trips.
Our destinations: Finland, Hungary, Luxembourg, Croatia, Vietnam, Brunei and Indonesia.

Today's date is {date.today().isoformat()}.

Choose the intent (or intents) from this list:

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
   - User asks where to stay, which hotel to book, or about
     accommodation used or recommended by previous travellers.

6. senior_cost
   - User asks about spending, living costs, budgets or expenses,
     how much a trip will cost, or how much they can claim.

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

13. human_help
    - User wants to talk to a real person or NTU staff, or needs
      something only NTU can decide or do: an appeal, a rejected
      application, a special case (e.g. a medical condition),
      a complaint, or an emergency abroad (lost passport, robbed,
      hurt, in hospital, missed flight).
    - Example: "Can I speak to someone?", "I lost my passport in Hanoi"

14. unknown
    - The request does not match any of the above.


If the message asks more than one thing (e.g. "Where should I stay
and how much does it cost?"), put EVERY matching intent in "intents",
in the order the user asked, up to 3. Put the first one in "intent".
If it asks one thing, "intents" has just that one intent.


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
- nights: number of nights of the trip, e.g. 4 (a 5-day trip is 4 nights)
- urgent: true if the user is in danger, hurt, robbed, lost their
  passport or is stuck abroad right now, otherwise false

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


CONVERSATION SO FAR (oldest first):

{format_history(history)}


Use the conversation to understand the latest message:

- The intent describes ONLY the latest user message.
- If the latest message refers back ("there", "that uni", "the same
  date", "go back to Aalto", "the first place I asked about"),
  fill in those details from the conversation.
- If the bot just asked the user for a missing detail (a date, cGPA,
  school, university) and the latest message only gives that detail,
  use the intent of the question the bot was answering.
- If the latest message names a new place, use the new place.


Return exactly this structure:

{{
    "intent": "intent_name",
    "intents": ["intent_name"],
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
    "semester": null,
    "nights": null,
    "urgent": false
}}


LATEST USER MESSAGE:

{message}
"""


        # -------------------------------------------------
        # Send request to Gemini
        # -------------------------------------------------

        interaction = None

        last_error = None


        for model_name in GEMINI_MODELS:

            try:

                waiting = gemini_pool.submit(
                    client.interactions.create,
                    model=model_name,
                    input=prompt
                )

                interaction = waiting.result(
                    timeout=GEMINI_TIMEOUT
                )

                break

            except GeminiTimeout:

                print(
                    f"Gemini error ({model_name}): no reply after {GEMINI_TIMEOUT} seconds"
                )

                last_error = "timeout"

            except Exception as error:

                print(
                    f"Gemini error ({model_name}):",
                    error
                )

                last_error = str(error)


        # every model failed
        if interaction is None:

            return {
                "intent": "unknown",
                "error": last_error
            }


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
            "human_help",
            "unknown"
        ]


        # Keep only valid intents, in order, without repeats (max 3)
        intents = result.get("intents") or [result.get("intent")]

        if isinstance(intents, str):
            intents = [intents]

        intents = [
            i for n, i in enumerate(intents)
            if i in valid_intents and i not in intents[:n]
        ]

        # "unknown" only counts if nothing else matched
        if len(intents) > 1:
            intents = [i for i in intents if i != "unknown"]

        if not intents:

            return {
                "intent": "unknown",
                "intents": ["unknown"]
            }

        result["intents"] = intents[:3]
        result["intent"] = result["intents"][0]


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

        "Where should I stay in Hanoi and how much does it cost?",

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
