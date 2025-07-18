import argparse
import asyncio
import logging
import sys
from typing import Dict

from .config import settings
from .search_system import AdvancedSearchSystem





async def run_research(query: str, mode: str = "quick"):
    """Run research with specified query and mode"""
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info(f"\n🔬 Starting {mode} research for query: {query}")

    if mode == "quick":
        print("\nResearching... This may take a few minutes.\n")
        system = AdvancedSearchSystem(max_iterations=settings.quick.iteration, 
                                      questions_per_iteration=settings.quick.questions_per_iteration,
                                      is_report = False)
    else:
        print(
            "\nGenerating detailed report...  Please be patient as this enables deeper analysis.\n"
        )
        system = AdvancedSearchSystem(max_iterations=settings.detailed.iteration, 
                                      questions_per_iteration=settings.detailed.questions_per_iteration,
                                      is_report = True)
    await system.initialize()
    results = await system.analyze_topic(query)
    print("Research analysis completed")
    return results


async def main():
    """Main function with both interactive and CLI support"""
    # Check if running with command line arguments
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="OriAgent Local Deep Research")
        parser.add_argument("query", help="Research query")
        parser.add_argument(
            "--mode",
            choices=["quick", "detailed"],
            default="quick",
            help="Research mode (default: quick)",
        )
        parser.add_argument(
            "--deep",
            action="store_true",
            help="Use detailed research mode (equivalent to --mode detailed)",
        )

        args = parser.parse_args()

        # Handle --deep flag
        mode = "detailed" if args.deep else args.mode

        # Run research with CLI arguments
        await run_research(args.query, mode)
        return

    # Interactive mode (original behavior)
    print("Welcome to the Advanced Research System")
    print("Type 'quit' to exit")

    while True:
        print("\nSelect output type:")
        print("1) Analysis (Few minutes, answer questions, summarize findings)")
        print("2) Detailed Report (More time, generates comprehensive report with deep analysis)"
        )
        choice = input("Enter number (1 or 2): ").strip()

        while choice not in ["1", "2"]:
            print("\nInvalid input. Please enter 1 or 2:")
            print("1) Analysis (Few minutes, answer questions, summarize findings)")
            print("2) Detailed Report (More time, generates comprehensive report with deep analysis)")
            choice = input("Enter number (1 or 2): ").strip()
        query = input("\nEnter your research query: ").strip()

        if query.lower() == "quit":
            break

        mode = "quick" if choice == "1" else "detailed"
        await run_research(query, mode)


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
