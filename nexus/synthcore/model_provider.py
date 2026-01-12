class NexusModelProvider:
    """
    Bridges Nexus to PyGPT's model selection system.
    All LLM calls route through PyGPT's configured models.
    """
    
    def __init__(self, pygpt_config):
        """Initialize with PyGPT settings"""
        self.config = pygpt_config
        # Assuming pygpt_config provides access to the model registry
        self.model_registry = pygpt_config.get_model_registry()
        
    def get_model_for_task(self, task_type: str):
        """
        task_type options:
        - 'primary_reasoning': Full response generation
        - 'fact_extraction': Semantic consolidation
        - 'identity_verification': Kernel consistency checks
        - 'mood_modulation': PAD state calculations
        - 'feedback_evaluation': Quality assessment
        - 'contradiction_detection': Multi-turn validation
        
        Returns: ConfiguredLLMClient for the task
        """
        config_key = f"nexus.model.{task_type}"
        model_name = self.config.get(config_key)
        
        # Fall back to PyGPT default if not configured
        if not model_name:
            model_name = self.config.get("model.default")
        
        return self.model_registry.get_client(model_name)
    
    def list_available_models(self):
        """Returns all models currently available in PyGPT"""
        return self.model_registry.list_models()
    
    def override_model_for_session(self, task_type: str, model_name: str):
        """Temporarily override model selection for a single session"""
        self.config.set_session(f"nexus.model.{task_type}", model_name)
