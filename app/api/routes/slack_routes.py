# api/routes/slack_events.py

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
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


async def process_slack_message(question: str, channel_id: str, ts: str | None):
    """
    Traitement du message Slack en tâche de fond.
    Slack n'attend pas ce traitement, donc aucun doublon.
    """

    system_prompt = (
        "Tu t'appelles Badinter. Tu es l'assistant juridique de la junior entreprise EPF Projets, spécialisé dans le cadre légal des Junior Entreprises."
        "Réponds en français, de manière claire et utile pour les membres."
    )

    response, sources, template_path = generate_answer(
        question,
        [],
        system_prompt
    )

    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
    }

    payload = {
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



@router.post("/events", response_model=None)
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint appelé par Slack 
    """
    body = await request.body()
    data = await request.json()

    event = data.get("event", {}) or {}
    # ack de slack quand on envoie un message, donc on répond ok
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return JSONResponse(content={"ok": True})

    retry_num = request.headers.get("X-Slack-Retry-Num")
    if retry_num is not None:
        reason = request.headers.get("X-Slack-Retry-Reason")
        event_id = data.get("event_id")
        print(f"[Slack] Retry ignoré num={retry_num} reason={reason} event_id={event_id}")
        return JSONResponse(content={"ok": True})
    
    verify_slack_signature(request, body)

    # pour config la connexion slack
    if data.get("type") == "url_verification":
        return JSONResponse(content={"challenge": data["challenge"]})
    

    event_type = event.get("type")
    
    if event_type == "app_mention":
        raw_text = event.get("text", "") or ""
        channel_id = event.get("channel")
        ts = event.get("ts")  

        parts = raw_text.split(">", 1)
        question = parts[1].strip() if len(parts) > 1 else raw_text.strip()


        ack = JSONResponse(content={"ok": True})


        if not question:
            question = "Peux-tu reformuler ta question ?"


        background_tasks.add_task(
            process_slack_message,
            question,
            channel_id,
            ts
        )

        return ack


    return JSONResponse(content={"ok": True})
