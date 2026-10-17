from openai import OpenAI

from .config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
r = client.chat.completions.create(
    model=LLM_MODEL,
    messages=[{"role": "user", "content": "Reply with exactly: LLM OK"}],
    max_tokens=260,
)

print(r)
print(r.choices[0].message.content)
