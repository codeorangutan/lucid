# Lucid
Cognitive testing automation tool for healthcare.

## Project Structure
- `src/` : Source code
- `tests/` : Test scripts
- `data/` : Database and reports

## Setup Steps
1. Python 3.11+ required.
2. Set up a virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Install Playwright browsers with `playwright install`.

## Description
Lucid automates cognitive test requests, report handling, and secure communications, with privacy and modularity as core principles.

## Docker Usage

To build and run Lucid in Docker:

1. Build the Docker image:
   ```sh
   docker build -t lucid-app .
   ```
2. Run the container:
   ```sh
   docker run --rm -it lucid-app
   ```

If you want to run your scripts interactively or mount your code for development, add:

```sh
docker run --rm -it -v %cd%/src:/app/src lucid-app bash
```

Replace the default CMD in the Dockerfile with your main script (e.g., `src/main.py`) as you develop.

## Stealth Automation

- Added a single `stealth_delay()` function to introduce random delays between browser actions for stealthier automation.
- All browser interactions now include a random delay (default 0.8–2.2s) to mimic human behavior and reduce detection risk.
- Added automated test for delay logic in `tests/test_stealth_delay.py`.

## How to Test Delays

Run:

```
pytest tests/test_stealth_delay.py
```

This will verify that the delay is randomized and within the expected range.

## Progress Log

### 2025-04-19
- Project initialized with Python, virtual environment, and Docker support.
- Test-driven development (TDD) framework set up with pytest and a basic environment test.
- Playwright installed and tested for browser automation.
- Playwright script refactored into a modular function that takes subject, DOB year, and email as arguments.
- Robust error handling and logging added (logs to both console and lucid_request.log).
- All major steps and exceptions are now logged for audit and debugging purposes.

Next: Expand modularity, write automated tests for the Playwright function, and continue workflow integration.
