import os
import json
import httpx
from google import genai
from google.genai import types

# Tiers of fallback providers
INTERMEDIATE_PROVIDERS = [
    {"type": "gemini", "model": "gemini-2.5-flash"},
    {"type": "groq", "model": "llama-3.3-70b-versatile", "url": "https://api.groq.com/openai/v1/chat/completions"},
    {"type": "groq", "model": "llama3-8b-8192", "url": "https://api.groq.com/openai/v1/chat/completions"},
    {"type": "openrouter", "model": "meta-llama/llama-3.2-3b-instruct:free", "url": "https://openrouter.ai/api/v1/chat/completions"},
    {"type": "openrouter", "model": "nvidia/nemotron-nano-9b-v2:free", "url": "https://openrouter.ai/api/v1/chat/completions"},
    {"type": "openrouter", "model": "google/gemma-2-9b-it:free", "url": "https://openrouter.ai/api/v1/chat/completions"}
]

FINAL_PROVIDERS = [
    {"type": "gemini", "model": "gemini-2.5-flash"},
    {"type": "groq", "model": "llama-3.3-70b-versatile", "url": "https://api.groq.com/openai/v1/chat/completions"},
    {"type": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free", "url": "https://openrouter.ai/api/v1/chat/completions"},
    {"type": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free", "url": "https://openrouter.ai/api/v1/chat/completions"},
    {"type": "openrouter", "model": "google/gemini-2.5-flash", "url": "https://openrouter.ai/api/v1/chat/completions"}
]

async def call_gemini(model: str, prompt: str, system_instruction: str = None, response_mime_type: str = "text/plain") -> str:
    """Call Gemini directly using google-genai SDK."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY")
        
    client = genai.Client(api_key=api_key)
    
    config = types.GenerateContentConfig(
        temperature=0.1
    )
    if system_instruction:
        config.system_instruction = system_instruction
    if response_mime_type == "application/json":
        config.response_mime_type = "application/json"
        
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config
    )
    return response.text

async def call_openai_compatible(url: str, api_key: str, model: str, prompt: str, system_instruction: str = None, response_mime_type: str = "text/plain") -> str:
    """Call OpenAI-compatible endpoints (Groq, OpenRouter) via HTTP POST."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.1
    }
    if response_mime_type == "application/json":
        data["response_format"] = {"type": "json_object"}
        
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=data, headers=headers, timeout=60.0)
        r.raise_for_status()
        res_json = r.json()
        return res_json["choices"][0]["message"]["content"]

async def generate_text(prompt: str, system_instruction: str = None, role: str = "intermediate", response_mime_type: str = "text/plain") -> str:
    """Generate text using a fallback sequence of providers based on the requested role."""
    providers = INTERMEDIATE_PROVIDERS if role == "intermediate" else FINAL_PROVIDERS
    errors = []
    
    for provider in providers:
        p_type = provider["type"]
        model = provider["model"]
        
        try:
            if p_type == "gemini":
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key or api_key.startswith("your_") or api_key == "dummy":
                    continue
                print(f"[LLM] Trying Gemini ({model})...")
                return await call_gemini(model, prompt, system_instruction, response_mime_type)
                
            elif p_type == "groq":
                api_key = os.getenv("GROQ_API_KEY")
                if not api_key or api_key.startswith("your_") or api_key == "dummy":
                    continue
                print(f"[LLM] Trying Groq ({model})...")
                return await call_openai_compatible(provider["url"], api_key, model, prompt, system_instruction, response_mime_type)
                
            elif p_type == "openrouter":
                api_key = os.getenv("OPENROUTER_API_KEY")
                if not api_key or api_key.startswith("your_") or api_key == "dummy":
                    continue
                print(f"[LLM] Trying OpenRouter ({model})...")
                return await call_openai_compatible(provider["url"], api_key, model, prompt, system_instruction, response_mime_type)
                
        except Exception as e:
            print(f"[LLM ERROR] Provider {p_type} ({model}) failed: {e}")
            errors.append(f"{p_type}:{model} failed: {e}")
            continue

    # If all providers fail or no keys were provided, raise error
    raise RuntimeError(f"All LLM providers failed. Errors:\n" + "\n".join(errors))
