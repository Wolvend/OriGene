import asyncio
import json
import logging
import os
import re
import textwrap
from datetime import datetime
from typing import  Dict, List, Tuple
from .config import (
    settings,    
    get_claude_openai,
    get_deepseek_r1,
    get_deepseek_v3,
    get_gpt4_1,
    get_gpt4_1_mini,
)

from .connect_mcp import OrigeneMCPToolClient, mcp_servers

# Import utilities from the new support module
from .search_system_support import (
    compress_all_llm,
    extract_and_convert_list,
    parse_single,  
    safe_json_from_text,
    SourcesReference,
)
from .tool_executor import ToolExecutor
from .tool_selector import ToolSelector
from .tools.template.templateagent import retrieve_small_template, retrieve_large_template
from .utilties.search_utilities import (
    invoke_with_timeout_and_retry,
    remove_think_tags,
    write_log_process_safe,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  ##  DEBUG


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


log_dir = os.path.join(ROOT_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)

log_file_path = os.path.join(
    log_dir, f"run_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setLevel(logging.ERROR)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
print(f"log save in {log_file_path}")


def add_hard_breaks_to_references(response_content: str) -> str:
    """
    """
    pattern = r"(##\s*References\s*\n)(.*?)(\n##\s|\Z)"  # 
    match = re.search(pattern, response_content, re.DOTALL | re.IGNORECASE)

    if not match:
        return response_content  # 

    header = match.group(1)
    refs_block = match.group(2)
    tail = match.group(3)

    updated_refs = []
    for line in refs_block.splitlines():
        if re.match(r"\s*\[\^\^\d+\]", line):  # 
            updated_line = line.rstrip() + "\n\n"  # 
        else:
            updated_line = line
        updated_refs.append(updated_line)

    new_refs_block = "\n".join(updated_refs)
    new_content = (
        response_content[: match.start()]
        + header
        + new_refs_block
        + tail
        + response_content[match.end() :]
    )

    return new_content

class ReferencePool:
    """
    the reference pool for the search system
    - only receive the new literature explicitly declared by LLM (extracted_papers or NewRef)
    - do not make academic judgment on the URL anymore
    - the pool is only added, not deleted, and the number is stable
    """

    def __init__(self) -> None:
        self.pool: List[SourcesReference] = []
        self.link2idx: dict[str, int] = {}
        self.dirty: bool = False  # mark if the right column needs to be refreshed

    def add(self, title: str, citation: str, link: str) -> int:
        if not link:
            return -1
        if link in self.link2idx:  # already exists
            return self.link2idx[link]

        idx = len(self.pool) + 1  # 1-based index
        self.link2idx[link] = idx
        self.pool.append(
            SourcesReference(title=title or link, subtitle=citation or "", link=link)
        )
        self.dirty = True
        return idx


logger = logging.getLogger(__name__)


class AdvancedSearchSystem:
    def __init__(
        self,
        verbose=True,
        mid_path="./middleresult.txt",
        report_path="./report.txt",
        use_template=True,
        max_iterations=2,
        questions_per_iteration=5,
        is_report=False,
        chosen_tools: list[str] = None,  ## None for using all tools
        error_log_path: str = "",
        using_model = "gpt4_1",
    ):
        self._action_blocks: dict[int, dict] = {}
        self.ref_pool = ReferencePool() 
        self.all_links_of_system: list[str] = []
        self.chosen_tools = chosen_tools
        self.is_report = is_report
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.questions_per_iteration = questions_per_iteration
        self.block_callback = None
        self.use_template = use_template
        self.mid_path = mid_path
        self.report_path = report_path
        self.knowledge_chunks = []

        if error_log_path == "":
            log_dir = os.path.join(ROOT_DIR, "logs")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            error_log_path = os.path.join(
                log_dir, f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            )
        self.error_log_path = error_log_path

        self.all_links_of_system = []
        self.questions_by_iteration = {}

        ### Model independent, you can use any model you like
        self.using_model = using_model
        if self.using_model == "claude":
            self.model = get_claude_openai()
            self.reasoning_model = get_claude_openai()
            self.tool_planning_model = get_deepseek_v3()
            self.fast_model = get_deepseek_v3()
            self.report_model = get_gpt4_1()

        if self.using_model == "deepseek":
            self.model = get_deepseek_r1()
            self.reasoning_model = get_deepseek_r1()
            self.tool_planning_model = get_deepseek_v3()
            self.fast_model = get_deepseek_v3()
            self.report_model = get_gpt4_1()

        if self.using_model == "gpt4_1":
            self.model = get_gpt4_1()
            self.reasoning_model = get_gpt4_1()
            self.tool_planning_model = get_gpt4_1()
            self.fast_model = get_gpt4_1_mini()
            self.report_model = get_gpt4_1()

        if self.using_model == "gpt4_1_mini":
            self.model = get_gpt4_1_mini()
            self.reasoning_model = get_gpt4_1_mini()
            self.tool_planning_model = get_gpt4_1_mini()
            self.fast_model = get_gpt4_1_mini()
            self.tool_query_model = get_gpt4_1_mini()
            self.report_model = get_gpt4_1()

    async def _get_follow_up_questions(
        self, current_knowledge: str, query: str
    ) -> List[str]:
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d")

        logger.info("Questions by iteration: %s", str(self.questions_by_iteration))

        chance = 3
        current_try = 0
        while current_try < chance:
            if self.questions_by_iteration:
                prompt = f"""
                # Biomedical Research Intelligent Search Assistant
                
                ## Context
                - Main research question: "{query}"
                - Current date: {current_time}
                - Iteration: {len(self.questions_by_iteration)} completed rounds
                - Past sub-questions: {str(self.questions_by_iteration)}
                - Current accumulated knowledge: {current_knowledge}
                               
                ## Your Task
                1. Analyze the main query to identify its core components, key terms, and primary questions.
                2. Break down the main query into no more than {self.questions_per_iteration} sub-queries that collectively address the main query.
                
                ## Guidelines
                1. Identify key information gaps in current knowledge
                2. Formulate each sub-query as a clear, open-ended question that avoids bias, assumptions, or leading language (e.g., use neutral phrasing instead of affirmative or suggestive statements).
                3. Include only sub-queries that are essential and directly relevant to addressing the main query.
                4. Break down complex concepts or relationships into distinct, independently answerable questions.
                5. Keep sub-queries concise, specific, and straightforward (e.g., inquire about definitions, roles, or relationships, such as "What is X?" or "How does X relate to Y?").
                6. Avoid repeating past searches
                
                ## Output Format
                You must provide your response in the following structured JSON format:
                {{
                    "thoughts": "Brief analysis of the problem and what needs investigation",
                    "strategy": ["1", "2", "3", "4", "5"],
                    "sub_queries": ["Search_Query_1", "Search_Query_2", "Search_Query_3", "Search_Query_4", "Search_Query_5"]
                }}
                
                ## Important Notes
                - Use terminology CONSISTENT with the main query, preserving specialized terms without arbitrary modifications.
                - Each query should target different aspects of the research question
                - Queries should be specific and actionable
                """
            else:
                prompt = f"""
                # Intelligent Search Assistant
                
                ## Context
                - Main query to answer: "{query}"
                - Current date: {current_time}
                - This is the first search iteration
                
                 ## Your Task
                1. Analyze the main query to identify its core components, key terms, and primary questions.
                2. Break down the main query into no more than {self.questions_per_iteration} sub-queries that collectively address the main query.
                
                ## Guidelines
                1. Identify key information gaps in current knowledge
                2. Formulate each sub-query as a clear, open-ended question that avoids bias, assumptions, or leading language (e.g., use neutral phrasing instead of affirmative or suggestive statements).
                3. Include only sub-queries that are essential and directly relevant to addressing the main query.
                4. Break down complex concepts or relationships into distinct, independently answerable questions.
                5. Keep sub-queries concise, specific, and straightforward (e.g., inquire about definitions, roles, or relationships, such as "What is X?" or "How does X relate to Y?").
                6. Avoid repeating past searches
                
                ## Output Format
                You must provide your response in the following structured JSON format:
                {{
                    "thoughts": "Brief analysis of the problem and what needs investigation",
                    "strategy": ["1", "2", "3", "4", "5"],
                    "sub_queries": ["Search_Query_1", "Search_Query_2", "Search_Query_3", "Search_Query_4", "Search_Query_5"]
                }}
                
                ## Important Notes
                - Use terminology CONSISTENT with the main query, preserving specialized terms without arbitrary modifications.
                - Each query should target different aspects of the research question
                - Queries should be specific and actionable
                """

            try:
                response = await invoke_with_timeout_and_retry(
                    self.reasoning_model,
                    prompt,
                    timeout=90.0,
                    max_retries=3,
                    retry_delay=30.0,
                )
            except Exception as e:
                logger.warning(f"Failed to generate follow-up questions: {e}")
                # Write error info to local log file in a process-safe way
                log_msg = f"[{datetime.now().isoformat()}] Failed to generate follow-up questions: {e}\n"
                write_log_process_safe(self.error_log_path, log_msg)
                current_try += 1
                retry_msg = f"⚠️  Retry {current_try}/{chance}: Failed to generate follow-up questions, retrying..."
                logger.warning(retry_msg)
                log_msg_retry = f"[{datetime.now().isoformat()}] {retry_msg}\n"
                write_log_process_safe(self.error_log_path, log_msg_retry)
                await asyncio.sleep(5) 
                continue

            # try to parse the response in JSON format
            try:
                response_text = response.content

                logger.info(f"important info stream in for process 0: break query in subquery")
                logger.info(f"important info stream in for process 0: prompt: {prompt}")   
                logger.info(f"important info stream in for process 0: planning Agent {response_text}")   




                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    parsed_response = safe_json_from_text(response_text)
                    if not parsed_response:
                        raise ValueError("No valid JSON found")

                    # extract the tool queries
                    questions = parsed_response.get("sub_queries", [])

                    if questions and len(questions) > 0:
                        questions = questions[: self.questions_per_iteration]
                        logger.info(
                            f"✅ Successfully generated {len(questions)} questions via JSON parsing"
                        )

                        # extract the thoughts and strategy content
                        thoughts_content = parsed_response.get("thoughts", "")
                        strategy_content = "\n".join(
                            [
                                f"{i + 1}. {step}"
                                for i, step in enumerate(
                                    parsed_response.get("strategy", [])
                                )
                            ]
                        )

                        break
                    else:
                        raise ValueError("No valid tool queries in JSON response")

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(
                    f"JSON parsing failed: {e}, falling back to legacy parsing"
                )
                # fall back to the original list extraction method
                questions = extract_and_convert_list(response.content)
                if questions is None or len(questions) == 0:
                    current_try += 1
                    logger.warning(
                        f"⚠️  Retry {current_try}/{chance}: Failed to extract questions, retrying..."
                    )
                    await asyncio.sleep(10)  # use async sleep
                    continue
                else:
                    questions = questions[: self.questions_per_iteration]
                    logger.info(
                        f"✅ Successfully generated {len(questions)} questions via legacy parsing"
                    )

                    # try to extract the thoughts and strategy content (fallback method)
                    thoughts_content, strategy_content = (
                        self._extract_thoughts_and_strategy(response.content)
                    )
                    logger.info(
                        "Agent : _extract_thoughts_and_strategy: thoughts_content",
                        thoughts_content,
                    )
                    logger.info(
                        "Agent : _extract_thoughts_and_strategy: strategy_content",
                        strategy_content,
                    )
                    break

        # Handle case where questions is still None after all retries
        if "questions" not in locals() or questions is None:
            questions = []
            logger.error(
                "⚠️  Warning: Failed to generate follow-up questions after all retries. Using empty list."
            )
        return questions

    def _extract_thoughts_and_strategy(self, response_content: str) -> tuple[str, str]:
        """Extract Thoughts and Strategy sections from the response content"""
        thoughts_content = ""
        strategy_content = ""

        try:
            # Ensure response_content is not None
            if response_content is None:
                response_content = ""

            lines = response_content.split("\n")
            current_section = None

            for line in lines:
                line_stripped = line.strip()
                if line_stripped.startswith("Thoughts:"):
                    current_section = "thoughts"
                    # Safe extraction after "Thoughts:"
                    if len(line_stripped) > 9:
                        extracted_part = line_stripped[9:].strip()
                        if extracted_part is not None:
                            thoughts_content += extracted_part + "\n"
                elif line_stripped.startswith("Strategy:"):
                    current_section = "strategy"
                    # Safe extraction after "Strategy:"
                    if len(line_stripped) > 9:
                        extracted_part = line_stripped[9:].strip()
                        if extracted_part is not None:
                            strategy_content += extracted_part + "\n"
                elif (
                    current_section == "thoughts"
                    and line_stripped
                    and not line_stripped.startswith("[")
                ):
                    thoughts_content += line + "\n"
                elif current_section == "strategy" and line_stripped:
                    strategy_content += line + "\n"
                elif line_stripped.startswith("[") and current_section:
                    # Stop when we hit the tool list again
                    break

        except Exception as e:
            print(f"Warning: Failed to extract thoughts and strategy: {e}")
            thoughts_content = "Unable to extract analysis from response"
            strategy_content = "Unable to extract strategy from response"

        # Ensure we never return None values
        thoughts_result = (
            thoughts_content.strip() if thoughts_content is not None else ""
        )
        strategy_result = (
            strategy_content.strip() if strategy_content is not None else ""
        )

        return thoughts_result, strategy_result

    async def process_multiple_knowledge_chunks(self, query: str, current_key_info: str) -> str:
        """
        """

        if not hasattr(self, "knowledge_chunks") or not self.knowledge_chunks:
            return current_key_info.strip()

        try:
            lines = []
            for chunk in self.knowledge_chunks:
                key_info = chunk.get("key_info", "").strip()
                if key_info:
                    lines.append(key_info)
                    
            knowledge_raw_md = "\n\n".join(lines)

            prompt = f"""
    You are assisting in organizing multi-round research findings for the main question: "{query}".

    Instructions:
    - Consolidate the following markdown facts into a clean, concise format.
    - DO NOT add new information or modify the meaning.
    - DO NOT remove or reformat <URL> references – they are placeholders for citations.
    - Avoid repeating similar facts or elaborating unnecessarily.
    - Use natural Markdown formatting (paragraphs or bullet points).
    - Try to keep the result under 2000 words.

    ### Findings:
    {knowledge_raw_md}
            """.strip()

        except Exception as e:
            logger.warning(f"process_multiple_knowledge_chunks (preprocessing) failed: {e}")
            return current_key_info.strip()

        try:
            response = await invoke_with_timeout_and_retry(
                self.fast_model,
                prompt=prompt,
                timeout=60.0,
                max_retries=2,
                retry_delay=30.0,
            )
            current_knowledge = response.content.strip()

            if "<" not in current_knowledge or ">" not in current_knowledge:
                logger.warning("LLM output lacks <URL> pattern, fallback to raw.")
                return knowledge_raw_md

            return current_knowledge

        except Exception as e:
            logger.warning(f"process_multiple_knowledge_chunks (LLM) failed: {e}")
            return knowledge_raw_md

    async def _get_follow_up_questions_with_templates(
        self, current_knowledge: str, query: str
    ) -> List[str]:
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d")

        try:
            logger.info(f"Retrieving template for query: {query}")
            # template = retrieve_small_template(query)   # for easy question, one senctence guide
            template = retrieve_large_template(query)     # for complicated question
            print(f"my template is {template}")
            tuple_examples = []
            for i in range(self.questions_per_iteration):
                tuple_examples.append(
                    f"(Tool_Index_{i + 1}, Tool_Name_{i + 1}, Search_Query_{i + 1})"
                )
            output_format_example = f"[{', '.join(tuple_examples)}, ...]"
        except Exception as e:
            logger.warning(f"Failed to retrieve template: {e}")
            template = "No template available for this query."
            output_format_example = "[('Tool_Index_1', 'Tool_Name_1', 'Search_Query_1'), ...]"

        chance = 3
        current_try = 0
        while current_try < chance:
            if self.questions_by_iteration:
                prompt = f"""
                # Intelligent Search Assistant
                
                ## Context
                - Main query: "{query}"
                - Current date: {current_time}
                - Already searched {len(self.questions_by_iteration)} iterations
                
                ## Current Status
                - Past questions: {str(self.questions_by_iteration)}
                - Gathered knowledge: {current_knowledge}
                
                ## Your Task
                Analyze what's missing to fully answer the main query. Generate exactly {self.questions_per_iteration} new search queries using different tools.
                
                ## Reference Example
                The following is a detailed example of how to decompose a similar research query into multiple search objectives and tools:
                {template}
                
                ## Guidelines
                1. Identify key information gaps in current knowledge
                2. Formulate each sub-query as a clear, open-ended question that avoids bias, assumptions, or leading language (e.g., use neutral phrasing instead of affirmative or suggestive statements).
                3. Include only sub-queries that are essential and directly relevant to addressing the main query.
                4. Break down complex concepts or relationships into distinct, independently answerable questions.
                5. Keep sub-queries concise, specific, and straightforward (e.g., inquire about definitions, roles, or relationships, such as "What is X?" or "How does X relate to Y?").
                6. Avoid repeating past searches
                
                ## Output Format
                You must provide your response in the following structured JSON format:
                {{
                    "thoughts": "Brief analysis of the problem and what needs investigation",
                    "strategy": ["1", "2", "3", "4", "5"],
                    "sub_queries": ["Search_Query_1", "Search_Query_2", "Search_Query_3", "Search_Query_4", "Search_Query_5"]
                }}
                
                ## Important Notes
                - Use terminology CONSISTENT with the main query, preserving specialized terms without arbitrary modifications.
                - Each query should target different aspects of the research question
                - Queries should be specific and actionable
                """
            else:
                prompt = f"""
                # Intelligent Search Assistant
                
                ## Context
                - Main query to answer: "{query}"
                - Current date: {current_time}
                - This is the first search iteration
                
                ## Your Task
                Select exactly {self.questions_per_iteration} search tools and create effective search queries to gather information for answering the main query.
                
                ## Reference Example
                The following is a detailed example of how to decompose a similar research query into multiple search objectives and tools:
                {template}
                
                ## Guidelines
                1. Identify key information gaps in current knowledge
                2. Formulate each sub-query as a clear, open-ended question that avoids bias, assumptions, or leading language (e.g., use neutral phrasing instead of affirmative or suggestive statements).
                3. Include only sub-queries that are essential and directly relevant to addressing the main query.
                4. Break down complex concepts or relationships into distinct, independently answerable questions.
                5. Keep sub-queries concise, specific, and straightforward (e.g., inquire about definitions, roles, or relationships, such as "What is X?" or "How does X relate to Y?").
                6. Avoid repeating past searches
                
                ## Output Format
                You must provide your response in the following structured JSON format:
                {{
                    "thoughts": "Brief analysis of the problem and what needs investigation",
                    "strategy": ["1", "2", "3", "4", "5"],
                    "sub_queries": ["Search_Query_1", "Search_Query_2", "Search_Query_3", "Search_Query_4", "Search_Query_5"]
                }}
                
                ## Important Notes
                - Use terminology CONSISTENT with the main query, preserving specialized terms without arbitrary modifications.
                - Each query should target different aspects of the research question
                - Queries should be specific and actionable
                """

            try:
                response = await invoke_with_timeout_and_retry(
                    self.reasoning_model,
                    prompt,
                    timeout=90.0,
                    max_retries=3,
                    retry_delay=60.0,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to generate follow-up questions with template: {e}"
                )
                # Write error info to local log file in a process-safe way
                log_msg = f"[{datetime.now().isoformat()}] Failed to generate follow-up questions with template: {e}\n"
                write_log_process_safe(self.error_log_path, log_msg)
                current_try += 1
                retry_msg = f"⚠️  Retry {current_try}/{chance}: Failed to generate follow-up questions with template, retrying..."
                logger.warning(retry_msg)
                log_msg_retry = f"[{datetime.now().isoformat()}] {retry_msg}\n"
                write_log_process_safe(self.error_log_path, log_msg_retry)
                await asyncio.sleep(5)  
                continue

            try:
                response_text = response.content
                logger.info(f"important info stream in for process 0: break query in subquery")
                logger.info(f"important info stream in for process 0: prompt: {prompt}")   
                logger.info(f"important info stream in for process 0: planning Agent {response_text}")   

                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    parsed_response = safe_json_from_text(response_text)
                    if not parsed_response:
                        raise ValueError("No valid JSON found")

                    # extract the tool queries
                    questions = parsed_response.get("sub_queries", [])

                    if questions and len(questions) > 0:
                        questions = questions[: self.questions_per_iteration]
                        logger.info(
                            f"✅ Successfully generated {len(questions)} questions via JSON parsing"
                        )

                        # extract the thoughts and strategy content
                        thoughts_content = parsed_response.get("thoughts", "")
                        strategy_content = "\n".join(
                            [
                                f"{i + 1}. {step}"
                                for i, step in enumerate(
                                    parsed_response.get("strategy", [])
                                )
                            ]
                        )
                        break
                    else:
                        raise ValueError("No valid tool queries in JSON response")

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(
                    f"JSON parsing failed: {e}, falling back to legacy parsing"
                )
                # fall back to the original list extraction method
                questions = extract_and_convert_list(response.content)
                if questions is None or len(questions) == 0:
                    current_try += 1
                    logger.warning(
                        f"⚠️  Retry {current_try}/{chance}: Failed to extract questions, retrying..."
                    )
                    await asyncio.sleep(10)  # use async sleep
                    continue
                else:
                    questions = questions[: self.questions_per_iteration]
                    logger.info(
                        f"✅ Successfully generated {len(questions)} questions via legacy parsing"
                    )

                    # try to extract the thoughts and strategy content (fallback method)
                    thoughts_content, strategy_content = (
                        self._extract_thoughts_and_strategy(response.content)
                    )
                    break

        # Handle case where questions is still None after all retries
        if "questions" not in locals() or questions is None:
            questions = []
            logger.error(
                "⚠️  Warning: Failed to generate follow-up questions after all retries. Using empty list."
            )
        return questions

    async def _compress_knowledge(self, current_knowledge: str, query: str) -> str:
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d")
        prompt = f"""You are a research synthesis agent working on the query: {query}

        You've collected multiple sets of keypoints from different subqueries. Below are all the accumulated keypoints with their citations:
        current_time: {current_time}
        {current_knowledge}

        Please synthesize and compress these keypoints into a concise, non-redundant list that:
        1. Eliminates duplicated information
        2. Merges related points
        3. Preserves the most important insights
        4. Retains all necessary citations and urls for each point
        5. Maintains the markdown list format

        Your goal is to create a comprehensive yet streamlined summary that captures all essential information while reducing redundancy. When multiple sources support the same point, include all relevant citations.
        Generate the compressed markdown keypoints list. Then follows the sources information.
        """
        try:
            response = await invoke_with_timeout_and_retry(
                self.model, prompt, timeout=60.0, max_retries=3, retry_delay=60.0
            )
        except Exception as e:
            logger.warning(f"Failed to compress knowledge: {e}")
            log_msg = (
                f"[{datetime.now().isoformat()}] Failed to compress knowledge: {e}\n"
            )
            write_log_process_safe(self.error_log_path, log_msg)
            raise e

        response_content = remove_think_tags(response.content)
        response_content = str(response_content)

        return response_content


    async def _extract_knowledge(
        self, facts_md: str, refs_in_round: List[Dict]
    ) -> Tuple[str, List[Dict]]:
        """ 
        Extract key information from the provided facts and references.
        """

        existing_pool = [
            {"idx": idx, "url": ref.link, "description": ref.title}
            for idx, ref in enumerate(self.ref_pool.pool, 1)
        ]

        prompt = textwrap.dedent(f"""
        You are an expert research assistant.

        ### Task
        1. Read the **candidate facts** and **candidate references** below.
        2. Remove URLs that are broken, extremely obviously unrelated to the query, or duplicate with the same information; but we need some references, add URLs at first time and when adding new refernece in pool that are useful for the current query if possible, but do not invent and never repeat.
        3. For every remaining URL, refine (or keep) its *description* so it is concise and copied verbatim from the source title/metadata.  
        • If the link is a scholaly article (DOI / PubMed / arXiv / journal), also fill an APA-style citation in **apa_citation**.  
        • Otherwise leave **apa_citation** empty.
        4. Produce a **Key Information** markdown block that integrates the facts or important details and cites sources *only via the raw URL string* (no numbering).  
        – If a fact has no URL, include it normally.  
        – When citing, wrap the URL in angle brackets like `<https://example.com/...>` (this is a placeholder that will be replaced by the system).
        5. Output JSON with two keys only:
        "key_information" and "cleaned_refs".

        ### Existing reference pool (keep these, don't modify)
        ```json
        {json.dumps(existing_pool, ensure_ascii=False)}
        ```

        ### Candidate facts (markdown)
        ```
        {facts_md}
        ```

        ### Candidate references (raw)
        ```json
        {json.dumps(refs_in_round, ensure_ascii=False)}
        ```

        ### Output JSON example
        ```json
        {{
        "key_information": "- **Point 1** … (<https://doi.org/...>)\\n- **Point 2** …",
        "cleaned_refs": [
            {{"url": "https://doi.org/…", "description": "Paper title …", "apa_citation": "Author A. (2024)…"}},
            {{"url": "https://news.com/…", "description": "News headline …", "apa_citation": ""}}
        ]
        }}
        ```

        Strictly follow the schema; do not add other keys.
        """)
        try:
            resp = await invoke_with_timeout_and_retry(
                self.model, prompt, timeout=60.0, max_retries=3, retry_delay=30.0
            )
            logger.info(f"important info stream in for process 5: extract_knowledge (Knowledge extraction Agent)")
            logger.info(f"important info stream in for process 5: prompt: {prompt}")   
            logger.info(f"important info stream in for process 5: _extract_knowledge (Knowledge extraction Agent): {resp.content}")   

        except Exception as e:
            logger.warning(f"Failed to extract knowledge: {e}")
            log_msg = (
                f"[{datetime.now().isoformat()}] Failed to extract knowledge: {e}\n"
            )
            write_log_process_safe(self.error_log_path, log_msg)
            raise e
        data = safe_json_from_text(resp.content) or {}
        key_info = data.get("key_information", "").strip()
        cleaned_refs = data.get("cleaned_refs", [])

        if not isinstance(key_info, str):
            key_info = ""
        if not isinstance(cleaned_refs, list):
            cleaned_refs = []

        key_info = re.sub(r"<(https?://[^>]+)>", r"\1", key_info)

        return key_info, cleaned_refs

    async def _answer_query(
        self,
        current_knowledge: str,
        query: str,
        current_iteration: int,
        max_iterations: int,
    ) -> str:
        is_final = current_iteration >= max_iterations
        title = "Closing Thoughts" if is_final else "Reflection"
        print("start answer query")
        print(query)
        existing_refs = [
            f"[{idx}] {ref.link} — {ref.title}"
            for idx, ref in enumerate(self.ref_pool.pool, 1)
        ]
        refs_block = "\n".join(existing_refs) or "*None yet*"
        if is_final:
            prompt_body = f""" 
            ## Original Query ##
            {query}

            ## Accumulated Knowledge ##
            {current_knowledge}

            ## Available SOURCES ##
            {refs_block}

            ### Instructions

            You are tasked with generating a **precise, well-reasoned, and evidence-aligned final answer** to the query above.

            Follow these strict guidelines:

            - **Focus only on information that is directly relevant, scientifically sound, and consistent.**
            - If the provided sources include **irrelevant, weakly related, or clearly flawed data**, **disregard them** in your reasoning.
            - Do **not invent** new references or URLs — cite sources only using the `[^^n]` format.
            - If certain key facts are **not explicitly stated in the sources**, you may rely on **logical inference, background knowledge, and cautious reasoning** to form a credible answer.
            - When evidence is incomplete or ambiguous, you are encouraged to **prioritize plausibility** and **choose the most reasonable and justifiable conclusion** based on available information.

            ---

            ### Output Markdown Template

            ## Conclusion

            Provide a clear, concise, and fully supported response to the query.  
            Avoid discussing unrelated details or speculative content unless essential to your reasoning.  
            In the face of conflicting or insufficient data, select the explanation that is **best supported by reasoning and contextual clues**.

            ## Thoughts

            Briefly describe your reasoning process:  
            - How did you assess the quality and reliability of the evidence?  
            - Which sources did you rely on, and which did you discard (and why)?  
            - If part of your answer was based on deduction rather than direct evidence, explain your logic clearly.

            ## Key Findings

            [A short summary (100–150 words) of the most important mechanistic or conceptual insight, written in a formal tone using markdown.]

            ## References

            [List all relevant references in this format — each must be on a new line:]

            [^^1] APA-style citation or description <https://example.com/source1>
            [^^2] APA-style citation or description <https://example.com/source2> 
            ...
            """
        else:

            prompt_body = f"""
            ## Query ##
            {query}

            ## Current Iteration ##
            {current_iteration} / {max_iterations}

            ## Knowledge So Far ##
            {current_knowledge}

            ## Available SOURCES ##
            {refs_block}

            ### Instructions
            1. Critically reflect on progress and propose strategy for next round.
            2. When you mention evidence, cite with existing `[^^n]` numbers only.


            ### Output Markdown Template
            Your response MUST follow this exact format in markdown,The classification of large and small titles should comply with the markdown specification:

            ## Thoughts
            Analyze,this is just a recommended title content range, but you don’t have to write a fixed title; you can answer each sub-heading in points: 
            ### What has been discovered so far, 
            ### What gaps or limitations exist in current knowledge, 
            ### What aspects of the original query remain unanswered, 
            ### How to improve research quality and coverage]

            ## Strategy 
            Provide numbered strategy points for the next research iteration, similar to initial strategy format,Do NOT include subheadings**, bullet points, or further nested structure under each point. Each point should be a **self-contained strategy**, ideally 2–3 sentences long, combining direction and rationale:
            1. Specific research direction with reasoning
            2. Another research direction with reasoning
            3. etc.
            ...

            ## References
            [Provide a list of references that you think are relevant to the query, with each reference on a new line(consider markdown's new line rules), such as:
            [^^1] academic format citation(if actually have else only show url)<https://example.com/source1> \\n (this \\n must include for new line)
            [^^2] academic format citation(if actually have else only show url)<https://example.com/source2> \\n (this \\n must include for new line)
            ...

            """

        prompt = textwrap.dedent(f"""
        You are an expert research assistant.

        {prompt_body}

        ### Strict Citation Rules
        * Use **numbered square-bracket citations** based on the **index in Available SOURCES** (e.g., [^^1], [^^2], ...).
        * Do not fabricate, skip, or renumber citations arbitrarily.
        * Each number must consistently refer to the **same URL or source** throughout the document.
        * If a source lacks a formal citation title or description, directly use the URL as a clickable markdown link.
        * Using markdown format, note that the title structure follows the common format of markdown.
        """)

        try:
            response = await invoke_with_timeout_and_retry(
                self.model, prompt, timeout=100.0, max_retries=3, retry_delay=30.0
            )
        except Exception as e:
            logger.warning(f"Failed to answer query: {e}")
            log_msg = f"[{datetime.now().isoformat()}] Failed to answer query: {e}\n"
            write_log_process_safe(self.error_log_path, log_msg)
            raise e




        response_content = remove_think_tags(response.content)
        response_content = add_hard_breaks_to_references(response_content)

        logger.info(f"important info stream in for process 6: answer query")
        logger.info(f"important info stream in for process 6: prompt: {prompt}")
        logger.info(f"important info stream in for process 6: response_content: (Critic or answer query Agent) {response_content}")
        

        return response_content
    async def _generate_detailed_report(
        self, current_knowledge: str, findings: List[Dict], query: str, iteration: int
    ):
        """
        Generate a publication-style report, with in-text [^^n] citations
        and a final reference list strictly come from self.ref_pool。
        """
        pool_objs = []
        for idx, ref in enumerate(self.ref_pool.pool, 1):
            pool_objs.append(
                {
                    "idx": idx,
                    "url": ref.link,
                    "apa": ref.subtitle or "", 
                    "desc": ref.title,
                }
            )
        pool_json = json.dumps(pool_objs, ensure_ascii=False, indent=2)

        prompt = textwrap.dedent(f"""
        You are a senior biomedical research analyst.  Write a professional report that synthesises all evidence.

        ### Research Context
        * Original Query: {query}
        * Iterations Completed: {iteration}

        ### Knowledge Base
        {current_knowledge}

        ### Citation Pool  (MUST cite only these!)
        ```json
        {pool_json}
        ```
        ## Task 
        Generate a professional research report that would be suitable for academic or clinical publication. The report should be comprehensive, well-structured, and scientifically rigorous.

        
        ### Strict Citation Rules
        1. In the narrative, cite sources only as `[^^n]`, where n equals "idx".
        2. Do **NOT** invent new URLs or citations.
        3. Every `[^^n]` used must appear in the final **References** list.
        4. If an entry's `"apa"` field is non-empty, write:
            `[^^n] {{"apa"}} <{{"url"}}>`
        else write:
            `[^^n] <{{"url"}}>`


        **IMPORTANT REQUIREMENTS:**
        1. The detailed report need to be 2000-3000 words in length.
        2. Write in a scholarly, narrative style similar to academic publications
        3. Provide in-depth analysis and synthesis of the research findings
        4. Include specific details, mechanisms, clinical implications, and evidence

        Your response MUST follow this exact format in markdown:

        Detailed
        ## Key Findings
        [200-300 word paragraph to directly and fully answer all parts of the instruction with specificity, providing some insight but in concise language,It will be better if some important statements be supported by references from the provided research.]

        ## Ideas
        [Paragraph to suggest potential research directions or new ideas based on the findings. You are allowed to reason and think more actively here and make inferences and assumptions based on the information you receive, but do not invent new references or URLs.]
        
        ## Detailed Analysis(s)
        [Main body: 1000-2000 words organized into logical sections you determine based on each aspect of the topic. Each section should contribute to answering the original instruction. Include comprehensive analysis, specific evidence, methodologies, and limitations where relevant. Evidence should be provided from both broader perspectives and concrete examples. It will be better if some statements be supported by references from the provided research.]

        ## Conclusion
        [200-300 words summarizing the evidences, discuss practical implications, reflect on agent's gathered data quality, and propose next-step recommendations, It will be better if some statements be supported by references from the provided research.]
        
        ## References
        [Provide a list of references that you think are relevant to the query, with each reference on a new line (consider markdown's new line rules), such as:
        [^^1] academic format citation(if actually have else only show url)<https://example.com/source1>
        [^^2] academic format citation(if actually have else only show url)<https://example.com/source2>
        ...
        ]
        """)

        logger.info("Generating detailed report with prompt:")
        logger.info(prompt)
        try:
            response = await invoke_with_timeout_and_retry(
                self.report_model,
                prompt,
                timeout=180.0,
                max_retries=3,
                retry_delay=60.0,
            )
        except Exception as e:
            logger.warning(f"Failed to generate detailed report: {e}")
            log_msg = f"[{datetime.now().isoformat()}] Failed to generate detailed report: {e}\n"
            write_log_process_safe(self.error_log_path, log_msg)
            raise e
        logger.info("Detailed report response first received:")
        logger.info(response.content)
        response_content = remove_think_tags(response.content)
        response_content = str(response_content)
        logger.info("Detailed report response second received:")
        logger.info(response_content)

        summary_content, detailed_content = self._extract_report_sections(
            response_content
        )



        logger.info(f"✅ Generated detailed research report for: {query}")
        logger.info(f"important info stream in for process 7: report")
        logger.info(f"prompt: {prompt}")
        logger.info(f"response_content: {response_content}")

        return response_content

    def _extract_report_sections(self, response_content: str):
        """
        extract the Key Findings from the markdown format report output by the model, and keep the full report content.

        parameters:
            response_content (str): the full markdown format content output by the model

        return:
            summary_content (str): the extracted Key Findings part (summary)
            detailed_content (str): the full report content
        """
        # use regex to extract the ## Key Findings part
        key_findings_match = re.search(
            r"## Key Findings\s+(.*?)(?=\n##\s+Detailed Analysis|\n##\s+Conclusion|\Z)",
            response_content,
            re.DOTALL | re.IGNORECASE,
        )

        if key_findings_match:
            summary_content = key_findings_match.group(1)  # .strip()
        else:
            summary_content = ""

        detailed_content = response_content  # .strip()

        return summary_content, detailed_content

    async def initialize(self):
        """Initialize async components"""

        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
        tool_type_info_path = os.path.join(
            CURRENT_DIR, "cache_data", "tool_info.xlsx"
        )
        embedding_cache = os.path.join(
            CURRENT_DIR, "cache_data", "tool_desc_embedding.pkl"
        )

        embedding_api_key = settings.embedding_api_key

        try:
            self.mcp_tool_client = OrigeneMCPToolClient(mcp_servers, self.chosen_tools)
            await self.mcp_tool_client.initialize()
        except Exception as e:
            logger.warning(f"Failed to initialize MCP tool client in initialize: {e}")
            log_msg = f"[{datetime.now().isoformat()}] Failed to initialize MCP tool client in initialize: {e}\n"
            write_log_process_safe(self.error_log_path, log_msg)
            raise e

        try:
            self.mcp_tool_dict = self.mcp_tool_client.tool2source
        except Exception as e:
            logger.warning(f"Failed to get MCP tool dict in initialize: {e}")
            log_msg = f"[{datetime.now().isoformat()}] Failed to get MCP tool dict in initialize: {e}\n"
            write_log_process_safe(self.error_log_path, log_msg)
            raise e

        try:
            self.tool_selector = ToolSelector(
                self.tool_planning_model,
                self.reasoning_model,
                self.mcp_tool_client,
                tool_type_info_path,
                embedding_api_key,
                embedding_cache,
                self.chosen_tools,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize tool selector in initialize: {e}")
            log_msg = f"[{datetime.now().isoformat()}] Failed to initialize tool selector in initialize: {e}\n"
            write_log_process_safe(self.error_log_path, log_msg)
            raise e

        try:
            self.tool_executor = ToolExecutor(
                self.mcp_tool_client, self.error_log_path, self.fast_model
            )
        except Exception as e:
            logger.warning(f"Failed to initialize tool executor in initialize: {e}")
            log_msg = f"[{datetime.now().isoformat()}] Failed to initialize tool executor in initialize: {e}\n"
            write_log_process_safe(self.error_log_path, log_msg)
            raise e

        num_tools = len(self.mcp_tool_client.mcp_tools)
        num_general_tools = len(self.tool_selector.general_tool_selector.general_tools)
        num_expert_tools = num_tools - num_general_tools
        logger.info("🔧 NUMBER OF AVAILABLE TOOLS IN POOL: %d", num_tools)
        logger.info("🔧      GENERAL TOOLS: %d", num_general_tools)
        logger.info("🔧      EXPERT TOOLS: %d", num_expert_tools)

    async def analyze_topic(self, query: str) -> Dict:
        logger.info("Starting research on topic: %s", query)
        logger.info("%s", "\n" + "=" * 80)
        logger.info("RESEARCH CONFIGURATION:")
        logger.info("%s", "=" * 80)
        logger.info("Query: %s", query)
        logger.info("Max Iterations: %d", self.max_iterations)
        logger.info("Questions per Iteration: %d", self.questions_per_iteration)
        logger.info("Use Template: %s", str(self.use_template))
        logger.info(
            "Available Tools: %d",
            len(self.mcp_tool_client.mcp_tools)
            if self.mcp_tool_client.mcp_tools
            else 0,
        )
        logger.info("%s", "=" * 80 + "\n")

        findings = []
        current_knowledge = ""
        iteration = 0


        if self.verbose:
            with open(self.mid_path , "a", encoding="utf-8") as f:
                f.write(f"User Qeury : {query} \n")


        # Check if search engine is available
        if (
            len(self.mcp_tool_client.mcp_tools) == 0
            or self.mcp_tool_client.mcp_tools is None
        ):
            error_msg = (
                "Error: No mcp_tool_client.mcp_tools available. Please check your configuration."
            )

            return {
                "findings": [],
                "iterations": 0,
                "questions": {},
                "current_knowledge": "",
                "error": error_msg,
            }

        while iteration < self.max_iterations:
            if self.verbose:
                with open(self.mid_path , "a", encoding="utf-8") as f:
                    f.write(f"Iteration : {iteration} \n")


            if self.use_template:
                questions = await self._get_follow_up_questions_with_templates(
                    current_knowledge, query
                )
            else:
                questions = await self._get_follow_up_questions(
                    current_knowledge, query
                )

            logger.info(f"important info stream in iteration {iteration} for process 1: query and subquery")
            logger.info(f"important info stream in iteration {iteration} for process 1; query: {query}")
            logger.info(f"important info stream in iteration {iteration} for process 1; questions: {questions}")   



            question_texts = questions
            self.questions_by_iteration[iteration] = question_texts

            fullquery_tool_results = []
            for q_idx, question in enumerate(question_texts, 1):
                tool_and_input_list = await self.tool_selector.run(question) or []
                logger.debug("debug: tool_and_input_list")
                logger.debug("Tool and input list: %s", str(tool_and_input_list))

                if self.verbose:
                    with open(self.mid_path , "a", encoding="utf-8") as f:
                        f.write(f"\n Tool and tool query in subquery : {question} : \n")
                        f.write(f"\n {tool_and_input_list} \n")


                logger.info(f"important info stream in iteration {iteration} for process 2: Tool and input list for subquery (Tool calling agents)")
                logger.info(f"important info stream in iteration {iteration} for process 2: subquery: {question}")   
                logger.info(f"important info stream in iteration {iteration} for process 2: tool_and_input_list: {tool_and_input_list}")   



                try:
                    tool_calling_results = (
                        await self.tool_executor.run(tool_and_input_list) or []
                    )
                except Exception as e:
                    logger.warning("Error during tool execution: %s", str(e))
                    tool_calling_results = []

                logger.debug("debug: tool_calling_results")
                logger.debug("Tool calling results: %s", str(tool_calling_results))

                logger.info(f"important info stream in iteration {iteration} for process 3: Tool result for subquery")
                logger.info(f"important info stream in iteration {iteration} for process 3: subquery: {question}")   
                logger.info(f"important info stream in iteration {iteration} for process 3: tool_calling_results: {tool_calling_results}")   

                try:
                    logger.debug("Processing tool results before extraction")
                    parsed_list = await asyncio.gather(
                        *(
                            parse_single(
                                tool_calling_results[i], 
                                query=tool_and_input_list[i]["item"],
                            ) 
                            for i in range(len(tool_calling_results))
                        )
                    )
                    logger.debug("Parsed list: %s", str(parsed_list))

                    compressed_list = await compress_all_llm(
                        model=self.fast_model,
                        parsed_list=parsed_list,
                        limit=3,
                        query=query,
                    )
                    logger.debug("Compressed list: %s", str(compressed_list))
                    fullquery_tool_results.extend(compressed_list)


                    logger.info(f"important info stream in iteration{iteration} for process 4: compressed_list for subquery (knowledge compress agent)")
                    logger.info(f"important info stream in iteration{iteration} for process 4: subquery  (knowledge compress agent): {question}")   
                    logger.info(f"important info stream in iteration{iteration} for process 4: compressed_list  (knowledge compress agent): {compressed_list}")   

                except Exception as e:
                    logger.warning("Error during parsing tool results: %s", str(e))

                logger.info("fullquery_tool_results: %s", str(fullquery_tool_results))
                logger.info(
                    "Questions by iteration: %s", str(self.questions_by_iteration)
                )

            iteration += 1
            facts, refs_raw = [], []
            for item in fullquery_tool_results:
                facts.extend(item.get("extracted_facts", []))
                refs_raw.extend(item.get("references", []))

            def _to_str(x):
                if x is None:
                    return ""
                if isinstance(x, (list, tuple)):
                    x = x[0] if x else ""
                return str(x).strip()

            unique_refs: dict[str, dict] = {}
            for ref in refs_raw:
                ref["url"]         = _to_str(ref.get("url"))
                ref["description"] = _to_str(ref.get("description"))
                ref["apa_citation"] = _to_str(ref.get("apa_citation"))

                url = ref["url"]
                if not url or not url.startswith("http"):
                    continue         
                if url not in unique_refs:       
                    unique_refs[url] = ref

            refs = list(unique_refs.values())
            urls = [r["url"] for r in refs]
            self.all_links_of_system.extend(urls)

            facts_md = (
                "\n".join(f"- **Fact**: {f}" for f in facts)
                if facts
                else "*No explicit facts extracted.*"
            )

            logger.info("facts_md")
            logger.info(facts_md)
            logger.info("refs")
            logger.info(refs)


            key_info, cleaned_refs = await self._extract_knowledge(
                facts_md=facts_md, refs_in_round=refs
            )

            self.knowledge_chunks.append({
                "question_texts": question_texts,
                "key_info": key_info
            })

            logger.info(f"knowledge_chunks")
            logger.info(self.knowledge_chunks)

            current_knowledge = await self.process_multiple_knowledge_chunks(query,key_info)
            

            for ref in cleaned_refs:
                idx = self.ref_pool.add(
                    title=ref.get("description")
                    or ref.get("apa_citation")
                    or ref["url"],
                    citation=ref.get("apa_citation", ""),
                    link=ref["url"],
                )
                current_knowledge = current_knowledge.replace(ref["url"], f"[{idx}]")

            logger.info(f"important info stream in for process new: knowledge memory Agent {current_knowledge}")   


            # Send Analysis & Strategy Refinement (only if not the last iteration)
            logger.info("getting final answer")

            final_answer = await self._answer_query(
                current_knowledge, query, iteration, self.max_iterations
            )
            if iteration >= self.max_iterations:
                answer_title = "Final Answer"
            else:
                answer_title = "Critc"
            if self.verbose:
                with open(self.mid_path , "a", encoding="utf-8") as f:
                    f.write(f"\n {answer_title} : \n")
                    f.write(f"\n {final_answer} \n")

            logger.info("Critic or answer: ")
            logger.info(final_answer)

        print(f"self.is_report {self.is_report}")
        final_report = ""
        if self.is_report:
            print("Generating final report")
            logger.info("Generating detailed report after final iteration")
            try:
                final_report = await self._generate_detailed_report(
                    current_knowledge, findings, query, iteration
                )
                if self.verbose:
                    print(f"writing final report in{self.report_path}")
                    with open(self.report_path , "a", encoding="utf-8") as f:
                        f.write(f"Query : {query} : \n")
                        f.write(f"\n {final_report} \n")

            except Exception as e:
                logger.warning(f"Warning: Failed to generate detailed report: {e}")

        current_knowledge = final_answer
        return {
            "findings": findings,
            "iterations": iteration,
            "questions": self.questions_by_iteration,
            "current_knowledge": current_knowledge,
            "final_report": final_report,
        }
