from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import List

warnings.filterwarnings("ignore", category=UserWarning, module="fuzzywuzzy")
warnings.filterwarnings("ignore", message=".*python-Levenshtein.*")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

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

# LLM provider configuration - you can add custom providers here.
# Format: {config_key: (display_name, required)}
LLM_PROVIDERS = {
    "openai": ("OpenAI", False),  # OpenAI (optional)
    "deepseek": ("DeepSeek", False),  # DeepSeek (optional)
    "closeai": (
        "CloseAI",
        False,
    ),  # CloseAI (optional; can be used as fallback for OpenAI/DeepSeek)
    "template": ("Template/Embedding", False),  # Template/Embedding API (optional)
    "volcengine": ("SiliconFlow", False),  # SiliconFlow (optional)
    # Add more providers here, for example:
    # "custom_provider": ("Custom Provider", False),
}


class CheckResult:
    def __init__(self, name: str, passed: bool, message: str):
        self.name = name
        self.passed = passed
        self.message = message

    def __str__(self) -> str:
        status = "[PASS]" if self.passed else "[FAIL]"
        return f"{status} {self.name}: {self.message}"


def load_config() -> dict | None:
    """Load configuration file."""
    config_path = PROJECT_ROOT / "_settings" / CONFIG_FILE_NAME
    if not config_path.exists():
        return None
    if tomllib is None:
        return None
    with config_path.open("rb") as f:
        return tomllib.load(f)


def test_llm_api(
    provider_key: str, provider_name: str, api_key: str, api_base: str
) -> CheckResult:
    """Generic LLM API test function, supports all OpenAI-compatible APIs."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=api_base, timeout=30)
        models = client.models.list()
        count = len(list(models))
        return CheckResult(
            f"{provider_name} API", True, f"OK ({count} models available)"
        )
    except Exception as e:
        err = str(e)
        if "401" in err or "Unauthorized" in err or "invalid" in err.lower():
            return CheckResult(f"{provider_name} API", False, "Invalid API key")
        elif "timeout" in err.lower():
            return CheckResult(f"{provider_name} API", False, "Connection timeout")
        elif "connection" in err.lower():
            return CheckResult(f"{provider_name} API", False, "Connection failed")
        return CheckResult(f"{provider_name} API", False, f"Error: {err[:60]}")


def run_checks() -> tuple[List[CheckResult], int, int]:
    results = []

    # Check config file
    config_path = PROJECT_ROOT / "_settings" / CONFIG_FILE_NAME
    if not config_path.exists():
        results.append(CheckResult("Config File", False, "Not found"))
        return results, 0, 1

    results.append(CheckResult("Config File", True, "Found"))

    # Load config
    config = load_config()
    if config is None:
        results.append(CheckResult("Config Parse", False, "Cannot parse TOML"))
        return results, 1, 1

    # Get closeai config if available (for fallback)
    closeai_config = None
    if "closeai" in config:
        closeai_api_key = config["closeai"].get("api_key", "")
        closeai_api_base = config["closeai"].get("api_base", "")
        if (
            closeai_api_key
            and closeai_api_base
            and closeai_api_key != "your-closeai-api-key-here"
        ):
            closeai_config = (closeai_api_key, closeai_api_base)

    # Test all configured LLM providers (Support custom providers)
    configured_providers = []
    openai_passed = False
    deepseek_passed = False

    for provider_key, (provider_name, required) in LLM_PROVIDERS.items():
        # Skip closeai in main loop, we'll handle it separately
        if provider_key == "closeai":
            continue

        if provider_key in config:
            api_key = config[provider_key].get("api_key", "")
            api_base = config[provider_key].get("api_base", "")
            # Check if api_key is a valid (non-default) value
            default_key = f"your-{provider_key}-api-key-here"
            if (
                api_key
                and api_base
                and api_key != default_key
                and api_key != "your-openai-api-key-here"  # Also check generic default
            ):
                result = test_llm_api(provider_key, provider_name, api_key, api_base)
                results.append(result)
                if result.passed:
                    configured_providers.append(provider_name)
                    if provider_key == "openai":
                        openai_passed = True
                    elif provider_key == "deepseek":
                        deepseek_passed = True
            else:
                if required:
                    results.append(
                        CheckResult(
                            f"{provider_name} API", False, "Not configured (required)"
                        )
                    )
                else:
                    # If not configured and closeai is available, use closeai as fallback
                    if closeai_config and provider_key in ["openai", "deepseek"]:
                        fallback_result = test_llm_api(
                            provider_key,
                            provider_name,
                            closeai_config[0],
                            closeai_config[1],
                        )
                        results.append(fallback_result)
                        if fallback_result.passed:
                            configured_providers.append(provider_name)
                            if provider_key == "openai":
                                openai_passed = True
                            elif provider_key == "deepseek":
                                deepseek_passed = True
                    else:
                        results.append(
                            CheckResult(
                                f"{provider_name} API",
                                False,
                                "Not configured (optional)",
                            )
                        )
        else:
            if required:
                results.append(
                    CheckResult(
                        f"{provider_name} API", False, "Not configured (required)"
                    )
                )
            else:
                # If not configured and closeai is available, use closeai as fallback
                if closeai_config and provider_key in ["openai", "deepseek"]:
                    fallback_result = test_llm_api(
                        provider_key,
                        provider_name,
                        closeai_config[0],
                        closeai_config[1],
                    )
                    results.append(fallback_result)
                    if fallback_result.passed:
                        configured_providers.append(provider_name)
                        if provider_key == "openai":
                            openai_passed = True
                        elif provider_key == "deepseek":
                            deepseek_passed = True
                # Optional providers are not configured, do not display errors

    # Check if there is at least one LLM provider configured successfully
    if not configured_providers:
        results.append(
            CheckResult("LLM Providers", False, "No LLM provider configured")
        )
    else:
        results.append(
            CheckResult(
                "LLM Providers", True, f"Configured: {', '.join(configured_providers)}"
            )
        )

    # Check MCP URL configured
    if "mcp" in config and config["mcp"].get("server_url"):
        results.append(CheckResult("MCP URL", True, "Configured"))
    else:
        results.append(CheckResult("MCP URL", False, "Not configured"))

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    return results, passed, failed


def main():
    print("\n" + "=" * 60)
    print(" Configuration Checks")
    print("=" * 60)

    print("\n> checking LLM API keys...")
    results, passed, failed = run_checks()

    for result in results:
        status_icon = "✓" if result.passed else "✗"
        print(f"  {status_icon} {result.name}: {result.message}")

    if failed == 0:
        print(f"\n> ✓ LLM API keys ready ({passed} APIs configured)")
    else:
        print(f"\n> ✗ LLM API keys check failed ({failed} failed, {passed} passed)")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
