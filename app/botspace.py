import httpx
import logging

from app.config import BOTSPACE_API_KEY, BOTSPACE_CHANNEL_ID, BOTSPACE_BASE_URL

logger = logging.getLogger("botspace")

HEADERS = {
    "Authorization": f"Bearer {BOTSPACE_API_KEY}",
    "Content-Type": "application/json",
}


async def send_text_message(phone: str, name: str, text: str) -> str | None:
    """
    Sends a plain text WhatsApp message via BotSpace.
    Returns the BotSpace message id if available (used to mark this
    message as 'sent by bot' so the outgoing webhook can recognize it).
    """
    url = f"{BOTSPACE_BASE_URL}/{BOTSPACE_CHANNEL_ID}/message/send-message"
    payload = {
        "name": name or "Customer",
        "phone": phone,
        "text": text,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=HEADERS, json=payload)
        resp.raise_for_status()
        data = resp.json()
        # NOTE: confirm the exact key BotSpace returns for the message id
        # (check the Swagger response schema for this endpoint) and adjust
        # below if it isn't "id".
        message_id = data.get("id") or data.get("messageId") or data.get("_id")
        logger.info("Sent message to %s, id=%s", phone, message_id)
        return message_id


async def send_template_message(phone: str, name: str, template_id: str,
                                  variables: list[str], media_variable: str = None,
                                  file_name: str = None) -> str | None:
    """Sends a WhatsApp template message (e.g. the initial marketing blast)."""
    url = f"{BOTSPACE_BASE_URL}/{BOTSPACE_CHANNEL_ID}/message/send-template"
    payload = {
        "name": name or "Customer",
        "phone": phone,
        "templateId": template_id,
        "variables": variables,
    }
    if media_variable:
        payload["mediaVariable"] = media_variable
    if file_name:
        payload["fileName"] = file_name

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=HEADERS, json=payload)
        resp.raise_for_status()
        data = resp.json()
        message_id = data.get("id") or data.get("messageId") or data.get("_id")
        return message_id
