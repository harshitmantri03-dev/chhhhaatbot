import logging
import os
import time

from fastapi import FastAPI, Request, HTTPException

from app.config import WEBHOOK_SECRET, AUTO_RESUME_HOURS, GOOGLE_SERVICE_ACCOUNT_FILE
from app import db, botspace, ai, sheets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="Jewellery WhatsApp AI Bot")


def write_google_credentials_file():
    """
    Railway env vars are text-only, so the Google service account JSON is stored
    as a single env var (GOOGLE_SERVICE_ACCOUNT_JSON) and written to disk here,
    at the path GOOGLE_SERVICE_ACCOUNT_FILE (should be on the persistent volume).
    """
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw_json:
        logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON not set — Google Sheets writes will fail.")
        return
    os.makedirs(os.path.dirname(GOOGLE_SERVICE_ACCOUNT_FILE), exist_ok=True)
    with open(GOOGLE_SERVICE_ACCOUNT_FILE, "w") as f:
        f.write(raw_json)
    logger.info("Google service account credentials written to %s", GOOGLE_SERVICE_ACCOUNT_FILE)


@app.on_event("startup")
def startup():
    db.init_db()
    write_google_credentials_file()
    logger.info("Startup complete.")


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    if WEBHOOK_SECRET:
        # If you configure a shared secret/header in BotSpace, check it here.
        provided = request.headers.get("x-webhook-secret", "")
        if provided != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()
    direction = body.get("direction")
    phone_obj = body.get("phone", {})
    # BotSpace's send-message endpoint expects phone numbers with a leading "+"
    phone = f"+{phone_obj.get('countryCode', '')}{phone_obj.get('phone', '')}"
    customer = body.get("customer", {})
    customer_name = customer.get("name", "")
    message_id = body.get("id")

    if not phone:
        return {"status": "ignored", "reason": "no phone"}

    if direction == "incoming":
        await handle_incoming(phone, customer_name, body)
    elif direction == "outgoing":
        await handle_outgoing(phone, message_id, body)
    else:
        logger.info("Unhandled event, full body: %s", body)

    return {"status": "ok"}


async def handle_incoming(phone: str, customer_name: str, body: dict):
    payload = body.get("payload", {}).get("payload", {})
    text = payload.get("text", "")
    if not text:
        # Non-text message (image/document/etc) — log only for now.
        logger.info("Non-text incoming message from %s, skipping AI reply", phone)
        return

    chat = db.get_or_create_chat(phone, customer_name)
    db.add_message(phone, "user", text)

    # --- auto-resume check ---
    if not chat["ai_active"] and AUTO_RESUME_HOURS > 0 and chat["last_human_reply_at"]:
        hours_since = (time.time() - chat["last_human_reply_at"]) / 3600
        if hours_since >= AUTO_RESUME_HOURS:
            db.set_ai_active(phone, True)
            chat["ai_active"] = 1

    if not chat["ai_active"]:
        logger.info("AI muted for %s (human is handling this chat) — not replying", phone)
        return

    history = db.get_history(phone, limit=20)
    result = await ai.generate_reply(history, text)
    reply_text = result["reply"]
    extracted = result.get("extracted", {})

    # Send reply via BotSpace
    sent_id = await botspace.send_text_message(phone, customer_name, reply_text)
    db.record_bot_sent(sent_id, phone, reply_text)

    db.add_message(phone, "assistant", reply_text)

    # Save + sync extracted info if anything useful was mentioned
    name = extracted.get("name")
    interest = extracted.get("interest")
    budget = extracted.get("budget")
    notes = extracted.get("notes")
    if any([name, interest, budget, notes]):
        db.upsert_customer_info(phone, name=name, interest=interest, budget=budget, notes=notes)
        sheets.upsert_row(phone, name=name or customer_name, interest=interest, budget=budget, notes=notes)


async def handle_outgoing(phone: str, message_id: str, body: dict):
    payload = body.get("payload", {}).get("payload", {})
    text = payload.get("text", "")

    # First check: exact ID match (fast path, works when BotSpace's IDs line up).
    if message_id and db.was_sent_by_bot(message_id):
        return

    # Fallback: content + time-window match. This covers cases where BotSpace's
    # webhook ID differs from the ID returned by the send API.
    if text and db.was_recently_sent_by_bot(phone, text):
        return

    # Neither matched — this really was typed by a human agent. Mute the bot.
    logger.info("Human agent reply detected for %s — muting AI", phone)
    db.mark_human_reply(phone)


@app.post("/resume/{phone}")
def resume_bot(phone: str):
    """Manually hand control back to the AI for a given phone number."""
    db.set_ai_active(phone, True)
    return {"status": "ok", "phone": phone, "ai_active": True}


@app.post("/pause/{phone}")
def pause_bot(phone: str):
    """Manually mute the AI for a given phone number."""
    db.set_ai_active(phone, False)
    return {"status": "ok", "phone": phone, "ai_active": False}


@app.get("/status/{phone}")
def status(phone: str):
    chat = db.get_or_create_chat(phone)
    history = db.get_history(phone, limit=50)
    return {"chat": chat, "history": history}
