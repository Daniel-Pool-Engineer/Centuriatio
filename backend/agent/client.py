from typing import Dict, List

from agno.agent import Agent

from backend.agent.llm import make_llm


class LLMClient:
    # Wrapper for making text-based requests to the LLM 

    def __init__(self) -> None:
        #Initialize the Agno Agent instance using the configured model.
        self._agent = Agent(
            model=make_llm(),
            markdown=False,
            telemetry=False,
        )

    def chat(self, messages: List[Dict[str, str]]) -> str:
        # Parse the incoming message list to separate the system instructions from the user prompt.
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = next((m["content"] for m in messages if m["role"] == "user"), "")

        # Combine the system and user prompts into a single string.
        response = self._agent.run(
            input=f"{system}\n\n{user}",
            stream=False,
        )

        # Return the raw text content output from the model.
        return response.content
