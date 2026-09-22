import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# API SESSION + RETRIES
# =========================================================

session = requests.Session()


retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[
        429,
        500,
        502,
        503,
        504
    ],
    allowed_methods=["GET"]
)


adapter = HTTPAdapter(
    max_retries=retry_strategy
)


session.mount(
    "https://",
    adapter
)


# =========================================================
# CLEAN NUMBER
# =========================================================

def clean_number(value):

    rounded = round(value, 1)

    # Prevent ugly "-0.0"
    if rounded == 0:
        return 0.0

    return rounded


# =========================================================
# GET CITY COORDINATES
# =========================================================

def get_coordinates(city):

    geocoding_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )


    geocoding_params = {
        "name": city,
        "count": 1,
        "language": "en",
        "format": "json"
    }


    response = session.get(
        geocoding_url,
        params=geocoding_params,
        timeout=15
    )


    response.raise_for_status()


    data = response.json()


    # City not found
    if (
        "results" not in data
        or len(data["results"]) == 0
    ):

        return None


    location = data["results"][0]


    return {
        "city": location["name"],
        "country": location.get(
            "country",
            ""
        ),
        "latitude": location["latitude"],
        "longitude": location["longitude"]
    }


# =========================================================
# CURRENT WEATHER
# =========================================================

def get_weather(city):

    try:

        # -----------------------------------
        # STEP 1: Get coordinates
        # -----------------------------------

        location = get_coordinates(city)


        if location is None:
            return None


        # -----------------------------------
        # STEP 2: Request current weather
        # -----------------------------------

        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
        )


        weather_params = {

            "latitude":
                location["latitude"],

            "longitude":
                location["longitude"],

            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "precipitation,"
                "weather_code,"
                "wind_speed_10m"
            ),

            "timezone": "auto"
        }


        response = session.get(
            weather_url,
            params=weather_params,
            timeout=15
        )


        response.raise_for_status()


        weather_data = response.json()


        if "current" not in weather_data:
            return None


        current = weather_data["current"]


        # -----------------------------------
        # STEP 3: Return weather
        # -----------------------------------

        return {

            "city":
                location["city"],

            "country":
                location["country"],

            "temperature":
                current.get(
                    "temperature_2m"
                ),

            "humidity":
                current.get(
                    "relative_humidity_2m"
                ),

            "precipitation":
                current.get(
                    "precipitation"
                ),

            "wind_speed":
                current.get(
                    "wind_speed_10m"
                ),

            "weather_code":
                current.get(
                    "weather_code"
                )
        }


    except requests.exceptions.RequestException as error:

        print(
            "Weather API error:",
            error
        )

        return None


    except Exception as error:

        print(
            "Unexpected weather error:",
            error
        )

        return None


# =========================================================
# HISTORICAL WEATHER
# =========================================================

def get_historical_weather(city, month):

    try:

        # -----------------------------------
        # STEP 1: Validate month
        # -----------------------------------

        if month < 1 or month > 12:
            return None


        # -----------------------------------
        # STEP 2: Get coordinates
        # -----------------------------------

        location = get_coordinates(city)


        if location is None:
            return None


        # -----------------------------------
        # STEP 3: Historical API
        # -----------------------------------

        historical_url = (
            "https://archive-api.open-meteo.com/v1/archive"
        )


        historical_params = {

            "latitude":
                location["latitude"],

            "longitude":
                location["longitude"],

            # Five complete years
            "start_date":
                "2021-01-01",

            "end_date":
                "2025-12-31",

            "daily": (
                "temperature_2m_max,"
                "temperature_2m_min,"
                "temperature_2m_mean,"
                "precipitation_sum"
            ),

            "timezone":
                "auto"
        }


        response = session.get(
            historical_url,
            params=historical_params,
            timeout=30
        )


        response.raise_for_status()


        historical_data = (
            response.json()
        )


        if "daily" not in historical_data:
            return None


        daily = historical_data["daily"]


        # -----------------------------------
        # STEP 4: Storage
        # -----------------------------------

        temperatures_max = []
        temperatures_min = []
        temperatures_mean = []


        rainfall_by_year = {}
        rainy_days_by_year = {}


        # -----------------------------------
        # STEP 5: Process daily data
        # -----------------------------------

        for i in range(
            len(daily["time"])
        ):

            date = daily["time"][i]


            year = int(
                date[0:4]
            )

            date_month = int(
                date[5:7]
            )


            # Ignore other months
            if date_month != month:
                continue


            max_temp = (
                daily[
                    "temperature_2m_max"
                ][i]
            )

            min_temp = (
                daily[
                    "temperature_2m_min"
                ][i]
            )

            mean_temp = (
                daily[
                    "temperature_2m_mean"
                ][i]
            )

            rain = (
                daily[
                    "precipitation_sum"
                ][i]
            )


            # --------------------------------
            # Temperature
            # --------------------------------

            if max_temp is not None:

                temperatures_max.append(
                    max_temp
                )


            if min_temp is not None:

                temperatures_min.append(
                    min_temp
                )


            if mean_temp is not None:

                temperatures_mean.append(
                    mean_temp
                )


            # --------------------------------
            # Rain
            # --------------------------------

            if rain is not None:

                if year not in rainfall_by_year:

                    rainfall_by_year[
                        year
                    ] = 0


                rainfall_by_year[
                    year
                ] += rain


                # Initialise rainy-day count
                if year not in rainy_days_by_year:

                    rainy_days_by_year[
                        year
                    ] = 0


                # Define rainy day as
                # at least 1 mm precipitation
                if rain >= 1:

                    rainy_days_by_year[
                        year
                    ] += 1


        # -----------------------------------
        # STEP 6: Check data exists
        # -----------------------------------

        if len(
            temperatures_mean
        ) == 0:

            return None


        # -----------------------------------
        # STEP 7: Temperature averages
        # -----------------------------------

        average_high = (
            sum(temperatures_max)
            / len(temperatures_max)
        )


        average_low = (
            sum(temperatures_min)
            / len(temperatures_min)
        )


        average_temperature = (
            sum(temperatures_mean)
            / len(temperatures_mean)
        )


        # -----------------------------------
        # STEP 8: Average monthly rainfall
        # -----------------------------------

        if rainfall_by_year:

            average_monthly_rainfall = (
                sum(
                    rainfall_by_year.values()
                )
                / len(
                    rainfall_by_year
                )
            )

        else:

            average_monthly_rainfall = 0


        # -----------------------------------
        # STEP 9: Average rainy days
        # -----------------------------------

        if rainy_days_by_year:

            average_rainy_days = (
                sum(
                    rainy_days_by_year.values()
                )
                / len(
                    rainy_days_by_year
                )
            )

        else:

            average_rainy_days = 0


        # -----------------------------------
        # STEP 10: Return results
        # -----------------------------------

        return {

            "city":
                location["city"],

            "country":
                location["country"],

            "month":
                month,

            "years":
                "2021–2025",

            "average_temperature":
                clean_number(
                    average_temperature
                ),

            "average_high":
                clean_number(
                    average_high
                ),

            "average_low":
                clean_number(
                    average_low
                ),

            "average_monthly_rainfall":
                clean_number(
                    average_monthly_rainfall
                ),

            "average_rainy_days":
                clean_number(
                    average_rainy_days
                )
        }


    except requests.exceptions.RequestException as error:

        print(
            "Historical weather API error:",
            error
        )

        return None


    except Exception as error:

        print(
            "Unexpected historical weather error:",
            error
        )

        return None


# =========================================================
# TESTING
# =========================================================

if __name__ == "__main__":

    print(
        "CURRENT WEATHER TEST"
    )

    print(
        "--------------------"
    )


    current = get_weather(
        "Tokyo"
    )

    print(current)


    print(
        "\nHISTORICAL WEATHER TEST"
    )

    print(
        "-----------------------"
    )


    historical = (
        get_historical_weather(
            "Seoul",
            12
        )
    )

    print(historical)