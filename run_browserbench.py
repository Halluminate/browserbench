#!/usr/bin/env python3
"""
Browser benchmark runner script.

This script runs browser automation tasks from browserbench.csv using various browser providers
with configurable concurrency and task selection. It reuses the core session management logic
from browser_test.py for consistency and maintainability.

Usage:
    python run_browserbench.py --provider anchor --concurrency 3 --tasks 10
    python run_browserbench.py --provider browserbase --concurrency 5 --tasks 50
    python run_browserbench.py --provider browserbase --no-stealth --concurrency 3
    python run_browserbench.py --help

Environment variables required:
- For Anchor: ANCHOR_API_KEY
- For Browserbase: BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID
- For Steel: STEEL_API_KEY
- For Hyperbrowser: HYPERBROWSER_API_KEY
- For all: OPENAI_API_KEY
"""

import argparse
import asyncio
import csv
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Data class to store benchmark results"""

    task_id: int
    starting_url: str
    task_description: str
    ground_truth_url: str
    ground_truth: str
    status: str
    provider: str
    session_id: Optional[str]
    session_url: Optional[str]
    launched_at: str
    agent_result: Optional[str]
    success: Optional[bool]
    error_message: Optional[str]
    task_duration: Optional[float]


class BrowserBenchmarkRunner:
    """Main class for running browser benchmarks"""

    def __init__(
        self,
        provider: str = "anchor",
        concurrency: int = 3,
        no_stealth: bool = False,
        output_file: Optional[str] = None,
    ):
        self.provider = provider
        self.concurrency = concurrency
        self.no_stealth = no_stealth
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        self.output_file = output_file
        self._write_lock = asyncio.Lock()  # Lock for thread-safe CSV writes

    def load_tasks(self, csv_file: str, max_tasks: Optional[int] = None) -> List[Dict]:
        """Load tasks from CSV file"""
        tasks = []
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                if max_tasks and i > max_tasks:
                    break
                tasks.append(
                    {
                        "task_id": int(row["task_id"]),
                        "starting_url": row["starting_url"],
                        "task_description": row["task_description"],
                        "ground_truth_url": row["ground_truth_url"],
                        "ground_truth": row["ground_truth"],
                    }
                )
        return tasks

    def get_existing_task_ids(self, filepath: Path) -> set:
        """Get set of task_ids already in the output file"""
        if not filepath.exists():
            return set()
        
        existing_ids = set()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("task_id"):
                        existing_ids.add(int(row["task_id"]))
            logger.info(f"Found {len(existing_ids)} existing tasks in {filepath}")
        except Exception as e:
            logger.error(f"Error reading existing task IDs: {e}")
        
        return existing_ids

    def initialize_output_file(self, filepath: Path):
        """Create output CSV with headers if it doesn't exist"""
        if not filepath.exists():
            fieldnames = [
                "task_id",
                "starting_url",
                "task_description",
                "ground_truth_url",
                "ground_truth",
                "status",
                "provider",
                "session_id",
                "session_url",
                "launched_at",
                "agent_result",
                "success",
                "error_message",
                "task_duration",
            ]
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            logger.info(f"Created output file with headers: {filepath}")

    async def write_initial_task_row(self, filepath: Path, result: BenchmarkResult):
        """Write initial task row to CSV (thread-safe)"""
        async with self._write_lock:
            try:
                fieldnames = [
                    "task_id",
                    "starting_url",
                    "task_description",
                    "ground_truth_url",
                    "ground_truth",
                    "status",
                    "provider",
                    "session_id",
                    "session_url",
                    "launched_at",
                    "agent_result",
                    "success",
                    "error_message",
                    "task_duration",
                ]
                with open(filepath, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writerow(asdict(result))
                logger.info(f"Wrote initial row for task {result.task_id}")
            except Exception as e:
                logger.error(f"Error writing initial row for task {result.task_id}: {e}")
                raise

    async def update_task_row(self, filepath: Path, result: BenchmarkResult):
        """Update a task row in the CSV file (thread-safe)"""
        async with self._write_lock:
            try:
                # Read all rows
                rows = []
                fieldnames = []
                with open(filepath, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    rows = list(reader)
                
                # Update the matching row
                updated = False
                for i, row in enumerate(rows):
                    if int(row["task_id"]) == result.task_id:
                        rows[i] = asdict(result)
                        updated = True
                        break
                
                if not updated:
                    logger.warning(f"Task {result.task_id} not found in file, appending")
                    rows.append(asdict(result))
                
                # Write back
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                
                logger.info(f"Updated row for task {result.task_id}")
            except Exception as e:
                logger.error(f"Error updating row for task {result.task_id}: {e}")
                raise

    def format_task_with_url(self, task: Dict) -> str:
        """Format task with starting URL"""
        return f"{task['task_description']}. Begin task on the following url: {task['starting_url']}"

    async def run_task_background(
        self, task: Dict, output_filepath: Path, worker_id: int
    ) -> BenchmarkResult:
        """Run a single task in background, writing initial row and updating when complete"""
        # Import the working browser_test main function
        from browser_test import main as run_single_browser_task

        launched_at = datetime.now().isoformat()
        start_time = datetime.now()

        # Determine stealth setting
        stealth_enabled = (
            self.provider in ["browserbase", "steelbrowser", "hyperbrowser"]
            and not self.no_stealth
        )

        # Create initial result object
        result = BenchmarkResult(
            task_id=task["task_id"],
            starting_url=task["starting_url"],
            task_description=task["task_description"],
            ground_truth_url=task["ground_truth_url"],
            ground_truth=task["ground_truth"],
            status="running",
            provider=self.provider,
            session_id=None,
            session_url=None,
            launched_at=launched_at,
            agent_result=None,
            success=None,
            error_message=None,
            task_duration=None,
        )

        try:
            logger.info(f"Worker {worker_id}: Starting task {task['task_id']}")

            # Write initial row to file (before running task)
            await self.write_initial_task_row(output_filepath, result)

            # Use the working browser_test.main() function
            formatted_task = self.format_task_with_url(task)
            agent_result, session_url = await run_single_browser_task(
                provider=self.provider,
                stealth=stealth_enabled,
                task=formatted_task
            )

            # Calculate duration
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Update result with completion info
            result.agent_result = agent_result or ""
            result.success = True
            result.error_message = None
            result.task_duration = duration
            result.status = "completed"
            result.session_url = session_url or ""
            
            # Extract session_id from session_url if possible
            if session_url and "sessions/" in session_url:
                result.session_id = session_url.split("sessions/")[-1].split("?")[0].split("/")[0]

            # Update row in file
            await self.update_task_row(output_filepath, result)

            logger.info(
                f"Worker {worker_id}: Task {task['task_id']} completed in {duration:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(
                f"Worker {worker_id}: Error running task {task['task_id']}: {e}"
            )
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result.status = "failed"
            result.error_message = str(e)
            result.success = False
            result.task_duration = duration

            # Update row in file with error
            try:
                await self.update_task_row(output_filepath, result)
            except Exception as update_error:
                logger.error(f"Failed to update error status: {update_error}")

            return result

    async def launch_benchmark(
        self, tasks: List[Dict], output_filepath: Path
    ) -> List[BenchmarkResult]:
        """Launch benchmark tasks in background with concurrency control"""
        # Initialize output file with headers
        self.initialize_output_file(output_filepath)

        # Get existing task IDs to skip
        existing_task_ids = self.get_existing_task_ids(output_filepath)

        # Filter to only new tasks
        new_tasks = [t for t in tasks if t["task_id"] not in existing_task_ids]
        
        if not new_tasks:
            logger.info("All tasks already exist in output file, nothing to run")
            return []
        
        logger.info(
            f"Skipping {len(existing_task_ids)} existing tasks, running {len(new_tasks)} new tasks"
        )
        logger.info(
            f"Running {len(new_tasks)} tasks using {self.concurrency} concurrent workers"
        )

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.concurrency)

        async def run_with_semaphore(task: Dict, worker_id: int) -> BenchmarkResult:
            async with semaphore:
                return await self.run_task_background(task, output_filepath, worker_id)

        # Launch all tasks as background tasks
        background_tasks = []
        for i, task in enumerate(new_tasks):
            worker_id = i % self.concurrency
            bg_task = asyncio.create_task(run_with_semaphore(task, worker_id))
            background_tasks.append(bg_task)

        # Wait for all tasks to complete
        logger.info("All tasks launched, waiting for completion...")
        results = await asyncio.gather(*background_tasks, return_exceptions=True)

        # Process results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {new_tasks[i]['task_id']} failed: {result}")
                # Results already written by run_task_background, just track it
            else:
                final_results.append(result)

        logger.info(f"Completed {len(final_results)} tasks")
        return final_results

    def get_output_filepath(self, filename: Optional[str] = None) -> Path:
        """Get the output file path, using provider name if not provided"""
        if filename is None:
            filename = f"browserbench_results_{self.provider}.csv"

        return self.results_dir / filename


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Run browser benchmark tests")
    parser.add_argument(
        "--provider",
        choices=["anchor", "browserbase", "steelbrowser", "hyperbrowser"],
        default="anchor",
        help="Browser provider to use (default: anchor)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Number of concurrent browser sessions (default: 3)",
    )
    parser.add_argument(
        "--tasks",
        type=int,
        default=None,
        help="Number of tasks to run (default: all tasks in CSV)",
    )
    parser.add_argument(
        "--csv-file",
        type=str,
        default="browserbench.csv",
        help="Path to CSV file containing tasks (default: browserbench.csv)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV filename (default: browserbench_results_{provider}.csv)",
    )
    parser.add_argument(
        "--no-stealth",
        action="store_true",
        help="Disable advanced stealth mode for Browserbase, Steel, and Hyperbrowser (stealth is enabled by default)",
    )

    args = parser.parse_args()

    # Validate provider environment variables
    required_env_vars = {
        "anchor": ["ANCHOR_API_KEY"],
        "browserbase": ["BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID"],
        "steelbrowser": ["STEEL_API_KEY"],
        "hyperbrowser": ["HYPERBROWSER_API_KEY"],
    }

    missing_vars = []
    for var in required_env_vars[args.provider]:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        logger.error(
            f"Missing required environment variables for {args.provider}: {', '.join(missing_vars)}"
        )
        return 1

    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable is required")
        return 1

    # Initialize runner
    runner = BrowserBenchmarkRunner(
        provider=args.provider,
        concurrency=args.concurrency,
        no_stealth=args.no_stealth,
        output_file=args.output,
    )

    # Load tasks
    try:
        tasks = runner.load_tasks(args.csv_file, args.tasks)
        logger.info(f"Loaded {len(tasks)} tasks from {args.csv_file}")
    except Exception as e:
        logger.error(f"Error loading tasks: {e}")
        return 1

    if not tasks:
        logger.error("No tasks loaded")
        return 1

    # Get output file path
    output_filepath = runner.get_output_filepath(args.output)
    logger.info(f"Output will be written to: {output_filepath}")

    # Run benchmark tasks
    try:
        results = asyncio.run(runner.launch_benchmark(tasks, output_filepath))
        logger.info(f"Completed {len(results)} tasks")
    except Exception as e:
        logger.error(f"Error running benchmark: {e}")
        return 1

    # Print summary
    completed_tasks = sum(1 for r in results if r.status == "completed")
    failed_tasks = sum(1 for r in results if r.status == "failed")
    total_duration = sum(r.task_duration for r in results if r.task_duration)
    avg_duration = total_duration / len(results) if results else 0

    print("\n=== Benchmark Summary ===")
    print(f"Provider: {args.provider}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Total tasks: {len(results)}")
    print(f"Completed successfully: {completed_tasks}")
    print(f"Failed: {failed_tasks}")
    print(f"Total time: {total_duration:.2f}s")
    print(f"Average time per task: {avg_duration:.2f}s")
    print(f"\nResults saved to: {output_filepath}")
    print("\nView session recordings at the session_url column in the CSV")

    return 0


if __name__ == "__main__":
    exit(main())
