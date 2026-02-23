from __future__ import annotations

import sys
import warnings
import importlib.util
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning, module="fuzzywuzzy")
warnings.filterwarnings("ignore", message=".*python-Levenshtein.*")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = Path(__file__).resolve().parent


def _import_check_modules():
    """Import check modules using importlib (no __init__.py needed)."""
    modules = {}
    for module_name in ["check_deps", "check_config", "check_mcp", "check_modules"]:
        module_path = TEST_DIR / f"{module_name}.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules[module_name] = module
    return (
        modules["check_deps"],
        modules["check_config"],
        modules["check_mcp"],
        modules["check_modules"],
    )


def main():
    # Import check modules
    check_deps, check_config, check_mcp, check_modules = _import_check_modules()

    print("\n" + "=" * 70)
    print(" " * 20 + "OriGene Environment Check")
    print("=" * 70)
    print(f"\nProject Root: {PROJECT_ROOT}")
    print(f"Python: {sys.executable}")
    print(f"Version: {sys.version.split()[0]}\n")

    total_passed = 0
    total_failed = 0

    # 1. Dependency checks
    print("> testing dependencies...")
    results, passed, failed = check_deps.run_checks()
    if failed == 0:
        print(f"> ✓ Dependencies ready ({passed} packages checked)")
    else:
        print(f"> ✗ Dependencies check failed ({failed} failed, {passed} passed)")
    for result in results:
        status_icon = "✓" if result.passed else "✗"
        print(f"  {status_icon} {result.name}: {result.message}")
        if result.details and not result.passed:
            print(f"    → {result.details}")
    total_passed += passed
    total_failed += failed
    print()

    # 2. Configuration checks
    print("> checking LLM API keys...")
    results, passed, failed = check_config.run_checks()
    if failed == 0:
        print(f"> ✓ LLM API keys ready ({passed} APIs configured)")
    else:
        print(f"> ✗ LLM API keys check failed ({failed} failed, {passed} passed)")
    for result in results:
        status_icon = "✓" if result.passed else "✗"
        print(f"  {status_icon} {result.name}: {result.message}")
    total_passed += passed
    total_failed += failed
    print()

    # 3. MCP server checks
    print("> checking MCP server connection...")
    results, passed, failed = check_mcp.run_checks()
    if failed == 0:
        print(f"> ✓ MCP tool list ready ({passed} checks passed)")
    else:
        print(f"> ✗ MCP server check failed ({failed} failed, {passed} passed)")
    for result in results:
        status_icon = "✓" if result.passed else "✗"
        print(f"  {status_icon} {result.name}: {result.message}")
        if result.details and not result.passed:
            print(f"    → {result.details}")
    total_passed += passed
    total_failed += failed
    print()

    # 4. Module import checks
    print("> checking module imports...")
    results, passed, failed = check_modules.run_checks()
    if failed == 0:
        print(f"> ✓ All modules ready ({passed} modules checked)")
    else:
        print(f"> ✗ Module import check failed ({failed} failed, {passed} passed)")
    for result in results:
        status_icon = "✓" if result.passed else "✗"
        print(f"  {status_icon} {result.name}: {result.message}")
        if result.details and not result.passed:
            print(f"    → {result.details}")
    total_passed += passed
    total_failed += failed
    print()

    # Final summary
    print("=" * 70)
    if total_failed == 0:
        print("> ✓ SUCCESS! You can run OriGene now!")
        print(f"\n  All {total_passed} checks passed. Your environment is ready!")
        return 0
    else:
        print(f"> ✗ FAILED: {total_failed} check(s) failed")
        print(f"\n  Total: {total_passed + total_failed} checks")
        print(f"  Passed: {total_passed}")
        print(f"  Failed: {total_failed}")
        print("\n  Please resolve the issues above before running OriGene.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
