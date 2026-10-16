from openai import OpenAI

from app.config import LLM_BASE_URL, LLM_API_KEY

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
for m in client.models.list():
    print(m.id)
