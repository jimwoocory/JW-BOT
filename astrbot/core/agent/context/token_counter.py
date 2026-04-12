import json
import math
import unicodedata
from typing import Protocol, runtime_checkable

from ..message import AudioURLPart, ImageURLPart, Message, TextPart, ThinkPart


@runtime_checkable
class TokenCounter(Protocol):
    """Protocol for token counters.
    Provides an interface for counting tokens in message lists.
    """

    def count_tokens(
        self,
        messages: list[Message],
        trusted_token_usage: int = 0,
    ) -> int:
        """Count the total tokens in the message list.

        Args:
            messages: The message list.
            trusted_token_usage: The total token usage that LLM API returned.
                For some cases, this value is more accurate.
                But some API does not return it, so the value defaults to 0.

        Returns:
            The total token count.

        """
        ...


# 图片/音频 token 开销估算值，参考 OpenAI vision pricing:
# low-res ~85 tokens, high-res ~170 per 512px tile, 通常几百到上千。
# 这里取一个保守中位数，宁可偏高触发压缩也不要偏低导致 API 报错。
IMAGE_TOKEN_ESTIMATE = 765
AUDIO_TOKEN_ESTIMATE = 500


class EstimateTokenCounter:
    """Estimate token counter implementation.
    Provides a simple estimation of token count based on character types.

    Supports multimodal content: images, audio, and thinking parts
    are all counted so that the context compressor can trigger in time.
    """

    def count_tokens(
        self,
        messages: list[Message],
        trusted_token_usage: int = 0,
    ) -> int:
        if trusted_token_usage > 0:
            return trusted_token_usage

        total = 0
        for msg in messages:
            content = msg.content
            if isinstance(content, str):
                total += self._estimate_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, TextPart):
                        total += self._estimate_tokens(part.text)
                    elif isinstance(part, ThinkPart):
                        total += self._estimate_tokens(part.think)
                    elif isinstance(part, ImageURLPart):
                        total += IMAGE_TOKEN_ESTIMATE
                    elif isinstance(part, AudioURLPart):
                        total += AUDIO_TOKEN_ESTIMATE

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tc_str = json.dumps(tc if isinstance(tc, dict) else tc.model_dump())
                    total += self._estimate_tokens(tc_str)

        return total

    ASCII_TOKEN_WEIGHT = 0.25
    CJK_TOKEN_WEIGHT = 1.5
    EMOJI_TOKEN_WEIGHT = 2.0
    NON_ASCII_TOKEN_WEIGHT = 0.5
    PUNCT_TOKEN_WEIGHT = 0.2
    WHITESPACE_TOKEN_WEIGHT = 0.05

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0

        total = 0.0
        for char in text:
            total += self._char_weight(char)

        return max(1, math.ceil(total))

    def _char_weight(self, char: str) -> float:
        if char.isspace():
            return self.WHITESPACE_TOKEN_WEIGHT

        if self._is_cjk(char):
            return self.CJK_TOKEN_WEIGHT

        if self._is_emoji_like(char):
            return self.EMOJI_TOKEN_WEIGHT

        if ord(char) < 128:
            if unicodedata.category(char).startswith("P"):
                return self.PUNCT_TOKEN_WEIGHT
            return self.ASCII_TOKEN_WEIGHT

        if unicodedata.category(char).startswith("P"):
            return self.PUNCT_TOKEN_WEIGHT

        return self.NON_ASCII_TOKEN_WEIGHT

    def _is_cjk(self, char: str) -> bool:
        code = ord(char)
        return any(
            start <= code <= end
            for start, end in (
                (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
                (0x4E00, 0x9FFF),   # CJK Unified Ideographs
                (0x3040, 0x309F),   # Hiragana
                (0x30A0, 0x30FF),   # Katakana
                (0x31F0, 0x31FF),   # Katakana Phonetic Extensions
                (0xAC00, 0xD7AF),   # Hangul Syllables
                (0x1100, 0x11FF),   # Hangul Jamo
                (0x3130, 0x318F),   # Hangul Compatibility Jamo
            )
        )

    def _is_emoji_like(self, char: str) -> bool:
        code = ord(char)
        return (
            code > 0xFFFF
            or 0x2600 <= code <= 0x27BF
            or unicodedata.category(char) == "So"
        )
