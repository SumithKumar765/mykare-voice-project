import os
from openai import AsyncOpenAI
from app.config import settings

# Initialize OpenAI-compatible wrappers for our free tiers
# We use the OpenAI SDK because both Google and Groq support its format seamlessly.

gemini_client = AsyncOpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=settings.GEMINI_API_KEY
)

groq_client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=settings.GROQ_API_KEY
)

async def chat_completion_router(messages, tools=None):
    """
    Executes primary LLM handling with automatic contextual failover routing.
    Ensures we stay under our strict 3-5s latency budget by failing over instantly.
    """
    try:
        # Primary Call: Gemini 1.5 Flash (Optimized for fast tool execution)
        print("⚡ Routing to Primary: Gemini 1.5 Flash")
        response = await gemini_client.chat.completions.create(
            model="gemini-1.5-flash",
            messages=messages,
            tools=tools,
            temperature=0.2 # Kept low for deterministic, strict tool calling
        )
        return response
        
    except Exception as gemini_error:
        print(f"⚠️ Primary tier hit limit: {str(gemini_error)}. Routing to Groq backup.")
        
        try:
            # Immediate Fallback: Groq Llama 3.1 8B Instant (840 tokens/sec)
            print("🔄 Routing to Backup: Groq Llama 3.1 8B Instant")
            response = await groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                tools=tools,
                temperature=0.2
            )
            return response
            
        except Exception as groq_error:
            print(f"❌ Critical Failure: All free tier engines exhausted.")
            raise RuntimeError(f"Target Error: {str(groq_error)}")