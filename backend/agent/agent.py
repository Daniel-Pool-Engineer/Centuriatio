from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import json
import logging

from backend.map.graph import VillageMap

logger = logging.getLogger(__name__)


# Creating an agent; role is a new profile.
@dataclass(frozen=True)
class RoleProfile:
    role: str
    permitted_actions: Set[str]
    identity_line: str
    role_guidance: str
    workplace: str = "office"
    speed: float = 1.0
    fallback_action: str = "wait"
    fallback_journal: str = "{name} stayed put; no valid action was chosen."


@dataclass
class ActionRequest:
    action: str
    target_location: Optional[str] = None
    journal: str = ""


# Snapshot of the village state.
@dataclass
class VillagerContext:
    villager_id: str
    name: str
    location_id: str
    day: int
    phase: str  # "day" | "night"
    crisis_active: bool
    crisis_day: int  # 0 if no crisis
    crisis_duration: int
    crisis_area: Optional[str]
    power_on: bool
    previous_action: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    parts_arrived: Optional[bool] = None


# Reusable agent; role behavior comes from profile + context.
class VillagerAgent:
    def __init__(
        self,
        villager_id: str,
        name: str,
        profile: RoleProfile,
        llm_client: Optional[Any] = None,
    ) -> None:
        self.villager_id = villager_id
        self.name = name
        self.profile = profile
        self.llm_client = llm_client

    @property
    def role(self) -> str:
        return self.profile.role

    @property
    def speed(self) -> float:
        return self.profile.speed

    def decide(self, ctx: VillagerContext) -> ActionRequest:
        prompt = self.build_prompt(ctx)
        try:
            raw = self._call_llm(prompt)
            action = self._parse(raw)
        except Exception as exc:
            logger.warning("Agent %s LLM failure: %s", self.villager_id, exc)
            return self.fallback(ctx)

        if action.action not in self.profile.permitted_actions:
            logger.info(
                "Agent %s requested disallowed action %r",
                self.villager_id, action.action,
            )
            return self.fallback(ctx)

        return action
    
    @classmethod
    def decide_batch(
        cls, 
        requests: list[tuple[str, "VillagerAgent", VillagerContext]], 
        llm_client: Optional[Any] = None
    ) -> dict[str, ActionRequest]:
        
        """Process multiple villager decisions in a single LLM call."""
        if not requests:
            return {}
        if llm_client is None:
            return {v_id: agent.fallback(ctx) for v_id, agent, ctx in requests}

        # 1. Batch system prompt
        system = (
            "You are the decision engine for multiple villagers in a village simulation.\n"
            "You must reply with a single JSON array of objects, one for each villager in the exact order they are presented.\n"
            "Schema for each object:\n"
            '{"action": "<action>", "target_location": "<location id or null>", "journal": "<one short sentence>"}\n'
            "Do not explain. Do not add fields."
        )

        # 2. Combined user prompt
        user_lines = []
        for i, (v_id, agent, ctx) in enumerate(requests):
            crisis_line = (
                f"Crisis: power outage, day {ctx.crisis_day} of {ctx.crisis_duration}, affected area: {ctx.crisis_area}."
                if ctx.crisis_active else "Crisis: none."
            )

            # Status of replacement parts
            string_addition = ""

            if agent.role == "electrician" and ctx.parts_arrived is not None:
                if ctx.parts_arrived:
                    string_addition = "Replacement part arrived, go to the electrical plant and restore power.\n"
                else:
                    string_addition = "Waiting for a replacement part.\n"
            
            user_lines.append(
                f"--- VILLAGER {i} (ID: {v_id}) ---\n"
                f"Name: {agent.name}\n"
                f"Role: {agent.role}\n"
                f"Role guidance: {agent.profile.role_guidance}\n"
                f"Location: {ctx.location_id}\n"
                f"Time: Day {ctx.day}, {ctx.phase}\n"
                f"{crisis_line}\n"
                f"Power: {'on' if ctx.power_on else 'off'}\n"
                f"{string_addition}"
                f"Previous action: {ctx.previous_action or 'none'}\n"
                f"Permitted actions: {sorted(agent.profile.permitted_actions)}\n"
                f"Valid locations: {sorted(VillageMap.locations)}\n"
            )
        user = "\n".join(user_lines) + "\nChoose the next action for each villager in the array."

        try:
            raw = llm_client.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
            
            # Clean potential markdown formatting from LLM
            raw = raw.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
            
            data = json.loads(raw)

            if not isinstance(data, list):
                raise ValueError("Expected a JSON array from batch LLM response")
            if len(data) != len(requests):
                raise ValueError(f"Expected {len(requests)} actions, got {len(data)}")

            results = {}
            for i, (v_id, agent, ctx) in enumerate(requests):
                item = data[i]
                action_str = str(item.get("action", "")).strip()
                
                if action_str not in agent.profile.permitted_actions:
                    results[v_id] = agent.fallback(ctx)
                else:
                    results[v_id] = ActionRequest(
                        action=action_str,
                        target_location=item.get("target_location") or None,
                        journal=str(item.get("journal", "")).strip()
                    )
            return results

        except Exception as exc:
            logger.warning("Batch LLM failure: %s", exc)
            # Fallback everyone if the API fails or parses incorrectly
            return {v_id: agent.fallback(ctx) for v_id, agent, ctx in requests}


    def fallback(self, ctx: VillagerContext) -> ActionRequest:
        return ActionRequest(
            action=self.profile.fallback_action,
            target_location=ctx.location_id,
            journal=self.profile.fallback_journal.format(name=self.name),
        )

    def build_prompt(self, ctx: VillagerContext) -> List[Dict[str, str]]:
        system = (
            f"{self.profile.identity_line}\n"
            f"Role: {self.profile.role}.\n"
            f"{self.profile.role_guidance}\n"
            "You must reply with a single JSON object and nothing else, "
            "matching this schema:\n"
            '{"action": "<one of the permitted actions>", '
            '"target_location": "<location id or null>", '
            '"journal": "<one short sentence>"}\n'
            "Do not explain. Do not add fields."
        )

        crisis_line = (
            f"Crisis: power outage, day {ctx.crisis_day} of {ctx.crisis_duration}, "
            f"affected area: {ctx.crisis_area}."
            if ctx.crisis_active
            else "Crisis: none."
        )

        string_addition = ""

        if self.role == "electrician" and ctx.parts_arrived is not None:
            if ctx.parts_arrived:
                string_addition = "Replacement part arrived, go to the electrical plant and restore power.\n"
            else:
                string_addition = "Waiting for a replacement part.\n"

        user = (
            f"Villager: {self.name} (id={self.villager_id})\n"
            f"Role: {self.profile.role}\n"
            f"Workplace: {self.profile.workplace}\n"
            f"Location: {ctx.location_id}\n"
            f"Time: Day {ctx.day}, {ctx.phase}\n"
            f"{crisis_line}\n"
            f"Power: {'on' if ctx.power_on else 'off'}\n"
            f"{string_addition}"
            f"Previous action: {ctx.previous_action or 'none'}\n"
            f"Permitted actions: {sorted(self.profile.permitted_actions)}\n"
            f"Valid locations: {sorted(VillageMap.locations)}\n"
            "If the action involves going somewhere, set target_location"
            " to one of the valid locations. Otherwise use null.\n"
            "Choose the next action."
        )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        if self.llm_client is None:
            raise RuntimeError("No LLM client configured")
        return self.llm_client.chat(messages)

    @staticmethod
    def _parse(raw: str) -> ActionRequest:
        data = json.loads(raw)
        if "action" not in data:
            raise ValueError(f"Missing 'action' in agent output: {data!r}")
        return ActionRequest(
            action=str(data["action"]).strip(),
            target_location=data.get("target_location") or None,
            journal=str(data.get("journal", "")).strip(),
        )

def building_convo(speaker, listener, history: list[dict], day: int, phase: str, location: str) -> str:
    history_text = "\n".join([f"{h["name"]}: {h["line"]}" for h in history])
    
    if not history_text:
        "(You are initiating the conversation)"

    return f"""You are {speaker.name} ({speaker.agent.profile.role}).
    You are at {location}. It is Day {day}, {phase}.
    You are talking to {listener.name} ({listener.agent.profile.role if listener.agent else 'NPC'}).

    Dialogue so far:
    {history_text}

    Write your next spoken line. Keep it to 1-2 short sentences. Spoken words only, no stage directions. 
    If you want to end the conversation and wlak away, set "walk_away" to true.
    Otherwise, output JSON: {"line": "Your spoken words", "walk_away": false}"""

def building_reflection_prompt(villager) -> str:
    if not villager.recent_encounters:
        return f"""You are {villager.name} ({villager.agent.profile.role}). 
        You just finished a simulation. You spent the entire time alone.
        Write exactly 2 sentences:
        1. How the silence felt.
        2. What you noticed about yourself without others around.
        Do not write a report. Do not use the word "journey".
        Output JSON: {"reflection": "...", "lessons": ["..."]}"""

    memories = "\n".join([f"- Day {m.day}, {m.phase} at {m.location}: {m.summary}" for m in villager.recent_encounters])

    return f""" You are {villager.name} ({villager.agent.profile.role}). You just finished a simulation. Here is what actually happened to you:
    {memories}

    Write exactly 2 sentences:
    1. What you felt at most memorable moment. Name a specific person and place. 
    2. One thing you now understand about yourself or the village. 
    Then, provide 1-2 actionable "lessons" for next time (e.g., "Next time, I will go to the school earlier").
    Do not write a report. Do not use the word "journey".
    Output JSON: {"reflection": "...", "lessons": ["...", "..."]}
    """
