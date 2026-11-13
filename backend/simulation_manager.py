"""villagers movement, AI coordination, and fire truck dispatch"""

from __future__ import annotations

import math
import random
import nltk
from nltk.stem import WordNetLemmatizer

from typing import Any
from frontend.village.map import Building, VillageMap
from backend.agent.agent import VillagerAgent, VillagerContext
from backend.map.pathfinding import SidewalkNetwork, centerline_point
from backend.simulation_state import Villager, FireTruck
from backend.agent.config import STARTING_VILLAGERS, SCRIPTED_NPCS
from backend.map.vehicle_navigation import VehicleNetwork
from backend.social_system import SocialSystem

# Download wordnet for lemmatization
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')

Vec = tuple[float,float]

class VillagerManager:
    """moves and draws every villager"""

    walk_speed = 140.0  # world units per second

    def __init__(self, village_map: VillageMap, rng: random.Random | None = None, llm_client: Any = None) -> None:
        self.network = SidewalkNetwork(village_map) #sidewalk graph for walking routes
        self.vehicle_network = VehicleNetwork(village_map) # road graph for fire truck

        self.buildings = {b.id: b for b in village_map.buildings}
        self.rng = rng or random.Random()
        self.social = SocialSystem(self.rng, self.buildings)
        self.llm_client = llm_client
        self.power_outage = False #while True, routine sleeping/waking is suppressed
        self.is_night = False

        # Recovery phase
        self.restore_requested = False
      
        # Initialize Fire Truck at the fire station
        fire_entrance = self.buildings["fire"].entrance
        start_road = self.vehicle_network._nearest_road_point(fire_entrance)
        self.fire_truck = FireTruck(position=start_road)

        #Spawn the AI-driven villagers
        self.villagers = [
            self._spawn(v_id, name, home_id, color, profile)
            for v_id, name, home_id, color, profile in STARTING_VILLAGERS
        ]

        #Spawn the scripted NPCs (no LLM)
        for v_id, name, home_id, color in SCRIPTED_NPCS:
            npc = self._spawn(v_id, name, home_id, color, None)
            npc.is_scripted = True
            npc.wait_time = self.rng.uniform(1.0, 5.0)

            #If it's fireman, it will follow Ben
            if "crew" in v_id:
                npc.following_target="v_ben"

            self.villagers.append(npc)


    def _curb_point(self, building: Building) -> Vec:
        """Point on the sidewalk centerline directly in front of a building entrance."""
        sidewalk = self.network.by_id[building.sidewalk_id]
        return centerline_point(sidewalk, building.entrance)

    
    def _spawn(self, agent_id: str, name: str, home_id: str, color: tuple[int,int, int], profile) -> Villager:
        # Build a villager positioned at its home entrance
        home = self.buildings[home_id]
        agent = VillagerAgent(agent_id, name, profile, llm_client=self.llm_client) if profile is not None else None

        return Villager(
            agent_id=agent_id,
            name=name,
            home_id=home_id,
            color=color,
            position=(float(home.entrance[0]), float(home.entrance[1])),
            sidewalk_id=home.sidewalk_id,
            location_id=home_id,
            agent=agent,
            wait_time=self.rng.uniform(0.5, 4.0),
            offset=(self.rng.uniform(-10, 10), self.rng.uniform(-10, 10)),
        )

    
    def get_villager(self, agent_id: str) -> Villager | None:
        # Loop up a villager object by their string Id.
        for v in self.villagers:
            if v.agent_id == agent_id:
                return v
        return None


    def dispatch_truck(self, driver: Villager, target_id: str) -> None:
        # Loads the driver (+ crew ) and set a road route.
        building = self.buildings[target_id]

        # Calculate a road route from the truck's current position
        road_points = self.vehicle_network.route(self.fire_truck.position, building.entrance,)
        self.fire_truck.is_active = True
        self.fire_truck.waypoints = road_points
        self.fire_truck.destination_building_id = target_id

        # Driver boards the truck
        self.fire_truck.passengers = [driver]
        driver.in_truck = True
        driver.location_id = target_id
        driver.destination_id = target_id
        driver.waypoints.clear()
        driver.position = self.fire_truck.position

        # Anyone following the driver boards too
        for v in self.villagers:
            if v.following_target == driver.agent_id:
                v.in_truck = True
                v.location_id = target_id
                v.destination_id = target_id
                v.waypoints.clear()
                v.position = self.fire_truck.position
                self.fire_truck.passengers.append(v)


    def set_night(self, is_night: bool) -> None:
        # Night: villagers go home, morning: they start wandering again
        self.is_night = is_night
        if self.power_outage:
            return  # During an outage, they stay where they are
        if is_night:
            self._send_everyone_home()
        else:
            self._wake_up()


    def _send_everyone_home(self) -> None:
        # Force all villagers to walk to their home building.
        for villager in self.villagers:
            at_home = villager.location_id == villager.home_id and not villager.is_walking
            if not at_home:
                self.send_to(villager, villager.home_id)


    def _wake_up(self) -> None:
        # leave in a few seconds so they don't all walk out at once
        for villager in self.villagers:
            villager.wait_time = self.rng.uniform(0.0, 3.0)


    def send_to(self, villager: Villager, building_id: str) -> None:
        # Assigns a new walking route. Clears 'location_id' until arrival
        building = self.buildings[building_id]
        villager.waypoints = self.network.route(villager.position, villager.sidewalk_id, building)
        villager.destination_id = building_id
        villager.location_id = None


    def _walk(self, villager: Villager, dt: float) -> bool:
        # move along the waypoints, returns True when the trip is finished
        distance = self.walk_speed * dt
        while villager.waypoints and distance > 0:
            (target_x, target_y), sidewalk_id = villager.waypoints[0]
            x, y = villager.position
            gap = math.hypot(target_x - x, target_y - y)

            if gap <= distance:
                # Reached the waypoint with leftover distance, then consume and move on.
                villager.position = (target_x, target_y)
                villager.sidewalk_id = sidewalk_id
                villager.waypoints.pop(0)
                distance -= gap
            else:
                # Move towards the waypoint.
                villager.position = (
                    x + (target_x - x) / gap * distance,
                    y + (target_y - y) / gap * distance,
                )
                distance = 0
        return not villager.waypoints


    def set_power_outage(self, active: bool) -> list[str]:
        # Called when the X-Factor menu toggles the outage
        messages: list[str] = []
        self.power_outage = active
        
        if active:
            for villager in self.villagers:
                if villager.is_scripted:
                    # NPCs instantly head home to evacuate
                    self.send_to(villager, villager.home_id)
                    messages.append(f"{villager.name} is evacuating indoors")
                    continue

                if villager.is_walking:
                    # If they are walking, let them finish their current trip first
                    continue
                
                # If they are standing around, make them ask the AI what to do right now
                villager.wait_time = 0.0

                # Clear their old destination so they don't accidentally go back
                villager.destination_id = None 
                
                if villager.agent is not None and villager.agent.profile.role == "citizen":
                    messages.append(f"{villager.name} is checking supplies")
        elif self.is_night:
            self._send_everyone_home()
        else:
            self._wake_up()
            
        return messages

    def get_top_memories(self, villager: Villager, current_day: int, is_power_outage: bool)-> list:
        """Calculates a score for every memory based on Recency, Importance, and Jaccard Similarity (with lemmatization)."""

        if not villager.recent_encounters:
            return []

        # Initialize the NLTK lemmatizer to reduce words to their root form
        lemmatizer = WordNetLemmatizer()

        # Define context keywords based on the current crisis state
        keywords = set()
        if is_power_outage:
            keywords.update(["power", "outage", "electricity", "dark", "light", "generator", "repair", "hospital", "medication", "doctor", "medical", "clinic"])

        # Lemmatize the keywords as both nouns (n) and verbs(v)
        stemmed_keywords = {lemmatizer.lemmatize(k , pos ='n') for k in keywords}
        stemmed_keywords.update({lemmatizer.lemmatize(k, pos='v') for k in keywords})

        scored_memories = []

        for mem in villager.recent_encounters:
            # Time Decay: Today = 1.0, Yesterday = 0.5, 2 days ago = 0.33
            days_old = max(0, current_day - mem.day)
            recency_score = 1.0 / (days_old + 1)

            # LLM Rating (Importance)
            importance_score = mem.importance / 10.0

            # Relevance (Keyword Matching)
            # Checks how many context keywords appear in the memory summary
            words = mem.summary.lower().split()
            mem_words = {lemmatizer.lemmatize(w) for w in words}
            union_words = mem_words.union(stemmed_keywords)

            if len(union_words) > 0:
                # Jaccard Similarity = (Number of shared words) / (Total number of unique words in both sets)
                relevance_score = len (mem_words.intersection(stemmed_keywords)) / len (union_words)
            else:
                relevance_score = 0.0

            # Total Score 
            total_score = (1.0 * recency_score) + (1.0 * importance_score) + (1.0 * relevance_score)
            scored_memories.append((total_score, mem))

        # Sore by highest memory
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        final_memories = [mem for score, mem in scored_memories if score >= 1.0][:5]

        if not final_memories and scored_memories:
            final_memories.append(scored_memories[0][1])

        return final_memories

    def update_agents(
        self, 
        sim_dt: float, 
        world_state: Any, 
        backend_sim: Any, 
        clock: Any, 
        is_power_outage: bool,
        outage_day: int,
        outage_duration: int,
        outage_area: str,
        recovery: Any = None
    ) -> list[str]:
        """Process AI results from the backend and queue new requests."""
        messages = []
        
        for villager in self.villagers:
            villager.decision_cooldown = max(0.0, villager.decision_cooldown - sim_dt)

        # Process results from the backend AI
        with world_state.lock:
            if world_state.is_data_ready:
                for v_id, action in world_state.new_actions.items():
                    villager = self.get_villager(v_id)
                    if villager is None:
                        continue

                    # Check if the power is restored
                    if action.action == "restore_power" and recovery is not None and is_power_outage:
                        if recovery.restore_possible(villager.location_id or ""):
                            self.restore_requested = True
                            messages.append(f"{villager.name} restored power")
                        else:
                            messages.append(f"{villager.name} is not able to restore power right now")

                    # Update the UI task label.
                    villager.current_task = action.action.replace("_", " ").title()
                    if action.target_location:
                        destination = action.target_location.replace("_", " ").title()
                        villager.current_task = f"{villager.current_task} - {destination}"
                        
                    log_text = action.journal if action.journal else villager.current_task
                    messages.append(f"{villager.name}: {log_text}")

                    # Save to task history (prevents duplicate consecutive entries)
                    if action.action != villager.previous_action:
                        villager.task_history.append( f"Day {clock.day_number}: {log_text}")
                    
                    villager.previous_action = action.action
                    
                    # Execute movement based on the AI's decision
                    if action.target_location and action.target_location != villager.location_id:
                        # Move to the requested location
                        try:
                            if villager.agent is not None and villager.agent.profile.role == "first_responder":
                                self.dispatch_truck(villager, action.target_location)
                            else:
                                self.send_to(villager, action.target_location)
                            villager.wait_time = 999.0 # Wait until they arrive to make a new decision

                        except (ValueError, KeyError) as exc:
                            messages.append(f"  route failed for {villager.name}: {exc}")
                            villager.wait_time = 5.0

                    # If they are a first reponder and didn't pick a detination, force them to patrol.
                    elif (
                        villager.agent is not None
                        and villager.agent.profile.role == "first_responder"
                        and villager.location_id != "school"
                    ): 
                        #First responder with no explicit destination; patrol random building.
                        choices = [b for b in self.buildings if b != villager.location_id]
                        next_patrol = self.rng.choice(choices)
                        try:
                            self.dispatch_truck(villager, next_patrol)
                            villager.wait_time = 999.0
                        except (ValueError, KeyError) as exc:
                            messages.append(f"  route failed for {villager.name}: {exc}")
                            villager.wait_time = 5.0
                    else:
                        villager.wait_time = 0.0

                # Reset the queue
                world_state.is_data_ready = False
                world_state.new_actions.clear()

        if clock.paused:
            return messages

        # Queue new AI requests for villagers who need to make a decision
        for villager in self.villagers:
            if villager.is_scripted or villager.agent is None:
                continue

            # They must be idle, not waiting, and not already queued. 
            if (
                not villager.is_walking
                and villager.wait_time <= 0
                and villager.decision_cooldown <= 0
            ):
                if not backend_sim.is_queued(villager.agent_id):
                    ctx = VillagerContext(
                        villager_id=villager.agent_id, 
                        name=villager.name, 
                        location_id=villager.location_id or "unknown",
                        day=clock.day_number, 
                        phase=clock.day_night.lower(),
                        crisis_active=is_power_outage, 
                        crisis_day=outage_day if is_power_outage else 0,
                        crisis_duration=outage_duration if is_power_outage else 0,
                        crisis_area=outage_area if is_power_outage else None,
                        power_on=not is_power_outage, 
                        previous_action=villager.previous_action,
                        parts_arrived=recovery.parts_arrived if recovery is not None and is_power_outage else None,
                        recent_encounters=self.get_top_memories(villager, clock.day_number, is_power_outage),
                        daily_summaries = villager.daily_summaries[-2:], # Last 2 days
                    )
                    backend_sim.queue_agent(villager.agent_id, villager.agent, ctx)
                    villager.wait_time = 999.0
                    villager.decision_cooldown = 0.0
        
        return messages

    def update(self, dt: float, day:int, is_night: bool) -> list[str]:
        """move villagers, returns journal messages for anything that happened"""
        messages: list[str] = []

        # Fire truck movement
        if self.fire_truck.is_active and self.fire_truck.waypoints:
            # Update heading for sprite rotation
            tx, ty = self.fire_truck.waypoints[0]
            x, y = self.fire_truck.position

            if tx != x or ty != y:
                self.fire_truck.angle = math.degrees(math.atan2(ty-y, tx-x))

            # Move at 1.5x speed along waypoints
            distance = (self.walk_speed * 1.5) * dt

            # If at the crosswalk and it is occupied, don't move
            if self.traffic(self.fire_truck, dt):
                distance = 0

            while self.fire_truck.waypoints and distance > 0:
                tx, ty = self.fire_truck.waypoints[0]
                x,y = self.fire_truck.position
                gap = math.hypot(tx-x, ty-y)
                if gap <=distance:
                    self.fire_truck.position = (tx,ty)
                    self.fire_truck.waypoints.pop(0)
                    distance -=gap
                else:
                    self.fire_truck.position = (x+(tx-x)/gap*distance, y+(ty-y)/gap*distance)
                    distance =0 

        # Passengers ride along with the truck
        if self.fire_truck.waypoints:
            for p in self.fire_truck.passengers:
                p.position = self.fire_truck.position
        else:
            # Truck arrived - unload passengers at the curb
            if self.fire_truck.is_active:
                self.fire_truck.is_active = False
                target_id = self.fire_truck.destination_building_id
                target_building = self.buildings[target_id] if target_id else None

                for p in self.fire_truck.passengers:
                    p.in_truck = False
                    p.destination_id = None
                    p.waypoints.clear()
                    p.wait_time = 0.5

                    if target_building is not None:
                        p.sidewalk_id = target_building.sidewalk_id
                        p.position = self._curb_point(target_building)

                self.fire_truck.passengers.clear()
                self.fire_truck.destination_building_id = None

        # Villager Movement
        for villager in self.villagers:

            if villager.in_truck:
                continue

            # Fireman crew follow the first responder agent
            if villager.following_target and not villager.is_walking:
                target = self.get_villager(villager.following_target)
                if target and target.location_id and target.location_id != villager.location_id:
                    self.send_to(villager, target.location_id)

            if villager.is_walking:
                # Stop at the crosswalk if the truck is coming
                if self.traffic(villager, dt):
                    continue
                if self._walk(villager, dt):
                    # Arrived at destination.
                    villager.location_id = villager.destination_id or villager.location_id
                    villager.destination_id = None
                    villager.wait_time = 0.0

            elif not self.is_night:
                if villager.wait_time > 0:
                    villager.wait_time -= dt

                elif villager.is_scripted and not self.power_outage and not villager.following_target:
                    # Scripted NPCs wander to random buildings 
                    if villager.wait_time <= 0:
                        choices = [b for b in self.buildings if b != villager.location_id]
                        dest = self.rng.choice(choices)
                        self.send_to(villager, dest)
                        villager.wait_time = self.rng.uniform(15.0, 30.0)

        # Check if any AI villagers are standing next to each other and should start a conversation.
        self.social.check_triggers(self.villagers, day, is_night) 
        return messages
        
    # Traffic system
    def traffic(self, crossing: Villager | FireTruck, time: float) -> bool:
        """Returns True if the villager or fire truck should wait at the crosswalk."""
        
        # If already waiting, decrease the timer until the time runs out
        if crossing.traffic_stop > 0:
            crossing.traffic_stop -= time
            if crossing.traffic_stop <= 0:
                crossing.intersection_occupied = True
            return True

        # Get x and y position of crossing entity
        x = crossing.position[0]
        y = crossing.position[1]

        # Create a block that contains all crosswalks
        crosswalk_occupied = False
        crosswalk_left = []
        crosswalk_right = []
        crosswalk_top = []
        crosswalk_bottom = []
        for sidewalk in self.network.by_id.values():
            if sidewalk.id.startswith("crosswalk"):
                side_x = sidewalk.bounds[0]
                side_y = sidewalk.bounds[1]
                side_width = sidewalk.bounds[2]
                side_height = sidewalk.bounds[3]
                if side_x <= x <= side_x + side_width and side_y <= y <= side_y + side_height:
                    crosswalk_occupied = True
                crosswalk_left.append(side_x)
                crosswalk_right.append(side_x + side_width)
                crosswalk_top.append(side_y)
                crosswalk_bottom.append(side_y + side_height)

        if crossing is self.fire_truck:
            crosswalk_box_left = min(crosswalk_left) - 10
            crosswalk_box_right = max(crosswalk_right) + 10
            crosswalk_box_top = min(crosswalk_top) - 10
            crosswalk_box_bottom = max(crosswalk_bottom) + 10

            if crosswalk_box_left <= x <= crosswalk_box_right and crosswalk_box_top <= y <= crosswalk_box_bottom:
                crosswalk_occupied = True
            else:
                crosswalk_occupied = False

        # If not at the crosswalk, keep moving
        if not crosswalk_occupied:
            crossing.intersection_occupied = False
            return False
        # If already at the crosswalk, keep moving
        if crossing.intersection_occupied:
            return False

        # If just got to the crosswalk, check if already occupied
        if crossing is self.fire_truck:
            crosswalk_occupied_state = False
            for v in self.villagers:
                if v.intersection_occupied and v.waypoints:
                    crosswalk_occupied_state = True
        else:
            crosswalk_occupied_state = self.fire_truck.intersection_occupied

        # If somebody is crossing, fire truck or villager, wait 5 seconds
        if crosswalk_occupied_state:
            crossing.traffic_stop = 5.0
            return True

        # If crosswalk is free, start crossing and let other know that you are crossing
        crossing.intersection_occupied = True
        return False
