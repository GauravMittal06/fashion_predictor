"""Settings shared by the forecasting code. Edit values here, not inside the scripts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'outputs'
SEED = 42

# ---------- forecasting ----------
SEASON = 12                   # months per year
HORIZON = 6                   # longest forecast, in months
MIN_HISTORY = 24              # a forecast needs two full years behind it
CALL_THRESHOLD = 0.10         # 10% above / below the same months last year = Rising / Fading
QUANTILES = [0.1, 0.5, 0.9]   # low, middle, high forecast (the shaded range holds 8 in 10)
CHRONOS2_MODEL = 'amazon/chronos-2'          # pretrained time-series transformer, used without training
LSTM_IN, LSTM_OUT, LSTM_UNITS = 12, 6, 64    # comparison model: 12 months in, 6 months out
LSTM_EPOCHS, LSTM_PATIENCE = 80, 5
