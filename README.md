# Jewellery WhatsApp AI Bot (BotSpace + OpenAI + Google Sheets)

## What this does
1. Customer replies to your WhatsApp template → BotSpace sends a webhook to `/webhook`.
2. If the AI is "active" for that customer, the bot replies automatically using OpenAI,
   informed by the system prompt in `app/ai.py`.
3. Any useful info the customer shares (name, jewellery interest, budget) gets written to
   your Google Sheet.
4. If you personally reply to a customer from the BotSpace dashboard, the bot detects
   this is NOT a message it sent (see "How handover works" below) and automatically
   goes silent for that customer until you resume it.

## How handover works (important — read this)
Every time the bot sends a message via the API, it saves that message's ID in the
`sent_by_bot` table. BotSpace also sends an "outgoing" webhook for every message that
leaves your number — whether sent by the bot's API or typed manually in the dashboard.
When that webhook arrives, the code checks: is this message ID one we sent? If yes,
ignore it (it's just the bot's own message being echoed back). If no, it means a human
typed it — so the bot mutes itself for that customer.

To hand control back to the AI for a customer, call:
```
POST /resume/{phone}
```
(phone in the format used in the webhook, e.g. `917203843782`)

To manually mute the bot for a customer:
```
POST /pause/{phone}
```

Optional: set `AUTO_RESUME_HOURS` in your env vars (e.g. `24`) if you want the AI to
automatically take back over after that many hours of you not replying.

## 1. Fill in the business "training" content
Open `app/ai.py` and edit the `SYSTEM_PROMPT` variable — replace the placeholder catalog,
pricing, and policies with the client's real info. This is what the AI reads before every
reply. Keep it clear and factual; don't let the AI invent prices or stock it isn't told.

## 2. Set up Google Sheets access
1. Go to https://console.cloud.google.com/ → create a project (or use an existing one).
2. Enable the **Google Sheets API** for that project.
3. Go to "IAM & Admin" → "Service Accounts" → "Create Service Account".
4. Once created, open it → "Keys" tab → "Add Key" → "Create new key" → JSON. This
   downloads a `.json` credentials file — keep it private.
5. Open your Google Sheet, click "Share", and share it with the service account's
   email address (looks like `something@your-project.iam.gserviceaccount.com`) with
   **Editor** access.
6. Copy the Sheet ID from its URL:
   `https://docs.google.com/spreadsheets/d/THIS_PART_IS_THE_ID/edit`

You'll upload the JSON file's contents to Railway (see step 4).

## 3. Verify the BotSpace send-message response format
Open `app/botspace.py` and check the `send_text_message` function. It currently reads
the returned message ID as `data.get("id")`. Check the actual response BotSpace returns
for the `send-message` endpoint (Swagger docs → try it out) and confirm the field name
matches — this is critical for the handover logic to work correctly.

## 4. Deploy to Railway
1. Push this project to a GitHub repo, then create a new Railway project from it
   (or use `railway up` from the CLI).
2. In Railway → your service → **Settings → Volumes**: add a volume mounted at `/data`.
   This is what makes the SQLite database (and the Google credentials file) persist
   across restarts/redeploys.
3. In Railway → **Variables**, add all the variables from `.env.example` with your real
   values (BOTSPACE_API_KEY, OPENAI_API_KEY, GOOGLE_SHEET_ID, etc).
4. For the Google service account JSON: the simplest approach is to add its full JSON
   content as an env var (e.g. `GOOGLE_SERVICE_ACCOUNT_JSON`), then add this one-line
   startup step to write it to disk. Tell me if you want me to wire this up — happy to
   add a small startup script that does this automatically so you don't have to
   manually upload a file to the volume.
5. Deploy. Railway gives you a public URL like `https://your-app.up.railway.app`.

## 5. Connect the webhook in BotSpace
In your BotSpace dashboard → webhook settings, set the webhook URL to:
```
https://your-app.up.railway.app/webhook
```
Make sure both incoming and outgoing message events are enabled (outgoing is required
for the handover logic to work).

## 6. Test
1. Send a WhatsApp template to a test number.
2. Reply as the customer — the AI should respond within a few seconds.
3. Check your Google Sheet — a row should appear/update with extracted info.
4. Manually reply from the BotSpace dashboard as if you're the agent — the AI should
   go silent for that number.
5. Call `POST /resume/{phone}` to hand it back to the AI.

## Local development
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export $(cat .env.example | xargs)   # then edit with real values
uvicorn app.main:app --reload
```
Use a tool like `ngrok` to expose your local server for webhook testing before deploying.

## Files
- `app/main.py` — webhook receiver, handover logic, resume/pause endpoints
- `app/ai.py` — OpenAI prompt + reply/extraction logic (**edit the business info here**)
- `app/botspace.py` — sends messages via BotSpace API
- `app/sheets.py` — writes customer info to Google Sheets
- `app/db.py` — SQLite storage (chat state, history, sent-message tracking)
- `app/config.py` — reads all settings from environment variables
