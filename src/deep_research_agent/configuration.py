import os
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional, Literal

from langchain_core.runnables import RunnableConfig

class SearchAPI(Enum):
    PERPLEXITY = "perplexity"
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    SEARXNG = "searxng"


def _schema_defaults_from_environment(schema: dict[str, Any], model: "type[Configuration]") -> None:
    # Studio and the runtime use the same environment overrides and type conversion.
    defaults = model.from_runnable_config().model_dump(mode="json")
    for name, value in defaults.items():
        schema["properties"][name]["default"] = value


class Configuration(BaseModel):
    """Research settings. Environment variables take precedence over assistant settings."""

    model_config = ConfigDict(json_schema_extra=_schema_defaults_from_environment)

    max_web_research_loops: int = Field(
        default=3,
        title="Additional Search Rounds",
        description="Search rounds after the first one in a new thread. 0 means one search. MAX_WEB_RESEARCH_LOOPS overrides this setting."
    )
    llm_model_name: str = Field(
        default="deepseek-chat",
        min_length=1,
        title="DeepSeek Model",
        description="DeepSeek model used by all three model nodes. LLM_MODEL_NAME overrides this setting."
    )
    llm_base_url: str = Field(
        default="https://api.deepseek.com",
        min_length=1,
        title="DeepSeek API Base URL",
        description="DeepSeek API endpoint. The key is read from DEEPSEEK_API_KEY. LLM_BASE_URL overrides this setting."
    )
    search_api: Literal["perplexity", "tavily", "duckduckgo", "searxng"] = Field(
        default="duckduckgo",
        title="Search API",
        description="Web search integration. Select duckduckgo to use DDGS Backend. SEARCH_API overrides this setting."
    )
    ddgs_backend: str = Field(
        default="auto",
        title="DDGS Backend",
        description="Search engine used by DDGS, such as auto, yahoo, or wikipedia. DDGS_BACKEND overrides this setting."
    )
    fetch_full_page: bool = Field(
        default=True,
        title="Fetch Full Page",
        description="Fetch webpage content in addition to search snippets. FETCH_FULL_PAGE overrides this setting."
    )
    strip_thinking_tokens: bool = Field(
        default=True,
        title="Strip Thinking Tokens",
        description="Whether to strip <think> tokens from model responses"
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )
        
        # Get raw values from environment or config
        raw_values: dict[str, Any] = {
            name: os.environ.get(name.upper(), configurable.get(name))
            for name in cls.model_fields.keys()
        }
        
        # Filter out None values
        values = {k: v for k, v in raw_values.items() if v is not None}
        
        return cls(**values)
