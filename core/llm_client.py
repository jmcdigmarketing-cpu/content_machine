from openai import OpenAI

from config.settings import get_settings


def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)


def get_model() -> str:
    return get_settings().openai_model
