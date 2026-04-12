"""
AstrBotLLMAdapter — wraps AstrBot's Context/Provider into LLMClient interface.

Usage in a plugin __init__:
    self.harness_bridge = HarnessAstrBotBridge()
    adapter = AstrBotLLMAdapter(context)
    if adapter.available():
        self.harness_bridge.set_llm_client(adapter)
    # else: harness falls back to cmd_config.json auto-detection
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("jw_claw.llm_adapter")


class AstrBotLLMAdapter:
    """
    Wraps AstrBot Context so it looks like jw_claw LLMClient.
    Uses context.get_using_provider() (the active default provider)
    and calls provider.text_chat(prompt, system_prompt).
    
    Supports lazy initialization - will try to get provider on each call
    if not available at init time.
    """

    def __init__(self, context: Any):
        self._context = context
        self._provider = None
        self._init_provider()

    def _init_provider(self) -> None:
        """Try to initialize provider. Can be called multiple times."""
        if self._provider is not None:
            return  # Already initialized
        try:
            prov = self._context.get_using_provider()
            if prov is not None:
                self._provider = prov
                meta = prov.meta() if hasattr(prov, "meta") else None
                model = meta.curr_model if meta else "unknown"
                logger.info("AstrBotLLMAdapter: provider=%s model=%s", type(prov).__name__, model)
            else:
                logger.info("AstrBotLLMAdapter: no active provider found in context")
        except Exception as exc:
            logger.info("AstrBotLLMAdapter: failed to get provider: %s", exc)

    def _ensure_provider(self) -> bool:
        """Ensure provider is initialized. Returns True if available."""
        if self._provider is None:
            self._init_provider()
        return self._provider is not None

    def available(self) -> bool:
        # Always try to get provider (supports lazy init)
        return self._ensure_provider()

    async def chat(
        self,
        user_message: str,
        system_message: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        if not self._ensure_provider():
            raise RuntimeError("AstrBotLLMAdapter: no provider available")
        try:
            resp = await self._provider.text_chat(
                prompt=user_message,
                system_prompt=system_message or None,
            )
            return resp.completion_text.strip()
        except Exception as exc:
            logger.error("AstrBotLLMAdapter.chat failed: %s", exc)
            raise

    async def chat_safe(
        self,
        user_message: str,
        system_message: str = "",
        fallback: str = "",
        **kwargs,
    ) -> str:
        try:
            return await self.chat(user_message, system_message=system_message)
        except Exception as exc:
            if fallback:
                logger.info("AstrBotLLMAdapter.chat_safe falling back: %s", exc)
            else:
                logger.warning("AstrBotLLMAdapter.chat_safe error: %s", exc)
            return fallback or f"[LLM 调用失败: {exc}]"

    # ── compatibility shim so executor can treat this like LLMClient ──────────
    @property
    def base_url(self) -> str:
        try:
            meta = self._provider.meta()
            return getattr(meta, "api_base", "astrbot://provider")
        except Exception:
            return "astrbot://provider"

    @property
    def model(self) -> str:
        try:
            meta = self._provider.meta()
            return getattr(meta, "curr_model", "astrbot-default")
        except Exception:
            return "astrbot-default"
