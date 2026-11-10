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
    recent_encounters: List[Any] = field(default_factory=list)
    daily_summaries: List[str] = field(default_factory = list)


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
        
        return action


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
            '{"action": "<a short snake_case action>", '
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

        memory_text = ""
        if ctx.daily_summaries:
            memory_text += "Past days summary: \n" + "\n".join([f"-{s}" for s in ctx.daily_summaries]) + "\n"

        if ctx.recent_encounters:
            memory_text += "Recent conversations: \n" + "\n".join([f"- {m.summary}" for m in ctx.recent_encounters]) + "\n"

        if memory_text:
            memory_text += "\n"

        user = (
            f"Villager: {self.name} (id={self.villager_id})\n"
            f"Role: {self.profile.role}\n"
            f"Workplace: {self.profile.workplace}\n"
            f"Location: {ctx.location_id}\n"
            f"{memory_text}"
            f"Time: Day {ctx.day}, {ctx.phase}\n"
            f"{crisis_line}\n"
            f"Power: {'on' if ctx.power_on else 'off'}\n"
            f"{string_addition}"
            f"Previous action: {ctx.previous_action or 'none'}\n"
            f"Suggested actions (you may invent others if appropriate): {sorted(self.profile.permitted_actions)}\n"
            f"Valid locations: {sorted(VillageMap.locations)}\n"
            "If the action involves going somewhere, set target_location"
            " to one of the valid locations. Otherwise use null.\n"
            "If you are traveling to another building, explain WHY in your journal (e.g., 'Going to the electrical plant to ask when power will be restored.').\n"
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

# Prompt for building a conversation
def building_convo(speaker, listener, history: list[dict], day: int, phase: str, location: str) -> str:
    history_text = "\n".join([f"{h['name']}: {h['line']}" for h in history])
    
    if not history_text:
        history_text = "(You are initiating the conversation)"

    return f"""You are {speaker.name} ({speaker.agent.profile.role}).
    You are at {location}. It is Day {day}, {phase}.
    You are talking to {listener.name} ({listener.agent.profile.role if listener.agent else 'NPC'}).

    Dialogue so far:
    {history_text}

    Write your next spoken line. Keep it to 1-2 short sentences. Spoken words only, no stage directions. 
    If you want to end the conversation and walk away, set "walk_away" to true.
    Otherwise, output JSON: {{"line": "Your spoken words", "walk_away": false}}"""

# Prompt for reflection at the end of simulation
def reflection_symbl(villager) -> str:
    if not villager.recent_encounters:
        return f"""You are {villager.name} ({villager.agent.profile.role}). 
        You just finished a simulation. You spent the entire time alone.
        Write exactly 2 sentences:
        1. How the silence felt.
        2. What you noticed about yourself without others around.
        Do not write a report. Do not use the word "journey".
        Output JSON: {{"reflection": "...", "lessons": ["..."]}}"""

    memories = "\n".join([f"- Day {m.day}, {m.phase} at {m.location}: {m.summary}" for m in villager.recent_encounters])

    return f""" You are {villager.name} ({villager.agent.profile.role}). You just finished a simulation. Here is what actually happened to you:
    {memories}

    Write exactly 2 sentences:
    1. What you felt at most memorable moment. Name a specific person and place. 
    2. One thing you now understand about yourself or the village. 
    Then, provide 1-2 actionable "lessons" for next time (e.g., "Next time, I will go to the school earlier").
    Do not write a report. Do not use the word "journey".
    Output JSON: {{"reflection": "...", "lessons": ["...", "..."]}}
    """

# Prompt for daily summary, sent after 1 day
def daily_summaries(villager, day: int) -> str:
    todays_encounters = [m.summary for m in villager.recent_encounters if m.day == day]

    todays_tasks = [t for t in villager.task_history if t.startswith(f"Day {day}:")]

    if not todays_encounters and not todays_tasks:
        return ""

    memories = "\n".join([f"- {m}" for m in todays_encounters + todays_tasks])

    return f"""You are {villager.name} ({villager.agent.profile.role}).
    Today is Day {day}.
    {memories}

    Write exactly 3 sentences summarizing your day. Keep it in first-person (e.g., "I helped Felix with his lights and then went to sleep.").

    Output JSON: {{"summary": "your 3 sentence here"}}"""

