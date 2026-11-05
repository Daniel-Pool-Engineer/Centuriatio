from __future__ import annotations

import pygame

from backend.simulation_state import Villager, FireTruck
from frontend.village.renderer import VillageMapRenderer


class VillagerRenderer:
    """draws villagers and the fire truck onto the screen"""

    def __init__(self) -> None:
        self.font = pygame.font.Font(None, 16)
        self._label_cache: dict[str, pygame.Surface] = {}

    def draw(
        self,
        surface: pygame.Surface,
        renderer: VillageMapRenderer,
        villagers: list[Villager],
        fire_truck: FireTruck,
    ) -> None:
        # Draw the fire truck (always visible, even when parked)
        tx, ty = renderer.world_to_screen(fire_truck.position)
        r = max(8, round(12 * renderer.zoom))

        truck_w, truck_h = r * 2, r * 3
        truck_surf = pygame.Surface((truck_w, truck_h), pygame.SRCALPHA)

        # truck body
        pygame.draw.rect(truck_surf, (200, 40, 40), (0, 0, truck_w, truck_h), border_radius=4)
        # truck outline
        pygame.draw.rect(truck_surf, (255, 255, 255), (0, 0, truck_w, truck_h), width=2, border_radius=4)
        # yellow stripe
        pygame.draw.rect(truck_surf, (255, 215, 0), (0, truck_h // 2, truck_w, 2), width=2)
        # siren
        pygame.draw.circle(truck_surf, (255, 100, 100), (truck_w // 2, 0), max(2, r // 2))

        # rotate truck angle
        rotated_truck = pygame.transform.rotate(truck_surf, -fire_truck.angle - 90)
        
        # Center the rotated truck on the screen position
        truck_rect = rotated_truck.get_rect(center=(tx, ty))
        surface.blit(rotated_truck, truck_rect)

        for villager in villagers:
            if villager.in_truck:
                continue

            x, y = villager.position
            offset_x, offset_y = villager.offset

            screen_pos = renderer.world_to_screen((x + offset_x, y + offset_y))
            radius = max(5, round(9 * renderer.zoom))

            pygame.draw.circle(surface, villager.color, screen_pos, radius)
            pygame.draw.circle(surface, (255, 255, 255), screen_pos, radius, width=2)

            head_pos = (screen_pos[0], screen_pos[1] - radius)
            pygame.draw.circle(surface, (240, 200, 170), head_pos, max(3, radius // 2))

            if villager.name not in self._label_cache:
                if villager.is_scripted or villager.agent is None:
                    label_text = villager.name
                else:
                    role_display = villager.agent.profile.role.replace("_", " ").title()
                    label_text = f"{villager.name} ({role_display})"
                
                self._label_cache[villager.name] = self.font.render(label_text, True, (20, 20, 20))
            
            label = self._label_cache[villager.name]
            label_rect = label.get_rect(
                midbottom=(screen_pos[0], screen_pos[1] - radius - 5)
            )
            label_background = label_rect.inflate(6, 3)

            pygame.draw.rect(surface, (245, 245, 240), label_background, border_radius=3)
            surface.blit(label, label_rect)