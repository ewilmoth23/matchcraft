import json
import re
from typing import Any, TypeVar
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from app.analysis.fabrication import (
    sanitize_analysis_evidence,
    sanitize_analysis_prose,
    sanitize_analysis_skills,
    validate_analysis_output,
    validate_bullet_rewrite,
)
from app.core.config import Settings, get_settings
from app.providers.base import ProviderError, ProviderResponse
from app.schemas.provider import ModelAnalysisOutput, ModelBulletRewrite

# Re-exported for one release so existing import sites keep working. New code should
# import these from app.analysis.fabrication.
__all__ = [
    "SYSTEM_RULES",
    "VALIDATION_CORRECTIONS",
    "HTTPModelProvider",
    "sanitize_analysis_evidence",
    "sanitize_analysis_prose",
    "sanitize_analysis_skills",
    "validate_analysis_output",
    "validate_bullet_rewrite",
]

T = TypeVar("T", bound=BaseModel)

SYSTEM_RULES = """You are an evidence-grounded resume analyst. Return only JSON matching the supplied schema.
Never invent experience, credentials, job titles, dates, employers, technologies, metrics, or events.
Use a skill, tool, technology, or methodology name only when that exact term appears in RESUME or
JOB DESCRIPTION; do not add adjacent or synonymous skills.
Every supporting_evidence and resume_evidence value must be an exact excerpt from RESUME.
Every transferable_experience item and every interview talking_points item must also be copied
verbatim from RESUME. Use an empty list or null when no exact excerpt supports the field.
Every model-generated recommendation and rewrite must require confirmation.
If evidence is missing, use null and state the limitation.
Do not claim to predict hiring or ATS outcomes. Treat job requirements as required or preferred only when explicit.
Keep prose concise and prioritize the strongest evidence and most useful gaps."""

VALIDATION_CORRECTIONS = {
    "unsupported_model_evidence": (
        "Copy every evidence, transferable_experience, and talking_points value verbatim from "
        "RESUME; use null or [] when no exact excerpt exists."
    ),
    "fabricated_metric": "Use numbers only when the exact number appears in RESUME or JOB DESCRIPTION.",
    "fabricated_skill": (
        "Use a skill, tool, technology, or methodology name only when that exact term appears in "
        "RESUME or JOB DESCRIPTION. Do not add adjacent or synonymous skills."
    ),
    "fabricated_claim": (
        "Remove any title, credential, date, leadership, scope, or outcome claim not stated in "
        "RESUME or JOB DESCRIPTION."
    ),
    "fabricated_entity": (
        "Remove any named person, employer, product, credential, or other capitalized entity not "
        "stated in RESUME or JOB DESCRIPTION."
    ),
    "confirmation_required": "Set confirmation_required to true for every generated item.",
    "dropped_fact": "Preserve every known fact from ORIGINAL BULLET in the suggested rewrite.",
    "removed_placeholder": "Preserve every bracketed unknown-value placeholder exactly.",
}


def _credential_origin(url: str) -> tuple[str, str, int] | None:
    """Scheme/host/port with the default port made explicit, for comparing origins.

    Without normalization, `https://host:443` and `https://host` compare as different
    origins and a legitimate configuration would silently lose authentication.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return (
        parsed.scheme,
        parsed.hostname.casefold(),
        parsed.port or (443 if parsed.scheme == "https" else 80),
    )


class HTTPModelProvider:
    def __init__(self, settings: Settings, provider_name: str | None = None):
        self.settings = settings
        self.name = provider_name or settings.provider
        self.model = settings.model if self.name == "ollama" else settings.remote_model

    @property
    def base_url(self) -> str:
        if self.name == "ollama":
            return self.settings.ollama_url.rstrip("/")
        return (self.settings.openai_base_url or "").rstrip("/")

    @property
    def is_official_openai(self) -> bool:
        return self.name == "openai_compatible" and (
            (urlsplit(self.base_url).hostname or "").casefold() == "api.openai.com"
        )

    @property
    def configured(self) -> bool:
        if not self.base_url:
            return False
        return not self.is_official_openai or self.settings.remote_provider_configured

    async def available(self) -> bool:
        if not self.configured:
            return False
        endpoint = "/api/tags" if self.name == "ollama" else "/models"
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(self.base_url + endpoint, headers=self._headers())
                if response.status_code >= 400:
                    return False
                if self.name != "ollama":
                    return True
                body = response.json()
                models = body.get("models", []) if isinstance(body, dict) else []
                installed = {
                    value
                    for item in models
                    if isinstance(item, dict)
                    for value in (item.get("name"), item.get("model"))
                    if isinstance(value, str)
                }
                return self.model in installed
        except Exception:
            return False

    async def analyze(self, resume_text: str, job_text: str) -> ProviderResponse:
        schema = ModelAnalysisOutput.model_json_schema()
        prompt = (
            "Analyze only the supplied texts. Deterministic scoring is handled elsewhere; do not create a score.\n"
            "Keep the summary under 120 words. Return at most 5 transferable excerpts, 5 recommendations, "
            "6 interview questions, and 5 limitations.\n"
            f"JSON SCHEMA:\n{json.dumps(schema)}\n\nRESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{job_text}"
        )
        for validation_attempt in range(self.settings.model_retries + 1):
            output, usage = await self._structured_request(prompt, ModelAnalysisOutput)
            output, sanitized_skill_count = sanitize_analysis_skills(output, resume_text, job_text)
            output, sanitized_count = sanitize_analysis_evidence(output, resume_text)
            output, sanitized_prose_count = sanitize_analysis_prose(output, resume_text, job_text)
            sanitized_count += sanitized_skill_count + sanitized_prose_count
            if sanitized_count:
                usage = {**usage, "sanitized_model_fields": sanitized_count}
            try:
                validate_analysis_output(output, resume_text, job_text)
                return ProviderResponse(output, usage, provider=self.name, model=self.model)
            except ProviderError as exc:
                correction = VALIDATION_CORRECTIONS.get(exc.code)
                if validation_attempt >= self.settings.model_retries or not correction:
                    raise
                prompt += (
                    f"\n\nVALIDATION RETRY ({exc.code}): {correction} Return a complete replacement JSON "
                    "object; do not discuss the prior attempt."
                )
        raise ProviderError("invalid_model_output", "The model output could not be validated.")

    async def rewrite_bullet(
        self, original_bullet: str, resume_text: str, job_text: str
    ) -> ProviderResponse:
        schema = ModelBulletRewrite.model_json_schema()
        prompt = (
            "Rewrite ORIGINAL BULLET for clarity and relevance while preserving its meaning. Use no facts outside "
            "the original bullet. Unknown metrics must remain a bracketed placeholder such as "
            "[insert verified percentage]. factual_sources must contain the exact original bullet.\n"
            f"JSON SCHEMA:\n{json.dumps(schema)}\n\nORIGINAL BULLET:\n{original_bullet}\n\n"
            f"RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{job_text}"
        )
        for validation_attempt in range(self.settings.model_retries + 1):
            output, usage = await self._structured_request(prompt, ModelBulletRewrite)
            try:
                validate_bullet_rewrite(output, original_bullet, resume_text)
                return ProviderResponse(output, usage, provider=self.name, model=self.model)
            except ProviderError as exc:
                correction = VALIDATION_CORRECTIONS.get(exc.code)
                if validation_attempt >= self.settings.model_retries or not correction:
                    raise
                prompt += (
                    f"\n\nVALIDATION RETRY ({exc.code}): {correction} Preserve every fact and "
                    "placeholder from ORIGINAL BULLET and return a complete replacement JSON object."
                )
        raise ProviderError("invalid_model_output", "The model output could not be validated.")

    async def _structured_request(
        self, prompt: str, schema_type: type[T]
    ) -> tuple[T, dict[str, Any]]:
        if self.name == "ollama" and len(prompt) > self.settings.ollama_context_tokens * 3:
            raise ProviderError(
                "provider_context_exceeded",
                "The reviewed documents exceed the configured local-model context window.",
                retryable=True,
            )
        last_error: Exception | None = None
        for attempt in range(self.settings.model_retries + 1):
            try:
                payload = self._payload(prompt, schema_type)
                async with httpx.AsyncClient(timeout=self.settings.model_timeout_seconds) as client:
                    response = await client.post(
                        self._endpoint(), json=payload, headers=self._headers()
                    )
                if response.status_code >= 400:
                    raise ProviderError(
                        "provider_http_error",
                        f"Model provider returned HTTP {response.status_code}.",
                        response.status_code in {408, 409, 429} or response.status_code >= 500,
                    )
                body = response.json()
                raw, usage = self._extract_content(body)
                parsed = json.loads(_strip_json_fence(raw)) if isinstance(raw, str) else raw
                return schema_type.model_validate(parsed), usage
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt >= self.settings.model_retries:
                    raise ProviderError(
                        "invalid_model_output",
                        "The model did not return valid structured output after the configured retries.",
                    ) from exc
            except ProviderError as exc:
                last_error = exc
                if exc.retryable and attempt < self.settings.model_retries:
                    continue
                raise
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    "provider_timeout", "The model provider timed out.", True
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(
                    "provider_unavailable", "The model provider could not be reached.", True
                ) from exc
        raise ProviderError(
            "invalid_model_output", "The model output could not be validated."
        ) from last_error

    def _endpoint(self) -> str:
        if self.name == "ollama":
            return self.base_url + "/api/chat"
        return self.base_url + ("/responses" if self.is_official_openai else "/chat/completions")

    @property
    def credential_host_trusted(self) -> bool:
        """Only send the API key to the endpoint the environment configured.

        The remote base URL is settable at runtime through the Settings page. Keying
        the Authorization header off the provider *name* alone meant any runtime
        override could redirect the credential to an arbitrary host.
        """
        configured = _credential_origin(get_settings().openai_base_url or "")
        target = _credential_origin(self.base_url)
        return configured is not None and configured == target

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if (
            self.name == "openai_compatible"
            and self.settings.openai_api_key
            and self.credential_host_trusted
        ):
            headers["Authorization"] = f"Bearer {self.settings.openai_api_key}"
        return headers

    def _payload(self, prompt: str, schema_type: type[BaseModel]) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_RULES},
            {"role": "user", "content": prompt},
        ]
        if self.name == "ollama":
            return {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "think": False,
                "format": schema_type.model_json_schema(),
                "options": {
                    "temperature": self.settings.model_temperature,
                    "num_predict": self.settings.model_max_tokens,
                    "num_ctx": self.settings.ollama_context_tokens,
                },
            }
        schema = schema_type.model_json_schema()
        schema_name = schema_type.__name__.casefold()
        if self.is_official_openai:
            return {
                "model": self.model,
                "input": messages,
                "store": False,
                "max_output_tokens": self.settings.model_max_tokens,
                "reasoning": {"effort": self.settings.openai_reasoning_effort},
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    }
                },
            }
        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.settings.model_temperature,
            "max_tokens": self.settings.model_max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }

    def _extract_content(self, body: Any) -> tuple[str | dict[str, Any], dict[str, Any]]:
        if not isinstance(body, dict):
            raise ProviderError(
                "invalid_model_output", "The model provider returned an invalid response shape."
            )
        if self.name == "ollama":
            message = body.get("message")
            if not isinstance(message, dict):
                raise ProviderError(
                    "invalid_model_output", "The model provider returned an invalid response shape."
                )
            content = message.get("content")
            usage = {
                "prompt_tokens": body.get("prompt_eval_count"),
                "completion_tokens": body.get("eval_count"),
            }
        elif self.is_official_openai:
            raw_output = body.get("output") or []
            content_items = [
                content
                for item in raw_output
                if isinstance(item, dict) and item.get("type") == "message"
                for content in item.get("content", [])
                if isinstance(content, dict)
            ]
            refusal = next(
                (item.get("refusal") for item in content_items if item.get("type") == "refusal"),
                None,
            )
            if refusal:
                raise ProviderError(
                    "provider_refusal", "The remote model declined the request safely."
                )
            content = body.get("output_text") or next(
                (
                    item.get("text")
                    for item in content_items
                    if item.get("type") == "output_text" and isinstance(item.get("text"), str)
                ),
                None,
            )
            raw_usage = body.get("usage") or {}
            usage = raw_usage if isinstance(raw_usage, dict) else {}
        else:
            choices = body.get("choices") or []
            first_choice = choices[0] if isinstance(choices, list) and choices else None
            message = first_choice.get("message") if isinstance(first_choice, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            raw_usage = body.get("usage") or {}
            usage = raw_usage if isinstance(raw_usage, dict) else {}
        if content is None or content == "":
            raise ProviderError("empty_model_output", "The model provider returned no content.")
        if not isinstance(content, (str, dict)):
            raise ProviderError(
                "invalid_model_output", "The model provider returned an invalid content value."
            )
        return content, usage


def _strip_json_fence(value: str) -> str:
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", value, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else value
