from __future__ import annotations

import sys
import asyncio
import importlib.util
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT.parent))


# =============================================================================
# Test Data
# =============================================================================

TEST_QUERY = "What is ATP?"
EXPECTED_KEYWORDS = ["adenosine", "triphosphate", "energy", "cell"]


# =============================================================================
# Helpers
# =============================================================================


class TestResult:
    def __init__(self, name: str, passed: bool, message: str, details: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details

    def __str__(self) -> str:
        status = "[PASS]" if self.passed else "[FAIL]"
        result = f"{status} {self.name}: {self.message}"
        if self.details:
            result += f"\n         {self.details}"
        return result


def _import_check_module(module_name: str):
    """Import a check module from test directory."""
    module_path = TEST_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None


def response_contains_keywords(response: str, keywords: list[str]) -> bool:
    """Check if response contains at least one expected keyword."""
    response_lower = response.lower()
    return any(kw.lower() in response_lower for kw in keywords)


# =============================================================================
# Section 1: Environment Self-Check
# =============================================================================


def run_environment_check() -> tuple[list[TestResult], int, int]:
    """Run all environment checks from check_*.py modules."""
    results = []

    check_deps = _import_check_module("check_deps")
    check_config = _import_check_module("check_config")
    check_modules = _import_check_module("check_modules")

    # Dependency checks
    dep_results, _, _ = check_deps.run_checks()
    for r in dep_results:
        results.append(
            TestResult(r.name, r.passed, r.message, getattr(r, "details", ""))
        )

    # Config checks
    cfg_results, _, _ = check_config.run_checks()
    for r in cfg_results:
        results.append(
            TestResult(r.name, r.passed, r.message, getattr(r, "details", ""))
        )

    # Module checks
    mod_results, _, _ = check_modules.run_checks()
    for r in mod_results:
        results.append(
            TestResult(r.name, r.passed, r.message, getattr(r, "details", ""))
        )

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    return results, passed, failed


# =============================================================================
# Section 2: MCP Tool Test
# =============================================================================

# Known working tool configurations for testing
MCP_TEST_TOOLS = [
    {
        "server": "ncbi_mcp",
        "tool": "get_gene_metadata_by_gene_name",
        "args": {"name": "TP53"},
    },
    {
        "server": "ncbi_mcp",
        "tool": "search_pubmed",
        "args": {"query": "TP53 cancer", "max_results": 1},
    },
    {
        "server": "pubchem_mcp",
        "tool": "search_compound_by_name",
        "args": {"name": "aspirin"},
    },
]


async def run_mcp_tool_test() -> tuple[list[TestResult], int, int]:
    """Connect to MCP server and call a simple tool."""
    results = []

    print("  Importing MCP client...")
    from local_deep_research.connect_mcp import OrigeneMCPToolClient, mcp_servers

    # Use ncbi_mcp for test
    test_config = MCP_TEST_TOOLS[0]
    minimal_servers = {test_config["server"]: mcp_servers[test_config["server"]]}

    print("  Connecting to MCP server...")
    client = OrigeneMCPToolClient(minimal_servers)
    await client.initialize()

    tool_count = len(client.mcp_tools) if client.mcp_tools else 0
    results.append(
        TestResult(
            "MCP Connection", tool_count > 0, f"Connected, {tool_count} tools loaded"
        )
    )

    if tool_count == 0:
        results.append(TestResult("MCP Tool Call", False, "No tools available"))
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        return results, passed, failed

    # Call the configured test tool
    tool_name = test_config["tool"]
    tool_args = test_config["args"]
    print(f"  Calling tool: {tool_name} with {tool_args}...")

    result = await client.call_tool(tool_name, tool_args)

    is_success = result is not None and len(str(result)) > 10
    results.append(
        TestResult(
            "MCP Tool Call",
            is_success,
            f"Tool '{tool_name}' returned {len(str(result))} chars"
            if is_success
            else "Empty response",
        )
    )

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    return results, passed, failed


# =============================================================================
# Section 3: LLM Query Test
# =============================================================================


def run_llm_query_test() -> tuple[list[TestResult], int, int]:
    """Send a simple query to the LLM."""
    results = []

    print("  Initializing LLM client...")
    from local_deep_research.config import get_gpt4_1_mini

    llm = get_gpt4_1_mini()
    results.append(
        TestResult("LLM Client Init", llm is not None, "GPT-4.1-mini initialized")
    )

    prompt = f"Answer in 2 sentences: {TEST_QUERY}"
    print(f"  Sending query: '{TEST_QUERY}'...")

    response = llm.invoke(prompt)
    response_text = response.content if hasattr(response, "content") else str(response)

    is_success = response_text is not None and len(response_text) > 20
    results.append(
        TestResult(
            "LLM Query",
            is_success,
            f"Response: {len(response_text)} chars" if is_success else "Empty response",
        )
    )

    if is_success:
        has_keywords = response_contains_keywords(response_text, EXPECTED_KEYWORDS)
        results.append(
            TestResult(
                "Response Validation",
                has_keywords,
                "Contains expected keywords" if has_keywords else "Missing keywords",
            )
        )

        preview = response_text[:150].replace("\n", " ")
        results.append(TestResult("Response Preview", True, preview + "..."))

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    return results, passed, failed


# =============================================================================
# Main
# =============================================================================


async def main() -> int:
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print(" OriGene End-to-End Test")
    print("=" * 60)
    print(f"\n  Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.executable}")
    print(f"  Project: {PROJECT_ROOT}")

    total_passed = 0
    total_failed = 0

    # Section 1: Environment Check
    print("\n" + "-" * 60)
    print(" [1/3] Environment Self-Check")
    print("-" * 60)

    results, passed, failed = run_environment_check()
    total_passed += passed
    total_failed += failed

    # Show only failed checks to keep output clean
    failed_checks = [r for r in results if not r.passed]
    if failed_checks:
        print(f"  Failed checks ({len(failed_checks)}):")
        for r in failed_checks[:10]:  # Show first 10 failures
            print(f"    {r}")
        if len(failed_checks) > 10:
            print(f"    ... and {len(failed_checks) - 10} more")

    status = "PASS" if failed == 0 else "FAIL"
    print(f"\n  Result: [{status}] {passed} passed, {failed} failed")

    # Section 2: MCP Tool Test
    print("\n" + "-" * 60)
    print(" [2/3] MCP Tool Test")
    print("-" * 60)

    results, passed, failed = await run_mcp_tool_test()
    total_passed += passed
    total_failed += failed

    for r in results:
        print(f"  {r}")

    status = "PASS" if failed == 0 else "FAIL"
    print(f"\n  Result: [{status}] {passed} passed, {failed} failed")

    # Section 3: LLM Query Test
    print("\n" + "-" * 60)
    print(" [3/3] LLM Query Test")
    print("-" * 60)

    results, passed, failed = run_llm_query_test()
    total_passed += passed
    total_failed += failed

    for r in results:
        print(f"  {r}")

    status = "PASS" if failed == 0 else "FAIL"
    print(f"\n  Result: [{status}] {passed} passed, {failed} failed")

    # Final Summary
    duration = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 60)
    print(" Final Summary")
    print("=" * 60)
    print(f"\n  Total: {total_passed + total_failed} checks")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"  Duration: {duration:.2f}s")

    if total_failed == 0:
        print("\n  ALL TESTS PASSED, YOU CAN RUN ORIGENE NOW")
        return 0
    else:
        print(f"\n  {total_failed} TESTS FAILED, PLEASE FIX THE ISSUES AND TRY AGAIN")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
