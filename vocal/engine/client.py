import json
from .prompts import SYSTEM_PROMPT
from .schema import CommandProposal
from ..context.collector import EnvironmentContext


class LLMError(Exception):
    pass


def parse_response(raw: str) -> CommandProposal:
    try:
        return CommandProposal.model_validate_json(raw)
    except (ValueError, TypeError) as exc:
        raise LLMError(f"Invalid structured response from model: {exc}") from exc


def generate_proposal(query: str, context: EnvironmentContext, settings: dict, failure: dict | None = None) -> CommandProposal:
    payload = json.dumps({"query": query, "environment": context.model_dump(), "previous_failure": failure}, ensure_ascii=False)
    provider = settings.get("provider", "openai").lower()
    try:
        if provider == "openai":
            key = settings.get("openai_api_key")
            if not key:
                raise LLMError("Set OPENAI_API_KEY or configure openai_api_key in ~/.vocal/config.json.")
            from openai import OpenAI
            response = OpenAI(api_key=key, timeout=60).chat.completions.parse(
                model=settings.get("model") or "gpt-4o-mini",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": payload}],
                response_format=CommandProposal,
            )
            message = response.choices[0].message
            if message.refusal:
                raise LLMError(f"Model refused the request: {message.refusal}")
            if message.parsed is None:
                raise LLMError("Model returned no structured response.")
            return message.parsed
        if provider == "gemini":
            key = settings.get("gemini_api_key")
            if not key:
                raise LLMError("Set GEMINI_API_KEY or configure gemini_api_key in ~/.vocal/config.json.")
            from google import genai
            from google.genai import types
            response = genai.Client(api_key=key).models.generate_content(
                model=settings.get("model") or "gemini-2.5-flash", contents=payload,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, response_mime_type="application/json", response_json_schema=CommandProposal.model_json_schema()),
            )
            return parse_response(response.text or "")
        raise LLMError(f"Unsupported provider: {provider}. Choose openai or gemini.")
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"Model request failed: {exc}") from exc
