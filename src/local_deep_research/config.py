# local_deep_research/config.py
import logging
import os
from types import SimpleNamespace
from langchain_openai import ChatOpenAI
from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH  = PROJECT_ROOT / "_settings" / ".secrets.toml"
with CONFIG_PATH.open("rb") as f:
    secrets = tomllib.load(f)



settings = SimpleNamespace(
    quick    = SimpleNamespace(iteration=2, questions_per_iteration=4),
    detailed = SimpleNamespace(iteration=2, questions_per_iteration=6),
    embedding_api_key = secrets["embedding"]["api_key"],
    embedding_cache   = secrets["embedding"]["cache"],
)

endpoint_openai_api_base_url   = secrets["openai"]["api_base"]
endpoint_openai_api_key        = secrets["openai"]["api_key"]

deepseek__openai_api_base_url  = secrets["deepseek"]["api_base"]
deepseek_openai_api_key        = secrets["deepseek"]["api_key"]

mcp_url = secrets["mcp"]["server_url"]

template_embedding_api_base_url = secrets["template"]["api_base"]
template_embedding_api_key   = secrets["template"]["api_key"]
def get_gpt4_1() -> ChatOpenAI:
    """
    Get GPT-4 1 model configuration.

    Returns:
        Configured ChatOpenAI instance for GPT-4 1
    """
    return ChatOpenAI(
        model="gpt-4.1",
        api_key=endpoint_openai_api_key,
        openai_api_base=endpoint_openai_api_base_url,
        temperature=0.6,
        top_p=0.9,
        max_tokens=32000,
    )
def get_gpt4_1_mini() -> ChatOpenAI:
    """
    Get GPT-4 1 mini model configuration.

    Returns:
        Configured ChatOpenAI instance for GPT-4 1 mini
    """
    return ChatOpenAI(
        model="gpt-4.1-mini",
        api_key=endpoint_openai_api_key,
        openai_api_base=endpoint_openai_api_base_url,
        temperature=0.6,
        top_p=0.9,
        max_tokens=32000,
    )

def get_claude_openai() -> ChatOpenAI:
    """
    Get Claude model configuration through OpenAI-compatible API.

    Returns:
        Configured ChatOpenAI instance for Claude
    """
    return ChatOpenAI(
        model="claude-3-opus-20240229",
        api_key=endpoint_openai_api_key,
        openai_api_base=endpoint_openai_api_base_url,
        temperature=0.6,
        top_p=0.9,
        max_tokens=32000,
    )
def get_deepseek_r1() -> ChatOpenAI:
    """
    Get DeepSeek R1 reasoning model configuration.

    Returns:
        Configured ChatOpenAI instance for DeepSeek R1
    """
    return ChatOpenAI(
        model="deepseek-reasoner",
        api_key=deepseek_openai_api_key,
        openai_api_base=deepseek__openai_api_base_url,
        temperature=0.6,
        top_p=0.9,
        max_tokens=32000,
    )
def get_deepseek_v3() -> ChatOpenAI:
    """
    Get DeepSeek V3 chat model configuration.

    Returns:
        Configured ChatOpenAI instance for DeepSeek V3
    """
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=deepseek_openai_api_key,
        openai_api_base=deepseek__openai_api_base_url,
        temperature=0.6,
        top_p=0.9,
        max_tokens=32000,
    )



