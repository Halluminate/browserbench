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
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Import browser automation components (only LLM needed for configuration)
# Import the main function from browser_test.py to reuse session management logic
from browser_test import main as run_single_browser_task
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
    provider: str
    agent_result: str
    session_url: Optional[str]
    success: bool
    error_message: Optional[str]
    execution_time: float
    timestamp: str


class BrowserBenchmarkRunner:
    """Main class for running browser benchmarks"""

    def __init__(
        self, provider: str = "anchor", concurrency: int = 3, no_stealth: bool = False
    ):
        self.provider = provider
        self.concurrency = concurrency
        self.no_stealth = no_stealth
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)

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
                        "task_id": i,
                        "starting_url": row["starting_url"],
                        "task_description": row["Task"],
                        "ground_truth_url": row["ground_truth_url"],
                        "ground_truth": row["Ground Truth"],
                    }
                )
        return tasks

    def format_task_with_url(self, task: Dict) -> str:
        """Format task with starting URL"""
        return f"{task['task_description']}. Begin task on the following url: {task['starting_url']}"

    async def run_single_task(self, task: Dict, worker_id: int) -> BenchmarkResult:
        """Run a single task using the browser_test.py main function"""
        start_time = time.time()
        result = BenchmarkResult(
            task_id=task["task_id"],
            starting_url=task["starting_url"],
            task_description=task["task_description"],
            ground_truth_url=task["ground_truth_url"],
            ground_truth=task["ground_truth"],
            provider=self.provider,
            agent_result="",
            session_url=None,
            success=False,
            error_message=None,
            execution_time=0.0,
            timestamp=datetime.now().isoformat(),
        )

        try:
            logger.info(f"Worker {worker_id}: Starting task {task['task_id']}")

            # Use the main function from browser_test.py
            # Determine stealth setting based on provider and no_stealth flag
            stealth_enabled = (
                self.provider in ["browserbase", "steelbrowser", "hyperbrowser"]
                and not self.no_stealth
            )

            formatted_task = self.format_task_with_url(task)
            agent_result, session_url = await run_single_browser_task(
                provider=self.provider, stealth=stealth_enabled, task=formatted_task
            )

            result.agent_result = agent_result
            result.session_url = session_url
            result.success = True

        except Exception as e:
            logger.error(
                f"Worker {worker_id}: Error running task {task['task_id']}: {e}"
            )
            result.error_message = str(e)
            result.success = False

        result.execution_time = time.time() - start_time
        return result

    async def run_benchmark(self, tasks: List[Dict]) -> List[BenchmarkResult]:
        """Run benchmark with concurrency control"""
        semaphore = asyncio.Semaphore(self.concurrency)
        results = []

        async def run_task_with_semaphore(
            task: Dict, worker_id: int
        ) -> BenchmarkResult:
            async with semaphore:
                return await self.run_single_task(task, worker_id)

        # Create tasks with worker IDs
        benchmark_tasks = []
        for i, task in enumerate(tasks):
            worker_id = i % self.concurrency
            benchmark_tasks.append(run_task_with_semaphore(task, worker_id))

        # Execute all tasks concurrently
        logger.info(
            f"Starting benchmark with {len(tasks)} tasks using {self.concurrency} concurrent workers"
        )
        results = await asyncio.gather(*benchmark_tasks, return_exceptions=True)

        # Handle any exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed with exception: {result}")
                # Create a failed result
                failed_result = BenchmarkResult(
                    task_id=tasks[i]["task_id"],
                    starting_url=tasks[i]["starting_url"],
                    task_description=tasks[i]["task_description"],
                    ground_truth_url=tasks[i]["ground_truth_url"],
                    ground_truth=tasks[i]["ground_truth"],
                    provider=self.provider,
                    agent_result="",
                    session_url=None,
                    success=False,
                    error_message=str(result),
                    execution_time=0.0,
                    timestamp=datetime.now().isoformat(),
                )
                final_results.append(failed_result)
            else:
                final_results.append(result)

        return final_results

    def save_results_to_csv(
        self, results: List[BenchmarkResult], filename: Optional[str] = None
    ):
        """Save results to CSV file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"browserbench_results_{self.provider}_{timestamp}.csv"

        filepath = self.results_dir / filename

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            if results:
                fieldnames = results[0].__dataclass_fields__.keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for result in results:
                    writer.writerow(asdict(result))

        logger.info(f"Results saved to {filepath}")
        return filepath


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
        help="Output CSV filename (default: auto-generated with timestamp)",
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
        provider=args.provider, concurrency=args.concurrency, no_stealth=args.no_stealth
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

    # Run benchmark
    try:
        results = asyncio.run(runner.run_benchmark(tasks))
        logger.info(f"Completed {len(results)} tasks")
    except Exception as e:
        logger.error(f"Error running benchmark: {e}")
        return 1

    # Save results
    try:
        output_file = runner.save_results_to_csv(results, args.output)
        logger.info(f"Benchmark completed successfully. Results saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving results: {e}")
        return 1

    # Print summary
    successful_tasks = sum(1 for r in results if r.success)
    total_time = sum(r.execution_time for r in results)
    avg_time = total_time / len(results) if results else 0

    print("\n=== Benchmark Summary ===")
    print(f"Provider: {args.provider}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Tasks completed: {len(results)}")
    print(
        f"Successful: {successful_tasks} ({successful_tasks / len(results) * 100:.1f}%)"
    )
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time per task: {avg_time:.2f}s")
    print(f"Results saved to: {output_file}")

    return 0


if __name__ == "__main__":
    exit(main())
