"""
AI Service Layer.
Configurable wrapper around OpenAI API with proper error handling, logging,
and validation. Does not return fake responses.
"""

from typing import Any

from config.settings import (
    get_openai_api_key,
    get_openai_base_url,
    get_openai_model,
    is_openai_configured,
)
from utils.logger import setup_logger

logger = setup_logger("ai_service")


class AIServiceError(Exception):
    """Base exception for AI Service errors."""


class APIKeyMissingError(AIServiceError):
    """Raised when the OpenAI API key is missing or invalid."""


class AIService:
    """
    Manages interactions with OpenAI or OpenAI-compatible language models (Groq, OpenRouter, Ollama, etc.).
    Supports dynamic hot-reloading when .env changes.
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        base_url: str | None = None,
    ):
        self._custom_api_key = api_key
        self._custom_model = default_model
        self._custom_base_url = base_url
        self._client = None
        self._client_key = None
        self._client_base_url = None

    def _get_active_config(self):
        """Resolves the most up-to-date configuration values."""
        key = self._custom_api_key or get_openai_api_key()
        model = self._custom_model or get_openai_model()
        base_url = self._custom_base_url or get_openai_base_url()
        return key, model, base_url

    def _get_client(self):
        """
        Lazily creates or refreshes the OpenAI client if API key or base_url changed.
        """
        key, _, base_url = self._get_active_config()

        if not is_openai_configured() and not key:
            logger.error("Attempted AI request without a configured API Key.")
            raise APIKeyMissingError(
                "API Key is missing or not configured. "
                "Please add your OPENAI_API_KEY in the .env file."
            )

        # Refresh client if config changed
        if (
            self._client is None
            or self._client_key != key
            or self._client_base_url != base_url
        ):
            try:
                from openai import OpenAI

                client_kwargs: dict[str, Any] = {"api_key": key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                    logger.info(
                        f"Initializing AI Client with custom base_url: {base_url}"
                    )
                self._client = OpenAI(**client_kwargs)
                self._client_key = key
                self._client_base_url = base_url
            except ImportError:
                logger.critical("openai package is not installed.")
                raise AIServiceError(
                    "The 'openai' Python package is not installed. Please install requirements.txt."
                )
            except Exception as e:  # noqa: BLE001 — wrap unexpected OpenAI client init failure
                logger.error(f"Failed to initialize AI client: {e}")
                raise AIServiceError(f"AI Client initialization error: {e}")

        return self._client

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        Sends a chat completion request to the AI model.
        """
        client = self._get_client()
        _, active_model, base_url = self._get_active_config()
        target_model = model or active_model

        # ปรับ max_tokens สำหรับ Groq เพื่อไม่ให้เกินเพดาน OTPM (1,000 tokens/min) ของแพ็กเกจฟรี
        is_groq = bool(base_url and "groq.com" in base_url)
        resolved_max_tokens = max_tokens
        if is_groq:
            resolved_max_tokens = min(max_tokens, 950) if max_tokens else 950

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(
            f"Dispatching AI request to model: {target_model} (max_tokens={resolved_max_tokens})"
        )

        try:
            import openai

            kwargs: dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
            }
            if resolved_max_tokens:
                kwargs["max_tokens"] = resolved_max_tokens

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            logger.info(
                f"AI response received. Finish reason: {response.choices[0].finish_reason}"
            )
            return content

        except openai.AuthenticationError as e:
            logger.error(f"AI authentication error: {e}")
            raise AIServiceError(
                "การยืนยันตัวตนล้มเหลว (Authentication failed): ตรวจสอบ API Key และ Base URL ในไฟล์ .env"
            ) from e

        except openai.RateLimitError as e:
            logger.error(f"AI rate limit exceeded: {e}")
            err_text = str(e)
            if is_groq or "groq" in err_text.lower():
                raise AIServiceError(
                    "⏳ ติดข้อจำกัดอัตราการส่งคำขอของ Groq (Rate Limit / OTPM ต่อนาที): "
                    "เนื่องจากเป็นบัญชีฟรีของ Groq กรุณารอประมาณ 30-60 วินาทีให้ระบบรีเซ็ตโควตารายนาที แล้วกดลองใหม่อีกครั้งครับ "
                    "(หรือหากต้องการใช้งานต่อเนื่อง สามารถสลับไปใช้โมเดลฟรีของ Gemini หรือ OpenRouter ใน .env ได้ครับ)"
                ) from e
            elif any(
                k in err_text.lower()
                for k in ["billing", "credit", "quota", "insufficient"]
            ):
                raise AIServiceError(
                    "โควตาหรือเครดิตในบัญชี AI หมดลง (Quota exhausted): "
                    "โปรดตรวจสอบยอดเงินในบัญชี หรือสลับไปใช้ Groq / Gemini ฟรีในไฟล์ .env"
                ) from e
            else:
                raise AIServiceError(
                    f"เกิด Rate Limit จากผู้ให้บริการ AI: {err_text} (โปรดรอสักครู่แล้วลองใหม่อีกครั้ง)"
                ) from e

        except openai.APIConnectionError as e:
            logger.error(f"AI network connection error: {e}")
            raise AIServiceError(
                "เกิดปัญหาการเชื่อมต่อเครือข่าย ไม่สามารถติดต่อเซิร์ฟเวอร์ AI ได้"
            ) from e

        except openai.APIError as e:
            logger.error(f"AI API returned an error: {e}")
            raise AIServiceError(f"AI API Error: {e.message}") from e

        except Exception as e:
            logger.exception("Unexpected error during AI generation")
            raise AIServiceError(f"เกิดข้อผิดพลาดในการติดต่อกับ AI Service: {e}") from e

    def generate_vision_response(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        system_prompt: str = "",
        user_prompt: str = "",
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        """
        Sends an image along with text to a multimodal / vision-capable AI model.
        Compatible with OpenAI (gpt-4o, gpt-4o-mini), OpenRouter, Groq Vision, etc.
        """
        import base64

        client = self._get_client()
        _, active_model, base_url = self._get_active_config()
        target_model = model or active_model
        is_groq = bool(base_url and "groq.com" in base_url)
        resolved_max_tokens = (
            min(max_tokens, 950)
            if (is_groq and max_tokens)
            else (950 if is_groq else max_tokens)
        )

        base64_img = base64.b64encode(image_bytes).decode("utf-8")
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content = [
            {"type": "text", "text": user_prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64_img}"},
            },
        ]
        messages.append({"role": "user", "content": user_content})

        logger.info(f"Dispatching Vision AI request to model: {target_model}")

        try:
            import openai

            kwargs: dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
            }
            if resolved_max_tokens:
                kwargs["max_tokens"] = resolved_max_tokens

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            logger.info(
                f"Vision AI response received. Finish reason: {response.choices[0].finish_reason}"
            )
            return content

        except openai.BadRequestError as e:
            err_str = str(e)
            logger.error(f"AI Vision BadRequestError: {err_str}")
            if any(k in err_str.lower() for k in ["image", "vision", "support"]):
                raise AIServiceError(
                    f"โมเดลปัจจุบัน `{target_model}` อาจไม่รองรับการวิเคราะห์รูปภาพ (Vision) "
                    "โปรดเปลี่ยนเป็นโมเดลที่รองรับรูปภาพในไฟล์ .env เช่น `gpt-4o-mini`, `gpt-4o` หรือโมเดล Vision อื่นๆ"
                ) from e
            raise AIServiceError(f"เกิดข้อผิดพลาดในการประมวลผลรูปภาพ: {e}") from e

        except openai.AuthenticationError as e:
            logger.error(f"AI authentication error: {e}")
            raise AIServiceError(
                "การยืนยันตัวตนล้มเหลว: ตรวจสอบ API Key และ Base URL ในไฟล์ .env"
            ) from e

        except openai.RateLimitError as e:
            logger.error(f"AI rate limit exceeded or quota exhausted: {e}")
            err_text = str(e)
            if is_groq or "groq" in err_text.lower():
                raise AIServiceError(
                    "⏳ ติดข้อจำกัดอัตราการส่งคำขอของ Groq (Rate Limit / OTPM): "
                    "กรุณารอประมาณ 30-60 วินาทีให้ระบบรีเซ็ตโควตารายนาที แล้วกดลองใหม่อีกครั้งครับ"
                ) from e
            raise AIServiceError(
                "โควตาการใช้งานของ AI หมดลง หรือเกิด Rate Limit โปรดตรวจสอบเครดิตในบัญชี"
            ) from e

        except Exception as e:
            logger.exception("Unexpected error during Vision AI generation")
            raise AIServiceError(f"เกิดข้อผิดพลาดในการวิเคราะห์รูปภาพด้วย AI: {e}") from e

    def test_connection(self) -> dict[str, Any]:
        """
        Runs a minimal check to verify API key and endpoint validity.
        """
        if not is_openai_configured():
            return {
                "success": False,
                "message": "ยังไม่ได้ระบุ API Key โปรดตั้งค่า OPENAI_API_KEY ในไฟล์ .env",
            }

        _key, active_model, base_url = self._get_active_config()
        provider_name = (
            f"Custom Base URL: {base_url}" if base_url else "OpenAI Official"
        )

        try:
            # Minimal 1-token call to test auth
            self.generate_response(
                system_prompt="You are a ping bot.",
                user_prompt="ping",
                temperature=0.0,
                max_tokens=2,
            )
            return {
                "success": True,
                "message": f"เชื่อมต่อสำเร็จกับ {provider_name} (โมเดล: {active_model})",
            }
        except AIServiceError as e:
            return {"success": False, "message": str(e)}


# Singleton instance for general use across modules
ai_service = AIService()
