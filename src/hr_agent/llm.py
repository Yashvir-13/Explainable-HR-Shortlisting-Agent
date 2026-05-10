from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

from .config import Settings
from .security import mask_pii

ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseJsonClient(ABC):
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    @abstractmethod
    def enabled(self) -> bool:
        pass

    @abstractmethod
    def complete_json(self, system_prompt: str, user_payload: dict[str, Any], model: type[ModelT]) -> ModelT | None:
        pass


class GroqJsonClient(BaseJsonClient):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        from groq import Groq
        self.client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def complete_json(self, system_prompt: str, user_payload: dict[str, Any], model: type[ModelT]) -> ModelT | None:
        if not self.client:
            return None
        try:
            safe_payload = json.dumps(user_payload, ensure_ascii=True, indent=2, default=str)
            response = self.client.chat.completions.create(
                model=self.settings.groq_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": mask_pii(safe_payload)},
                ],
                temperature=0,
            )
            content = response.choices[0].message.content or "{}"
            try:
                return model.model_validate_json(content)
            except Exception:
                return model.model_validate(json.loads(content))
        except Exception as e:
            print(f"Groq error: {e}")
            return None


class HuggingFaceJsonClient(BaseJsonClient):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        try:
            from huggingface_hub import InferenceClient
            # We pass the model directly to the client to avoid auto-routing issues
            if settings.hf_token and settings.hf_token.startswith("hf_"):
                self.client = InferenceClient(model=settings.hf_model, api_key=settings.hf_token)
            elif settings.hf_token:
                print("Warning: HF_TOKEN does not look like a valid Hugging Face token (should start with 'hf_').")
                self.client = None
            else:
                self.client = None
        except ImportError:
            self.client = None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def complete_json(self, system_prompt: str, user_payload: dict[str, Any], model: type[ModelT]) -> ModelT | None:
        if not self.client:
            return None
        try:
            safe_payload = json.dumps(user_payload, ensure_ascii=True, indent=2, default=str)
            # Instruct the model to return raw JSON.
            sys_msg = system_prompt + "\n\nCRITICAL: You must return raw, valid JSON only. Do not include markdown code blocks or any other text."
            response = self.client.chat.completions.create(
                model=self.settings.hf_model,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": mask_pii(safe_payload)},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
            content = response.choices[0].message.content or "{}"
            
            # Clean up markdown if the model added it despite instructions
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            try:
                return model.model_validate_json(content)
            except Exception:
                return model.model_validate(json.loads(content))
        except Exception as e:
            print(f"HuggingFace error: {e}")
            return None


class GeminiJsonClient(BaseJsonClient):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        try:
            from google import genai
            self.genai = genai
            if settings.gemini_api_key:
                self.client = genai.Client(api_key=settings.gemini_api_key)
                self._enabled = True
            else:
                self.client = None
                self._enabled = False
        except ImportError:
            self.client = None
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def complete_json(self, system_prompt: str, user_payload: dict[str, Any], model: type[ModelT]) -> ModelT | None:
        if not self._enabled or not self.client:
            return None
            
        import time
        for attempt in range(3):
            try:
                safe_payload = json.dumps(user_payload, ensure_ascii=True, indent=2, default=str)
                response = self.client.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=mask_pii(safe_payload),
                    config=self.genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        system_instruction=system_prompt,
                        temperature=0.0,
                    ),
                )
                content = response.text or "{}"
                try:
                    return model.model_validate_json(content)
                except Exception:
                    return model.model_validate(json.loads(content))
            except Exception as e:
                err_str = str(e)
                if attempt < 2 and ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate limit" in err_str.lower() or "quota" in err_str.lower()):
                    print(f"Gemini rate limit hit. Sleeping 25s before retry... (Attempt {attempt + 1}/3)")
                    time.sleep(25)
                    continue
                print(f"Gemini error: {e}")
                return None


def get_llm_client(settings: Settings) -> BaseJsonClient | None:
    provider = settings.active_provider.lower().replace(" ", "")
    if provider == "groq":
        return GroqJsonClient(settings)
    elif provider == "huggingface":
        return HuggingFaceJsonClient(settings)
    elif provider == "gemini":
        return GeminiJsonClient(settings)
    else:
        return None

