# api/routes/slack_events.py

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from core.security import verify_slack_signature
import hmac
import hashlib
import time
import os
import httpx

from rag.answer import generate_answer

router = APIRouter(
    prefix="/slack",
    tags=["Slack"],
)

SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]


@router.post("/events", response_model=None)
async def slack_events(request: Request):
    """
    Endpoint appelé par Slack 
    """
    body = await request.body()
    verify_slack_signature(request, body)

    data = await request.json()

    # pour config la connexion slack
    if data.get("type") == "url_verification":
        return JSONResponse(content={"challenge": data["challenge"]})

    event = data.get("event", {}) or {}
    # ack de slack quand on envoie un message, donc on répond ok
    if event.get("subtype") == "bot_message":
        return JSONResponse(content={"ok": True})

    event_type = event.get("type")
    
    if event_type == "app_mention":
        raw_text = event.get("text", "") or ""
        channel_id = event.get("channel")
        ts = event.get("ts")  

        parts = raw_text.split(">", 1)
        question = parts[1].strip() if len(parts) > 1 else raw_text.strip()

        if not question:
            question = "Peux-tu reformuler ta question ?"

        system_prompt = (
            "Tu es Badinter, le chatbot de la Junior-Entreprise. "
            "Réponds en français, de manière claire et utile pour les membres."
        )
        conversation_history: list = []

        response, sources, template_path = generate_answer(
            question,
            conversation_history,
            system_prompt,
        )

        headers = {
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        }    

        payload: dict = {
            "channel": channel_id,
            "text": response,
        }
        if ts:
            payload["thread_ts"] = ts

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers=headers,
                json=payload,
            )
            data = r.json()
            if not data.get("ok"):
                print("Erreur Slack:", data)

    return JSONResponse(content={"ok": True})
