from __future__ import annotations

import sys
import warnings
import importlib
from pathlib import Path
from typing import List

warnings.filterwarnings("ignore", category=UserWarning, module="fuzzywuzzy")
warnings.filterwarnings("ignore", message=".*python-Levenshtein.*")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

CORE_MODULES = [
    "local_deep_research",
    "local_deep_research.config",
    "local_deep_research.connect_mcp",
    "local_deep_research.search_system",
    "local_deep_research.tool_selector",
    "local_deep_research.tool_executor",
    "local_deep_research.data_structures",
    "local_deep_research.tool_parsers",
    "local_deep_research.evidence_parser",
    "local_deep_research.trace_logger",
    "local_deep_research.search_system_support",
    "local_deep_research.tool_embedding_retriever",
    "local_deep_research.utils",
    "local_deep_research.utilties.search_utilities",
]


class CheckResult:
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


def check_module_import(module_name: str) -> CheckResult:
    try:
        importlib.import_module(module_name)
        return CheckResult(module_name, True, "Import successful")
    except ImportError as e:
        return CheckResult(module_name, False, "Import failed", f"Error: {str(e)}")
    except Exception as e:
        return CheckResult(
            module_name,
            False,
            "Error during import",
            f"Error: {type(e).__name__}: {str(e)}",
        )


def check_core_classes() -> List[CheckResult]:
    results = []

    try:
        from local_deep_research import AdvancedSearchSystem

        results.append(CheckResult("AdvancedSearchSystem", True, "Class accessible"))
    except Exception as e:
        results.append(
            CheckResult("AdvancedSearchSystem", False, f"Cannot access class: {str(e)}")
        )

    try:
        from local_deep_research.config import (
            get_gpt4_1,
            get_gpt4_1_mini,
            get_deepseek_r1,
            get_deepseek_v3,
        )

        results.append(
            CheckResult(
                "Config Model Functions", True, "All model config functions accessible"
            )
        )
    except Exception as e:
        results.append(
            CheckResult(
                "Config Model Functions",
                False,
                f"Cannot access config functions: {str(e)}",
            )
        )

    try:
        from local_deep_research.connect_mcp import OrigeneMCPToolClient, mcp_servers

        results.append(
            CheckResult(
                "MCP Client Classes",
                True,
                f"OrigeneMCPToolClient accessible, {len(mcp_servers)} servers configured",
            )
        )
    except Exception as e:
        results.append(
            CheckResult(
                "MCP Client Classes", False, f"Cannot access MCP client: {str(e)}"
            )
        )

    try:
        from local_deep_research.tool_selector import (
            ToolSelector,
            ExpertToolSelector,
            GeneralToolSelector,
        )

        results.append(
            CheckResult(
                "Tool Selector Classes", True, "All tool selector classes accessible"
            )
        )
    except Exception as e:
        results.append(
            CheckResult(
                "Tool Selector Classes",
                False,
                f"Cannot access tool selectors: {str(e)}",
            )
        )

    return results


def run_checks() -> tuple[List[CheckResult], int, int]:
    results = []

    for module in CORE_MODULES:
        results.append(check_module_import(module))

    for result in check_core_classes():
        results.append(result)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    return results, passed, failed


def main():
    print("\n" + "=" * 60)
    print(" Module Import Checks")
    print("=" * 60)

    print("\n> checking module imports...")
    results, passed, failed = run_checks()

    for result in results:
        status_icon = "✓" if result.passed else "✗"
        print(f"  {status_icon} {result.name}: {result.message}")
        if result.details and not result.passed:
            print(f"    → {result.details}")

    if failed == 0:
        print(f"\n> ✓ All modules ready ({passed} modules checked)")
    else:
        print(f"\n> ✗ Module import check failed ({failed} failed, {passed} passed)")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
