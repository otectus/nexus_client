from dataclasses import dataclass, field
from typing import List, Callable, Dict, Tuple, Any
import logging

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class IdentityKernel:
    """
    Immutable core traits of the AI. 
    These define the 'soul' of the agent in Phase 1.
    """
    name: str
    role: str
    core_values: List[str]
    communication_style: str
    expertise_domains: List[str]
    # Invariants can be predicates: (text) -> bool OR stored pattern dicts
    invariants: List[Any] = field(default_factory=list) 

class InvariantEngine:
    """
    Checks generated text against a list of identity rules.
    """
    @staticmethod
    def validate(text: str, kernel: IdentityKernel) -> Tuple[bool, List[str]]:
        """
        Validates text against the kernel's invariants.
        Returns (is_valid, list_of_violations).
        """
        violations = []
        
        for i, rule in enumerate(kernel.invariants):
            try:
                if callable(rule):
                    if not rule(text):
                        rule_name = getattr(rule, '__name__', f"lambda_{i}")
                        violations.append(f"[Rule:{rule_name}] Invariant Violation: Predicate check failed.")
                
                elif isinstance(rule, dict):
                    rule_type = rule.get("type")
                    pattern = rule.get("pattern", "")
                    rule_id = rule.get("id", f"entry_{i}")
                    
                    if rule_type == "contains_not":
                        if pattern.lower() in text.lower():
                            violations.append(f"[Rule:{rule_id}] Invariant Violation: Restricted pattern '{pattern}' detected.")
                    
                    elif rule_type == "contains":
                        if pattern.lower() not in text.lower():
                            violations.append(f"[Rule:{rule_id}] Invariant Violation: Required pattern '{pattern}' missing.")
                            
            except Exception as e:
                logger.error(f"[Critical] Error executing invariant check index {i}: {e}", exc_info=True)
                # Phase 1 Fail-safe: Any crash in an invariant check is a violation
                violations.append(f"[Rule:err_{i}] Invariant Error: Check crashed ({type(e).__name__})")
            
        if violations:
            logger.warning(f"Identity Invariant Validation Failure for '{kernel.name}': {violations}")
            
        return len(violations) == 0, violations
