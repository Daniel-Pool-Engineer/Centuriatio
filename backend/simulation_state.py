from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

Color = tuple[int, int, int]
Vec = tuple[float, float]
@dataclass

class WorldState:
    is_data_ready: bool = False
    new_actions: Dict[str, Any] = field(default_factory=dict)
    
    # Thread lock to prevent race conditions
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass
class FireTruck:
    position: Vec = (0.0,0.0)
    waypoints: list[Vec] = field(default_factory = list) # remaining road points
    passengers: list["Villager"] = field(default_factory =list) # driver + crew, snapped to position
    is_active: bool = False #True while driving
    destination_building_id: str | None = None #target building on arrival
    angle: float = 0.0 # heading in degrees, for sprite rotation


@dataclass
class Villager:

    # Agent's Identity
    agent_id: str # unique key, matches the AI agent and world_state entries
    name: str # display name
    home_id: str # building the villager returns to at night
    color: Color # sprite fill color

    # Position + Movement
    position: Vec #current world-space (x,y)
    sidewalk_id: str # sidewalk the villager is currently on or last on
    location_id: str | None   # building they are at, None while walking
    destination_id: str | None = None
    waypoints: list[tuple[Vec, str]] = field(default_factory=list)

    # Simulation Timing 
    wait_time: float = 0.0   # seconds before leaving the current building
    offset: Vec = (0.0, 0.0)   # small shift so villagers don't overlap
    decision_cooldown: float = 0.0

    # AI decisions
    agent: VillagerAgent | None
    previous_action: str | None = None
    current_task: str = "Waiting"

    # Scripted behavior
    is_scripted: bool = False
    following_target: str | None = None

    # Ben only - fire fighter agent
    in_truck: bool = False

    @property
    def is_walking(self) -> bool:
        return bool(self.waypoints) or self.in_truck
