import httpx
import logging

from app.config import BOTSPACE_API_KEY, BOTSPACE_CHANNEL_ID, BOTSPACE_BASE_URL

logger = logging.getLogger("botspace")

HEADERS = {
    "Content-Type": "application/json",
    "accept": "application/json",
}


async def send_text_message(phone: str, name: str, text: str) -> str | None:
    """
    Sends a plain text WhatsApp message via BotSpace.
    Returns the BotSpace message id if available (used to mark this
    message as 'sent by bot' so the outgoing webhook can recognize it).
    """
    url = f"{BOTSPACE_BASE_URL}/{BOTSPACE_CHANNEL_ID}/message/send-message"
    params = {"apiKey": BOTSPACE_API_KEY}
    payload = {
        "name": name or "Customer",
        "phone": phone,
        "text": text,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=HEADERS, params=params, json=payload)
        if resp.status_code >= 400:
            logger.error("BotSpace send-message failed (%s): %s", resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()
        # BotSpace nests the id under "data": {"id": "...", ...}
        inner = data.get("data", data)
        message_id = inner.get("id") or inner.get("messageId") or inner.get("_id")
        logger.info("Sent message to %s, id=%s", phone, message_id)
        return message_id


async def send_template_message(phone: str, name: str, template_id: str,
                                  variables: list[str], media_variable: str = None,
                                  file_name: str = None) -> str | None:
    """Sends a WhatsApp template message (e.g. the initial marketing blast)."""
    url = f"{BOTSPACE_BASE_URL}/{BOTSPACE_CHANNEL_ID}/message/send-template"
    params = {"apiKey": BOTSPACE_API_KEY}
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
        resp = await client.post(url, headers=HEADERS, params=params, json=payload)
        if resp.status_code >= 400:
            logger.error("BotSpace send-template failed (%s): %s", resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()
        inner = data.get("data", data)
        message_id = inner.get("id") or inner.get("messageId") or inner.get("_id")
        return message_id
