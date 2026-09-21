"""Capa LLM: contrato, fábrica, prompts y backends por proveedor."""

from .errors import (
    GEMINI_QUOTA_USER_MESSAGE,
    LLM_QUOTA_USER_MESSAGE,
    LLM_UNAVAILABLE_USER_MESSAGE,
    is_model_unavailable,
    is_quota_or_rate_limit,
    llm_user_message,
    should_backoff_gemini,
)
from .factory import get_cv_llm_backend, reset_cv_llm_backend_cache
from .protocol import CvLlmBackend

__all__ = [
    "CvLlmBackend",
    "GEMINI_QUOTA_USER_MESSAGE",
    "LLM_QUOTA_USER_MESSAGE",
    "LLM_UNAVAILABLE_USER_MESSAGE",
    "get_cv_llm_backend",
    "is_model_unavailable",
    "is_quota_or_rate_limit",
    "llm_user_message",
    "reset_cv_llm_backend_cache",
    "should_backoff_gemini",
]
