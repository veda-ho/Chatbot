"""
Train the fare model once and save it to data/fare_model.joblib.

Render runs this during the build (see the Build Command), so the website
starts quickly and never has to retrain the model on its small free server.
You can also run it yourself: python train_fare_model.py
"""
from pathlib import Path

MODEL_FILE = Path(__file__).resolve().parent / "data" / "fare_model.joblib"

# start fresh so the model always matches the installed scikit-learn version
if MODEL_FILE.exists():
    MODEL_FILE.unlink()

# importing the flight service trains the model and saves it
import services.flight_service  # noqa: E402,F401

print("Done:", MODEL_FILE, f"({MODEL_FILE.stat().st_size / 1e6:.1f} MB)")
