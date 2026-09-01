import os

# --- BotSpace ---
BOTSPACE_API_KEY = os.environ.get("BOTSPACE_API_KEY", "")
BOTSPACE_CHANNEL_ID = os.environ.get("BOTSPACE_CHANNEL_ID", "6a7ee53dd30b3992237344ac")
BOTSPACE_BASE_URL = "https://public-api.bot.space/v1"

# --- OpenAI ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# --- Google Sheets ---
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
# Path to the service account JSON file (mounted as a Railway secret file,
# or written from an env var at startup — see README).
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_FILE", "/data/service_account.json"
)

# --- Database (SQLite on a persistent Railway volume) ---
DB_PATH = os.environ.get("DB_PATH", "/data/bot.db")

# --- Webhook security (optional shared secret you configure in BotSpace) ---
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# --- Auto-resume: hours of silence from the human agent before AI resumes automatically ---
AUTO_RESUME_HOURS = float(os.environ.get("AUTO_RESUME_HOURS", "0"))  # 0 = disabled
