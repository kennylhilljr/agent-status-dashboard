"""Shared pytest configuration: keep the test suite credential-free.

Tests must behave the same on a developer machine with a populated ``.env`` file
or exported provider keys as they do in CI, where neither exists. This module is
imported by pytest before any test module, so it:

* turns ``dotenv.load_dotenv`` into a no-op, so importing modules such as
  ``client.py`` cannot pull a local ``.env`` into the test process, and
* removes provider credentials and other environment-driven settings from
  ``os.environ`` (child processes started by tests inherit the cleaned copy).
"""

import os

import dotenv

# Provider credentials and settings read by the application or its bridges.
_ISOLATED_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "ARCADE_API_KEY",
    "ARCADE_GATEWAY_SLUG",
    "ARCADE_USER_ID",
    "CHATGPT_AUTH_TYPE",
    "CHATGPT_MODEL",
    "CHATGPT_SESSION_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CORS_ALLOWED_ORIGINS",
    "GEMINI_API_KEY",
    "GEMINI_AUTH_TYPE",
    "GEMINI_MODEL",
    "GOOGLE_API_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_CLOUD_LOCATION",
    "GOOGLE_CLOUD_PROJECT",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "KIMI_API_KEY",
    "KIMI_MODEL",
    "LINEAR_API_KEY",
    "MOONSHOT_API_KEY",
    "OPENAI_API_KEY",
    "ORCHESTRATOR_MODEL",
    "SLACK_CHANNEL",
)


def _no_dotenv(*args, **kwargs) -> bool:
    """Stand-in for dotenv.load_dotenv that loads nothing."""
    return False


dotenv.load_dotenv = _no_dotenv

for _name in _ISOLATED_ENV_VARS:
    os.environ.pop(_name, None)
