from dataclasses import dataclass, field, asdict
from typing import List, Callable, Dict, Tuple, Any
import logging

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class IdentityKernel:
    """
    Immutable core traits of the AI. 
    These define the 'soul' of the agent.
    """
    name: str
    role: str
    core_values: List[str]
    communication_style: str
    expertise_domains: List[str]
    invariants: List[Any] = field(default_factory=list) 

    def to_dict(self) -> dict:
        """Serialize kernel for persistence"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'IdentityKernel':
        """Restore kernel from dict"""
        return cls(**data)

    def to_str(self) -> str:
        return (f"Name: {self.name}\n"
                f"Role: {self.role}\n"
                f"Values: {', '.join(self.core_values)}\n"
                f"Style: {self.communication_style}\n"
                f"Domains: {', '.join(self.expertise_domains)}")

class InvariantEngine:
    """
    Checks generated text against a list of identity rules.
    """
    @staticmethod
    def validate(text: str, kernel: IdentityKernel) -> Tuple[bool, List[str]]:
        violations = []
        for i, rule in enumerate(kernel.invariants):
            if isinstance(rule, dict):
                rule_type = rule.get("type")
                pattern = rule.get("pattern", "")
                if rule_type == "contains_not" and pattern.lower() in text.lower():
                    violations.append(f"Restricted pattern '{pattern}' detected.")
                elif rule_type == "contains" and pattern.lower() not in text.lower():
                    violations.append(f"Required pattern '{pattern}' missing.")
        return len(violations) == 0, violations
