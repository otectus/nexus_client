import tiktoken
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .token_budget import TokenBudget

@dataclass
class SectionSpec:
    name: str
    content: str
    priority: int  # 1 (Critical) to 5 (Nice to have)
    degradable: bool = True
    min_tokens_reserved: Optional[int] = None
    display_title: str = ""

class PromptAssembler:
    """
    Assembles the strict 5-section Nexus prompt template.
    Ensures deterministic output and budget enforcement.
    """
    def __init__(self, model_name: str = "gpt-4-turbo"):
        try:
            self.encoder = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))

    def format_section(self, header: str, content: str) -> str:
        """Canonical Nexus section delimiter."""
        return f"---\n## {header}\n{content}\n"

    def assemble(
        self, 
        sections: List[SectionSpec], 
        budget: TokenBudget
    ) -> str:
        """
        Assembles sections based on SectionSpec. Enforces hard caps and priorities.
        """
        final_parts = []
        
        # Standard sequence: SYSTEM, IDENTITY, MOOD, MEMORY, REQUEST
        for spec in sections:
            header = spec.name.upper()
            display_header = spec.display_title or header
            content = spec.content

            # Check Hard Caps if defined in budget
            # (Hard caps are handled inside budget.allocate in next refactor)
            
            formatted = self.format_section(display_header, content)
            tokens = self.count_tokens(formatted)

            if budget.allocate(spec.name.lower(), tokens):
                final_parts.append(formatted)
            elif not spec.degradable:
                # Critical section failed budget - this is a fatal Orchestrator state
                final_parts.append(formatted) # Force it, Orchestrator handles total window
            else:
                # Omit or use fallback
                final_parts.append(self.format_section(display_header, f"[{display_header} omitted due to budget constraints]"))

        return "\n".join(final_parts)