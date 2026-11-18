"""
AI Service Layer.
Configurable wrapper around OpenAI API with proper error handling, logging,
and validation. Does not return fake responses.
"""
from typing import Optional, List, Dict, Any
from config.settings import (
    get_openai_api_key,
    get_openai_model,
    get_openai_base_url,
    is_openai_configured,
)
from utils.logger import setup_logger

logger = setup_logger("ai_service")


class AIServiceError(Exception):
    """Base exception for AI Service errors."""
    pass


class APIKeyMissingError(AIServiceError):
    """Raised when the OpenAI API key is missing or invalid."""
    pass


class AIService:
    """
    Manages interactions with OpenAI or OpenAI-compatible language models (Groq, OpenRouter, Ollama, etc.).
    Supports dynamic hot-reloading when .env changes.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        base_url: Optional[str] = None,
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
        if self._client is None or self._client_key != key or self._client_base_url != base_url:
            try:
                from openai import OpenAI
                client_kwargs: Dict[str, Any] = {"api_key": key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                    logger.info(f"Initializing AI Client with custom base_url: {base_url}")
                self._client = OpenAI(**client_kwargs)
                self._client_key = key
                self._client_base_url = base_url
            except ImportError:
                logger.critical("openai package is not installed.")
                raise AIServiceError("The 'openai' Python package is not installed. Please install requirements.txt.")
            except Exception as e:
                logger.error(f"Failed to initialize AI client: {e}")
                raise AIServiceError(f"AI Client initialization error: {e}")

        return self._client

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Sends a chat completion request to the AI model.
        """
        client = self._get_client()
        _, active_model, _ = self._get_active_config()
        target_model = model or active_model

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"Dispatching AI request to model: {target_model}")

        try:
            import openai

            kwargs: Dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            logger.info(f"AI response received. Finish reason: {response.choices[0].finish_reason}")
            return content

        except openai.AuthenticationError as e:
            logger.error(f"AI authentication error: {e}")
            raise AIServiceError("การยืนยันตัวตนล้มเหลว (Authentication failed): ตรวจสอบ API Key และ Base URL ในไฟล์ .env") from e

        except openai.RateLimitError as e:
            logger.error(f"AI rate limit exceeded or quota exhausted: {e}")
            raise AIServiceError(
                "โควตาการใช้งานของ AI หมดลง (Quota exhausted หรือ Rate limit): "
                "โปรดตรวจสอบยอดเงินในบัญชี หรือสลับไปใช้บริการฟรี เช่น Groq โดยตั้งค่า OPENAI_BASE_URL ในไฟล์ .env"
            ) from e

        except openai.APIConnectionError as e:
            logger.error(f"AI network connection error: {e}")
            raise AIServiceError("เกิดปัญหาการเชื่อมต่อเครือข่าย ไม่สามารถติดต่อเซิร์ฟเวอร์ AI ได้") from e

        except openai.APIError as e:
            logger.error(f"AI API returned an error: {e}")
            raise AIServiceError(f"AI API Error: {e.message}") from e

        except Exception as e:
            logger.error(f"Unexpected error during AI generation: {e}", exc_info=True)
            raise AIServiceError(f"เกิดข้อผิดพลาดในการติดต่อกับ AI Service: {e}") from e

    def test_connection(self) -> Dict[str, Any]:
        """
        Runs a minimal check to verify API key and endpoint validity.
        """
        if not is_openai_configured():
            return {
                "success": False,
                "message": "ยังไม่ได้ระบุ API Key โปรดตั้งค่า OPENAI_API_KEY ในไฟล์ .env",
            }

        key, active_model, base_url = self._get_active_config()
        provider_name = f"Custom Base URL: {base_url}" if base_url else "OpenAI Official"

        try:
            # Minimal 1-token call to test auth
            self.generate_response(
                system_prompt="You are a ping bot.",
                user_prompt="ping",
                temperature=0.0,
                max_tokens=2,
            )
            return {"success": True, "message": f"เชื่อมต่อสำเร็จกับ {provider_name} (โมเดล: {active_model})"}
        except AIServiceError as e:
            return {"success": False, "message": str(e)}


# Singleton instance for general use across modules
ai_service = AIService()
