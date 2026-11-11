import json
import os
import time
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from backend.agent.agent import building_convo, reflection_symbl
from backend.simulation_state import MemoryEntry, Villager

class SocialSystem:
    """Manages background tasks for conversations, daily summaries, and JSON export."""
    def __init__(self, rng, buildings):
        self.rng = rng
        self.buildings = buildings

        # Thread pool to handle LLM API calls without freezing the main game loop.
        # Prevents program crashing capped at 5
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Tracks how many conversations are currently running in the background.
        self.active_conversations = 0

        # UI state tracking for export progress screen.
        self.export_data = None 
        self.export_progress = [] 
        self.is_exporting = False

    
    def check_triggers(self, villagers: list[Villager], day: int, is_night: bool):
        # Do not start new conversations if the user is currently exporting.
        if self.is_exporting:
            return

        # Limit to 2 simultaneous conversations at a time to avoid overwhelming the API.
        if self.active_conversations >= 2: 
            return 

        # Filter for AI villagers who are standing idle in a building
        idle = [v for v in villagers if not v.is_walking and v.location_id and not v.conversation_partner and not v.is_scripted]

        # Check every pair of idle villagers to see if they are in the same building.
        for i, a in enumerate(idle):
            for b in idle[i+1:]:
                if a.location_id == b.location_id:

                    # Prevent the same pair from talking repeatedly in one phase
                    phase_key = f"day{day}" if not is_night else f"night{day}"
                    if a.last_spoke_phase.get(b.agent_id) == phase_key: continue

                    #Lock the villagers into a conversation state so they can't start another one.
                    a.conversation_partner = b
                    b.conversation_partner = a
                    a.last_spoke_phase[b.agent_id] = phase_key
                    b.last_spoke_phase[a.agent_id] = phase_key
                    
                    self.active_conversations += 1

                    #Offload the actual LLM chat to the background thread pool
                    self.executor.submit(self.run_convo, a, b, day, is_night)
                    return 

    def run_convo(self, a: Villager, b: Villager, day: int, is_night: bool):
        # Runs a turn-by-turn conversation between two villagers in the background.
        try:
            loc_name = self.buildings[a.location_id].display_name if a.location_id else "Unknown"
            history = []

            # Randomize who starts the conversation.
            speaker, listener = (a, b) if self.rng.random() > 0.5 else (b, a)
            phase_str = "Night" if is_night else "Day"

            # Max 6 turns (3 per person) to prevent infinite loops and save API costs
            for _ in range(6): 
                prompt = building_convo(speaker, listener, history, day, phase_str, loc_name)
                try:
                    raw = speaker.agent._call_llm([{"role": "user", "content": prompt}])

                    #Cleans up Markdown formatting
                    if "'''json" in raw: 
                        raw = raw.split("'''json")[1].split("'''")[0].strip()
                    
                    data = json.loads(raw)
                    line = data.get("line", "...")
                    history.append({"name": speaker.name, "line": line})

                    # If the LLM decieds to leave, break the loop
                    if data.get("walk_away", False):
                        break

                except Exception:
                    # If the LLM fails to respond, log silence and end the chat.
                    history.append({"name": speaker.name, "line": "(remained silent)"})
                    break

                #Swap speaker and listener for the next turn
                speaker, listener = listener, speaker

            # Combine the full transcript into a single memory string
            convo_text = " | ".join([f"{h['name']}: {h['line']}" for h in history]) if history else "..."

            #Write to both Villagers' episodic memory banks
            a.recent_encounters.append(MemoryEntry(day, phase_str, loc_name, [b.agent_id], f"Conversation with {b.name}: '{convo_text}'"))
            b.recent_encounters.append(MemoryEntry(day, phase_str, loc_name, [a.agent_id], f"Conversation with {a.name}: '{convo_text}'"))

        except Exception as e:
            print(f"[SocialSystem] Conversation error: {e}")
        finally:
            a.conversation_partner = None
            b.conversation_partner = None
            self.active_conversations -= 1

    def export_now(self, villagers: list[Villager], day: int):
        # Triggers the final export process. Runs in the background so the UI doesn't freeze.
        if self.is_exporting: return
        self.is_exporting = True
        self.export_progress = [("Waiting for conversations to finish...", "...")]
        
        def _export_task():
            try:
                # Giving some time for the simulation to wrap up last minute conversations
                time.sleep(5)
                start_drain = time.time()
                while self.active_conversations > 0 and time.time() - start_drain < 10:
                    time.sleep(0.1)
                
                self.export_progress = []
                results = {}

                # Reflection Phase: Generate the emotional exit interview for every API agent
                for v in villagers:
                    if v.agent is None:
                        continue


                    # Update the UI progress list
                    self.export_progress.append((v.name, "..."))
                    
                    prompt = reflection_symbl(v)
                    try:
                        raw = v.agent._call_llm([{"role": "user", "content": prompt}])
                        if "'''json" in raw: raw = raw.split("'''json")[1].split("'''")[0].strip()
                        results[v.agent_id] = json.loads(raw)
                        self.export_progress[-1] = (v.name, "OK")
                    except Exception as e:
                        print(f"[Export] LLM failed for {v.name}: {e}")

                        # Use a fall back reflection if the LLM fails.
                        results[v.agent_id] = {"reflection": "I survived the simulation.", "lessons": []}
                        self.export_progress[-1] = (v.name, "!!")


                #JSON Assembly phase
                self.export_progress.append(("Writing file...", "..."))
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                os.makedirs("exports", exist_ok=True)
                filepath = f"exports/simulation_{timestamp}.json"
                
                villagers_data = []
                for v in villagers:
                    if v.agent is None:
                        continue  # Skip scripted NPCs

                    villagers_data.append({
                        "id": v.agent_id, "name": v.name, "role": v.agent.profile.role,
                        "reflection": results.get(v.agent_id, {}).get("reflection", ""),
                        "lessons": results.get(v.agent_id, {}).get("lessons", []),
                        "daily_summaries": v.daily_summaries,
                        "task_history": v.task_history,
                        "encounters": [{"day": m.day, "location": m.location, "summary": m.summary} for m in v.recent_encounters]
                    })
                    
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump({"meta": {"timestamp": timestamp, "day": day}, "villagers": villagers_data}, f, indent=4)

                # Signal file is ready
                self.export_data = filepath
                
            except Exception as e:
                traceback.print_exc()
                #Signal failure so the UI doesn't freeze on the loading screen.
                self.export_data = f"ERROR: {e}"
                
        self.executor.submit(_export_task)


    def generate_daily_summaries(self, villagers: list[Villager], day: int):
        # Triggers the nightly memory summary generation for all AI villagers. 

        def _summary_task(v):
            # Wait for active conversations to end so the summary includes all memories.
            start_wait = time.time()
            while self.active_conversations > 0 and time.time() - start_wait < 5:
                time.sleep(0.1)

            try:
                # local import
                from backend.agent.agent import daily_summaries
                prompt = daily_summaries(v, day)
                if not prompt:
                    return # Skip if they did nothing today.
                
                raw = v.agent._call_llm([{"role": "user", "content": prompt}])
                if "'''json" in raw: raw = raw.split("'''json")[1].split("'''")[0].strip()
                data = json.loads(raw)
                summary = data.get("summary", "")
                if summary:
                    v.daily_summaries.append(f"Day {day}: {summary}")
            except Exception as e:
                print(f"[Summary] Failed for {v.name}: {e}")

        # Loop through every AI agent and submit their summary generation to the background
        for v in villagers:
            if v.agent is not None:
                self.executor.submit(_summary_task, v)