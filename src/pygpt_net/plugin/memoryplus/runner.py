import asyncio
import json
import sys
import os
import argparse
import re
import importlib.util
import types
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

# 1. Pre-compile Regex Patterns for performance
TOOL_CODE_PATTERN = re.compile(r'<tool_code>.*?</tool_code>', flags=re.DOTALL)
TOOL_CALL_PATTERN = re.compile(r'<tool_call>.*?</tool_call>', flags=re.DOTALL)
CODE_BLOCK_PATTERN = re.compile(r'```.*?```', flags=re.DOTALL)

# Lazy-loaded Graphiti dependencies (used by worker + CLI entrypoint)
Graphiti = None
EpisodeType = None
LLMConfig = None
OpenAIGenericClient = None
OpenAIEmbedder = None
OpenAIEmbedderConfig = None
GeminiEmbedder = None
GeminiEmbedderConfig = None

def _inject_openai_generic_client_shim() -> bool:
    try:
        from graphiti_core.llm_client.openai_client import OpenAIClient as _OpenAIClient
    except ImportError:
        try:
            from graphiti_core.llm_client import OpenAIClient as _OpenAIClient
        except ImportError:
            return False
    import types

    shim = types.ModuleType("graphiti_core.llm_client.openai_generic_client")
    shim.OpenAIGenericClient = _OpenAIClient
    sys.modules.setdefault("graphiti_core.llm_client.openai_generic_client", shim)
    return True

def _inject_embedder_shim() -> bool:
    if importlib.util.find_spec("graphiti_core.embedder") is not None:
        return True
    spec = importlib.util.find_spec("graphiti_core")
    if not spec or not spec.submodule_search_locations:
        return False
    base_path = next(iter(spec.submodule_search_locations))

    def _ensure_pkg():
        if "graphiti_core" in sys.modules:
            return
        pkg = types.ModuleType("graphiti_core")
        pkg.__path__ = [base_path]
        pkg.__file__ = os.path.join(base_path, "__init__.py")
        sys.modules["graphiti_core"] = pkg

    def _load_module(module_name: str, file_path: str):
        _ensure_pkg()
        mod_spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not mod_spec or not mod_spec.loader:
            return None
        module = importlib.util.module_from_spec(mod_spec)
        sys.modules[module_name] = module
        mod_spec.loader.exec_module(module)
        return module

    def _build_embedder_shim(module):
        openai_embedder = getattr(module, "OpenAIEmbedder", None)
        if not openai_embedder:
            return False
        openai_config = getattr(module, "OpenAIEmbedderConfig", None)
        if not openai_config:
            class _OpenAIEmbedderConfig:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)
            openai_config = _OpenAIEmbedderConfig
        embedder_client = getattr(module, "EmbedderClient", None) or getattr(module, "EmbeddingClient", None)
        if not embedder_client:
            class _EmbedderClient:
                pass
            embedder_client = _EmbedderClient

        embedder_pkg = types.ModuleType("graphiti_core.embedder")
        embedder_pkg.OpenAIEmbedder = openai_embedder
        embedder_pkg.OpenAIEmbedderConfig = openai_config
        embedder_pkg.EmbedderClient = embedder_client
        sys.modules.setdefault("graphiti_core.embedder", embedder_pkg)

        openai_mod = types.ModuleType("graphiti_core.embedder.openai")
        openai_mod.OpenAIEmbedder = openai_embedder
        openai_mod.OpenAIEmbedderConfig = openai_config
        sys.modules.setdefault("graphiti_core.embedder.openai", openai_mod)

        gemini_embedder = getattr(module, "GeminiEmbedder", None)
        gemini_config = getattr(module, "GeminiEmbedderConfig", None)
        if gemini_embedder and gemini_config:
            gemini_mod = types.ModuleType("graphiti_core.embedder.gemini")
            gemini_mod.GeminiEmbedder = gemini_embedder
            gemini_mod.GeminiEmbedderConfig = gemini_config
            sys.modules.setdefault("graphiti_core.embedder.gemini", gemini_mod)

        return True

    candidates = [
        ("graphiti_core.embedder.openai", "embedder/openai.py"),
        ("graphiti_core.embedder", "embedder.py"),
        ("graphiti_core.embeddings.openai", "embeddings/openai.py"),
        ("graphiti_core.embeddings", "embeddings.py"),
        ("graphiti_core.embedding.openai", "embedding/openai.py"),
        ("graphiti_core.embedding", "embedding.py"),
    ]
    for module_name, rel_path in candidates:
        file_path = os.path.join(base_path, rel_path)
        if not os.path.isfile(file_path):
            continue
        module = _load_module(module_name, file_path)
        if not module:
            continue
        if _build_embedder_shim(module):
            return True

    # Fallback: scan for any module defining OpenAIEmbedder.
    for root, _, files in os.walk(base_path):
        for filename in files:
            if not filename.endswith(".py"):
                continue
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    if "OpenAIEmbedder" not in handle.read():
                        continue
            except Exception:
                continue
            rel_path = os.path.relpath(file_path, base_path)
            module_name = "graphiti_core." + rel_path.replace(os.sep, ".")[:-3]
            module = _load_module(module_name, file_path)
            if module and _build_embedder_shim(module):
                return True

    return False

def _patch_graphiti_dedupe_schema() -> bool:
    try:
        from pydantic import BaseModel, Field
        from graphiti_core.prompts import dedupe_nodes
    except Exception:
        return False

    try:
        class NodeDuplicateFixed(BaseModel):
            id: int = Field(..., description="integer id of the entity")
            duplicate_idx: int = Field(
                ...,
                description="idx of the duplicate entity. If no duplicate entities are found, default to -1.",
            )
            name: str = Field(
                ...,
                description="Name of the entity. Should be the most complete and descriptive name of the entity.",
            )
            duplicates: list[int] = Field(
                default_factory=list,
                description="idx of all entities that are a duplicate of the entity with the above id.",
            )

        class NodeResolutionsFixed(BaseModel):
            entity_resolutions: list[NodeDuplicateFixed] = Field(
                ..., description="List of resolved nodes"
            )
    except Exception:
        return False

    dedupe_nodes.NodeDuplicate = NodeDuplicateFixed
    dedupe_nodes.NodeResolutions = NodeResolutionsFixed
    try:
        from graphiti_core.utils.maintenance import node_operations
        node_operations.NodeDuplicate = NodeDuplicateFixed
        node_operations.NodeResolutions = NodeResolutionsFixed
    except Exception:
        pass

    return True

def load_graphiti_dependencies() -> bool:
    global Graphiti, EpisodeType, LLMConfig, OpenAIGenericClient
    global OpenAIEmbedder, OpenAIEmbedderConfig, GeminiEmbedder, GeminiEmbedderConfig

    if Graphiti is not None:
        return True
    try:
        try:
            _inject_embedder_shim()
            from graphiti_core import Graphiti as _Graphiti
        except ImportError as e:
            err_msg = str(e)
            if "graphiti_core.llm_client.openai_generic_client" in err_msg:
                if _inject_openai_generic_client_shim():
                    from graphiti_core import Graphiti as _Graphiti
                else:
                    raise
            elif "graphiti_core.embedder" in err_msg:
                if _inject_embedder_shim():
                    from graphiti_core import Graphiti as _Graphiti
                else:
                    raise
            else:
                raise
        from graphiti_core.nodes import EpisodeType as _EpisodeType
        _patch_graphiti_dedupe_schema()
        try:
            from graphiti_core.llm_client import LLMConfig as _LLMConfig
        except ImportError:
            from graphiti_core.llm_client.config import LLMConfig as _LLMConfig
        try:
            from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient as _OpenAIGenericClient
        except ImportError:
            try:
                from graphiti_core.llm_client.openai_client import OpenAIClient as _OpenAIGenericClient
            except ImportError:
                from graphiti_core.llm_client import OpenAIClient as _OpenAIGenericClient
        from graphiti_core.embedder.openai import OpenAIEmbedder as _OpenAIEmbedder
        from graphiti_core.embedder.openai import OpenAIEmbedderConfig as _OpenAIEmbedderConfig
    except ImportError as e:
        extra = ""
        if "graphiti_core.embedder" in str(e):
            extra = " Graphiti Core is missing the embedder module; verify graphiti-core>=0.1.0 is installed for this Python."
        print(json.dumps({"error": f"ImportError: {e}. Please ensure graphiti-core is installed.{extra} (python={sys.executable})"}))
        return False

    Graphiti = _Graphiti
    EpisodeType = _EpisodeType
    LLMConfig = _LLMConfig
    OpenAIGenericClient = _OpenAIGenericClient
    OpenAIEmbedder = _OpenAIEmbedder
    OpenAIEmbedderConfig = _OpenAIEmbedderConfig

    try:
        from graphiti_core.embedder.gemini import GeminiEmbedder as _GeminiEmbedder
        from graphiti_core.embedder.gemini import GeminiEmbedderConfig as _GeminiEmbedderConfig
    except ImportError:
        _GeminiEmbedder = None
        _GeminiEmbedderConfig = None
    GeminiEmbedder = _GeminiEmbedder
    GeminiEmbedderConfig = _GeminiEmbedderConfig
    return True

# --- CONSTANTS ---
ANALYSIS_PROMPTS = {
    "Identity": (
        "Analyze the following interaction for shifts in the AI's persona, new relationship dynamics, "
        "or reinforced traits. Focus on 'Persona Calibration'. Output a concise 'Calibration Log' summarizing these changes."
    ),
    "Assistant": (
        "Analyze the user's request for workflow patterns, repetitive tasks, or implied needs. "
        "Focus on 'Anticipatory Needs'. Output a concise 'User Profile Update'."
    ),
    "Chatbot": (
        "Analyze the interaction for both user preferences and model identity traits. "
        "Identify which context (Identity vs User) is dominant. Output a 'Relational Context Summary'."
    ),
    "Productivity": (
        "Analyze the text to extract actionable tasks, project dependencies, and potential bottlenecks. "
        "Focus on 'Workflow Optimization'. Output a concise 'Dependency Map'."
    ),
    "Research": (
        "Extract key claims, source reliability (if mentioned), and potential contradictions with established facts. "
        "Focus on 'Source Integrity'. Output a 'Semantic Validation Log'."
    ),
    "Discourse": (
        "Identify the logical structure of the argument, note any fallacies (strawman, ad hominem, etc.), "
        "and map the rhetorical strategy. Output a 'Logic & Rhetoric Analysis'."
    ),
    "Synthesizer": (
        "Summarize the current user's mood and the AI's relationship to them in 2 sentences."
    ),
}

# --- PROCESSING LAYERS ---

def sanitize_memory(raw_text: str, config: Dict[str, Any]) -> str:
    """
    Strips tool usage and code blocks based on plugin settings.
    """
    if not isinstance(raw_text, str):
        return ""
    
    text = raw_text
    sanitization_config = config.get("sanitization", {})

    if sanitization_config.get("sanitize_tool_calls", True):
        text = TOOL_CODE_PATTERN.sub('', text)
        text = TOOL_CALL_PATTERN.sub('', text)
    
    if sanitization_config.get("sanitize_code_blocks", True):
        text = CODE_BLOCK_PATTERN.sub('', text)
    
    # Handle preserve_tagged_code
    if sanitization_config.get("preserve_tagged_code", True):
        # Placeholder for future logic
        pass
    
    # Truncate to max length
    max_len = sanitization_config.get("max_memory_length", 4096)
    if len(text) > max_len:
        text = text[:max_len]
    
    # Custom rules
    custom_rules = sanitization_config.get("custom_sanitization_rules", "")
    if custom_rules:
        for rule in custom_rules.split(";"):
            try:
                text = re.sub(rule, "", text)
            except Exception:
                pass  # Silently ignore malformed regex
    
    return text.strip()

def detect_emotion(text: str, sensitivity: str = "Medium") -> str:
    # Placeholder logic for emotion detection
    emotions = {
        "Low": {"happy": 0.2, "sad": 0.1, "angry": 0.1},
        "Medium": {"happy": 0.3, "sad": 0.2, "curious": 0.2},
        "High": {"excited": 0.4, "thoughtful": 0.3, "amused": 0.2},
    }
    # Simplified emotion tagging logic
    if sensitivity not in emotions:
        sensitivity = "Medium"
    for emotion, threshold in emotions[sensitivity].items():
        if hash(text) % 100 < threshold * 100:
            return emotion.capitalize()
    return "Neutral"

def detect_topics(text: str) -> List[str]:
    # Keywords-based topic detection
    topics = []
    keywords_to_topic = {
        "linux|bash|shell|kernel": "Linux",
        "python|flask|django|asyncio": "Python",
        "game|gaming|play|fun": "Gaming",
        "finance|money|invest|stock": "Finance",
        "anime|manga|otaku": "Anime",
        "poetry|creative|art": "Art",
        "tech|cyber|code": "Tech",
        "love|romance|feeling": "Love"
    }
    for pattern, topic in keywords_to_topic.items():
        if re.search(pattern, text, re.IGNORECASE):
            topics.append(topic)
    return topics if topics else ["Unclassified"]

def apply_intelligence_layer(content: str, original_content: str, config: Dict[str, Any]) -> str:
    """
    Applies emotion/topic tagging based on plugin settings.
    """
    intelligence_config = config.get("intelligence", {})
    
    # Emotion Tagging
    if intelligence_config.get("enable_emotion_tagging", False):
        sensitivity = intelligence_config.get("emotion_sensitivity", "Medium")
        emotion = detect_emotion(original_content, sensitivity)
        content = f"[EMOTION: {emotion}] {content}"

    # Topic Tagging
    if intelligence_config.get("enable_topic_tagging", False):
        topics = detect_topics(original_content)
        topic_tags = " ".join([f"[TOPIC: {topic}]" for topic in topics])
        content = f"{topic_tags} {content}"
        
    return content

def check_lifecycle(content: str, config: Dict[str, Any]) -> bool:
    """
    Checks if a memory should be pruned based on lifecycle settings.
    Returns True if the memory should be pruned, False otherwise.
    """
    lifecycle_config = config.get("lifecycle", {})

    # Auto-Pruning
    if lifecycle_config.get("auto_prune_low_value", False):
        threshold = lifecycle_config.get("low_value_threshold", 3)
        if len(content.strip().split()) < threshold:
            return True

    return False

def extract_episode_id(episode: Any) -> Optional[str]:
    if episode is None:
        return None
    if isinstance(episode, dict):
        for key in ("episode_id", "id", "uuid"):
            value = episode.get(key)
            if value:
                return str(value)
        return None
    for attr in ("episode_id", "id", "uuid"):
        value = getattr(episode, attr, None)
        if value:
            return str(value)
    return None

async def call_maybe_async(func, *args, **kwargs):
    result = func(*args, **kwargs)
    if asyncio.iscoroutine(result):
        await result
    return True

async def delete_episode_safe(client, episode_id: Optional[str], name: Optional[str], group_id: Optional[str]) -> Tuple[bool, Optional[str]]:
    delete_fn = getattr(client, "delete_episode", None) or getattr(client, "delete_episodes", None)
    if not delete_fn:
        return False, "delete_episode is not available"

    if episode_id:
        for kwargs in ({"episode_id": episode_id}, {"id": episode_id}, {"uuid": episode_id}):
            try:
                await call_maybe_async(delete_fn, **kwargs)
                return True, None
            except TypeError:
                continue
            except Exception as exc:
                return False, str(exc)
        try:
            await call_maybe_async(delete_fn, episode_id)
            return True, None
        except TypeError:
            pass
        except Exception as exc:
            return False, str(exc)

    if name:
        for kwargs in ({"name": name, "group_id": group_id}, {"name": name}):
            try:
                await call_maybe_async(delete_fn, **kwargs)
                return True, None
            except TypeError:
                continue
            except Exception as exc:
                return False, str(exc)
        try:
            await call_maybe_async(delete_fn, name)
            return True, None
        except TypeError:
            pass
        except Exception as exc:
            return False, str(exc)

    return False, "No episode identifier provided"

# --- CONFIG HELPERS ---
def get_llm_config_params(section_conf: Dict[str, Any]) -> Dict[str, Any]:
    # (No changes needed in this function)
    provider = section_conf.get("provider", "").lower()
    model = section_conf.get("model", "gpt-4o")
    base_url = section_conf.get("base_url")
    api_key = section_conf.get("api_key")
    if provider == "ollama":
        if not base_url: base_url = "http://localhost:11434/v1"
        if not api_key: api_key = "ollama"
    if "google" in provider and not base_url:
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    if not api_key and not base_url:
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
    return {"api_key": api_key, "base_url": base_url, "model": model, "provider": provider}

# --- DRIVER SETUP ---
def setup_neo4j_driver(config: Dict[str, Any], group_id: str) -> bool:
    # (No changes needed in this function)
    if group_id in ["neo4j", "system"]:
        return True
    try:
        import neo4j
    except ImportError as e:
        print(json.dumps({"error": f"ImportError: {e}. Please ensure neo4j is installed."}))
        return False
    uri, user, password = config.get("uri"), config.get("user"), config.get("password")
    try:
        driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
        with driver.session(database="system") as session:
            session.run(f"CREATE DATABASE {group_id} IF NOT EXISTS")
        driver.close()
    except Exception:
        pass
    return True

def setup_kuzu_driver(config: Dict[str, Any], group_id: str) -> Optional[Any]:
    # (No changes needed in this function)
    try:
        from graphiti_core.driver.kuzu_driver import KuzuDriver
    except ImportError:
        print(json.dumps({"error": "Kuzu driver requested but Kuzu is not installed."}))
        return None
    try:
        import kuzu
    except ImportError as e:
        print(json.dumps({"error": f"Kuzu driver requested but kuzu is not installed: {e}"}))
        return None
    try:
        kuzu_root = config.get("kuzu_path", ".")
        if not os.path.exists(kuzu_root): os.makedirs(kuzu_root)
        safe_group = "".join(c for c in group_id if c.isalnum() or c in (' ', '_', '-')).strip() or "default"
        db_path = os.path.join(kuzu_root, safe_group)
        driver = KuzuDriver(db=db_path)
        driver._database = group_id
        try:
            conn = kuzu.Connection(driver.db)
            for query in [
                "CALL CREATE_FTS_INDEX('Entity', 'node_name_and_summary', ['name', 'summary'])",
                "CALL CREATE_FTS_INDEX('RelatesToNode_', 'edge_name_and_fact', ['name', 'fact'])"
            ]:
                try: conn.execute(query)
                except Exception: pass
        except Exception as e: print(json.dumps({"error": f"Kuzu Index Patch Failed: {e}"}))
        return driver
    except Exception as e:
        print(json.dumps({"error": f"Kuzu Init Failed: {e}"}))
        return None

# --- CORE LOGIC ---
def generate_insight(config: Dict[str, Any], content: str, mode: str) -> str:
    # (No changes needed in this function)
    if mode not in ANALYSIS_PROMPTS: return ""
    params = get_llm_config_params(config.get("insight_llm", {}))
    if not params["api_key"]: return "[Analysis Error: No API Key for Insight Model]"
    try:
        import openai
        client = openai.OpenAI(api_key=params["api_key"], base_url=params["base_url"])
        temperature = config.get("advanced", {}).get("insight_model_temperature", 0.3)
        call_args = {
            "model": params["model"],
            "messages": [
                {"role": "system", "content": f"You are a memory optimization engine. {ANALYSIS_PROMPTS[mode]}"},
                {"role": "user", "content": content}
            ],
            "temperature": temperature,
            "max_tokens": 500
        }
        if "google" not in params.get("provider", ""):
            call_args["frequency_penalty"] = 0.0
            call_args["presence_penalty"] = 0.0
        response = client.chat.completions.create(**call_args)
        return response.choices[0].message.content.strip() if response.choices[0].message.content else ""
    except Exception as e:
        return f"[Analysis Failed: {str(e)}]"

async def execute_operation(client, args: argparse.Namespace, config: Dict[str, Any], driver_type: str, episode_type):
    """Route and execute the requested operation."""
    
    if args.operation == "add":
        original_content = args.content
        
        # 1. Lifecycle Check
        if check_lifecycle(original_content, config):
            print(json.dumps({"status": "skipped", "message": "Content pruned by lifecycle rules."}))
            return

        # 2. Sanitization
        sanitized_content = sanitize_memory(original_content, config)
        if not sanitized_content:
            print(json.dumps({"status": "skipped", "message": "Content was empty after sanitization."}))
            return

        # 3. Insight Generation (on original content for full context)
        insight = generate_insight(config, original_content, args.mode)
        
        # 4. Assemble Content
        # Start with the cleaned conversation
        final_content = sanitized_content
        
        # Prepend insight if it exists
        if insight:
            final_content = f"[MEMORY_MODE: {args.mode}]\n[INSIGHT_START]\n{insight}\n[INSIGHT_END]\n\n{final_content}"

        # 5. Intelligence Layer (e.g., tagging)
        final_content = apply_intelligence_layer(final_content, original_content, config)

        # 6. Custom Memory Tags
        advanced = config.get("advanced", {})
        custom_tags = advanced.get("custom_memory_tags", "")
        if custom_tags:
            tag_list = [t.strip() for t in custom_tags.split(",") if t.strip()]
            tag_prefix = "".join([f"[TAG: {t}]" for t in tag_list])
            final_content = f"{tag_prefix} {final_content}"

        # 7. Add to Database
        episode = await client.add_episode(
            name=args.name,
            episode_body=final_content,
            source=episode_type.text,
            source_description=f"Py-GPT Chat ({args.mode})",
            reference_time=datetime.now(),
            group_id=args.group_id
        )
        episode_id = extract_episode_id(episode)
        print(json.dumps({
            "status": "success",
            "message": f"Episode added. [Backend: {driver_type}] [DB: {args.group_id}]",
            "episode_id": episode_id,
            "episode_name": args.name,
        }))

    elif args.operation == "search":
        results = await client.search(
            query=args.query,
            num_results=args.limit,
            group_ids=[args.group_id] if args.group_id else None
        )
        output = [getattr(res, 'fact', getattr(res, 'body', getattr(res, 'content', str(res)))) for res in results if res]
        print(json.dumps({"status": "success", "results": output}))

    elif args.operation == "forget":
        deleted, error = await delete_episode_safe(client, args.episode_id, args.name, args.group_id)
        if not deleted:
            print(json.dumps({"status": "error", "error": error or "Delete failed"}))
            return
        print(json.dumps({
            "status": "success",
            "message": "Episode deleted.",
            "episode_id": args.episode_id,
            "episode_name": args.name,
        }))

    elif args.operation == "synthesize":
        content = args.content or ""
        if not content:
            print(json.dumps({"status": "error", "error": "Missing content for synthesis."}))
            return
        summary = generate_insight(config, content, args.mode or "Synthesizer")
        if not summary:
            print(json.dumps({"status": "error", "error": "Synthesis failed."}))
            return
        print(json.dumps({"status": "success", "summary": summary}))

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--name", help="Episode Name")
    parser.add_argument("--content", help="Episode Content")
    parser.add_argument("--query", help="Search Query")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--mode", help="Memory Mode", default="Chatbot")
    parser.add_argument("--group_id", help="Database Name", default="neo4j")
    parser.add_argument("--episode_id", help="Episode ID")
    args = parser.parse_args()
    config = json.loads(args.config)

    if not load_graphiti_dependencies():
        return

    # 1. Driver Setup
    driver_type = config.get("driver_type", "Neo4j")
    graph_driver = None
    if driver_type == "Kuzu":
        graph_driver = setup_kuzu_driver(config, args.group_id)
        if not graph_driver: return
    elif driver_type == "Neo4j" and args.group_id:
        if not setup_neo4j_driver(config, args.group_id):
            return

    # 2. LLM Client & Embedder Setup
    llm_conf = config.get("llm", {})
    llm_params = get_llm_config_params(llm_conf)
    if llm_params["base_url"]: os.environ["OPENAI_BASE_URL"] = llm_params["base_url"]
    else: os.environ.pop("OPENAI_BASE_URL", None)
    if llm_params["api_key"]: os.environ["OPENAI_API_KEY"] = llm_params["api_key"]
    
    try:
        llm_config = LLMConfig(
            model=llm_params["model"], api_key=llm_params["api_key"], base_url=llm_params["base_url"],
            temperature=0.0, max_tokens=int(llm_conf.get("max_tokens", 8192))
        )
        custom_llm = OpenAIGenericClient(llm_config)

        embed_conf = config.get("embedding", {})
        embed_model = embed_conf.get("model", "text-embedding-3-small")
        embed_provider = embed_conf.get("provider", "OpenAI")
        embedder = None
        if embed_provider == "Google":
            try:
                from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
            except ImportError:
                print(json.dumps({"error": "Google GenAI library missing."}))
                return
            google_key = embed_conf.get("google_api_key") or os.environ.get("GOOGLE_API_KEY")
            if not google_key:
                print(json.dumps({"error": "Google Embedding selected but no API Key found."}))
                return
            embedder = GeminiEmbedder(GeminiEmbedderConfig(api_key=google_key, embedding_model=embed_model))
        elif embed_provider == "Ollama":
            embedder = OpenAIEmbedder(OpenAIEmbedderConfig(embedding_model=embed_model, base_url="http://localhost:11434/v1", api_key="ollama"))
        else:
            embedder = OpenAIEmbedder(OpenAIEmbedderConfig(embedding_model=embed_model))

        # 4. Initialize Graphiti
        client_kwargs = {"llm_client": custom_llm, "embedder": embedder}
        if graph_driver:
            client_kwargs["graph_driver"] = graph_driver
        else:
            client_kwargs.update({"uri": config["uri"], "user": config["user"], "password": config["password"]})

        client = Graphiti(**client_kwargs)
        if driver_type == "Neo4j":
            try: await client.build_indices_and_constraints()
            except Exception: pass

        # 5. Execute
        await execute_operation(client, args, config, driver_type, EpisodeType)
            
    except Exception as e:
        print(json.dumps({"error": f"Runner Execution Failed: {e}"}))

if __name__ == "__main__":
    asyncio.run(main())
