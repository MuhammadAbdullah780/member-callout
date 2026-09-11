"""
AI draft-cleanup adapter.

Turns messy leader-authored text into a title/body/push-preview draft. Never
sends anything and never blocks a manual send: a slow, erroring, or
unconfigured provider surfaces a clear error while manual title/body entry
keeps working.

Integration notes (the part that matters more than the prompt):

- Every failure mode is funnelled into AIProviderError, so the view always
  answers 502 with a readable message instead of leaking a 500.
- Transient failures (timeout, 429, 5xx) are retried once with a short
  backoff, then fall through to the next configured model. Free OpenRouter
  endpoints rate-limit often enough that a single upstream 429 should not
  look like a broken feature.
- max_tokens is generous because reasoning models spend tokens on a hidden
  reasoning channel first. Too small a budget returns finish_reason="length"
  with content=None - a successful HTTP 200 carrying no draft.
"""

import os
import time

import requests
from requests.exceptions import RequestException

PUSH_PREVIEW_MAX_LENGTH = 120
REQUEST_TIMEOUT_SECONDS = 20

# Reasoning models emit a hidden reasoning channel before the visible answer.
# 512 was not enough: the budget was exhausted before any content was produced.
MAX_TOKENS = 2000

RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
ATTEMPTS_PER_MODEL = 2
RETRY_BACKOFF_SECONDS = 1.5

DEFAULT_MODELS = 'cohere/north-mini-code:free,google/gemma-4-31b-it:free'

SYSTEM_PROMPT = (
    'Rewrite the union announcement below into a clear title, body, and a push '
    'notification preview of 120 characters or fewer. Respond with exactly three '
    'lines prefixed "TITLE:", "BODY:", and "PUSH:".'
)


class AIProviderError(Exception):
    """Raised when the AI provider is unavailable, errors, or times out."""


def is_configured():
    return bool(os.environ.get('AI_PROVIDER_API_KEY'))


def _configured_models():
    """AI_PROVIDER_MODEL is a comma-separated preference order, tried left to right."""
    raw = os.environ.get('AI_PROVIDER_MODEL') or DEFAULT_MODELS
    return [slug.strip() for slug in raw.split(',') if slug.strip()]


def generate_draft(raw_text):
    """
    Returns {'title': str, 'body': str, 'push_preview': str} from messy source text.

    Raises AIProviderError if no provider is configured, every configured model
    fails, or the response cannot be parsed. Callers must treat the result as a
    draft only - it never implies approval and never sends anything.
    """
    if not is_configured():
        raise AIProviderError('AI draft assistance is not configured for this deployment.')

    api_key = os.environ['AI_PROVIDER_API_KEY']
    last_error = 'no model configured'

    for model in _configured_models():
        for attempt in range(ATTEMPTS_PER_MODEL):
            try:
                return _parse_draft(_request_completion(api_key, model, raw_text))
            except _TransientProviderError as exc:
                last_error = f'{model}: {exc}'
                if attempt + 1 < ATTEMPTS_PER_MODEL:
                    time.sleep(RETRY_BACKOFF_SECONDS)
            except AIProviderError as exc:
                # Permanent for this model (403/404, unparseable). Try the next one.
                last_error = f'{model}: {exc}'
                break

    raise AIProviderError(f'AI draft is temporarily unavailable ({last_error}).')


class _TransientProviderError(AIProviderError):
    """A failure worth retrying on the same model."""


def _request_completion(api_key, model, raw_text):
    """Returns the assistant's visible text, or raises an AIProviderError subclass."""
    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'max_tokens': MAX_TOKENS,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': raw_text},
                ],
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except RequestException as exc:
        # Timeouts and connection resets are worth one more try.
        raise _TransientProviderError(f'request failed: {exc}') from exc

    if response.status_code in RETRYABLE_STATUS:
        raise _TransientProviderError(f'provider returned {response.status_code}')
    if response.status_code >= 400:
        raise AIProviderError(f'provider returned {response.status_code}')

    try:
        message = response.json()['choices'][0]['message']
    except (KeyError, IndexError, ValueError) as exc:
        raise AIProviderError('provider returned an unexpected response') from exc

    content = message.get('content')
    if not content:
        # A 200 with no visible content: the token budget went to the hidden
        # reasoning channel. Retrying can succeed, so treat it as transient.
        raise _TransientProviderError('provider returned an empty draft')

    return content


def _parse_draft(text):
    title, body, push_preview = '', '', ''
    for line in text.splitlines():
        if line.startswith('TITLE:'):
            title = line.removeprefix('TITLE:').strip()
        elif line.startswith('BODY:'):
            body = line.removeprefix('BODY:').strip()
        elif line.startswith('PUSH:'):
            push_preview = line.removeprefix('PUSH:').strip()[:PUSH_PREVIEW_MAX_LENGTH]

    if not title and not body:
        raise AIProviderError('provider returned an unparseable draft')

    return {'title': title, 'body': body, 'push_preview': push_preview}
