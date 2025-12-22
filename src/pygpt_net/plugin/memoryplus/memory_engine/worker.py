import asyncio
import json
import os
import queue
from datetime import datetime
from multiprocessing import Process
from typing import Dict, Any, Optional

from .protocol import (
    REQUEST_FORGET,
    REQUEST_HEALTH,
    REQUEST_INGEST,
    REQUEST_SEARCH,
    REQUEST_SYNTH,
    REQUEST_SHUTDOWN,
    EngineRequest,
    EngineResponse,
)


class MemoryWorker(Process):
    def __init__(self, config: Dict[str, Any], group_id: str, request_queue, response_queue):
        super().__init__(daemon=True)
        self.config = config
        self.group_id = group_id
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.client = None
        self.driver_type = ""

    def _send_response(self, resp: EngineResponse):
        try:
            self.response_queue.put(resp.to_dict())
        except Exception:
            pass

    def _build_client(self):
        # Lazy import to avoid impacting the parent process
        from pygpt_net.plugin.memoryplus import runner as runner_module
        if not runner_module.load_graphiti_dependencies():
            raise RuntimeError("Graphiti dependencies are missing")

        self.driver_type = self.config.get("driver_type", "Neo4j")
        graph_driver = None
        if self.driver_type == "Kuzu":
            graph_driver = runner_module.setup_kuzu_driver(self.config, self.group_id)
            if not graph_driver:
                raise RuntimeError("Failed to initialize Kuzu driver")
        elif self.driver_type == "Neo4j" and self.group_id:
            runner_module.setup_neo4j_driver(self.config, self.group_id)

        llm_conf = self.config.get("llm", {})
        llm_params = runner_module.get_llm_config_params(llm_conf)
        if llm_params.get("base_url"):
            os.environ["OPENAI_BASE_URL"] = llm_params["base_url"]
        else:
            os.environ.pop("OPENAI_BASE_URL", None)
        if llm_params.get("api_key"):
            os.environ["OPENAI_API_KEY"] = llm_params["api_key"]

        max_tokens = int(llm_conf.get("max_tokens", 8192))
        if max_tokens > 16384:
            max_tokens = 16384
        llm_config = runner_module.LLMConfig(
            model=llm_params["model"],
            api_key=llm_params["api_key"],
            base_url=llm_params["base_url"],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        custom_llm = runner_module.OpenAIGenericClient(llm_config)

        embed_conf = self.config.get("embedding", {})
        embed_model = embed_conf.get("model", "text-embedding-3-small")
        embed_provider = embed_conf.get("provider", "OpenAI")
        embedder = None
        if embed_provider == "Google":
            if runner_module.GeminiEmbedder:
                google_key = embed_conf.get("google_api_key") or os.environ.get("GOOGLE_API_KEY")
                if not google_key:
                    raise RuntimeError("Google Embedding selected but no API Key found.")
                embedder = runner_module.GeminiEmbedder(
                    runner_module.GeminiEmbedderConfig(api_key=google_key, embedding_model=embed_model)
                )
            else:
                raise RuntimeError("Google GenAI library missing.")
        elif embed_provider == "Ollama":
            embedder = runner_module.OpenAIEmbedder(
                runner_module.OpenAIEmbedderConfig(
                    embedding_model=embed_model,
                    base_url="http://localhost:11434/v1",
                    api_key="ollama",
                )
            )
        else:
            embedder = runner_module.OpenAIEmbedder(runner_module.OpenAIEmbedderConfig(embedding_model=embed_model))

        client_kwargs = {"llm_client": custom_llm, "embedder": embedder}
        if graph_driver:
            client_kwargs["graph_driver"] = graph_driver
        else:
            client_kwargs.update({
                "uri": self.config["uri"],
                "user": self.config["user"],
                "password": self.config["password"],
            })

        client = runner_module.Graphiti(**client_kwargs)
        if self.driver_type == "Neo4j":
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(client.build_indices_and_constraints())
            except Exception:
                pass
        return client

    @staticmethod
    def _extract_episode_id(episode: Any) -> Optional[str]:
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

    def _handle_ingest(self, payload: Dict[str, Any]) -> EngineResponse:
        from pygpt_net.plugin.memoryplus import runner as runner_module

        original_content = payload.get("content", "")
        if runner_module.check_lifecycle(original_content, self.config):
            return EngineResponse(payload.get("request_id", ""), "skipped", data={
                "message": "Content pruned by lifecycle rules."
            })

        sanitized_content = runner_module.sanitize_memory(original_content, self.config)
        if not sanitized_content:
            return EngineResponse(payload.get("request_id", ""), "skipped", data={
                "message": "Content was empty after sanitization."
            })

        mode = payload.get("mode", "Chatbot")
        insight = runner_module.generate_insight(self.config, original_content, mode)
        final_content = sanitized_content
        if insight:
            final_content = (
                f"[MEMORY_MODE: {mode}]\n[INSIGHT_START]\n{insight}\n[INSIGHT_END]\n\n{final_content}"
            )
        final_content = runner_module.apply_intelligence_layer(final_content, original_content, self.config)

        advanced = self.config.get("advanced", {})
        custom_tags = advanced.get("custom_memory_tags", "")
        if custom_tags:
            tag_list = [t.strip() for t in custom_tags.split(",") if t.strip()]
            tag_prefix = "".join([f"[TAG: {t}]" for t in tag_list])
            final_content = f"{tag_prefix} {final_content}"

        async def _write_episode():
            return await self.client.add_episode(
                name=payload.get("name"),
                episode_body=final_content,
                source=runner_module.EpisodeType.text,
                source_description=f"Py-GPT Chat ({mode})",
                reference_time=datetime.now(),
                group_id=self.group_id,
            )

        episode = asyncio.get_event_loop().run_until_complete(_write_episode())
        episode_id = self._extract_episode_id(episode)
        return EngineResponse(payload.get("request_id", ""), "success", data={
            "message": f"Episode added. [Backend: {self.driver_type}] [DB: {self.group_id}]",
            "episode_id": episode_id,
            "episode_name": payload.get("name"),
        })

    def _handle_search(self, payload: Dict[str, Any]) -> EngineResponse:
        async def _search():
            results = await self.client.search(
                query=payload.get("query"),
                num_results=payload.get("limit", 10),
                group_ids=[self.group_id] if self.group_id else None,
            )
            return [
                getattr(res, "fact", getattr(res, "body", getattr(res, "content", str(res))))
                for res in results if res
            ]

        output = asyncio.get_event_loop().run_until_complete(_search())
        return EngineResponse(payload.get("request_id", ""), "success", data={"results": output})

    def _handle_forget(self, payload: Dict[str, Any]) -> EngineResponse:
        async def _call_maybe_async(func, *args, **kwargs):
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                await result
            return True

        async def _try_delete(episode_id: Optional[str], name: Optional[str]):
            delete_fn = getattr(self.client, "delete_episode", None) or getattr(self.client, "delete_episodes", None)
            if not delete_fn:
                return False, "delete_episode is not available"

            if episode_id:
                for kwargs in ({"episode_id": episode_id}, {"id": episode_id}, {"uuid": episode_id}):
                    try:
                        await _call_maybe_async(delete_fn, **kwargs)
                        return True, None
                    except TypeError:
                        continue
                    except Exception as exc:
                        return False, str(exc)
                try:
                    await _call_maybe_async(delete_fn, episode_id)
                    return True, None
                except TypeError:
                    pass
                except Exception as exc:
                    return False, str(exc)

            if name:
                for kwargs in ({"name": name, "group_id": self.group_id}, {"name": name}):
                    try:
                        await _call_maybe_async(delete_fn, **kwargs)
                        return True, None
                    except TypeError:
                        continue
                    except Exception as exc:
                        return False, str(exc)
                try:
                    await _call_maybe_async(delete_fn, name)
                    return True, None
                except TypeError:
                    pass
                except Exception as exc:
                    return False, str(exc)

            return False, "No episode identifier provided"

        episode_id = payload.get("episode_id")
        name = payload.get("name")
        deleted, error = asyncio.get_event_loop().run_until_complete(_try_delete(episode_id, name))
        if not deleted:
            return EngineResponse(payload.get("request_id", ""), "error", error=error or "Delete failed")
        return EngineResponse(payload.get("request_id", ""), "success", data={
            "message": "Episode deleted.",
            "episode_id": episode_id,
            "episode_name": name,
        })

    def _handle_synth(self, payload: Dict[str, Any]) -> EngineResponse:
        from pygpt_net.plugin.memoryplus import runner as runner_module

        content = payload.get("content", "")
        mode = payload.get("mode", "Synthesizer")
        if not content:
            return EngineResponse(payload.get("request_id", ""), "error", error="Missing content for synthesis.")
        summary = runner_module.generate_insight(self.config, content, mode)
        if not summary:
            return EngineResponse(payload.get("request_id", ""), "error", error="Synthesis failed.")
        return EngineResponse(payload.get("request_id", ""), "success", data={"summary": summary})

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            self.client = self._build_client()
        except Exception as e:
            self._send_response(EngineResponse("init", "error", error=str(e)))
            return

        while True:
            try:
                request: EngineRequest = self.request_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            except (EOFError, OSError):
                break

            if not request:
                continue

            req_dict = request if isinstance(request, dict) else request.to_dict()
            op = req_dict.get("operation")
            payload = req_dict.get("payload", {})
            request_id = req_dict.get("request_id", "")

            try:
                if op == REQUEST_SHUTDOWN:
                    self._send_response(EngineResponse(request_id, "success", data={"message": "Shutdown"}))
                    break
                if op == REQUEST_HEALTH:
                    self._send_response(EngineResponse(request_id, "success", data={"status": "ok"}))
                    continue
                if op == REQUEST_INGEST:
                    resp = self._handle_ingest({**payload, "request_id": request_id})
                elif op == REQUEST_SEARCH:
                    resp = self._handle_search({**payload, "request_id": request_id})
                elif op == REQUEST_FORGET:
                    resp = self._handle_forget({**payload, "request_id": request_id})
                elif op == REQUEST_SYNTH:
                    resp = self._handle_synth({**payload, "request_id": request_id})
                else:
                    resp = EngineResponse(request_id, "error", error=f"Unknown operation: {op}")
            except Exception as e:
                resp = EngineResponse(request_id, "error", error=str(e))

            self._send_response(resp)

        try:
            loop.stop()
            loop.close()
        except Exception:
            pass
