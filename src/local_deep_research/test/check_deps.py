from __future__ import annotations

import sys
import warnings
import importlib
import re
from typing import List

warnings.filterwarnings("ignore", category=UserWarning, module="fuzzywuzzy")
warnings.filterwarnings("ignore", message=".*python-Levenshtein.*")

REQUIRED_PYTHON_VERSION = (3, 13)

# All dependencies from pyproject.toml (import_name, min_version)
DEPENDENCIES = [
    ("aiocache", "0.12.3"),
    ("aiofiles", "24.1.0"),
    ("anthropic", "0.52.2"),
    ("anyio", "4.9.0"),
    ("arxiv", "2.2.0"),
    ("bcrypt", "4.3.0"),
    ("Bio", "1.8.0"),
    ("browser_use", "0.1.24"),
    ("click", "8.2.1"),
    ("colorlog", "6.9.0"),
    ("datasets", "3.6.0"),
    ("dynaconf", "3.2.11"),
    ("email_validator", "2.2.0"),
    ("fabric", "3.2.2"),
    ("fastapi", "0.115.12"),
    ("fuzzywuzzy", "0.18.0"),
    ("gseapy", "1.1.9"),
    ("humanize", "4.12.3"),
    ("IPython", "9.3.0"),
    ("langchain", "0.3.25"),
    ("langchain_deepseek", "0.1.3"),
    ("langchain_mcp_adapters", "0.1.7"),
    ("langchain_ollama", "0.3.3"),
    ("langgraph", "0.4.8"),
    ("langgraph_cli", "0.3.1"),
    ("markdown2", "2.5.3"),
    ("mcp", "1.9.3"),
    ("memoization", "0.4.0"),
    ("networkx", "3.5"),
    ("openai", "1.84.0"),
    ("openpyxl", "3.1.5"),
    ("passlib", "1.7.4"),
    ("platformdirs", "4.3.8"),
    ("playwright", "1.52.0"),
    ("psutil", "7.0.0"),
    ("base62", "1.0.0"),
    ("jwt", "2.10.1"),
    ("pymupdf", "1.26.1"),
    ("pymysql", "1.1.1"),
    ("pytest", "8.4.0"),
    ("pytest_asyncio", "1.0.0"),
    ("docx", "1.1.2"),
    ("dotenv", "1.1.0"),
    ("pptx", "1.0.2"),
    ("zmq", "26.4.0"),
    ("ruff", "0.12.1"),
    ("sklearn", "1.7.0"),
    ("snowflake", "1.0.2"),
    ("sqlmodel", "0.0.24"),
    ("toml", "0.10.2"),
    ("tooluniverse", "0.2.0"),
    ("unstructured", "0.17.2"),
    ("weasyprint", "65.1"),
]

PACKAGE_NAME_MAP = {
    "sklearn": "scikit-learn",
    "jwt": "pyjwt",
    "docx": "python-docx",
    "dotenv": "python-dotenv",
    "pptx": "python-pptx",
    "zmq": "pyzmq",
    "IPython": "ipython",
    "browser_use": "browser-use",
    "snowflake": "snowflake-id",
    "Bio": "bio",
    "base62": "pybase62",
}


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


def compare_versions(v1: str, v2: str) -> int:
    def normalize(v):
        parts = re.findall(r"\d+", v)
        return [int(x) for x in parts]

    try:
        v1_parts = normalize(v1)
        v2_parts = normalize(v2)
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        for a, b in zip(v1_parts, v2_parts):
            if a < b:
                return -1
            elif a > b:
                return 1
        return 0
    except Exception:
        return 0


def check_python_version() -> CheckResult:
    current = sys.version_info[:2]
    required = REQUIRED_PYTHON_VERSION

    if current >= required:
        return CheckResult(
            "Python Version",
            True,
            f"Python {current[0]}.{current[1]} (required: >= {required[0]}.{required[1]})",
        )
    else:
        return CheckResult(
            "Python Version",
            False,
            f"Python {current[0]}.{current[1]} is below required version",
            f"Required: Python >= {required[0]}.{required[1]}",
        )


def check_dependency(import_name: str, min_version: str) -> CheckResult:
    pip_name = PACKAGE_NAME_MAP.get(import_name, import_name)

    try:
        module = importlib.import_module(import_name)

        try:
            from importlib.metadata import version as get_version

            installed_version = get_version(pip_name.replace("_", "-"))
        except Exception:
            installed_version = getattr(module, "__version__", "unknown")

        if installed_version == "unknown":
            return CheckResult(
                pip_name,
                True,
                f"Installed (version unknown, required: >= {min_version})",
            )

        if compare_versions(installed_version, min_version) >= 0:
            return CheckResult(
                pip_name,
                True,
                f"version {installed_version} (required: >= {min_version})",
            )
        else:
            return CheckResult(
                pip_name,
                False,
                f"version {installed_version} is below required",
                f"Required: >= {min_version}",
            )

    except ImportError:
        return CheckResult(
            pip_name,
            False,
            "Not installed",
            f"Install with: uv add {pip_name}",
        )
    except Exception as e:
        return CheckResult(pip_name, False, f"Error checking package: {str(e)}")


def run_checks() -> tuple[List[CheckResult], int, int]:
    results = []

    results.append(check_python_version())

    for import_name, version in DEPENDENCIES:
        results.append(check_dependency(import_name, version))

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    return results, passed, failed


def main():
    print("\n" + "=" * 60)
    print(" Dependency Checks")
    print("=" * 60)

    print("\n> testing dependencies...")
    results, passed, failed = run_checks()

    for result in results:
        status_icon = "✓" if result.passed else "✗"
        print(f"  {status_icon} {result.name}: {result.message}")
        if result.details and not result.passed:
            print(f"    → {result.details}")

    if failed == 0:
        print(f"\n> ✓ Dependencies ready ({passed} packages checked)")
    else:
        print(f"\n> ✗ Dependencies check failed ({failed} failed, {passed} passed)")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
