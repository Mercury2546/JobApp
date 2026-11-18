"""
AI Service Layer.
Configurable wrapper around OpenAI API with proper error handling, logging,
and validation. Does not return fake responses.
"""
from typing import Optional, List, Dict, Any
from config.settings import OPENAI_API_KEY, OPENAI_MODEL, is_openai_configured
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
    Manages interactions with OpenAI language models.
    """

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.default_model = default_model or OPENAI_MODEL
        self._client = None

    def _get_client(self):
        """
        Lazily creates and returns the OpenAI client.
        Raises APIKeyMissingError if the key is missing or invalid.
        """
        if not is_openai_configured() and not self.api_key:
            logger.error("Attempted AI request without a configured OpenAI API Key.")
            raise APIKeyMissingError(
                "OpenAI API key is missing or not configured. "
                "Please add your valid OPENAI_API_KEY in the .env file."
            )

        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.critical("openai package is not installed.")
                raise AIServiceError("The 'openai' Python package is not installed. Please install requirements.txt.")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise AIServiceError(f"OpenAI Client initialization error: {e}")

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
        Sends a chat completion request to the OpenAI model.
        """
        client = self._get_client()
        target_model = model or self.default_model

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
            logger.error(f"OpenAI authentication error: {e}")
            raise AIServiceError("Authentication failed: Invalid OpenAI API key. Check your .env file.") from e

        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            raise AIServiceError("OpenAI rate limit reached or quota exhausted. Please check your account quota.") from e

        except openai.APIConnectionError as e:
            logger.error(f"OpenAI network connection error: {e}")
            raise AIServiceError("Network error: Unable to reach OpenAI servers. Please check your internet connection.") from e

        except openai.APIError as e:
            logger.error(f"OpenAI API returned an error: {e}")
            raise AIServiceError(f"OpenAI API error: {e.message}") from e

        except Exception as e:
            logger.error(f"Unexpected error during AI generation: {e}", exc_info=True)
            raise AIServiceError(f"An unexpected error occurred while communicating with AI service: {e}") from e

    def test_connection(self) -> Dict[str, Any]:
        """
        Runs a minimal check to verify API key validity without high token costs.
        """
        if not is_openai_configured():
            return {
                "success": False,
                "message": "API key is not configured. Please set OPENAI_API_KEY in .env.",
            }

        try:
            # Minimal 1-token call to test auth
            self.generate_response(
                system_prompt="You are a ping bot.",
                user_prompt="ping",
                temperature=0.0,
                max_tokens=2,
            )
            return {"success": True, "message": "Successfully connected to OpenAI API."}
        except AIServiceError as e:
            return {"success": False, "message": str(e)}


# Singleton instance for general use across modules
ai_service = AIService()
