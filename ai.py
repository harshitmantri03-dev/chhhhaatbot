import json
import logging
from openai import AsyncOpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger("ai")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# EDIT THIS: this is where you "teach" the bot about the jewellery business.
# Replace the placeholder text with the client's real catalog, pricing
# ranges, policies, tone of voice, FAQs, etc. Keep it as plain, clear
# instructions — the model reads this before every reply.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are a friendly, knowledgeable WhatsApp sales assistant for [CLIENT JEWELLERY BUSINESS NAME].

ABOUT THE BUSINESS (placeholder — replace with real info):
- We sell gold, diamond, and silver jewellery: rings, necklaces, earrings, bangles.
- Price ranges: silver from ₹1,500, gold from ₹15,000, diamond from ₹25,000.
- We offer custom design orders and free resizing within 15 days.
- Store location / hours: [ADD DETAILS]

YOUR JOB:
- Answer customer questions helpfully and warmly, like a real sales assistant would.
- Ask about their preferences (occasion, budget, metal type, style) to guide them.
- Never make up specific prices, stock availability, or promises you're not told about.
- If you don't know something, say a team member will follow up shortly.
- Keep replies short and WhatsApp-appropriate (2-4 sentences, no long paragraphs).
- Do not use markdown formatting (no asterisks, no headers) — plain conversational text only.

ALSO: as you chat, quietly pick up on these details whenever the customer mentions them:
- their name
- what type of jewellery they're interested in (e.g. rings, necklaces, bangles, gold, diamond)
- their budget, if mentioned
- any other useful note (e.g. "wants something for a wedding")

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
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
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
