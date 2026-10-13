"""Optional Mem0 adapters that honor explicit endpoints and keys, including no key.

Mem0's default OpenAI adapters consult unrelated cloud-key environment variables
and treat an empty local key as missing. These adapters retain SDK inference and
embedding behavior while constructing the OpenAI clients from validated app
configuration only. This module is imported only when semantic memory is enabled.
"""

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.embeddings.base import EmbeddingBase
from mem0.embeddings.openai import OpenAIEmbedding
from mem0.llms.base import LLMBase
from mem0.llms.openai import OpenAILLM
from mem0.utils.factory import EmbedderFactory, LlmFactory
from openai import OpenAI


class ConfiguredOpenAILLM(OpenAILLM):
    """Use Mem0's real LLM behavior without environment-driven credential routing."""

    def __init__(self, config: OpenAIConfig) -> None:
        LLMBase.__init__(self, config)
        self.client = OpenAI(api_key=config.api_key, base_url=config.openai_base_url, http_client=config.http_client)


class ConfiguredOpenAIEmbedding(OpenAIEmbedding):
    """Use the configured embedding service, independently of the causal model."""

    def __init__(self, config: BaseEmbedderConfig) -> None:
        EmbeddingBase.__init__(self, config)
        self._pass_dimensions_to_api = config.embedding_dims is not None
        self.config.embedding_dims = config.embedding_dims or 1536
        self.client = OpenAI(api_key=config.api_key, base_url=config.openai_base_url, http_client=config.http_client)


def register_openai_providers() -> None:
    """Install explicit-key implementations in the SDK's application-local factories."""
    LlmFactory.register_provider("openai", "taskweaver.database.mem0_openai.ConfiguredOpenAILLM", OpenAIConfig)
    EmbedderFactory.provider_to_class["openai"] = "taskweaver.database.mem0_openai.ConfiguredOpenAIEmbedding"
