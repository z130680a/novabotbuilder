# NOVA Bot Builder

**An AI-powered agent for building, testing, deploying, and maintaining Telegram bots from natural language requirements.**

NOVA Bot Builder is a Python-based project that helps users turn business requirements into working Telegram bots. Instead of manually implementing every feature, users describe what they need, answer clarification questions when necessary, and let the agent generate and test a bot implementation.

The initial implementation focuses on workshop reservation bots and supports updating an existing bot through descriptive instructions.

## Project Overview

The project follows an agent-driven workflow:

1. **Requirement Analysis:** The user describes the desired bot in natural language.
2. **Clarification:** The agent identifies missing information and asks follow-up questions.
3. **Specification Generation:** The requirements are converted into a structured bot specification.
4. **Code Generation:** The system generates the Telegram bot implementation.
5. **Sandbox Testing:** The generated implementation is tested before being accepted.
6. **Publishing:** The system attempts to start or restart the generated bot.
7. **Bot Maintenance:** The user can request changes to an existing workshop bot, which is regenerated, tested, and restarted.

## Telegram Bot

- **Bot name:** NovaBuilderBot
- **Telegram username:** [@Novazmit_Bot](https://t.me/Novazmit_Bot)
- **Initial use case:** Workshop reservation and registration management.

## Features

### Workshop Reservation Bot

The generated bot is designed to support:

- User registration
- Workshop reservations
- Reservation cancellation
- Capacity management
- Waiting list management
- Automatic promotion of waiting-list participants when a place becomes available

### AI-Powered Bot Builder

- Natural-language requirement processing
- Automatic identification of missing information
- Structured bot specification generation
- Programmatic bot code generation
- Sandbox validation
- Updating an existing bot through descriptive requests
- Restarting the generated bot after changes

### Web Interface

The project includes a web-based interface for creating and managing workshops. Users can review workshop specifications, enter event details, request changes, and follow the generation, testing, and publishing workflow.

## Technology Stack

### Programming Languages

- **Python:** Backend logic, agent workflow, code generation, testing, and Telegram bot execution.
- **HTML:** Web interface structure.
- **CSS:** Web interface styling.
- **JavaScript:** Client-side interactions in the web interface.

### Frameworks and Libraries

- **FastAPI:** Web application and HTTP endpoints.
- **Uvicorn:** ASGI server used to run the web application.
- **python-telegram-bot:** Telegram Bot API integration.
- **AI/LLM integration:** Requirement analysis and bot specification generation through the project's agent module.

Additional AI libraries and provider-specific dependencies are determined by the project's configuration and dependency files.

### Data Storage

The workshop builder uses JSON-based file storage for workshop specifications, including `workshops.json`. The generated bot may also use JSON configuration and data files.

No external SQL database is required for the JSON-based workshop storage described above.

## Project Structure

The main modules include:

- `app/web.py` — FastAPI web interface and application routes.
- `app/agent.py` — Agent workflow for processing user requirements.
- `app/builder.py` — Building and refining bot specifications.
- `app/code_generator.py` — Generating Telegram bot code.
- `app/sandbox.py` — Testing generated bot implementations.
- `app/bot_manager.py` — Starting and restarting the generated bot.
- `app/workshop_store.py` — Workshop data storage and management.
- `generated_bots/generated_bot.py` — Generated Telegram bot implementation.

The exact file layout may vary between project versions.

## Requirements

- Python 3.11 or another version supported by the project's dependencies.
- A Telegram bot token obtained through Telegram's BotFather.
- Any required AI provider credentials configured by the agent module.
- The Python packages listed in `requirements.txt`.

## Installation

Clone the repository and open the project directory:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/novabotbuilder.git
cd novabotbuilder
```

Create and activate a virtual environment.

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure the required environment variables using a local `.env` file, following the configuration expected by the project.

Never commit real API keys, bot tokens, passwords, or session secrets to the repository.

## Running the Web Application

From the project root, start the FastAPI application:

```bash
python -m uvicorn app.web:app --reload
```

Open the following address in your browser:

http://127.0.0.1:8000

Use the interface to describe a workshop bot, answer any clarification questions, generate the implementation, run the sandbox tests, and publish the resulting bot.

If your local version uses a different module layout, adjust the Uvicorn import path to match the location of `web.py`.

## Running the Generated Telegram Bot

The builder normally attempts to start or restart the generated bot during the publishing workflow.

To run the generated bot manually on Windows, if the file exists and the required configuration is available:

```powershell
python generated_bots\generated_bot.py
```

Run only one instance of the same Telegram bot at a time. Multiple polling instances using the same token can cause Telegram polling conflicts.

## Updating an Existing Bot

1. Open the web interface.
2. Select the workshop you want to modify.
3. Describe the requested change, such as increasing the workshop capacity or adding a waiting list.
4. Submit the update request.
5. Allow the agent to regenerate the bot implementation.
6. Review the sandbox test results.
7. Publish or restart the updated bot.

The updated implementation should be accepted only when the required validation succeeds.

## Security Notes

- Store credentials in environment variables or a local `.env` file.
- Exclude secrets, local virtual environments, caches, and private runtime data from Git.
- Do not publish real user records, passwords, Telegram IDs, or personal information.
- Review generated code before executing it.
- Use a restricted environment when testing AI-generated code.

## Project Status

Minimum Viable Product (MVP) — developed as an implementation of the NOVA team's AI-powered Telegram bot builder project.

The completeness of publishing and live Telegram execution depends on the current configuration and successful runtime tests.

## Team

**NOVA**

Repository: `novabotbuilder`

## License

No open-source license has been selected yet.
