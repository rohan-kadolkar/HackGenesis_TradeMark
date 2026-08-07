from backend.agents.image_agent import ImageAnalysisAgent
from backend.agents.retriever_agent import RetrieverAgent
from backend.agents.reasoning_agent import ReasoningAgent
from backend.agents.formatter_agent import FormatterAgent

class AgenticRAGPipeline:
    """
    Coordinates the 4-Agent Pipeline:
    Agent 1 (Image Analysis) -> Agent 2 (Retriever) -> Agent 3 (Reasoning) -> Agent 4 (Formatter)
    """
    def __init__(self, reranker):
        self.image_agent = ImageAnalysisAgent()
        self.retriever_agent = RetrieverAgent(reranker)
        self.reasoning_agent = ReasoningAgent()
        self.formatter_agent = FormatterAgent()

    def run(self, gemma_output, raw_form_data=None):
        # Step 1: Agent 1 - Image Analysis Agent
        incident_obj = self.image_agent.execute(gemma_output, raw_form_data)

        # Step 2: Agent 2 - Retriever Agent
        retrieved_context = self.retriever_agent.execute(
            animal_type=incident_obj["animal_type"],
            symptoms=incident_obj["symptoms_observed"],
            severity=incident_obj["severity"],
            top_k=4
        )

        # Step 3: Agent 3 - Reasoning Agent (Strict Non-Hallucination)
        reasoning_text = self.reasoning_agent.execute(
            incident_obj=incident_obj,
            retrieved_context=retrieved_context
        )

        # Step 4: Agent 4 - Formatter Agent (Structured JSON)
        formatted_response = self.formatter_agent.execute(
            incident_obj=incident_obj,
            retrieved_context=retrieved_context,
            reasoning_text=reasoning_text
        )

        return formatted_response
