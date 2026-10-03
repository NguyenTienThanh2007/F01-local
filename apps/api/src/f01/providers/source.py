"""Provider-independent contract, intentionally not connected to a public run endpoint."""
from typing import Protocol

from f01.domain.source import GenerationContext, GenerationResult


class SourceGenerationProvider(Protocol):
    async def propose_source(self, context: GenerationContext, maximum_output_tokens: int) -> GenerationResult: ...
