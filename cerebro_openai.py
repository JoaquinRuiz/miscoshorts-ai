import os
import re

import httpx
from openai import OpenAI

# Any OpenAI-compatible endpoint works. Common local defaults:
#   Ollama    -> http://localhost:11434/v1
#   LM Studio -> http://localhost:1234/v1
#   llama.cpp -> http://localhost:8080/v1
BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "none")
# Model name as your server knows it (e.g. "qwen3:30b" in Ollama).
MODEL_NAME = os.getenv("OPENAI_MODEL", "qwen3:30b")

# Local models on long transcripts can be slow, so allow a generous timeout.
client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=httpx.Timeout(7200))

# Reasoning models may prepend their chain of thought in these tags.
_THINK_TAGS = re.compile(r"<(think|thinking)>.*?</\1>", re.DOTALL | re.IGNORECASE)


def encontrar_clip_viral(segmentos_whisper):
    print(f"✨ Consultando a {MODEL_NAME} (con timestamps)...")

    texto_con_tiempos = ""
    for seg in segmentos_whisper:
        texto_con_tiempos += f"[{seg['start']:.1f}s] {seg['text']}\n"

    prompt = f"""
    Actúa como editor de video profesional. Analiza esta transcripción timestamped.
    Identifica EL MEJOR segmento para un Short viral (30-60 seg).

    Transcripción:
    {texto_con_tiempos}

    Responde SOLO con este formato exacto (sin explicaciones extra):
    TITULO: [Escribe un título gancho aquí]
    INICIO: [Solo el número del segundo, ej: 120.5]
    FIN: [Solo el número del segundo, ej: 155.0]
    RAZON: [Breve motivo]
    """

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    return _THINK_TAGS.sub("", response.choices[0].message.content or "").strip()
