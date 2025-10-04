# BrowserBench

BrowserBench exercises multiple hosted Chromium providers against a shared set of autonomous web-browsing tasks. It wraps the provider-specific session bootstrap in `browser_test.py` and coordinates parallel task execution in `run_browserbench.py`, emitting timestamped CSV reports so you can compare reliability and latency provider by provider.

## Repository Layout
- `run_browserbench.py` – asynchronous benchmark runner; loads tasks from CSV, fans them out with bounded concurrency, and writes aggregated results.
- `browser_test.py` – single-task harness that spins up a provider session, runs the `browser_use` agent, captures the final message, and performs provider-specific teardown.
- `providers/` – lightweight adapters for Anchor, Browserbase, SteelBrowser, and Hyperbrowser. Each exposes `create_session(...)` and `cleanup_session(...)` so the runner never touches SDK details.
- `browserbench.csv` / `test_tasks.csv` – canonical and sandbox task lists. Each row describes the start URL, natural-language instruction, and ground-truth expectation.
- `results/` – auto-created folder containing `browserbench_results_<provider>_<timestamp>.csv` exports for every run.
- `requirements.txt` – Python dependencies required by the runner and provider adapters.

A pre-created `venv/` is checked in for convenience, but feel free to recreate it if needed.

## Prerequisites
1. **Python environment** – Use the repo's virtualenv (`source venv/bin/activate`) or create a fresh one (`python -m venv venv && source venv/bin/activate`).
2. **Install dependencies** – `pip install -r requirements.txt`.
3. **Environment variables** – Load from `.env` or export manually:
   - `OPENAI_API_KEY`
   - `ANCHOR_API_KEY`
   - `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`
   - `STEEL_API_KEY`
   - `HYPERBROWSER_API_KEY`

`run_browserbench.py` and `browser_test.py` both call `python-dotenv.load_dotenv()`, so a local `.env` file is respected automatically.

## Running the Benchmark Suite
```bash
python run_browserbench.py \
  --provider browserbase \
  --concurrency 5 \
  --tasks 20 \
  --csv-file browserbench.csv
```

Key flags:
- `--provider {anchor|browserbase|steelbrowser|hyperbrowser}` – choose which adapter to exercise. Each run targets a single provider.
- `--concurrency <int>` – number of simultaneous browser sessions. The runner uses an `asyncio.Semaphore` to cap parallelism.
- `--tasks <int>` – optionally limit the number of rows pulled from the CSV.
- `--csv-file <path>` – alternate task list.
- `--output <filename>` – custom name for the result CSV (otherwise auto-generated).
- `--no-stealth` – disable provider-specific stealth settings where available.

The runner validates that required environment variables exist, loads tasks, dispatches them through `browser_test.main(...)`, and writes a CSV report under `results/`. Each row includes:
- task metadata (ID, prompt, URLs, ground truth)
- provider + configuration fields (`provider`, `timestamp`, `success`, `error_message`)
- completion info (`agent_result`, `session_url`, `execution_time`)

## Running a Single Task
Use `browser_test.py` when you need to debug prompts or provider wiring:
```bash
python browser_test.py --provider steelbrowser --task "Find the latest pricing for the Oculus Quest 3" --no-stealth
```
This script spins up the requested provider, launches the `browser_use.Agent`, streams intermediate logging, and returns both the final natural-language answer and any provider session URL/recording. Cleanup is performed automatically even on failure.

## Provider Behaviors
All adapters follow the same two-function contract but expose slightly different features:
- **Anchor** – provisions a mobile proxy with CAPTCHA solving and returns a CDP URL alongside recording links.
- **Browserbase** – can enable `advanced_stealth` + proxies; session URLs follow `https://www.browserbase.com/sessions/<id>`.
- **SteelBrowser** – REST API for session creation/release with optional stealth payload (`useProxy`, `solveCaptcha`, `stealthConfig`).
- **Hyperbrowser** – REST API for session start/stop, optional stealth/captcha solving, and direct session playback URLs.

Because the runner calls `browser_test.main(...)`, any provider enhancements made there automatically propagate to batch runs.

## Customising Task Sets
The benchmark CSV expects four columns: `starting_url`, `Task`, `ground_truth_url`, and `Ground Truth`. Add rows, duplicate the file under a new name, and supply it via `--csv-file`. For quick smoke tests, trim the dataset or point to `test_tasks.csv` with a small subset of records.

## Operational Notes
- Logging is configured at `INFO` level in `run_browserbench.py`; per-task start/stop messages stream to stdout.
- Result files are overwritten only when you supply the same `--output` name. The default timestamped filenames are unique.
- Failures are captured with the raised exception stored in `error_message`; the row still appears in the CSV so aggregate success rates remain accurate.
- Session teardown happens in adapter-specific `cleanup_session(...)` calls. We still attempt to return human-usable session URLs even if the cleanup API raises.

## Next Steps
- Integrate the produced CSVs with your analytics tooling to visualise latency and success deltas per provider.
- Extend `providers/` with additional adapters by mirroring the `create_session`/`cleanup_session` contract and adding the provider name to the CLI choices in both scripts.
