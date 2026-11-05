"""villagers movement, AI coordination, and fire truck dispatch"""

from __future__ import annotations

import math
import random

from typing import Any
from frontend.village.map import Building, VillageMap
from backend.agent.agent import VillagerAgent, VillagerContext
from backend.map.pathfinding import SidewalkNetwork, centerline_point
from backend.simulation_state import Villager, FireTruck
from backend.agent.config import STARTING_VILLAGERS, SCRIPTED_NPCS
from backend.map.vehicle_navigation import VehicleNetwork

Vec = tuple[float,float]

class VillagerManager:
    """moves and draws every villager"""

    walk_speed = 140.0  # world units per second

    def __init__(self, village_map: VillageMap, rng: random.Random | None = None, llm_client: Any = None) -> None:
        self.network = SidewalkNetwork(village_map) #sidewalk graph for walking routes
        self.vehicle_network = VehicleNetwork(village_map) # road graph for fire truck

        self.buildings = {b.id: b for b in village_map.buildings}
        self.rng = rng or random.Random()
        self.llm_client = llm_client
        self.power_outage = False #while True, routine sleeping/waking is suppressed
        self.is_night = False
      
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
        for v in self.villagers:
            if v.agent_id == agent_id:
                return v
        return None


    def dispatch_truck(self, driver: Villager, target_id: str) -> None:
        # Load the driver (+ crew ) and set a road route.
        building = self.buildings[target_id]

        # Calculate a road route from the truck's current position
        road_points = self.vehicle_network.route(self.fire_truck.position, building.entrance,)
        self.fire_truck.is_active = True
        self.fire_truck.waypoints = road_points
        self.fire_truck.destination_building_id = target_id

        # Driver boards
        self.fire_truck.passengers = [driver]
        driver.in_truck = True
        driver.location_id = target_id
        driver.destination_id = target_id
        driver.waypoints.clear()
        driver.position = self.fire_truck.position

        #Anyone following the driver boards too
        for v in self.villagers:
            if v.following_target == driver.agent_id:
                v.in_truck = True
                v.location_id = target_id
                v.destination_id = target_id
         python -m frontend.ui.window       v.waypoints.clear()
                v.position = self.fire_truck.position
                self.fire_truck.passengers.append(v)


    def set_night(self, is_night: bool) -> None:
        # night: villagers go home, morning: they start wandering again
        self.is_night = is_night
        if self.power_outage:
            return  # during an outage they stay at the shelter
        if is_night:
            self._send_everyone_home()
        else:
            self._wake_up()


    def _send_everyone_home(self) -> None:
        for villager in self.villagers:
            at_home = villager.location_id == villager.home_id and not villager.is_walking
            if not at_home:
                self.send_to(villager, villager.home_id)


    def _wake_up(self) -> None:
        # leave in a few seconds so they don't all walk out at once
        for villager in self.villagers:
            villager.wait_time = self.rng.uniform(0.0, 3.0)


    def send_to(self, villager: Villager, building_id: str) -> None:
        # Assign a new walking route. Clears 'location_id' until arrival
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
                villager.position = (target_x, target_y)
                villager.sidewalk_id = sidewalk_id
                villager.waypoints.pop(0)
                distance -= gap
            else:
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

    def update_agents(
        self, 
        sim_dt: float, 
        world_state: Any, 
        backend_sim: Any, 
        clock: Any, 
        is_power_outage: bool,
        outage_day: int,
        outage_duration: int,
        outage_area: str
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

                    if action.journal:
                        messages.append(f"{villager.name}: {action.journal}")

                    villager.previous_action = action.action
                    villager.current_task = action.action.replace("_", " ").title()
                    if action.target_location:
                        destination = action.target_location.replace("_", " ").title()
                        villager.current_task = f"{villager.current_task} - {destination}"

                    if action.target_location and action.target_location != villager.location_id:
                        # Move to the requested location
                        try:
                            if villager.agent is not None and villager.agent.profile.role == "first_responder":
                                self.dispatch_truck(villager, action.target_location)
                            else:
                                self.send_to(villager, action.target_location)
                            villager.wait_time = 999.0
                        except (ValueError, KeyError) as exc:
                            messages.append(f"  route failed for {villager.name}: {exc}")
                            villager.wait_time = 5.0
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
                
                world_state.is_data_ready = False
                world_state.new_actions.clear()

        if clock.paused:
            return messages

        # Queue new AI requests for villagers who need to make a decision
        for villager in self.villagers:
            if villager.is_scripted or villager.agent is None:
                continue
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
                    )
                    backend_sim.queue_agent(villager.agent_id, villager.agent, ctx)
                    villager.wait_time = 999.0
                    villager.decision_cooldown = 0.0
        
        return messages

    def update(self, dt: float) -> list[str]:
        """move villagers, returns journal messages for anything that happened"""
        messages: list[str] = []

        #moving fire truck
        if self.fire_truck.is_active and self.fire_truck.waypoints:
            # Update heading for sprite rotation
            tx, ty = self.fire_truck.waypoints[0]
            x, y = self.fire_truck.position

            if tx != x or ty != y:
                self.fire_truck.angle = math.degrees(math.atan2(ty-y, tx-x))

            # Move at 1.5x speed along waypoints
            distance = (self.walk_speed * 1.5) * dt
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
        
        for villager in self.villagers:

            if villager.in_truck:
                continue

            # fireman crew follow the first responder agent
            if villager.following_target and not villager.is_walking:
                target = self.get_villager(villager.following_target)
                if target and target.location_id and target.location_id != villager.location_id:
                    self.send_to(villager, target.location_id)

            if villager.is_walking:
                if self._walk(villager, dt):
                    villager.location_id = villager.destination_id or villager.location_id
                    villager.destination_id = None
                    villager.wait_time = 0.0
                    if villager.location_id:
                        place = self.buildings[villager.location_id].display_name
                        messages.append(f"{villager.name} arrived at {place}")

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
                        
        return messages
   
    