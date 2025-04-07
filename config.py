import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- Gemini Configuration ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_NAME = "gemini-1.5-flash" # Or "gemini-pro-vision", "gemini-1.5-pro" etc.

# --- ADB Configuration ---
ADB_HOST = "127.0.0.1"
ADB_PORT = 5037

# --- Agent Configuration ---
MAX_STEPS = 15 # Increased max steps slightly
DEFAULT_WAIT_TIME = 2.0
SCREENSHOT_DIR = "screenshots"
SCREENSHOT_FILENAME = "temp_screenshot.png"
ACTION_HISTORY_LENGTH = 5 # Number of recent steps to include in LLM prompt

# --- Omniparser Configuration ---
# Set to False to use the real Omniparser client via Gradio API
USE_OMNIPARSER_SIMULATION = False
# URL of your locally running Omniparser Gradio service
OMNIPARSER_URL = "http://127.0.0.1:7788/"
# Default parameters for Omniparser API call (adjust if needed)
OMNIPARSER_BOX_THRESHOLD = 0.05
OMNIPARSER_IOU_THRESHOLD = 0.1
OMNIPARSER_USE_PADDLEOCR = True
OMNIPARSER_IMGSZ = 640

# --- Keep this for parsing the string output from the REAL API ---
# (Even the real API returns the elements as a string in index [1])
SIMULATED_OMNIPARSER_OUTPUT = """
# You can leave the old example string here or remove it,
# it's only used if USE_OMNIPARSER_SIMULATION = True
# ... (rest of the example string) ...
"""