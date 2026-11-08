import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from backend.agent.agent import building_convo, building_reflection_prompt
from backend.simulation_state import MemoryEntry, Villager

class SocialSystem:
    def __init__(self, rng, buildings):
        self.rng = rng
        self.buildings = buildings
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.active_conversations = 0
        self.export_data = None 
        self.export_progress = [] 
        self.is_exporting = False

