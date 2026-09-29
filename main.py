import asyncio
import os
import sys
from time import perf_counter
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Retrieve API key (checking GEMINI_KEY as defined in your .env, with fallbacks)
GEMINI_KEY = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not GEMINI_KEY:
    print("Error: GEMINI_KEY not found in .env file.")
    print("Please ensure your .env has: GEMINI_KEY=your_gemini_api_key")
    sys.exit(1)

# Lightweight models priority list (fast, low latency, and high availability)
DEFAULT_LIGHTWEIGHT_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

# Set active model from environment or default to the fastest lightweight model
GEMINI_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_LIGHTWEIGHT_MODELS[0])

system_prompt = (
    "You are a friendly and helpful assistant that specializes exclusively in cats and dogs. "
    "Provide informative and engaging answers. Keep answers concise unless the user asks for detail."
)

# Setup Gemini Client (supports google-genai or google-generativeai)
try:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_KEY)
    USE_NEW_SDK = True
except ImportError:
    try:
        import google.generativeai as legacy_genai

        legacy_genai.configure(api_key=GEMINI_KEY)
        USE_NEW_SDK = False
    except ImportError:
        print("Please install the Gemini SDK: pip install google-genai python-dotenv")
        sys.exit(1)


async def call_gemini_async(prompt: str, sys_instruction: str = "", temperature: float = 0.7) -> str:
    """Helper to invoke Gemini asynchronously with automatic fallback to other lightweight models on 503/404."""
    global GEMINI_MODEL
    # Build list of models to try starting with currently selected model
    models_to_try = [GEMINI_MODEL] + [m for m in DEFAULT_LIGHTWEIGHT_MODELS if m != GEMINI_MODEL]
    last_error = None

    for model_name in models_to_try:
        try:
            if USE_NEW_SDK:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=sys_instruction if sys_instruction else None,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                )
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                # If this model succeeded and was a fallback, remember it
                if model_name != GEMINI_MODEL:
                    GEMINI_MODEL = model_name
                return response.text or ""
            else:
                model = legacy_genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=sys_instruction if sys_instruction else None,
                    generation_config={"temperature": temperature},
                )
                response = await model.generate_content_async(prompt)
                if model_name != GEMINI_MODEL:
                    GEMINI_MODEL = model_name
                return response.text or ""
        except Exception as e:
            err_str = str(e)
            # If 503 (high demand) or 404 (not found), try next lightweight model
            if "503" in err_str or "404" in err_str or "UNAVAILABLE" in err_str or "NOT_FOUND" in err_str:
                print(f"  [Model Warning] {model_name} unavailable ({'503 High Demand' if '503' in err_str else 'Not Available'}). Trying alternate lightweight model...")
                last_error = e
                continue
            raise e

    if last_error:
        raise last_error
    return ""


async def get_chat_response(user_request: str) -> str:
    """Main LLM call: Generates the actual conversational response."""
    print("  [Chat LLM] Requesting answer...")
    started = perf_counter()
    response_text = await call_gemini_async(
        prompt=user_request,
        sys_instruction=system_prompt,
        temperature=0.5,
    )
    print(f"  [Chat LLM] Response generated in {perf_counter() - started:.2f}s.")
    return response_text


async def topical_guardrail(user_request: str) -> str:
    """Guardrail LLM call: Assesses if the question topic is allowed."""
    print("  [Guardrail] Assessing topic...")
    started = perf_counter()
    guardrail_sys_prompt = (
        "Your role is to assess whether the user question is allowed or not. "
        "The allowed topics are strictly cats and dogs. "
        "If the topic is allowed, respond ONLY with 'allowed'. "
        "Otherwise, respond ONLY with 'not_allowed'."
    )
    response_text = await call_gemini_async(
        prompt=f"User question: {user_request}\nDecision:",
        sys_instruction=guardrail_sys_prompt,
        temperature=0.0,
    )
    print(f"  [Guardrail] Assessment complete in {perf_counter() - started:.2f}s.")
    return response_text.strip().lower()


async def execute_chat_with_guardrail(user_request: str) -> str:
    """
    Executes both the guardrail check and the chat response concurrently.
    If the guardrail finishes and detects a disallowed topic, the chat task is
    cancelled immediately to save resources and block unauthorized output.
    """
    topical_guardrail_task = asyncio.create_task(topical_guardrail(user_request))
    chat_task = asyncio.create_task(get_chat_response(user_request))

    try:
        # Both requests run concurrently; release output only after explicit approval.
        guardrail_response = await topical_guardrail_task
        if guardrail_response != "allowed":
            print("\n  >>> [GUARD TRIGGERED] Topical guardrail blocked this request! <<<")
            return "I can only talk about cats and dogs, the best animals that ever lived."
        return await chat_task
    finally:
        # Drain tasks on rejection or errors so requests do not linger between turns.
        for task in (topical_guardrail_task, chat_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(topical_guardrail_task, chat_task, return_exceptions=True)


async def run_chatbot():
    """Interactive CLI Chatbot to test guardrails."""
    print("=" * 60)
    print(f"🐾 Gemini Guardrails Chatbot Demo (Model: {GEMINI_MODEL})")
    print("Rules: Only questions about cats and dogs are allowed.")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            print("\nProcessing request with speculative guardrail check...")
            started = perf_counter()
            bot_reply = await execute_chat_with_guardrail(user_input)
            print(f"  [Total] {perf_counter() - started:.2f}s")
            print(f"\nBot: {bot_reply}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    asyncio.run(run_chatbot())
