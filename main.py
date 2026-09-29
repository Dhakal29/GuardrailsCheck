import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Retrieve API key (checking GEMINI_KEY as defined in your .env, with fallbacks)
GEMINI_KEY = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not GEMINI_KEY:
    print("Error: GEMINI_KEY not found in .env file.")
    print("Please ensure your .env has: GEMINI_KEY=your_gemini_api_key")
    sys.exit(1)

# Override the default model with GEMINI_MODEL in the environment or .env.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

system_prompt = (
    "You are a friendly and helpful assistant that specializes exclusively in cats and dogs. "
    "Provide informative and engaging answers."
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
    """Helper to invoke Gemini asynchronously using either google-genai or google-generativeai."""
    if USE_NEW_SDK:
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=sys_instruction if sys_instruction else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        # Using the async client
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        return response.text or ""
    else:
        model = legacy_genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=sys_instruction if sys_instruction else None,
            generation_config={"temperature": temperature},
        )
        response = await model.generate_content_async(prompt)
        return response.text or ""


async def get_chat_response(user_request: str) -> str:
    """Main LLM call: Generates the actual conversational response."""
    print("  [Chat LLM] Requesting answer...")
    response_text = await call_gemini_async(
        prompt=user_request,
        sys_instruction=system_prompt,
        temperature=0.5,
    )
    print("  [Chat LLM] Response generated.")
    return response_text


async def topical_guardrail(user_request: str) -> str:
    """Guardrail LLM call: Assesses if the question topic is allowed."""
    print("  [Guardrail] Assessing topic...")
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
    print("  [Guardrail] Assessment complete.")
    return response_text.strip().lower()


async def execute_chat_with_guardrail(user_request: str) -> str:
    """
    Executes both the guardrail check and the chat response concurrently.
    If the guardrail finishes and detects a disallowed topic, the chat task is
    cancelled immediately to save resources and block unauthorized output.
    """
    topical_guardrail_task = asyncio.create_task(topical_guardrail(user_request))
    chat_task = asyncio.create_task(get_chat_response(user_request))

    # Wait for the guardrail task to complete first
    while not topical_guardrail_task.done():
        done, _ = await asyncio.wait(
            [topical_guardrail_task, chat_task], return_when=asyncio.FIRST_COMPLETED
        )
        if topical_guardrail_task in done:
            break
        await asyncio.sleep(0.05)

    guardrail_response = topical_guardrail_task.result()

    if "not_allowed" in guardrail_response:
        chat_task.cancel()
        print("\n  >>> [GUARD TRIGGERED] Topical guardrail blocked this request! <<<")
        return "I can only talk about cats and dogs, the best animals that ever lived."

    # If allowed, await the chat response (if not finished already)
    return await chat_task


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
            bot_reply = await execute_chat_with_guardrail(user_input)
            print(f"\nBot: {bot_reply}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    asyncio.run(run_chatbot())
