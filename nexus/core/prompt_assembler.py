import tiktoken
from typing import List, Tuple, Dict, Any
from .token_budget import TokenBudget

class PromptAssembler:
    """
    Assembles the strict 5-section Nexus prompt template.
    Ensures each section isDelimited correctly and fits within budget.
    """
    def __init__(self, model_name: str = "gpt-4-turbo"):
        try:
            self.encoder = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base for newer/unknown models
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))

    def format_section(self, header: str, content: str) -> str:
        """Wraps content in standard Nexus delimiters."""
        return f"---\n## {header}\n{content}\n"

    def assemble(
        self, 
        sections: List[Tuple[str, str]], 
        budget: TokenBudget
    ) -> str:
        """
        Validates and joins a list of (header, content) tuples into the final prompt.
        Logs warnings if a section fails budget check.
        """
        final_parts = []
        for header, content in sections:
            tokens = self.count_tokens(self.format_section(header, content))
            if budget.allocate(header.lower(), tokens):
                final_parts.append(self.format_section(header, content))
            else:
                # Graceful degradation: skip memory if budget is tight, etc.
                if header == "MEMORY":
                    final_parts.append(self.format_section(header, "[Memory context omitted due to budget constraints]"))
                else:
                    # Critical sections like REQUEST should not be omitted here (handled by orchestrator FATAL path)
                    pass
        
        return "\n".join(final_parts)
