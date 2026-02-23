from __future__ import annotations

import sys
import asyncio
import warnings
import io
from contextlib import redirect_stdout
from pathlib import Path
from typing import List

warnings.filterwarnings("ignore", category=UserWarning, module="fuzzywuzzy")
warnings.filterwarnings("ignore", message=".*python-Levenshtein.*")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

try:
    import tomllib
except ImportError:
    try:
        import toml as tomllib

        _original_load = tomllib.load

        def _compatible_load(f):
            if hasattr(f, "read"):
                content = f.read()
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                return tomllib.loads(content)
            return _original_load(f)

        tomllib.load = _compatible_load
    except ImportError:
        tomllib = None

CONFIG_FILE_NAME = ".secrets.toml"


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


def check_mcp_url_config() -> tuple[CheckResult, str]:
    """Check if MCP URL is configured in config file."""
    config_path = PROJECT_ROOT / "_settings" / CONFIG_FILE_NAME

    if not config_path.exists():
        return CheckResult(
            "MCP URL Config",
            False,
            "Config file not found",
            f"Expected: {config_path}",
        ), ""

    if tomllib is None:
        return CheckResult("MCP URL Config", False, "TOML parser not available"), ""

    try:
        with config_path.open("rb") as f:
            config = tomllib.load(f)

        mcp_url = config.get("mcp", {}).get("server_url", "")

        if not mcp_url:
            return CheckResult(
                "MCP URL Config", False, "MCP server_url is not configured"
            ), ""

        return CheckResult(
            "MCP URL Config", True, f"URL configured: {mcp_url}"
        ), mcp_url

    except Exception as e:
        return CheckResult(
            "MCP URL Config", False, f"Error reading config: {str(e)}"
        ), ""


async def check_mcp_connection() -> List[CheckResult]:
    """
    Actually connect to MCP server and load tools.
    This is the real connectivity test.
    """
    results = []

    # First check URL config
    url_result, mcp_url = check_mcp_url_config()
    results.append(url_result)

    if not url_result.passed or not mcp_url:
        return results

    # Try to import MCP client
    try:
        from local_deep_research.connect_mcp import (
            OrigeneMCPToolClient,
            mcp_servers,
        )

        results.append(
            CheckResult(
                "MCP Client Import",
                True,
                f"Client imported, {len(mcp_servers)} server configs found",
            )
        )
    except ImportError as e:
        results.append(
            CheckResult(
                "MCP Client Import",
                False,
                "Failed to import MCP client",
                f"Error: {str(e)}",
            )
        )
        return results
    except Exception as e:
        results.append(
            CheckResult(
                "MCP Client Import",
                False,
                f"Error importing MCP client: {str(e)}",
            )
        )
        return results

    # Try to connect and load tools
    try:
        print("  Connecting to MCP server and loading tools...", end="", flush=True)

        # Redirect stdout to capture print output during initialize().
        f = io.StringIO()
        with redirect_stdout(f):
            client = OrigeneMCPToolClient(mcp_servers)
            await client.initialize()

        tool_count = len(client.mcp_tools) if client.mcp_tools else 0
        tool_sources = len(client.tool2source) if client.tool2source else 0

        print("\r" + " " * 60 + "\r", end="")  # Clear the loading message

        if tool_count > 0:
            results.append(
                CheckResult(
                    "MCP Connection",
                    True,
                    f"Connected successfully, loaded {tool_count} tools from {tool_sources} sources",
                )
            )

            # Show some tool examples
            if client.mcp_tools:
                sample_tools = [t.name for t in client.mcp_tools[:5]]
                results.append(
                    CheckResult(
                        "MCP Tools Sample",
                        True,
                        f"Sample tools: {', '.join(sample_tools)}...",
                    )
                )
        else:
            results.append(
                CheckResult(
                    "MCP Connection",
                    False,
                    "Connected but no tools loaded",
                    "Server may be running but tools are not available",
                )
            )

    except ConnectionRefusedError:
        results.append(
            CheckResult(
                "MCP Connection",
                False,
                "Connection refused",
                "MCP server is not running or port is blocked",
            )
        )
    except TimeoutError:
        results.append(
            CheckResult(
                "MCP Connection",
                False,
                "Connection timeout",
                "Server did not respond in time",
            )
        )
    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages
        if "refused" in error_msg.lower():
            detail = "MCP server is not running"
        elif "timeout" in error_msg.lower():
            detail = "Server did not respond"
        elif "404" in error_msg or "not found" in error_msg.lower():
            detail = "MCP endpoint not found - check server configuration"
        elif "connection" in error_msg.lower():
            detail = "Network connection issue"
        else:
            detail = error_msg

        results.append(
            CheckResult(
                "MCP Connection",
                False,
                "Failed to connect and load tools",
                detail,
            )
        )

    return results


def run_checks() -> tuple[List[CheckResult], int, int]:
    results = asyncio.run(check_mcp_connection())

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    return results, passed, failed


def main():
    print("\n" + "=" * 60)
    print(" MCP Server Checks")
    print("=" * 60)

    print("\n> checking MCP server connection...")
    results, passed, failed = run_checks()

    for result in results:
        status_icon = "✓" if result.passed else "✗"
        print(f"  {status_icon} {result.name}: {result.message}")
        if result.details and not result.passed:
            print(f"    → {result.details}")

    if failed == 0:
        print(f"\n> ✓ MCP tool list ready ({passed} checks passed)")
    else:
        print(f"\n> ✗ MCP server check failed ({failed} failed, {passed} passed)")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
