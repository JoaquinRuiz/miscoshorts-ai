"""Ask an LLM (Gemini or any OpenAI-compatible API) for the best Shorts in a transcript."""

from __future__ import annotations

from typing import Protocol

from miscoshorts.clips import Clip, parse_clips, select_best, validate_clip
from miscoshorts.config import Settings

# The transcript goes first and the instructions last: if a local server's context is too small
# it drops the start of the prompt, and the instructions must survive.
PROMPT = """Actúa como editor de vídeo profesional especializado en contenido viral.
Esta es la transcripción de un vídeo, con marcas de tiempo en segundos ([inicio-fin] texto):

<transcripcion>
{transcript}
</transcripcion>

Encuentra los {count} mejores segmentos de la transcripción para Shorts virales de {min_s:g} a {max_s:g} segundos.

Reglas:
- Cada segmento debe tener sentido por sí solo, con un gancho al principio.
- Empieza y termina en frases completas, usando los tiempos de la transcripción.
- Cada segmento dura entre {min_s:g} y {max_s:g} segundos ("end" - "start").
- Los segmentos no se pueden solapar.
- "start" y "end" son números en segundos, dentro de la transcripción.
- "score" es el potencial viral del 1 al 10.
- "title", "description" y "hashtags" en el mismo idioma que la transcripción.

Responde SOLO con JSON válido, sin texto adicional, con este formato:
{{"clips": [{{"title": "Título gancho", "start": 120.5, "end": 155.0, "score": 8,
"reason": "Por qué funciona", "description": "Descripción para YouTube/TikTok/Reels",
"hashtags": ["#shorts", "#tema"]}}]}}
"""

RETRY = """
Tu respuesta anterior no era válida:
{errors}
Vuelve a responder SOLO con el JSON, corrigiendo esos problemas.
"""

_CLIP_FIELDS = {
    "title": {"type": "string"},
    "start": {"type": "number"},
    "end": {"type": "number"},
    "score": {"type": "number"},
    "reason": {"type": "string"},
    "description": {"type": "string"},
    "hashtags": {"type": "array", "items": {"type": "string"}},
}


def clips_schema(strict: bool = True) -> dict:
    """JSON Schema of the answer. ``strict`` adds ``additionalProperties: false`` (OpenAI strict mode)."""
    item = {"type": "object", "properties": _CLIP_FIELDS, "required": list(_CLIP_FIELDS)}
    root = {
        "type": "object",
        "properties": {"clips": {"type": "array", "items": item}},
        "required": ["clips"],
    }
    if strict:
        item["additionalProperties"] = False
        root["additionalProperties"] = False
    return root


class Backend(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


class GeminiBackend:
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise RuntimeError(
                "Falta GEMINI_API_KEY. Ponla en el entorno o en un archivo .env, "
                "o usa un modelo local con --backend openai."
            )
        from google import genai
        from google.genai import types

        self.name = settings.gemini_model
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._config = types.GenerateContentConfig(
            temperature=settings.temperature,
            response_mime_type="application/json",
            response_json_schema=clips_schema(strict=False),
        )

    def complete(self, prompt: str) -> str:
        response = self._client.models.generate_content(model=self.name, contents=prompt, config=self._config)
        return response.text or ""


# Structured output, best first. Servers that reject one (HTTP 400) get the next one.
_RESPONSE_FORMATS = [
    {"type": "json_schema", "json_schema": {"name": "shorts", "schema": clips_schema(), "strict": True}},
    {"type": "json_object"},
    None,
]


class OpenAIBackend:
    def __init__(self, settings: Settings):
        import httpx
        from openai import OpenAI

        self.name = settings.openai_model
        self._temperature = settings.temperature
        # Local models on long transcripts can be slow, so allow a generous timeout.
        self._client = OpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            timeout=httpx.Timeout(7200),
        )
        self._format = 0

    def complete(self, prompt: str) -> str:
        import openai

        kwargs = dict(
            model=self.name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
        )
        while True:
            response_format = _RESPONSE_FORMATS[self._format]
            try:
                if response_format is None:
                    response = self._client.chat.completions.create(**kwargs)
                else:
                    response = self._client.chat.completions.create(**kwargs, response_format=response_format)
                return response.choices[0].message.content or ""
            except openai.BadRequestError:
                if response_format is None:
                    raise
                self._format += 1  # remembered for the next calls


def make_backend(settings: Settings) -> Backend:
    if settings.backend == "gemini":
        return GeminiBackend(settings)
    if settings.backend == "openai":
        return OpenAIBackend(settings)
    raise ValueError(f"Backend no soportado: {settings.backend!r} (usa 'gemini' u 'openai')")


def format_transcript(segments: list[dict]) -> str:
    return "\n".join(f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text'].strip()}" for seg in segments)


def chunk_segments(segments: list[dict], max_chars: int, overlap_seconds: float = 60) -> list[list[dict]]:
    """Split segments into chunks whose formatted text fits in ``max_chars``.

    Consecutive chunks overlap by about ``overlap_seconds`` so a good clip that crosses a
    boundary is still seen whole by one of them.
    """
    chunks: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for seg in segments:
        line = len(seg["text"]) + 20
        if current and size + line > max_chars:
            chunks.append(current)
            boundary = current[-1]["end"]
            current = [s for s in current if s["start"] >= boundary - overlap_seconds]
            # Never carry over so much that the next chunk can't make progress.
            while current and sum(len(s["text"]) + 20 for s in current) > max_chars // 2:
                current.pop(0)
            size = sum(len(s["text"]) + 20 for s in current)
        current.append(seg)
        size += line
    if current:
        chunks.append(current)
    return chunks


def _ask(
    backend: Backend,
    segments: list[dict],
    count: int,
    settings: Settings,
    duration: float | None,
    log,
) -> list[Clip]:
    prompt = PROMPT.format(
        count=count,
        min_s=settings.min_seconds,
        max_s=settings.max_seconds,
        transcript=format_transcript(segments),
    )
    errors: list[str] = []
    for attempt in range(2):
        answer = backend.complete(prompt if attempt == 0 else prompt + RETRY.format(errors="\n".join(errors)))
        try:
            proposed = parse_clips(answer)
        except ValueError as exc:
            errors = [f"- {exc}"]
            log(f"⚠️  Respuesta no válida, reintentando… ({exc})")
            continue
        valid, errors = [], []
        for clip in proposed:
            problems = validate_clip(clip, duration, settings.min_seconds, settings.max_seconds)
            if problems:
                errors.append(f"- {clip.start:g}-{clip.end:g}: " + "; ".join(problems))
            else:
                valid.append(clip)
        if valid:
            return valid
        log("⚠️  Ningún segmento válido, reintentando…\n" + "\n".join(errors))
    return []


def find_clips(
    segments: list[dict],
    settings: Settings,
    duration: float | None = None,
    backend: Backend | None = None,
    log=print,
) -> list[Clip]:
    """Return up to ``settings.count`` valid, non-overlapping clips, best first."""
    backend = backend or make_backend(settings)
    chunks = chunk_segments(segments, settings.effective_chunk_chars)
    log(f"✨ Consultando a {backend.name} ({len(chunks)} bloque{'s' if len(chunks) > 1 else ''})...")
    candidates: list[Clip] = []
    for i, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            log(f"   bloque {i}/{len(chunks)}: {chunk[0]['start']:.0f}s-{chunk[-1]['end']:.0f}s")
        candidates += _ask(backend, chunk, settings.count, settings, duration, log)
    return select_best(candidates, settings.count)
