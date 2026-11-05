import json
import pytest
from vocal.engine.client import LLMError, generate_proposal, parse_response
from vocal.context.collector import EnvironmentContext


def proposal():
    return {"command": "git status", "explanation": "Shows status.", "risk_level": "LOW", "target_binary": "git", "requires_sudo": False, "is_destructive": False}


def test_parse_valid():
    assert parse_response(json.dumps(proposal())).command == "git status"


@pytest.mark.parametrize("change", [{"risk_level": "UNKNOWN"}, {"requires_sudo": "false"}, {"extra": "x"}, {"command": ""}])
def test_reject_invalid(change):
    data = proposal() | change
    with pytest.raises(LLMError):
        parse_response(json.dumps(data))


def test_reject_markdown_and_missing_key():
    with pytest.raises(LLMError):
        parse_response('```json\n{}\n```')
    ctx = EnvironmentContext(os="Linux", shell="bash", cwd="/tmp")
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        generate_proposal("status", ctx, {"provider": "openai"})


def test_openai_request_and_response(monkeypatch):
    from types import SimpleNamespace
    import openai
    called = {}
    model = parse_response(json.dumps(proposal()))
    def parse(**kwargs):
        called.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=model, refusal=None))])
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse))))
    ctx = EnvironmentContext(os="Linux", shell="bash", cwd="/tmp")
    result = generate_proposal("git status", ctx, {"provider": "openai", "openai_api_key": "test"}, {"exit_code": 1})
    assert result == model
    assert called["response_format"] is type(model)
    payload = json.loads(called["messages"][1]["content"])
    assert payload["previous_failure"]["exit_code"] == 1
    assert payload["environment"]["cwd"] == "/tmp"


def test_gemini_request_and_response(monkeypatch):
    from types import SimpleNamespace
    from google import genai
    called = {}
    def generate_content(**kwargs):
        called.update(kwargs)
        return SimpleNamespace(text=json.dumps(proposal()))
    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    ctx = EnvironmentContext(os="Linux", shell="bash", cwd="/tmp")
    assert generate_proposal("git status", ctx, {"provider": "gemini", "gemini_api_key": "test"}).command == "git status"
    assert called["config"].response_mime_type == "application/json"
