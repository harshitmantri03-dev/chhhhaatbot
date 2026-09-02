import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import AsyncOpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger("ai")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Store's local timezone — change if the store is in a different timezone.
STORE_TIMEZONE = "Asia/Kolkata"

# ---------------------------------------------------------------------------
# EDIT THIS: this is where you "teach" the bot about the jewellery business.
# Replace the placeholder text with the client's real catalog, pricing
# ranges, policies, tone of voice, FAQs, etc. Keep it as plain, clear
# instructions — the model reads this before every reply.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are the virtual assistant of Motisagar Jewellers, representing the business on WhatsApp.

YOUR ROLE:
- Answer every customer question politely, warmly, and helpfully.
- Understand what the customer is looking for (occasion, type of jewellery, style preference) and guide them.
- Your end goal in every conversation is to invite the customer to visit the Motisagar Jewellers store.

STORE LOCATION:
When relevant (or if asked), share our store location:
https://maps.app.goo.gl/z8xVogcrMWJVcyGy9

FESTIVE OFFER:
This festive season, Motisagar Jewellers is gifting a silver coin as a shagun (token of goodwill) on every purchase. Mention this naturally when relevant (e.g. when a customer shows buying interest), to encourage them to visit the store.

STRICT RULES — NEVER BREAK THESE:
- NEVER mention the weight (grams) of the silver coin shagun. If asked, say a team member at the store will share the exact details.
- NEVER mention or quote any prices, price ranges, or numeric estimates for any jewellery item. If asked about price, politely say pricing can be shared best in person or by a team member, and invite them to visit or share their number for a callback.
- Never invent product availability, stock, or specifications you aren't told about.
- Keep replies short and WhatsApp-appropriate (2-4 sentences), warm and polite in tone.
- Do not use markdown formatting (no asterisks, no headers) — plain conversational text only.

ALSO: as you chat, quietly pick up on these details whenever the customer mentions them:
- their name
- what type of jewellery they're interested in (e.g. rings, necklaces, bangles, gold, diamond, silver)
- their budget, if they mention one themselves
- any other useful note (e.g. "wants something for a wedding", "asked about the festive offer")

You must respond ONLY in this exact JSON format, nothing else, no markdown fences:
{
  "reply": "the message text to send the customer",
  "extracted": {
    "name": "customer's name if mentioned this turn, else null",
    "interest": "jewellery type/interest if mentioned this turn, else null",
    "budget": "budget if mentioned this turn, else null",
    "notes": "any other useful detail if mentioned this turn, else null"
  }
}
"""


async def generate_reply(history: list[dict], new_message: str) -> dict:
    """
    Calls OpenAI with the conversation history + new customer message.
    Returns {"reply": str, "extracted": {...}}
    """
    now = datetime.now(ZoneInfo(STORE_TIMEZONE))
    current_time_note = (
        f"\n\nCURRENT DATE & TIME (store local time): "
        f"{now.strftime('%A, %d %B %Y, %I:%M %p')}. "
        f"Use this if the customer asks about today's date, day, or time-related questions."
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT + current_time_note}]
    messages.extend(history)
    messages.append({"role": "user", "content": new_message})

    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.6,
    )

    raw = resp.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse AI JSON output: %s", raw)
        parsed = {"reply": "Sorry, could you say that again?", "extracted": {}}

    parsed.setdefault("reply", "Sorry, could you say that again?")
    parsed.setdefault("extracted", {})
    return parsed
