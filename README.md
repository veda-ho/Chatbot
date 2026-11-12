# ExchangeBot

ExchangeBot is a Flask-based chatbot for NTU students and staff planning exchange or work trips. It helps users understand exchange eligibility, course mapping, travel costs, weather, flight options, and recommendations from prior students and travellers, while using a simple web UI to guide the conversation.

## Overview

The project is designed around two user flows:

- Student mode: supports exchange planning for NTU students, including eligibility checks, partner university information, module mapping, flight pricing, accommodation guidance, and weather insights.
- Staff / Faculty mode: focuses on staff travel planning, such as claimable flight and stay costs, accommodation suggestions, and destination guidance.

The app combines:

- a Flask web frontend,
- Google Gemini for intent detection and conversation understanding,
- rule-based service modules for trip-related answers,
- CSV-backed travel, policy, and fare data for NTU-specific domain answers.

## Features

- Natural-language travel and exchange queries
- Student vs staff routing based on user role
- Intent classification using Gemini
- Flight price and cheapest-day/month analysis
- Weather lookup for current and monthly conditions
- Exchange eligibility and module guidance
- Senior traveller advice and destination recommendations
- Human handoff prompts for urgent or unsupported cases
- Trip.com referral buttons for applicable flight or accommodation searches

## Tech Stack

- Python 3
- Flask
- Google GenAI SDK
- pandas, numpy, scikit-learn, joblib
- Gunicorn for production serving
- CSV data files for NTU and travel policies

## Repository Structure

```text
Chatbot/
├── app.py                  # Flask app and chat routes
├── requirements.txt        # Python dependencies
├── train_fare_model.py     # Fare model training script
├── .gitignore              # Git ignore rules
├── data/                   # Policy, destination, fare, and traveller data
│   ├── eligibility.csv
│   ├── flight_fares.csv
│   ├── modules.csv
│   ├── ntu_travel_policies.csv
│   ├── seniors.csv
│   ├── staff_claim_limits.csv
│   ├── staff_trips.csv
│   └── universities.csv
├── services/               # Business logic modules
│   ├── chat_service.py
│   ├── data_loader.py
│   ├── eligibility_service.py
│   ├── flight_service.py
│   ├── handoff_service.py
│   ├── senior_service.py
│   ├── staff_service.py
│   ├── tripcom_service.py
│   └── weather_service.py
├── static/                 # CSS and JavaScript assets
│   ├── script.js
│   └── style.css
├── templates/              # Flask HTML pages
│   ├── home.html
│   └── index.html
└── README.md               # Project documentation
```

## Prerequisites

- Python 3.10+
- A Google Gemini API key
- Optional: a virtual environment manager such as `venv`

## Setup

1. Clone the repository:

```bash
git clone https://github.com/veda-ho/Chatbot.git
cd Chatbot
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your Gemini key:

```env
GEMINI_API_KEY=your_api_key_here
```

Optional:

```env
GEMINI_MODELS=gemini-3.5-flash-lite,gemini-3.6-flash
```

## Running the App

Start the Flask server:

```bash
python app.py
```

Then open the app in your browser:

- `http://localhost:5000/`

The app starts on the home page, where you choose either Student or Staff / Faculty before entering the chat.

## Example Questions

- "Which universities can I apply to for exchange?"
- "How much does a flight to Helsinki cost?"
- "What is the weather in Budapest in January?"
- "Can I take computer engineering modules in Aalto?"
- "Where should I stay in Hanoi?"
- "What do previous students say about living in Finland?"

## How It Works

1. The user selects a role: Student or Staff.
2. The message is sent to Gemini for intent detection and extraction of key fields like university, month, cGPA, destination, and semester.
3. The Flask app routes the request to the relevant service module.
4. Data from local CSV files and the travel rules engine is used to generate an answer.
5. If the request cannot be answered or requires human intervention, the app offers escalation to a real person.

## Data and Decision Logic

The repository includes domain-specific datasets such as:

- `data/universities.csv` for partner universities and route metadata
- `data/eligibility.csv` for exchange conditions
- `data/modules.csv` for module mapping information
- `data/flight_fares.csv` for airfare calculations and trend analysis
- `data/ntu_travel_policies.csv` for NTU policy data
- `data/seniors.csv` and `data/staff_trips.csv` for traveller experience and trip summaries

## Production Notes

For a production deployment, the project can be served with Gunicorn:

```bash
gunicorn app:app
```

Configure the environment as needed for your deployment platform and set `GEMINI_API_KEY` securely.

## License

This project is intended for academic and internal travel-assistant use within the repository context. Please check the project owner and institutional policy before reuse or distribution.
