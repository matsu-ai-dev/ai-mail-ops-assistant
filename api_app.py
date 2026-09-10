import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

import mail_classifier


app = FastAPI(title="AI Mail Ops Assistant")


class ClassifyRequest(BaseModel):
    subject: str
    sender: str
    body: str


class ClassifyResponse(BaseModel):
    folder: str | None
    ai_response: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/classify", response_model=ClassifyResponse)
def classify(mail: ClassifyRequest):
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

    try:
        with OpenAI(api_key=api_key) as client:
            response_text = mail_classifier.ask_ai(
                client, mail.subject, mail.sender, mail.body
            )
    except OpenAIError:
        raise HTTPException(status_code=502, detail="AI classification failed") from None

    if not isinstance(response_text, str) or not response_text.strip():
        raise HTTPException(status_code=502, detail="AI returned no text")

    return ClassifyResponse(
        folder=mail_classifier.extract_folder(response_text),
        ai_response=response_text,
    )
