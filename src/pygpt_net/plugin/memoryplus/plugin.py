import atexit
import json
import os
import socket
import sys
import subprocess
import threading
import queue
import time
import re
import tempfile
import webbrowser
from collections import OrderedDict
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional, List, Tuple, Dict, Any

from PySide6.QtCore import QTimer

from pygpt_net.plugin.base.plugin import BasePlugin
from pygpt_net.core.events import Event
from pygpt_net.item.ctx import CtxItem
from .memory_engine.client import MemoryEngineClient, ENGINE_MODES


class SearchCache:
    """Simple LRU cache with TTL for recent search results."""

    def __init__(self):
        self.max_entries = 0
        self.ttl = 0.0
        self.fuzzy_ratio = 1.0
        self._cache: "OrderedDict[str, tuple[float, List[str]]]" = OrderedDict()

    def configure(self, max_entries: int, ttl_seconds: float, fuzzy_ratio: float):
        self.max_entries = max(0, int(max_entries))
        self.ttl = max(0.0, float(ttl_seconds))
        self.fuzzy_ratio = min(1.0, max(0.0, float(fuzzy_ratio)))
        if self.max_entries == 0 or self.ttl == 0:
            self.clear()

    def _normalize(self, query: str) -> str:
        return re.sub(r"\s+", " ", query or "").strip().lower()

    def _prune(self):
        if self.max_entries == 0 or self.ttl == 0:
            self._cache.clear()
            return
        now = time.time()
        expired = [key for key, (ts, _) in self._cache.items() if now - ts > self.ttl]
        for key in expired:
            self._cache.pop(key, None)
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)

    def get(self, query: str) -> Optional[List[str]]:
        if self.max_entries == 0 or self.ttl == 0:
            return None
        normalized = self._normalize(query)
        self._prune()
        if normalized in self._cache:
            ts, payload = self._cache.pop(normalized)
            self._cache[normalized] = (ts, payload)
            return payload
        if self.fuzzy_ratio < 1.0:
            for key in list(self._cache.keys()):
                ratio = SequenceMatcher(None, normalized, key).ratio()
                if ratio >= self.fuzzy_ratio:
                    ts, payload = self._cache.pop(key)
                    self._cache[normalized] = (ts, payload)
                    return payload
        return None

    def set(self, query: str, results: List[str]):
        if self.max_entries == 0 or self.ttl == 0:
            return
        normalized = self._normalize(query)
        self._cache[normalized] = (time.time(), list(results))
        self._prune()

    def clear(self):
        self._cache.clear()

class Plugin(BasePlugin):
    def __init__(self, *args, **kwargs):
        super(Plugin, self).__init__(*args, **kwargs)
        self.id = "memoryplus"
        self.name = "MemoryPlus (Graphiti)"
        self.description = "Advanced Temporal Memory using Graphiti with Active Insight Analysis."
        self.type = ["memory"]
        self.order = 90
        self.prefix = "memoryplus"
        self.memory_buffer = None
        self.tabs = {}
        self.ingest_queue: Optional[queue.Queue] = None
        self.ingest_thread: Optional[threading.Thread] = None
        self.ingest_stop_event: Optional[threading.Event] = None
        self.engine_client = None
        self.engine_restart_attempted = False
        self.search_cache = SearchCache()
        self._cache_config_signature = None
        self._cache_group_id = None
        self._last_search_query: Optional[str] = None
        self._last_search_results: Optional[List[str]] = None
        self._last_episode_id: Optional[str] = None
        self._last_episode_name: Optional[str] = None
        self._turn_counter = 0
        self._persona_summary: Optional[str] = None
        self._synth_lock = threading.Lock()
        self._synth_in_progress = False
        self._engine_active = False
        self._neo4j_container_managed = False
        self._neo4j_container_ready = False
        self._engine_deferred = False
        self._container_sync_lock = threading.Lock()
        self._container_sync_thread: Optional[threading.Thread] = None
        self._container_sync_pending = False
        self._persistent_disabled_until = 0.0
        self._persistent_failures = 0
        self._last_engine_error_msg = ""
        self._last_engine_error_ts = 0.0
        self._llm_tokens_warned = False

    def init_options(self):
        """Initialize options and tabs"""
        # General
        self.add_option("auto_ingest", "bool", value=True,
                        label="Auto-Ingest",
                        description="Automatically save conversations to memory after each interaction.",
                        tab="general")
        self.add_option("engine_mode", "combo", value="persistent",
                        label="Engine Mode",
                        description="Choose how Graphiti should be executed (persistent worker or per-call subprocess).",
                        keys=list(ENGINE_MODES),
                        tab="general")
        self.add_option("inject_context", "bool", value=True,
                        label="Inject Context",
                        description="Inject relevant memories into the system prompt before generating a response.",
                        tab="general")
        self.add_option("search_depth", "int", value=5,
                        label="Context Limit",
                        description="The maximum number of relevant memories to retrieve for context.",
                        min=1, max=100,
                        tab="general")
        self.add_option("disable_default_vectors", "bool", value=False,
                        label="Disable Default Vector Store",
                        description="If checked, an instruction will be added to prioritize Graphiti memory over other context sources.",
                        tab="general")

        # Database
        self.add_option("driver_type", "combo", value="Neo4j",
                        label="Database Backend",
                        description="Select the Graph Database backend for storing memories.",
                        keys=["Neo4j", "Kuzu"],
                        tab="database")
        self.add_option("link_to_preset", "bool", value=True,
                        label="Link DB to Preset",
                        description="If enabled, creates/selects a database named after the active Nexus Preset, isolating memories per preset.",
                        tab="database")
        # Neo4j
        self.add_option("db_uri", "text", value="bolt://localhost:7687",
                        label="Neo4j URI",
                        description="The connection URI for the Neo4j database.",
                        tab="database",
                        advanced=False)
        self.add_option("db_user", "text", value="neo4j",
                        label="Neo4j User",
                        description="The username for Neo4j authentication.",
                        tab="database",
                        advanced=False)
        self.add_option("db_pass", "text", value="password",
                        label="Neo4j Password",
                        description="The password for Neo4j authentication.",
                        secret=True,
                        tab="database",
                        advanced=False)
        self.add_option("db_name", "text", value="neo4j",
                        label="Database Name (Fallback)",
                        description="The default Neo4j database name to use if not linking to a preset.",
                        tab="database",
                        advanced=False)
        self.add_option("auto_run_container", "bool", value=False,
                        label="Auto-Run Container",
                        description="Automatically run a local Neo4j Docker container while this plugin is enabled.",
                        tab="database",
                        advanced=True)
        self.add_option("neo4j_container_image", "text", value="neo4j:5-community",
                        label="Neo4j Docker Image",
                        description="Docker image to use for the Neo4j container.",
                        tab="database",
                        advanced=True)
        self.add_option("neo4j_container_name", "text", value="nexus_neo4j",
                        label="Neo4j Container Name",
                        description="Name of the Neo4j Docker container managed by this plugin.",
                        tab="database",
                        advanced=True)
        self.add_option("neo4j_http_port", "int", value=7474,
                        label="Neo4j HTTP Port",
                        description="Host port to expose the Neo4j Browser (HTTP).",
                        min=1, max=65535,
                        tab="database",
                        advanced=True)
        opt = self.get_option("neo4j_http_port")
        if opt:
            opt["description_base"] = opt.get("description", "")
        self.add_option("neo4j_bolt_port", "int", value=7687,
                        label="Neo4j Bolt Port",
                        description="Host port to expose Neo4j Bolt.",
                        min=1, max=65535,
                        tab="database",
                        advanced=True)
        self.add_option("neo4j_data_path", "text",
                        value="",
                        label="Neo4j Data Path",
                        description="Local directory used to persist Neo4j data for the container. Leave blank to use a 'memory' folder in the current workdir.",
                        tab="database",
                        advanced=True)
        opt = self.get_option("neo4j_data_path")
        if opt:
            opt["description_base"] = opt.get("description", "")
        # Kuzu
        self.add_option("kuzu_path", "text", value=os.path.join(os.environ.get("HOME", ""), ".apex", "memories"),
                        label="Kuzu Storage Path",
                        description="The root directory where Kuzu database files will be stored.",
                        tab="database",
                        advanced=True)

        # Models
        self.add_option("memory_mode", "combo",
                        value="Chatbot",
                        label="Memory Mode",
                        description="Select the active memory analysis mode. This determines the lens through which conversations are analyzed for insights.",
                        keys=["Identity", "Assistant", "Chatbot", "Productivity", "Research", "Discourse", "Synthesizer"],
                        tab="models")
        self.add_option("insight_model", "combo", value="gpt-4o",
                        label="Insight Model",
                        description="The model used for generating analytical insights from conversations.",
                        use="models",
                        tab="models")
        self.add_option("llm_model", "combo", value="gpt-4o",
                        label="Graphiti Internal Model",
                        description="The model used by the Graphiti backend for its internal graph-building operations.",
                        use="models",
                        tab="models")
        self.add_option("llm_max_tokens", "int", value=8192,
                        label="Max Context Tokens",
                        description="Maximum tokens for the internal LLM's context window.",
                        min=1024, max=128000,
                        tab="models")
        self.add_option("embedding_provider", "combo",
                        value="OpenAI",
                        label="Embedding Provider",
                        description="The service provider for generating vector embeddings.",
                        keys=["OpenAI", "Ollama", "Google"],
                        tab="models")
        self.add_option("embedding_model", "combo",
                        value="text-embedding-3-small",
                        label="Embedding Model",
                        description="The specific model used to create vector embeddings for semantic search.",
                        keys=[
                            "text-embedding-3-small", "text-embedding-3-large", "nomic-embed-text",
                            "mxbai-embed-large", "all-minilm", "models/text-embedding-004", "models/gemini-embedding-001"
                        ],
                        tab="models")
        self.add_option("override_base_url", "text", value="",
                        label="Override Base URL",
                        description="(Advanced) Override the base URL for the Graphiti Internal Model.",
                        tab="models",
                        advanced=True)
        self.add_option("override_api_key", "text", value="",
                        label="Override API Key",
                        description="(Advanced) Override the API key for the Graphiti Internal Model.",
                        secret=True,
                        tab="models",
                        advanced=True)
        
        # Sanitization
        self.add_option("sanitize_tool_calls", "bool", value=True,
                        label="Sanitize Tool Calls",
                        description="Strip tool usage syntax (e.g., <tool_code>) from memories to focus on conversational content.",
                        tab="sanitization")
        self.add_option("sanitize_code_blocks", "bool", value=True,
                        label="Sanitize Code Blocks",
                        description="Strip markdown code blocks (```...```) from memories.",
                        tab="sanitization")
        self.add_option("preserve_tagged_code", "bool", value=True,
                        label="Preserve Tagged Code",
                        description="Keep code blocks tagged with [KEEP_CODE].",
                        tab="sanitization")
        self.add_option("max_memory_length", "int", value=4096,
                        label="Max Memory Length",
                        description="Truncate memories to this token length.",
                        min=100, max=10000,
                        tab="sanitization")

        # Intelligence
        self.add_option("enable_emotion_tagging", "bool", value=True,
                        label="Enable Emotion Tagging",
                        description="Automatically detect and tag memories with emotional context (e.g., [EMOTION: amused]).",
                        tab="intelligence")
        self.add_option("emotion_sensitivity", "combo", value="Medium",
                        label="Emotion Sensitivity",
                        description="Adjust how aggressively emotions are tagged.",
                        keys=["Low", "Medium", "High"],
                        tab="intelligence")
        self.add_option("enable_topic_tagging", "bool", value=True,
                        label="Enable Topic Tagging",
                        description="Automatically tag memories with relevant topics (e.g., [TOPIC: linux]).",
                        tab="intelligence")
        self.add_option("enable_vibe_scoring", "bool", value=False,
                        label="Enable Vibe Scoring",
                        description="Enable a vibe score (e.g., 0.9) for emotional tone.",
                        tab="intelligence")
        self.add_option("enable_persona_synth", "bool", value=True,
                        label="Enable Persona Synthesizer",
                        description="Generate a brief persona summary every N turns.",
                        tab="intelligence")
        self.add_option("synthesizer_interval", "int", value=5,
                        label="Synthesizer Interval (Turns)",
                        description="How often to refresh the persona summary (every N turns).",
                        min=1, max=100,
                        tab="intelligence")
        self.add_option("inject_persona_summary", "bool", value=True,
                        label="Inject Persona Summary",
                        description="Inject the synthesized persona summary into the system prompt.",
                        tab="intelligence")

        # Lifecycle
        self.add_option("auto_prune_low_value", "bool", value=False,
                        label="Auto-Prune Low-Value Memories",
                        description="Automatically remove memories that are deemed trivial or low-value (e.g., simple greetings).",
                        tab="lifecycle")
        self.add_option("low_value_threshold", "int", value=3,
                        label="Low-Value Threshold",
                        description="Minimum number of words a memory must have to be considered worth retaining.",
                        min=1, max=50,
                        tab="lifecycle")
        self.add_option("manual_memory_flagging", "bool", value=True,
                        label="Enable Manual Memory Flagging",
                        description="Allow manual flagging of memories via commands like /remember_this and /forget_that.",
                        tab="lifecycle")
        self.add_option("memory_expiry_days", "int", value=0,
                        label="Memory Expiry (Days)",
                        description="Automatically delete memories older than this number of days. Set to 0 to disable expiry.",
                        min=0, max=3650,
                        tab="lifecycle")

        # Advanced
        self.add_option("custom_sanitization_rules", "text", value="",
                        label="Custom Sanitization Rules",
                        description="Regex patterns separated by semicolons to apply during sanitization.",
                        tab="advanced")
        self.add_option("custom_memory_tags", "text", value="",
                        label="Custom Memory Tags",
                        description="Custom tags (comma-separated) to apply to all memories.",
                        tab="advanced")
        self.add_option("insight_model_temperature", "float", value=0.3,
                        label="Insight Model Temperature",
                        description="Adjust creativity of insight generation.",
                        min=0.0, max=1.0, step=0.1,
                        tab="advanced")
        self.add_option("memory_review_interval", "int", value=7,
                        label="Memory Review Interval (Days)",
                        description="Prompt the user to review memories every X days (0 = disabled).",
                        min=0, max=365,
                        tab="advanced")
        self.add_option("enable_memory_feedback", "bool", value=True,
                        label="Enable Memory Feedback",
                        description="Let the user rate memories via 👍/👎.",
                        tab="advanced")
        self.add_option("memory_search_depth", "int", value=10,
                        label="Memory Search Depth",
                        description="Number of memories to retrieve during search.",
                        min=1, max=100,
                        tab="advanced")
        self.add_option("enable_search_cache", "bool", value=True,
                        label="Enable Search Cache",
                        description="Cache the most recent memory searches to avoid redundant Graphiti calls.",
                        tab="advanced")
        self.add_option("search_cache_size", "int", value=8,
                        label="Search Cache Size",
                        description="Maximum number of cached searches to keep.",
                        min=0, max=100,
                        tab="advanced")
        self.add_option("search_cache_ttl_seconds", "int", value=45,
                        label="Search Cache TTL (s)",
                        description="Seconds a cached search result remains valid.",
                        min=0, max=600,
                        tab="advanced")
        self.add_option("search_cache_similarity", "float", value=0.85,
                        label="Search Cache Similarity",
                        description="Similarity ratio (0-1) required to treat two queries as the same for caching.",
                        min=0.0, max=1.0, step=0.05,
                        tab="advanced")
        self.add_option("ingest_queue_size", "int", value=50,
                        label="Ingestion Queue Size",
                        description="Maximum number of pending ingestion items. 0 = unlimited.",
                        min=0, max=1000,
                        tab="advanced")
        self.add_option("ingest_overflow_policy", "combo", value="drop_new",
                        label="Ingestion Overflow Policy",
                        description="When the ingestion queue is full: drop new item, drop oldest item, or block until space is free.",
                        keys=["drop_new", "drop_oldest", "block"],
                        tab="advanced")
        self.add_option("ingest_batch_max_items", "int", value=5,
                        label="Ingestion Batch Size",
                        description="Maximum number of items to process together from the queue.",
                        min=1, max=100,
                        tab="advanced")
        self.add_option("ingest_batch_max_delay_ms", "int", value=250,
                        label="Ingestion Batch Delay (ms)",
                        description="Maximum time to wait for additional items before processing a batch.",
                        min=0, max=5000,
                        tab="advanced")
        self.add_option("ingest_retry_attempts", "int", value=3,
                        label="Ingestion Retry Attempts",
                        description="Number of times to retry a failed ingestion before giving up.",
                        min=1, max=10,
                        tab="advanced")
        self.add_option("ingest_retry_backoff_ms", "int", value=500,
                        label="Ingestion Retry Backoff (ms)",
                        description="Initial delay before retrying ingestion. Doubles with each retry.",
                        min=100, max=5000,
                        tab="advanced")
        self.add_option("ctx_search_timeout_seconds", "int", value=3,
                        label="Context Search Timeout (s)",
                        description="Max time to wait for memory search before sending. Set to 0 to skip waiting.",
                        min=0, max=30,
                        tab="advanced")
        self.add_option("persistent_timeout_seconds", "int", value=60,
                        label="Persistent Timeout (s)",
                        description="Timeout for persistent Graphiti worker requests.",
                        min=5, max=300,
                        tab="advanced")
        self.add_option("runner_timeout_seconds", "int", value=45,
                        label="Runner Timeout (s)",
                        description="Timeout for per-call Graphiti subprocess operations.",
                        min=5, max=180,
                        tab="advanced")


    def init_tabs(self) -> dict:
        """Initialize provider tabs"""
        tabs = {}
        tabs["general"] = "General"
        tabs["database"] = "Database"
        tabs["models"] = "Models"
        tabs["sanitization"] = "Sanitization"
        tabs["intelligence"] = "Intelligence"
        tabs["lifecycle"] = "Lifecycle"
        tabs["advanced"] = "Advanced"
        return tabs

    def attach(self, window):
        super(Plugin, self).attach(window)
        self.window = window
        self.tabs = self.init_tabs()
        self.init_options()
        if self._is_enabled():
            self._on_enable()

    def detach(self, *args, **kwargs):
        self._on_disable()
        super(Plugin, self).detach(*args, **kwargs)

    def handle(self, event: Event, *args, **kwargs):
        if event.name == Event.ENABLE and event.data.get("value") == self.id:
            self._on_enable()
            return
        if event.name == Event.DISABLE and event.data.get("value") == self.id:
            self._on_disable()
            return
        if event.name == Event.PLUGIN_SETTINGS_CHANGED:
            self._sync_container_state()
            self._update_neo4j_path_hint()
        if event.name == Event.CMD_SYNTAX:
            self._register_command(event.data)
            return
        if event.name in (Event.CMD_EXECUTE, Event.CMD_INLINE):
            self.cmd(event.ctx, event.data.get("commands", []))
            return
        if event.name == Event.MODELS_CHANGED:
            self.refresh_option("llm_model")
            self.refresh_option("insight_model")
        elif event.name == Event.CTX_BEFORE:
            self._on_ctx_before(event)
        elif event.name == Event.SYSTEM_PROMPT:
            self._on_system_prompt(event)
        elif event.name == Event.CTX_AFTER:
            self._on_ctx_after(event)

    def _is_enabled(self) -> bool:
        try:
            return bool(self.window and self.window.controller.plugins.is_enabled(self.id))
        except Exception:
            return False

    def _on_enable(self):
        if self._engine_active:
            return
        self._engine_active = True
        self._update_neo4j_path_hint()
        self._sync_container_state()
        self._init_engine()
        self._start_ingest_worker()

    def _on_disable(self):
        if not self._engine_active:
            self._stop_ingest_worker()
            self._shutdown_engine()
            self._stop_neo4j_container()
            return
        self._engine_active = False
        self._stop_ingest_worker()
        self._shutdown_engine()
        self._stop_neo4j_container()

    def _sync_container_state(self):
        if self._container_sync_thread and self._container_sync_thread.is_alive():
            self._container_sync_pending = True
            return
        self._container_sync_pending = False
        self._container_sync_thread = threading.Thread(
            target=self._sync_container_state_worker,
            daemon=True,
        )
        self._container_sync_thread.start()

    def _sync_container_state_worker(self):
        with self._container_sync_lock:
            if self._should_manage_container():
                self._ensure_neo4j_container()
            else:
                self._neo4j_container_ready = False
                self._engine_deferred = False
                self._stop_neo4j_container()
        if self._container_sync_pending:
            self._container_sync_pending = False
            self._sync_container_state()

    def _should_manage_container(self) -> bool:
        if not self._is_enabled():
            return False
        if not self.get_option_value("auto_run_container"):
            return False
        if self.get_option_value("driver_type") != "Neo4j":
            return False
        uri = (self.get_option_value("db_uri") or "").strip()
        host, port = self._parse_db_uri(uri)
        if host and host not in ("localhost", "127.0.0.1"):
            self._log_error("Auto-Run Container requires db_uri to use localhost.")
            return False
        bolt_port = self._safe_int(self.get_option_value("neo4j_bolt_port"), 7687)
        if port and port != bolt_port:
            self._log_error("Auto-Run Container Bolt port does not match db_uri.")
        return True

    @staticmethod
    def _parse_db_uri(uri: str) -> Tuple[Optional[str], Optional[int]]:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(uri)
            return parsed.hostname, parsed.port
        except Exception:
            return None, None

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _ensure_neo4j_container(self):
        self._neo4j_container_ready = False
        try:
            import docker
            from docker.errors import NotFound, DockerException, APIError
        except Exception:
            self._log_error("Docker SDK not available; disable Auto-Run Container or install docker.")
            return

        try:
            client = docker.from_env()
            client.ping()
        except Exception as e:
            self._log_error(f"Docker is not available: {e}")
            return

        name = self.get_option_value("neo4j_container_name") or "nexus_neo4j"
        image = self.get_option_value("neo4j_container_image") or "neo4j:5-community"
        http_port = self._safe_int(self.get_option_value("neo4j_http_port"), 7474)
        bolt_port = self._safe_int(self.get_option_value("neo4j_bolt_port"), 7687)
        data_path = self._get_neo4j_data_path()
        db_user = (self.get_option_value("db_user") or "neo4j").strip()
        if db_user != "neo4j":
            self._log_error("Auto-Run Container requires Neo4j user 'neo4j'. Updating db_user to 'neo4j'.")
            self.set_option_value("db_user", "neo4j")
            db_user = "neo4j"
        db_pass = self.get_option_value("db_pass") or "password"
        desired_auth = f"{db_user}/{db_pass}"

        volumes = {}
        if data_path:
            try:
                os.makedirs(data_path, exist_ok=True)
                volumes[data_path] = {"bind": "/data", "mode": "rw"}
            except Exception as e:
                self._log_error(f"Unable to prepare Neo4j data path: {e}")

        env = {
            "NEO4J_AUTH": desired_auth,
            "NEO4J_ACCEPT_LICENSE_AGREEMENT": "yes",
        }
        ports = {
            "7474/tcp": http_port,
            "7687/tcp": bolt_port,
        }

        container = None
        try:
            container = client.containers.get(name)
            try:
                container.reload()
                env_list = container.attrs.get("Config", {}).get("Env", []) or []
                current_auth = ""
                for entry in env_list:
                    if entry.startswith("NEO4J_AUTH="):
                        current_auth = entry.split("=", 1)[1]
                        break
                if current_auth and current_auth.split("/", 1)[0] != "neo4j":
                    self._log_error("Neo4j container was created with an invalid admin user; recreating container.")
                    try:
                        container.stop()
                        container.remove()
                    except Exception:
                        pass
                    container = None
            except Exception:
                pass
            self._neo4j_container_managed = True
            if container and container.status != "running":
                container.start()
        except NotFound:
            container = None
        except DockerException as e:
            self._log_error(f"Failed to inspect Neo4j container: {e}")
            return

        if container is None:
            try:
                container = client.containers.run(
                    image,
                    name=name,
                    detach=True,
                    environment=env,
                    ports=ports,
                    volumes=volumes,
                    restart_policy={"Name": "unless-stopped"},
                )
                self._neo4j_container_managed = True
            except APIError as e:
                self._log_error(f"Failed to start Neo4j container: {e}")
                return

        try:
            container.reload()
            if container.status != "running":
                self._log_error(f"Neo4j container '{name}' not running (status: {container.status}).")
                return
        except Exception:
            pass

        bolt_ready = self._wait_for_port("127.0.0.1", bolt_port, timeout=30)
        if not bolt_ready:
            self._log_error("Neo4j Bolt port did not become ready.")
            return
        http_ready = self._wait_for_port("127.0.0.1", http_port, timeout=10)
        if not http_ready:
            self._log_error(f"Neo4j Browser not reachable at {self._get_neo4j_browser_url()}")
        self._neo4j_container_ready = True
        if self._engine_deferred and self._engine_active:
            self._engine_deferred = False
            QTimer.singleShot(0, self._init_engine)

    def _stop_neo4j_container(self):
        if not self._neo4j_container_managed and not self.get_option_value("auto_run_container"):
            return
        try:
            import docker
            from docker.errors import NotFound, DockerException
        except Exception:
            return

        name = self.get_option_value("neo4j_container_name") or "nexus_neo4j"
        try:
            client = docker.from_env()
            container = client.containers.get(name)
            container.stop()
        except NotFound:
            pass
        except DockerException:
            pass
        finally:
            self._neo4j_container_managed = False
            self._neo4j_container_ready = False
            self._engine_deferred = False

    def _get_neo4j_data_path(self) -> str:
        configured = (self.get_option_value("neo4j_data_path") or "").strip()
        if configured:
            return configured
        if self.window:
            workdir = self.window.core.config.get_user_path()
            return os.path.join(workdir, "memory")
        return os.path.join(os.environ.get("HOME", ""), ".apex", "neo4j")

    def _get_neo4j_browser_url(self) -> str:
        host = "localhost"
        uri = (self.get_option_value("db_uri") or "").strip()
        try:
            from urllib.parse import urlparse
            parsed = urlparse(uri)
            if parsed.hostname:
                host = parsed.hostname
        except Exception:
            pass
        if host in ("0.0.0.0", ""):
            host = "localhost"
        http_port = self._safe_int(self.get_option_value("neo4j_http_port"), 7474)
        return f"http://{host}:{http_port}"

    def _update_neo4j_path_hint(self):
        opt = self.get_option("neo4j_data_path")
        if not opt:
            self._update_neo4j_browser_hint()
            return
        base = opt.get("description_base") or opt.get("description", "")
        default_path = self._get_neo4j_data_path()
        opt["description"] = f"{base} Default (blank): {default_path}"
        opt["tooltip"] = opt["description"]
        self.refresh_option("neo4j_data_path")
        self._update_neo4j_browser_hint()

    def _update_neo4j_browser_hint(self):
        opt = self.get_option("neo4j_http_port")
        if not opt:
            return
        base = opt.get("description_base") or opt.get("description", "")
        url = self._get_neo4j_browser_url()
        opt["description"] = f"{base} Browser URL: {url}"
        opt["tooltip"] = opt["description"]
        self.refresh_option("neo4j_http_port")

    @staticmethod
    def _wait_for_port(host: str, port: int, timeout: int = 20) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            try:
                with socket.create_connection((host, port), timeout=1):
                    return True
            except Exception:
                time.sleep(1)
        return False

    def _register_command(self, data: Optional[Dict[str, Any]]) -> None:
        if data is None:
            return
        commands = data.setdefault("cmd", [])
        commands.append({
            "cmd": "graph_query",
            "params": [],
            "desc": "Query the memory graph",
            "help": "/graph_query <question>",
            "syntax": {"query": "text", "limit": "text"},
        })
        commands.append({
            "cmd": "graph_visualize",
            "params": [],
            "desc": "Visualize a memory subgraph",
            "help": "/graph_visualize <optional query>",
            "syntax": {"query": "text", "limit": "text"},
        })
        commands.append({
            "cmd": "forget_last",
            "params": [],
            "desc": "Delete the most recently ingested memory",
            "help": "/forget_last",
            "syntax": {},
        })

    def cmd(self, ctx: CtxItem, cmds: List[Dict[str, Any]]) -> CtxItem:
        handled = False
        for item in cmds:
            cmd = item.get("cmd")
            params = item.get("params") or {}
            if cmd == "graph_query":
                handled = True
                result = self._cmd_graph_query(params)
            elif cmd == "graph_visualize":
                handled = True
                result = self._cmd_graph_visualize(params)
            elif cmd == "forget_last":
                handled = True
                result = self._cmd_forget_last()
            else:
                continue

            result["request"] = {"cmd": cmd, "params": params}
            ctx.results.append(result)

        if handled:
            ctx.reply = True
        return ctx

    def _parse_command_text(self, params: Dict[str, Any]) -> str:
        for key in ("query", "text", "args"):
            value = params.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _get_command_limit(self, params: Dict[str, Any]) -> int:
        limit_value = params.get("limit")
        if limit_value is None:
            limit_value = self.get_option_value("memory_search_depth") or self.get_option_value("search_depth")
        try:
            return max(1, int(limit_value))
        except Exception:
            return 5

    def _cmd_graph_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = self._parse_command_text(params)
        if not query:
            return {"ok": False, "error": "Missing query. Example: /graph_query What do you know about X?"}
        limit = self._get_command_limit(params)
        response = self._search_memories(query, limit)
        if not response:
            return {"ok": False, "error": "Graph query failed."}
        if response.get("status") != "success":
            return {"ok": False, "error": response.get("error", "Graph query failed.")}
        results = self._extract_results(response)
        return {"ok": True, "data": {"query": query, "results": results}}

    def _cmd_graph_visualize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = self._parse_command_text(params) or self._last_search_query
        if not query:
            return {"ok": False, "error": "Missing query. Example: /graph_visualize <query>."}

        limit = self._get_command_limit(params)
        results = None
        if self._last_search_query == query and self._last_search_results is not None:
            results = self._last_search_results
        if results is None:
            response = self._search_memories(query, limit)
            if not response or response.get("status") != "success":
                return {"ok": False, "error": response.get("error", "Graph search failed.") if response else "Graph search failed."}
            results = self._extract_results(response)

        if not results:
            return {"ok": False, "error": "No results to visualize."}

        try:
            from pyvis.network import Network
        except Exception:
            return {"ok": False, "error": "pyvis is not installed. Add it to your environment to use graph visualization."}

        graph_dir = os.path.join(os.path.dirname(__file__), "graphs")
        try:
            os.makedirs(graph_dir, exist_ok=True)
        except Exception as exc:
            return {"ok": False, "error": f"Failed to create graph directory: {exc}"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"memory_graph_{timestamp}.html"
        path = os.path.join(graph_dir, filename)

        try:
            net = Network(
                height="750px",
                width="100%",
                bgcolor="#111827",
                font_color="#e5e7eb",
                cdn_resources="in_line",
            )
        except TypeError:
            net = Network(height="750px", width="100%", bgcolor="#111827", font_color="#e5e7eb")
        net.add_node("query", label="Query", title=query, color="#f59e0b", size=30)

        for idx, memory in enumerate(results):
            label = memory
            if len(label) > 80:
                label = f"{label[:77]}..."
            node_id = f"m{idx}"
            net.add_node(node_id, label=label, title=memory, color="#60a5fa", size=15)
            net.add_edge("query", node_id)

        try:
            net.write_html(path)
        except Exception as exc:
            return {"ok": False, "error": f"Failed to write graph HTML: {exc}"}

        try:
            webbrowser.open(f"file://{path}")
        except Exception:
            pass

        return {"ok": True, "data": {"path": path, "count": len(results), "query": query}}

    def _cmd_forget_last(self) -> Dict[str, Any]:
        if not self._last_episode_id and not self._last_episode_name:
            return {"ok": False, "error": "No recently ingested memory found to forget."}
        response = self._engine_request(
            "FORGET",
            {"episode_id": self._last_episode_id, "name": self._last_episode_name},
            lambda: self._run_subprocess(
                self._get_runner_cmd(
                    "forget",
                    episode_id=self._last_episode_id or "",
                    name=self._last_episode_name or "",
                )
            ),
        )
        if not response:
            return {"ok": False, "error": "Forget request failed."}
        if response.get("status") != "success":
            return {"ok": False, "error": response.get("error", "Forget request failed.")}
        self._last_episode_id = None
        self._last_episode_name = None
        payload = response.get("data") if isinstance(response.get("data"), dict) else response
        return {"ok": True, "data": payload}

    def _get_model_config(self, option_name="llm_model"):
        model_id = self.get_option_value(option_name)
        config = {"model": model_id, "api_key": "", "base_url": "", "provider": "openai"}

        if self.window and self.window.core.models.has(model_id):
            model_item = self.window.core.models.get(model_id)
            client_args = self.window.core.models.prepare_client_args(model=model_item)
            config["api_key"] = client_args.get("api_key", "")
            config["base_url"] = client_args.get("base_url", "")
            config["provider"] = model_item.provider

        if option_name == "llm_model":
            if self.get_option_value("override_api_key"):
                config["api_key"] = self.get_option_value("override_api_key")
            if self.get_option_value("override_base_url"):
                config["base_url"] = self.get_option_value("override_base_url")
        return config

    def _get_group_id(self):
        if self.get_option_value("link_to_preset"):
            preset_id = self.window.core.config.get('preset')
            if preset_id:
                return preset_id
        return self.get_option_value("db_name")

    def _is_kuzu_driver(self) -> bool:
        try:
            return self.get_option_value("driver_type") == "Kuzu"
        except Exception:
            return False

    def _build_engine_config(self):
        main_model_config = self._get_model_config("llm_model")
        insight_model_config = self._get_model_config("insight_model")
        google_key = self.window.core.config.get("api_key_google") or ""
        llm_max_tokens = self._get_llm_max_tokens()

        return {
            # DB
            "driver_type": self.get_option_value("driver_type"),
            "uri": self.get_option_value("db_uri"),
            "user": self.get_option_value("db_user"),
            "password": self.get_option_value("db_pass"),
            "kuzu_path": self.get_option_value("kuzu_path"),
            # LLM
            "llm": {
                "provider": main_model_config["provider"],
                "model": main_model_config["model"],
                "base_url": main_model_config["base_url"],
                "api_key": main_model_config["api_key"],
                "max_tokens": llm_max_tokens,
            },
            # Insight LLM
            "insight_llm": {
                "provider": insight_model_config["provider"],
                "model": insight_model_config["model"],
                "base_url": insight_model_config["base_url"],
                "api_key": insight_model_config["api_key"],
            },
            # Embedding
            "embedding": {
                "provider": self.get_option_value("embedding_provider"),
                "model": self.get_option_value("embedding_model"),
                "google_api_key": google_key
            },
            # New config options
            "sanitization": {
                "sanitize_tool_calls": self.get_option_value("sanitize_tool_calls"),
                "sanitize_code_blocks": self.get_option_value("sanitize_code_blocks"),
                "preserve_tagged_code": self.get_option_value("preserve_tagged_code"),
                "max_memory_length": self.get_option_value("max_memory_length"),
                "custom_sanitization_rules": self.get_option_value("custom_sanitization_rules"),
            },
            "intelligence": {
                "enable_emotion_tagging": self.get_option_value("enable_emotion_tagging"),
                "emotion_sensitivity": self.get_option_value("emotion_sensitivity"),
                "enable_topic_tagging": self.get_option_value("enable_topic_tagging"),
                "enable_vibe_scoring": self.get_option_value("enable_vibe_scoring"),
            },
            "lifecycle": {
                "auto_prune_low_value": self.get_option_value("auto_prune_low_value"),
                "low_value_threshold": self.get_option_value("low_value_threshold"),
                "manual_memory_flagging": self.get_option_value("manual_memory_flagging"),
                "memory_expiry_days": self.get_option_value("memory_expiry_days"),
            },
            "advanced": {
                "custom_memory_tags": self.get_option_value("custom_memory_tags"),
                "insight_model_temperature": self.get_option_value("insight_model_temperature"),
                "memory_review_interval": self.get_option_value("memory_review_interval"),
                "enable_memory_feedback": self.get_option_value("enable_memory_feedback"),
                "memory_search_depth": self.get_option_value("memory_search_depth"),
            }
        }

    def _get_runner_timeout(self) -> int:
        try:
            return max(5, int(self.get_option_value("runner_timeout_seconds")))
        except Exception:
            return 45

    def _get_persistent_timeout(self) -> int:
        try:
            return max(5, int(self.get_option_value("persistent_timeout_seconds")))
        except Exception:
            return 60

    def _get_ctx_search_timeout(self) -> int:
        try:
            return max(0, int(self.get_option_value("ctx_search_timeout_seconds")))
        except Exception:
            return 3

    def _get_llm_max_tokens(self) -> int:
        try:
            value = int(self.get_option_value("llm_max_tokens") or 0)
        except Exception:
            value = 0
        if value <= 0:
            value = 8192
        safe_max = 16384
        if value > safe_max:
            if not self._llm_tokens_warned:
                self._llm_tokens_warned = True
                self._log_error(f"Graphiti max tokens clamped to {safe_max} (requested {value}).")
            value = safe_max
        return value

    def _configure_cache(self) -> bool:
        group_id = self._get_group_id()
        enable = bool(self.get_option_value("enable_search_cache"))
        size = int(self.get_option_value("search_cache_size") or 0)
        ttl = int(self.get_option_value("search_cache_ttl_seconds") or 0)
        similarity = float(self.get_option_value("search_cache_similarity") or 0)
        signature = (group_id, enable, size, ttl, similarity)

        if signature == self._cache_config_signature:
            return enable and size > 0 and ttl > 0

        if not enable or size <= 0 or ttl <= 0:
            self.search_cache.clear()
            self._cache_config_signature = signature
            self._cache_group_id = group_id
            return False

        if self._cache_group_id != group_id:
            self.search_cache.clear()
            self._cache_group_id = group_id

        self.search_cache.configure(size, ttl, similarity or 1.0)
        self._cache_config_signature = signature
        return True

    def _cache_key(self, query: str, limit: int) -> str:
        group_id = self._cache_group_id or self._get_group_id()
        return f"{group_id}::{limit}::{query}"

    def _invalidate_cache(self):
        self.search_cache.clear()
        self._cache_config_signature = None
        self._cache_group_id = None

    def _extract_results(self, response) -> List[str]:
        if not response:
            return []
        results = response.get("results")
        if isinstance(results, list):
            return results
        data = response.get("data")
        if isinstance(data, dict):
            nested = data.get("results")
            if isinstance(nested, list):
                return nested
        return []

    def _get_runner_cmd(self, operation: str, **kwargs):
        runner_path = os.path.join(os.path.dirname(__file__), "runner.py")
        config = self._build_engine_config()

        kwargs["group_id"] = self._get_group_id()

        cmd = [sys.executable, runner_path, "--operation", operation]
        cleanup_paths: List[str] = []

        config_json = json.dumps(config)
        config_path = self._write_temp_file(config_json, suffix=".json")
        cleanup_paths.append(config_path)
        cmd.extend(["--config-file", config_path])

        for key, value in list(kwargs.items()):
            if value is None:
                kwargs.pop(key, None)

        content = kwargs.pop("content", None)
        if isinstance(content, str):
            if len(content) > 2000:
                content_path = self._write_temp_file(content, suffix=".txt")
                cleanup_paths.append(content_path)
                cmd.extend(["--content-file", content_path])
            else:
                cmd.extend(["--content", content])

        query = kwargs.pop("query", None)
        if isinstance(query, str):
            if len(query) > 2000:
                query_path = self._write_temp_file(query, suffix=".txt")
                cleanup_paths.append(query_path)
                cmd.extend(["--query-file", query_path])
            else:
                cmd.extend(["--query", query])

        for k, v in kwargs.items():
            cmd.append(f"--{k}")
            cmd.append(str(v))
        return cmd, cleanup_paths

    def _write_temp_file(self, payload: str, suffix: str = "") -> str:
        fd, path = tempfile.mkstemp(prefix="memoryplus_", suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        return path

    def _run_subprocess(self, cmd, background=False):
        timeout = self._get_runner_timeout()
        cleanup_paths: List[str] = []
        if isinstance(cmd, tuple):
            cmd, cleanup_paths = cmd
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            response = None
            if result.stdout.strip():
                try:
                    response = json.loads(result.stdout)
                except json.JSONDecodeError: pass

            if result.returncode != 0:
                err_msg = result.stderr.strip() or (response and response.get("error")) or "Unknown runner error"
                msg = f"Runner failed: {err_msg}"
                self._log_error(msg)
                return None
            return response
        except subprocess.TimeoutExpired:
            msg = f"Subprocess timed out after {timeout}s: {' '.join(cmd)}"
            self._log_error(msg)
            return None
        except Exception as e:
            msg = f"Subprocess error: {e}"
            self._log_error(msg)
            return None
        finally:
            for path in cleanup_paths:
                try:
                    os.remove(path)
                except Exception:
                    pass

    def _init_engine(self):
        if self._should_manage_container() and not self._neo4j_container_ready:
            self._engine_deferred = True
            return
        if self.get_option_value("engine_mode") not in ["persistent", "auto"] and not self._is_kuzu_driver():
            return
        if self._is_kuzu_driver() and self.get_option_value("engine_mode") == "subprocess":
            if hasattr(self.window, "update_status"):
                self.log("Kuzu requires persistent engine mode; overriding subprocess.")
        if self.get_option_value("driver_type") == "Kuzu":
            path = self.get_option_value("kuzu_path")
            if path and not os.path.exists(path):
                try:
                    os.makedirs(path)
                except Exception as e:
                    self.error(f"Cannot create Kuzu path: {path}. Error: {e}")
                    return
        self._reset_persistent_failures()
        self._ensure_engine_client()
        client = self.engine_client
        if client:
            started = client.start()
            if not started or not client.is_alive():
                if hasattr(self.window, "update_status"):
                    self.log("Persistent Graphiti worker not running; attempting restart.")
                if not client.restart():
                    if self._is_kuzu_driver():
                        msg = "Failed to start persistent Graphiti worker for Kuzu."
                    else:
                        msg = "Failed to start persistent Graphiti worker. Falling back to subprocess mode."
                    if hasattr(self.window, "update_status"):
                        self.error(msg)

    def _ensure_engine_client(self):
        if not self.engine_client:
            self.engine_client = MemoryEngineClient(
                self._build_engine_config,
                self._get_group_id,
                logger=self.log,
                error_logger=self._engine_error
            )
            self.engine_client.set_default_timeout(self._get_persistent_timeout())
            atexit.register(self._shutdown_engine)
        return self.engine_client

    def _should_use_persistent(self):
        if self._is_kuzu_driver():
            return True
        if time.time() < self._persistent_disabled_until:
            return False
        return self.get_option_value("engine_mode") in ["persistent", "auto"]

    def _record_persistent_failure(self, reason: str):
        if self._is_kuzu_driver():
            return
        now = time.time()
        cooldown = max(30, min(120, self._get_persistent_timeout()))
        if now >= self._persistent_disabled_until:
            self._log_error(f"Persistent worker paused for {int(cooldown)}s: {reason}")
        self._persistent_disabled_until = now + cooldown
        self._persistent_failures += 1

    def _reset_persistent_failures(self):
        self._persistent_failures = 0
        self._persistent_disabled_until = 0.0
        self.engine_restart_attempted = False

    def _restart_engine(self):
        if not self._should_use_persistent():
            return False
        if self.engine_restart_attempted:
            return False
        self.engine_restart_attempted = True
        client = self._ensure_engine_client()
        self.log("Restarting persistent Graphiti worker after failure.")
        return client.restart()

    def _engine_request(
        self,
        request_type: str,
        payload: dict,
        fallback_fn,
        timeout: Optional[float] = None,
        allow_fallback: bool = True,
        allow_restart: bool = True,
        record_failure: bool = True,
    ):
        if not self._should_use_persistent():
            return fallback_fn()

        client = self._ensure_engine_client()
        client.set_default_timeout(self._get_persistent_timeout())
        method = {
            "SEARCH": client.search,
            "INGEST": client.ingest,
            "FORGET": client.forget,
            "HEALTH": client.health,
            "SYNTH": client.synthesize,
        }.get(request_type)

        if not method:
            return fallback_fn()

        timeout = self._get_persistent_timeout() if timeout is None else float(timeout)
        response = method(timeout=timeout, **payload)
        if response and response.get("status") == "success":
            self._reset_persistent_failures()
            return response

        if (not response or response.get("status") == "error") and not self.engine_restart_attempted and allow_restart:
            if self._restart_engine():
                response = method(timeout=timeout, **payload)
                if response and response.get("status") == "success":
                    self._reset_persistent_failures()
                    return response

        if not response or response.get("status") == "error":
            failure_reason = "error response"
            if getattr(client, "last_error_type", None):
                failure_reason = client.last_error_type or failure_reason
            if record_failure:
                self._record_persistent_failure(failure_reason)
            if self._is_kuzu_driver() and request_type != "SYNTH":
                return response
            if not allow_fallback:
                return response
            return fallback_fn()
        return response

    def _shutdown_engine(self):
        if self.engine_client:
            try:
                self.engine_client.shutdown()
            except Exception:
                pass

    def _on_ctx_before(self, event: Event):
        if not self.get_option_value("inject_context"):
            return
        ctx = event.ctx
        if not ctx.input:
            return

        limit = self.get_option_value("search_depth")
        if self._configure_cache():
            cached = self.search_cache.get(self._cache_key(ctx.input, limit))
            if cached:
                self._format_memory_buffer(cached)
                return
        timeout = self._get_ctx_search_timeout()
        if timeout == 0:
            return

        response_holder: Dict[str, Any] = {}
        done = threading.Event()

        def _worker():
            response_holder["response"] = self._search_memories(
                ctx.input,
                limit,
                timeout=timeout,
                allow_fallback=False,
                allow_restart=False,
                record_failure=False,
                suppress_errors=True,
            )
            done.set()

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        if not done.wait(timeout):
            return
        response = response_holder.get("response")

        if response and response.get("status") == "success":
            results = self._extract_results(response)
            if results:
                self._format_memory_buffer(results)

    def _format_memory_buffer(self, memories: List[str]):
        memory_block = "\n".join([f"- {m}" for m in memories])
        header = "\n--- RELEVANT MEMORY (GRAPHITI) ---\n"
        footer = "\n--- END MEMORY ---\n"
        self.memory_buffer = f"{header}{memory_block}{footer}"
        if self.get_option_value("disable_default_vectors"):
            self.memory_buffer += "\n[INSTRUCTION: Prioritize the above Graphiti memory over any other context.]\n"

    def _format_persona_summary(self) -> str:
        header = "\n--- RELATIONSHIP SUMMARY ---\n"
        footer = "\n--- END SUMMARY ---\n"
        return f"{header}{self._persona_summary}{footer}"

    def _on_system_prompt(self, event: Event):
        if self.get_option_value("inject_persona_summary") and self._persona_summary:
            event.data['value'] = (event.data.get('value') or "") + self._format_persona_summary()
            if hasattr(self.window, "update_status"):
                self.log("Injecting persona summary into System Prompt.")
        if self.memory_buffer:
            event.data['value'] = (event.data.get('value') or "") + self.memory_buffer
            self.memory_buffer = None
            if hasattr(self.window, "update_status"):
                self.log("Injecting memory into System Prompt.")

    def _on_ctx_after(self, event: Event):
        ctx = event.ctx
        if not ctx:
            return
        episode_body = f"User: {ctx.input}\nAssistant: {ctx.output}"
        self._maybe_schedule_persona_synthesis(episode_body)
        if not self.get_option_value("auto_ingest"):
            return
        
        title = "Unsaved Chat"
        try:
            meta = self.window.core.ctx.get_current_meta()
            if meta and meta.name:
                title = meta.name
        except Exception: pass
        title = re.sub(r'[^a-zA-Z0-9 _-]', '', title)
        ep_name = f"{title} - {datetime.now().strftime('%H:%M:%S')}"

        mode = self.get_option_value("memory_mode")
        self._enqueue_ingest_request(ep_name, episode_body, mode)

    def _maybe_schedule_persona_synthesis(self, content: str):
        if not self.get_option_value("enable_persona_synth"):
            return
        interval = int(self.get_option_value("synthesizer_interval") or 0)
        if interval <= 0:
            return
        self._turn_counter += 1
        if self._turn_counter % interval != 0:
            return
        if not content:
            return
        with self._synth_lock:
            if self._synth_in_progress:
                return
            self._synth_in_progress = True
        thread = threading.Thread(target=self._run_persona_synthesis, args=(content,), daemon=True)
        thread.start()

    def _run_persona_synthesis(self, content: str):
        try:
            response = self._engine_request(
                "SYNTH",
                {"content": content, "mode": "Synthesizer"},
                lambda: self._run_subprocess(
                    self._get_runner_cmd("synthesize", content=content, mode="Synthesizer")
                ),
            )
            summary = None
            if response:
                summary = response.get("summary")
                if not summary and isinstance(response.get("data"), dict):
                    summary = response["data"].get("summary")
            if summary:
                self._persona_summary = summary.strip()
                if hasattr(self.window, "update_status"):
                    self.log("Persona summary updated.")
            elif response:
                error = response.get("error")
                if error:
                    self.error(f"Persona synthesis failed: {error}")
        finally:
            with self._synth_lock:
                self._synth_in_progress = False

    def _start_ingest_worker(self):
        if self.ingest_thread and self.ingest_thread.is_alive():
            return

        maxsize = self.get_option_value("ingest_queue_size") or 0
        self.ingest_queue = queue.Queue(maxsize=maxsize)
        self.ingest_stop_event = threading.Event()
        self.ingest_thread = threading.Thread(target=self._ingest_loop, daemon=True)
        self.ingest_thread.start()

    def _stop_ingest_worker(self):
        if self.ingest_stop_event:
            self.ingest_stop_event.set()
        if self.ingest_thread and self.ingest_thread.is_alive():
            self.ingest_thread.join(timeout=2)
        if self.ingest_queue:
            try:
                while True:
                    dropped = self.ingest_queue.get_nowait()
                    self.log(f"[WARN] Ingest worker stopped. Dropping pending item: {dropped[0]}")
                    self.ingest_queue.task_done()
            except queue.Empty:
                pass
        self.ingest_thread = None
        self.ingest_queue = None
        self.ingest_stop_event = None

    def _enqueue_ingest_request(self, name: str, content: str, mode: str):
        if not self.ingest_queue:
            self._start_ingest_worker()

        overflow_policy = self.get_option_value("ingest_overflow_policy")
        item = (name, content, mode)

        if overflow_policy == "block":
            while self.ingest_stop_event and not self.ingest_stop_event.is_set():
                try:
                    self.ingest_queue.put(item, timeout=0.5)
                    return
                except queue.Full:
                    continue
            self.log(f"[WARN] Ingest worker stopping. Dropping item: {name}")
            return

        try:
            self.ingest_queue.put(item, block=False)
        except queue.Full:
            if overflow_policy == "drop_oldest":
                try:
                    dropped = self.ingest_queue.get_nowait()
                    self.ingest_queue.task_done()
                    self.log(f"[WARN] Ingest queue full. Dropping oldest item: {dropped[0]}")
                except queue.Empty:
                    pass
                try:
                    self.ingest_queue.put_nowait(item)
                except queue.Full:
                    self.log(f"[WARN] Ingest queue full. Dropping new item: {name}")
            else:
                self.log(f"[WARN] Ingest queue full. Dropping new item: {name}")

    def _ingest_loop(self):
        while self.ingest_stop_event and not self.ingest_stop_event.is_set():
            try:
                first_item: Tuple[str, str, str] = self.ingest_queue.get(timeout=0.5)  # type: ignore
            except queue.Empty:
                continue

            batch = [first_item]
            max_items = max(1, int(self.get_option_value("ingest_batch_max_items") or 1))
            max_delay = max(0, int(self.get_option_value("ingest_batch_max_delay_ms") or 0)) / 1000
            start = time.monotonic()

            while len(batch) < max_items:
                remaining = max_delay - (time.monotonic() - start)
                if remaining <= 0:
                    break
                try:
                    next_item = self.ingest_queue.get(timeout=remaining)
                    batch.append(next_item)
                except queue.Empty:
                    break

            for name, content, mode in batch:
                try:
                    self._process_ingest(name, content, mode)
                except Exception as exc:
                    self._log_error(f"Ingest loop error for '{name}': {exc}")
                self.ingest_queue.task_done()

    def _process_ingest(self, name: str, content: str, mode: str):
        attempts = max(1, int(self.get_option_value("ingest_retry_attempts") or 1))
        backoff = max(0.1, (int(self.get_option_value("ingest_retry_backoff_ms") or 100) / 1000))
        last_response = None

        for attempt in range(1, attempts + 1):
            response = self._engine_request(
                "INGEST",
                {"name": name, "content": content, "mode": mode},
                lambda: self._run_subprocess(
                    self._get_runner_cmd("add", name=name, content=content, mode=mode),
                    background=True,
                ),
            )
            last_response = response
            if response:
                status = response.get("status")
                if status == "success":
                    self._update_last_episode(response, name)
                    self.log(f"Ingested: {name} [Mode: {mode}]")
                    self._invalidate_cache()
                    return
                if status == "skipped":
                    self.log(f"Ingest skipped: {response.get('data', {}).get('message', 'Lifecycle rule matched')}")
                    return
            if attempt < attempts:
                time.sleep(backoff)
                backoff *= 2

        if last_response:
            self.log(f"[ERROR] Ingest Error: {last_response.get('error') or last_response.get('data')}")
        else:
            self.log(f"[ERROR] Ingest Error: runner produced no response for {name}")

    def _update_last_episode(self, response: Dict[str, Any], fallback_name: str):
        episode_id = None
        episode_name = fallback_name
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        if data:
            episode_id = data.get("episode_id") or data.get("id") or data.get("uuid")
            episode_name = data.get("episode_name") or episode_name
        if not episode_id:
            episode_id = response.get("episode_id") or response.get("id") or response.get("uuid")
        if response.get("episode_name"):
            episode_name = response.get("episode_name")
        if episode_id or episode_name:
            self._last_episode_id = str(episode_id) if episode_id else None
            self._last_episode_name = episode_name

    def _search_memories(
        self,
        query: str,
        limit: int,
        timeout: Optional[float] = None,
        allow_fallback: bool = True,
        allow_restart: bool = True,
        record_failure: bool = True,
        suppress_errors: bool = False,
    ):
        use_cache = self._configure_cache()
        cache_key = None
        if use_cache:
            cache_key = self._cache_key(query, limit)
            cached = self.search_cache.get(cache_key)
            if cached is not None:
                return {"status": "success", "results": cached, "cached": True}

        response = self._engine_request(
            "SEARCH",
            {"query": query, "limit": limit},
            lambda: self._run_subprocess(self._get_runner_cmd("search", query=query, limit=limit)),
            timeout=timeout,
            allow_fallback=allow_fallback,
            allow_restart=allow_restart,
            record_failure=record_failure,
        )

        if response and response.get("status") == "success":
            results = self._extract_results(response)
            self._last_search_query = query
            self._last_search_results = results
            if use_cache and cache_key and results is not None:
                self.search_cache.set(cache_key, results)
        elif response and response.get("status") == "error" and not suppress_errors:
            self.error(f"Search Error: {response.get('error', 'Unknown error')}")
        return response

    def _engine_error(self, msg: str):
        self._log_error(msg)
        if not self.window:
            return
        now = time.time()
        if msg == self._last_engine_error_msg and (now - self._last_engine_error_ts) < 15:
            return
        self._last_engine_error_msg = msg
        self._last_engine_error_ts = now
        self.window.update_status(f"{self.name}: {msg}")

    def _log_error(self, msg: str):
        if not self.window:
            return
        self.window.core.debug.error(f"[{self.prefix}] {msg}", console=False)

    def log(self, msg: str):
        if self.is_threaded() or not self.window:
            return
        self.window.core.debug.info(f"[{self.prefix}] {msg}", console=False)

    def error(self, err: Any):
        if not self.window:
            return
        self.window.core.debug.log(err, console=False)
        msg = self.window.core.debug.parse_alert(err)
        self.window.update_status(f"{self.name}: {msg}")
