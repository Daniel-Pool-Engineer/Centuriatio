from backend.agent.profile import CITIZEN, FIRST_RESPONDER, ELECTRICIAN, DOCTOR

# name, home building, color (building ids match backend/map/graph.py)
STARTING_VILLAGERS = [
    ("m1", "Maria", "home_a", (200, 40, 40), CITIZEN),
    ("v_ana", "Dr. Ana", "home_a", (220, 60, 60), DOCTOR),        # Doctor
    ("v_ben", "Ben", "fire", (40, 120, 220), FIRST_RESPONDER),      # First Responder
    ("v_carla", "Carla", "home_b", (240, 140, 20), ELECTRICIAN),  # Electrician
    ("v_diego", "Diego", "home_c", (30, 160, 90), CITIZEN),       # Citizen
    ("v_elena", "Elena", "home_d", (170, 60, 190), CITIZEN),      # Citizen
    ("v_felix", "Felix", "home_b", (20, 20, 20), CITIZEN),        # Citizen
]


# Scripted, non-AI NPCs
SCRIPTED_NPCS = [
    ("npc_1", "Sam", "home_c", (100, 200, 150)),
    ("npc_2", "Lily", "home_d", (200, 100, 250)),
    ("npc_3", "Jack", "home_b", (150, 150, 50)),
    ("npc_4", "Chloe", "home_a", (250, 150, 150)),
    ("npc_5", "Tom", "home_c", (50, 200, 200)),

    # First responder crew. Follows the first responder agent around
    ("npc_crew_1", "Fireman 1", "fire", (200, 50, 50)),
    ("npc_crew_2", "Fireman 2", "fire", (200, 50, 50)),
    ("npc_crew_3", "Fireman 3", "fire", (200, 50, 50)),
]
