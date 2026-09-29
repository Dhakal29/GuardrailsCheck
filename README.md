# GuardrailsCheck

A Python command-line chatbot demonstrating a Gemini-powered topical guardrail. The chatbot is instructed to answer only questions about **cats and dogs**.

For each message, a guardrail checks the topic while a separate request generates an answer concurrently. The answer is displayed only if the guardrail approves it.

## Setup with uv

You need Python, uv, and a Gemini API key with access to the configured model.

```bash
git clone https://github.com/Dhakal29/GuardrailsCheck.git
cd GuardrailsCheck
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

If you already have the repository open, start with `uv venv`. The activation command above is for macOS/Linux; on Windows PowerShell, use `.venv\Scripts\Activate.ps1`.

Create a `.env` file in the project directory:

```dotenv
GEMINI_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash
```

`GEMINI_MODEL` is optional and defaults to `gemini-1.5-flash`. The application also features automatic fallback to alternative lightweight models (`gemini-2.0-flash-lite`, `gemini-1.5-flash-8b`) in case of temporary high-demand spikes (503). The app also accepts `GEMINI_API_KEY` or `GOOGLE_API_KEY` if `GEMINI_KEY` is absent. Existing shell environment variables take precedence over `.env` values.

The repository's `.gitignore` excludes `.env` and `.venv`; keep your API key out of committed files.

## Run

With the virtual environment activated:

```bash
python main.py
```

Try questions such as:

- `Why do cats purr?`
- `How can I teach my dog to sit?`
- `Write an email about a business meeting.` — expected to be blocked.

For a rejected question, the chatbot returns:

```text
I can only talk about cats and dogs, the best animals that ever lived.
```

Type `exit` or `quit` to stop. Each message is processed independently; the app does not send conversation history.

## How the guardrail works

1. Start the topic check and answer generation as concurrent asyncio tasks.
2. Wait for the topic check, which is instructed to return `allowed` or `not_allowed`.
3. Display the generated answer only when the normalized decision is exactly `allowed`. Other decisions produce the rejection message.
4. Cancel and await any unfinished tasks on rejection or error. API errors are reported in the terminal without displaying the generated answer.

This is speculative generation: the answer request starts before approval to reduce waiting time. Both requests receive the user's message, including messages that are later rejected. Cancelling the local task does not guarantee that server-side generation or billing stops.

This demo checks the input topic using an LLM. It does not independently validate the generated answer, and model decisions can be incorrect.

## Performance and timings

The terminal reports elapsed time for the completed guardrail request, completed chat request, and successful overall execution. For allowed questions, total latency is approximately the slower of the two concurrent requests, rather than their sum.

The current implementation uses low thinking for Gemini 3 models through `google-genai`, requests concise answers, and disables unused automatic function calling. Answers are displayed after full generation; output is not streamed. API and network latency still affect response time.

## Troubleshooting

- **Missing API key:** Set `GEMINI_KEY` in `.env` in the project directory.
- **Model unavailable / 404:** Set `GEMINI_MODEL` to a model available to your account. Check both `.env` and any shell override. Model overrides must support the configuration used in `main.py`.
- **Missing dependencies:** Activate `.venv` and run `uv pip install -r requirements.txt`.
- **Slow responses:** Compare the `[Guardrail]`, `[Chat LLM]`, and `[Total]` timings to identify which request is taking longer. A cancelled chat request will not print a completion time.

## Project files

| File | Purpose |
| --- | --- |
| `main.py` | Gemini requests, topical guardrail, and interactive CLI |
| `requirements.txt` | Python dependencies: `google-genai` and `python-dotenv` |
| `.gitignore` | Excludes local credentials and the virtual environment |
| `.env` | Local API key and optional model override; not committed |


## Permission-based deletion exercise

Run `python pet_database.py` for a standalone SQLite exercise with no API key required, or use these commands in `python main.py`:

```text
list pets
delete pet 2
delete pet 1
list pets
```

The first command initializes a local `demo_pets.sqlite3` database with sample records. The simulated user `demo-owner` owns pet 1 (Milo) and pet 3 (Luna). Pet 2 belongs to another user, so deleting it is blocked. Deleting pet 1 marks it deleted and hides it from future listings; its row remains in the database. Restarting does not undo deletion.

Only the exact command `delete pet <id>` invokes deletion. These commands are handled by Python before the LLM path; they are not natural-language tool calls. No prompt or model output is executed as SQL. The parameterized update includes both the record ID and owner ID, enforcing ownership in the same operation. Bulk deletion is unsupported.

This is a local teaching example, not real authentication or a secure multi-user application. The identity is fixed in Python, and anyone with direct access to the SQLite file can change it. A deployed version must derive identity from a verified server-side login and restrict direct database access.

Relevant code: `handle_pet_command()` parses commands, `delete_pet()` enforces ownership, and `main.py` routes commands before chat generation. Run the permission tests with `python -m unittest test_pet_database.py`.
