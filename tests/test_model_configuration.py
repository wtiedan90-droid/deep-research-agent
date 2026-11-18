"""Check Studio configuration and model calls without external requests."""

import json
import os
import unittest
import warnings
from unittest.mock import patch

from langchain_core.messages import AIMessage
from pydantic import TypeAdapter

from deep_research_agent import graph as app
from deep_research_agent.configuration import Configuration
from deep_research_agent.state import SummaryState


class ModelConfigurationTest(unittest.TestCase):
    def test_studio_schema_matches_deepseek_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            fields = TypeAdapter(Configuration).json_schema()["properties"]
        self.assertEqual(fields["llm_model_name"]["default"], "deepseek-chat")
        self.assertEqual(fields["llm_base_url"]["default"], "https://api.deepseek.com")
        for obsolete in ("local_llm", "llm_provider", "ollama_base_url", "lmstudio_base_url"):
            self.assertNotIn(obsolete, fields)

    def test_schema_defaults_use_typed_environment_values(self):
        values = {
            "LLM_MODEL_NAME": "model-from-env",
            "LLM_BASE_URL": "https://example.com/v1",
            "MAX_WEB_RESEARCH_LOOPS": "0",
            "DDGS_BACKEND": "yahoo",
            "FETCH_FULL_PAGE": "false",
        }
        with patch.dict(os.environ, values, clear=True), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            schemas = [
                TypeAdapter(Configuration).json_schema(),
                app.graph.get_config_jsonschema()["$defs"]["Configuration"],
            ]
        for schema in schemas:
            fields = schema["properties"]
            self.assertEqual(fields["llm_model_name"]["default"], "model-from-env")
            self.assertEqual(fields["llm_base_url"]["default"], "https://example.com/v1")
            self.assertEqual(fields["max_web_research_loops"]["default"], 0)
            self.assertIsInstance(fields["max_web_research_loops"]["default"], int)
            self.assertIs(fields["fetch_full_page"]["default"], False)
            self.assertEqual(fields["ddgs_backend"]["default"], "yahoo")

    def test_old_assistant_fields_are_safely_ignored(self):
        old = {"local_llm": "llama3.2", "llm_provider": "ollama", "ollama_base_url": "http://localhost:11434"}
        with patch.dict(os.environ, {}, clear=True):
            config = Configuration.from_runnable_config({"configurable": old})
        self.assertEqual(config.llm_model_name, "deepseek-chat")
        self.assertEqual(config.llm_base_url, "https://api.deepseek.com")

    def test_all_three_nodes_use_assistant_model_settings(self):
        settings = {"configurable": {
            "llm_model_name": "assistant-model",
            "llm_base_url": "https://example.com/v1",
        }}
        cases = [
            (app.generate_query, '{"query": "CPU"}', True),
            (app.summarize_sources, "CPU summary", False),
            (app.reflect_on_summary, '{"follow_up_query": "CPU pipeline"}', True),
        ]
        for node, reply, json_mode in cases:
            with self.subTest(node=node.__name__), patch.dict(
                os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=True
            ), patch.object(app, "ChatOpenAI") as model:
                model.return_value.invoke.return_value = AIMessage(content=reply)
                node(SummaryState(research_topic="CPU", web_research_results=["CPU source"]), settings)
                kwargs = model.call_args.kwargs
                self.assertEqual(kwargs["model"], "assistant-model")
                self.assertEqual(kwargs["base_url"], "https://example.com/v1")
                self.assertEqual(kwargs["api_key"], "test-key")
                self.assertEqual("model_kwargs" in kwargs, json_mode)

    def test_environment_overrides_assistant_model_settings(self):
        with patch.dict(os.environ, {"LLM_MODEL_NAME": "env-model"}, clear=True):
            config = Configuration.from_runnable_config({"configurable": {"llm_model_name": "assistant-model"}})
        self.assertEqual(config.llm_model_name, "env-model")

    def test_api_key_is_not_in_studio_schema(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "PRIVATE_TEST_KEY"}, clear=True):
            schema = TypeAdapter(Configuration).json_schema()
        self.assertNotIn("PRIVATE_TEST_KEY", json.dumps(schema))
        self.assertNotIn("api_key", schema["properties"])


if __name__ == "__main__":
    unittest.main()
