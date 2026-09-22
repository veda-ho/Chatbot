import re


# =========================================================
# MONTHS
# =========================================================

# Allows both full month names and abbreviations
MONTHS = {
    "january": 1,
    "jan": 1,

    "february": 2,
    "feb": 2,

    "march": 3,
    "mar": 3,

    "april": 4,
    "apr": 4,

    "may": 5,

    "june": 6,
    "jun": 6,

    "july": 7,
    "jul": 7,

    "august": 8,
    "aug": 8,

    "september": 9,
    "sept": 9,
    "sep": 9,

    "october": 10,
    "oct": 10,

    "november": 11,
    "nov": 11,

    "december": 12,
    "dec": 12
}


# Used for displaying the full month name
MONTH_NAMES = {
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


# =========================================================
# UNDERSTAND USER MESSAGE
# =========================================================

def understand_message(message):

    original_message = message.strip()
    text = original_message.lower()


    # -----------------------------------------------------
    # STEP 1: Detect month
    # -----------------------------------------------------

    detected_month = None
    detected_month_word = None


    # Sort longest first so "september" is checked
    # before "sep", for example
    month_words = sorted(
        MONTHS.keys(),
        key=len,
        reverse=True
    )


    for month_word in month_words:

        # Use word boundaries so "mar" doesn't match
        # unrelated words containing "mar"
        if re.search(
            rf"\b{re.escape(month_word)}\b",
            text
        ):

            detected_month = MONTHS[month_word]
            detected_month_word = month_word

            break


    # -----------------------------------------------------
    # STEP 2: Detect historical weather request
    # -----------------------------------------------------

    historical_words = [
        "historical",
        "usually",
        "typical",
        "normally",
        "average"
    ]


    historical_request = any(
        word in text
        for word in historical_words
    )


    # If the user mentions a month and talks about
    # weather / temperature / rain / what a place is like,
    # treat it as historical weather.

    if detected_month and (
        "weather" in text
        or historical_request
        or "rain" in text
        or "temperature" in text
        or "like" in text
    ):

        city = extract_city(
            original_message,
            detected_month_word
        )


        if city:

            return {
                "intent": "historical_weather",
                "city": city,
                "month": detected_month,

                # Always return full month name
                "month_name": MONTH_NAMES[
                    detected_month
                ]
            }


    # -----------------------------------------------------
    # STEP 3: Detect current weather request
    # -----------------------------------------------------

    weather_words = [
        "weather",
        "temperature",
        "rain",
        "raining"
    ]


    if any(
        word in text
        for word in weather_words
    ):

        city = extract_city(
            original_message
        )


        if city:

            return {
                "intent": "current_weather",
                "city": city
            }


    # -----------------------------------------------------
    # STEP 4: Unknown request
    # -----------------------------------------------------

    return {
        "intent": "unknown"
    }


# =========================================================
# EXTRACT CITY
# =========================================================

def extract_city(message, month_word=None):

    text = message


    # -----------------------------------------------------
    # Remove punctuation
    # -----------------------------------------------------

    text = re.sub(
        r"[?!.,]",
        "",
        text
    )


    # -----------------------------------------------------
    # Remove month
    # -----------------------------------------------------

    if month_word:

        text = re.sub(
            rf"\b{re.escape(month_word)}\b",
            " ",
            text,
            flags=re.IGNORECASE
        )


    # -----------------------------------------------------
    # Remove words that aren't part of the city
    # -----------------------------------------------------

    phrases_to_remove = [

        "what is",
        "what's",
        "whats",

        "how is",
        "how's",
        "hows",

        "tell me",

        "current",
        "historical",
        "history",

        "typical",
        "usually",
        "normally",
        "average",

        "weather",
        "temperature",

        "raining",
        "rainy",
        "rain",

        "right now",
        "now",

        "like",

        "the",

        "in",
        "for"
    ]


    # Remove longer phrases first
    phrases_to_remove.sort(
        key=len,
        reverse=True
    )


    for phrase in phrases_to_remove:

        text = re.sub(
            rf"\b{re.escape(phrase)}\b",
            " ",
            text,
            flags=re.IGNORECASE
        )


    # -----------------------------------------------------
    # Clean extra spaces
    # -----------------------------------------------------

    text = " ".join(
        text.split()
    )


    if not text:
        return None


    # Make city look nice:
    # "new york" -> "New York"
    return text.title()


# =========================================================
# TESTING
# =========================================================

if __name__ == "__main__":

    tests = [
        "weather Seoul",
        "What's the weather in Tokyo?",
        "How is the weather in Paris?",
        "historical Seoul December",
        "What's Seoul usually like in dec?",
        "What's Tokyo like in jan?",
        "Singapore weather in feb",
        "What is the weather in Singapore in June?"
    ]


    for test in tests:

        print("\nUSER:", test)

        print(
            "RESULT:",
            understand_message(test)
        )