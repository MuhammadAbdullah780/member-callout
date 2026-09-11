"""
AI draft-cleanup adapter.

Turns messy leader-authored text into a title/body/push-preview draft. Never
sends anything and never blocks a manual send: a slow, erroring, or
unconfigured provider surfaces a clear error while manual title/body entry
keeps working.
"""

import os

import requests
from requests.exceptions import RequestException

PUSH_PREVIEW_MAX_LENGTH = 120
REQUEST_TIMEOUT_SECONDS = 8


class AIProviderError(Exception):
    """Raised when the AI provider is unavailable, errors, or times out."""


def is_configured():
    return bool(os.environ.get('AI_PROVIDER_API_KEY'))


def generate_draft(raw_text):
    """
    Returns {'title': str, 'body': str, 'push_preview': str} from messy source text.

    Raises AIProviderError if no provider is configured, the request times out,
    or the provider returns an error. Callers must treat the result as a draft
    only - it never implies approval or sends anything.

    Talks to OpenRouter's OpenAI-compatible chat completions endpoint, so any
    model slug OpenRouter serves can be used via AI_PROVIDER_MODEL.
    """
    if not is_configured():
        raise AIProviderError('AI draft assistance is not configured for this deployment.')

    api_key = os.environ.get('AI_PROVIDER_API_KEY')
    model = os.environ.get('AI_PROVIDER_MODEL', 'cohere/north-mini-code:free')

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'max_tokens': 512,
                'messages': [
                    {
                        'role': 'system',
                        'content': (
                            'Rewrite the union announcement below into a clear title, '
                            'body, and a push notification preview of 120 characters or '
                            'fewer. Respond with exactly three lines prefixed "TITLE:", '
                            '"BODY:", and "PUSH:".'
                        ),
                    },
                    {'role': 'user', 'content': raw_text},
                ],
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except RequestException as exc:
        raise AIProviderError(f'AI provider request failed: {exc}') from exc

    try:
        text = response.json()['choices'][0]['message']['content']
    except (KeyError, IndexError, ValueError) as exc:
        raise AIProviderError('AI provider returned an unexpected response.') from exc

    return _parse_draft(text)


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
        raise AIProviderError('AI provider returned an unparseable draft.')

    return {'title': title, 'body': body, 'push_preview': push_preview}
