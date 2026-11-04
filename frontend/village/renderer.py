"""pygame renderer for the village map"""

from __future__ import annotations

import pygame

from pathlib import Path

from .map import Building, VillageMap


Color = tuple[int, int, int]


class VillageMapRenderer:
    """draws the village map"""

    background_color: Color = (66, 105, 65)
    grid_color: Color = (72, 112, 70)

    main_road_color: Color = (68, 72, 80)
    local_road_color: Color = (91, 95, 102)

    sidewalk_color: Color = (191, 187, 173)
    crosswalk_color: Color = (238, 238, 225)
    crosswalk_stripe_size = 8
    crosswalk_stripe_gap = 8
    crosswalk_margin = 4
    road_sidewalk_gap_limit = 8

    entrance_color: Color = (250, 190, 54)
    spawn_color: Color = (42, 116, 70)

    text_color: Color = (35, 38, 42)
    window_color: Color = (225, 239, 245)
    door_color: Color = (75, 58, 48)
    shadow_color: Color = (170, 173, 164)

    building_colors: dict[str, Color] = {
        # Houses
        "home_a": (196, 145, 105),      # warm brown
        "home_b": (185, 185, 190),      # light gray apartment
        "home_c": (170, 120, 145),      # muted pink
        "home_d": (125, 155, 190),      # muted blue

        # Public / community buildings
        "hospital": (235, 235, 228),    # off-white
        "fire": (178, 65, 55),          # fire-station red
        "police": (75, 95, 130),        # dark blue
        "school": (205, 175, 75),       # yellow
        "grocery": (190, 145, 75),      # warm tan
        "electrical": (125, 130, 128),  # gray utility building

        # Work / office
        "office": (145, 155, 165),      # gray-blue office
        "work": (145, 155, 165),        # fallback
    }
    
    building_border_colors: dict[str, Color] = {
        "home_a": (130, 85, 60),
        "home_b": (105, 105, 110),
        "home_c": (115, 75, 95),
        "home_d": (75, 100, 130),

        "hospital": (180, 180, 175),
        "fire": (125, 40, 35),
        "police": (45, 60, 85),
        "school": (145, 120, 45),
        "grocery": (135, 95, 45),
        "electrical": (80, 85, 84),
        "office": (90, 100, 110),
        "work": (90, 100, 110),
    }

    # Trees placed around the map
    tree_positions = {
        (180, 300), (850, 250), (1200, 350),
        (2700, 300), (3050, 450),
        (180, 1800), (1100, 1850), (1350, 2050),
        (2200, 1900), (3000, 2050),
        (800, 2200), (1800, 2200), (2800, 2250),
    }

    # Street lamps along the sidewalks
    lamp_positions = {
        (250, 1072), (850, 1072), (1300, 1072),
        (1850, 1072), (2450, 1072), (3000, 1072),
        (200, 1264), (700, 1264), (1200, 1264),
        (1850, 1264), (2400, 1264), (3000, 1264),
        (1456, 300), (1456, 750),
        (1648, 300), (1648, 750),
        (1456, 1650), (1456, 2100),
        (1648, 1650), (1648, 2100),
    }

    # Benches along the sidewalks
    bench_positions = {
        (550, 1072), (1100, 1072),
        (2150, 1072), (2750, 1072),
        (450, 1264), (1050, 1264),
        (2150, 1264), (2750, 1264),
    }

    def __init__(
        self,
        *,
        camera: tuple[float, float] = (0, 0),
        zoom: float = 0.5,
    ) -> None:
        self.camera_x, self.camera_y = camera
        self.zoom = zoom
        self.font = pygame.font.Font(None, 16)
        self._label_cache: dict[str, pygame.Surface] = {}

        # Adds PNG Icons from Assets
        self.building_icons = {}
        icon_folder = Path(__file__).parent.parent / "assets" / "buildings"

        icon_names = [
            "house", "apartment", "hospital", "grocery", "school",
            "fire", "police", "electrical", "office",
        ]

        for icon_name in icon_names:
            path = icon_folder / f"{icon_name}.png"
            if path.exists():
                self.building_icons[icon_name] = pygame.image.load(path).convert_alpha()

    def set_camera(self, x: float, y: float) -> None:
        self.camera_x = x
        self.camera_y = y

    def set_zoom(self, zoom: float) -> None:
        if zoom <= 0:
            raise ValueError("zoom must be positive")
        self.zoom = zoom

    def world_to_screen(self, point: tuple[int, int]) -> tuple[int, int]:
        x, y = point
        return (
            round((x - self.camera_x) * self.zoom),
            round((y - self.camera_y) * self.zoom),
        )

    def _rect_to_screen(self, bounds: tuple[int, int, int, int]) -> pygame.Rect:
        x, y, width, height = bounds
        screen_x, screen_y = self.world_to_screen((x, y))
        return pygame.Rect(
            screen_x,
            screen_y,
            max(1, round(width * self.zoom)),
            max(1, round(height * self.zoom)),
        )

    def draw(
        self,
        surface: pygame.Surface,
        village_map: VillageMap,
        *,
        show_grid: bool = False,
        show_labels: bool = True,
    ) -> None:
        surface.fill(self.background_color)

        if show_grid:
            self._draw_grid(surface, village_map)

        for sidewalk in village_map.sidewalks:
            if not sidewalk.id.startswith("crosswalk-"):
                pygame.draw.rect(surface, self.sidewalk_color, self._rect_to_screen(sidewalk.bounds))

        self._draw_road_sidewalk_gaps(surface, village_map)

        # Roads are redrawn over sidewalk edges so their bounds stay visually exact.
        for road in village_map.roads:
            color = self.main_road_color if road.road_type == "main" else self.local_road_color
            pygame.draw.rect(surface, color, self._rect_to_screen(road.bounds))
            self._draw_road_lines(surface, road.bounds, village_map)

        for sidewalk in village_map.sidewalks:
            if sidewalk.id.startswith("crosswalk-"):
                road_color = self._crosswalk_road_color(sidewalk.bounds, village_map)
                pygame.draw.rect(surface, road_color, self._rect_to_screen(sidewalk.bounds))
                self._draw_crosswalk_stripes(surface, sidewalk.bounds)

        for tree in self.tree_positions:
            self._draw_tree(surface, tree)

        for bench in self.bench_positions:
            self._draw_bench(surface, bench)

        for building in village_map.buildings:
            self._draw_building(surface, building, show_labels=show_labels)
            
        for lamp in self.lamp_positions:
            self._draw_lamp(surface, lamp)

        spawn = self.world_to_screen(village_map.villager_spawn)
        pygame.draw.circle(surface, self.spawn_color, spawn, max(6, round(12 * self.zoom)))

    def _draw_road_sidewalk_gaps(self, surface: pygame.Surface, village_map: VillageMap) -> None:
        # fill in the gaps where a sidewalk runs alongside a road
        for road in village_map.roads:
            road_x, road_y, road_width, road_height = road.bounds
            road_color = self.main_road_color if road.road_type == "main" else self.local_road_color
            for sidewalk in village_map.sidewalks:
                sidewalk_x, sidewalk_y, sidewalk_width, sidewalk_height = sidewalk.bounds

                overlap_left = max(road_x, sidewalk_x)
                overlap_right = min(road_x + road_width, sidewalk_x + sidewalk_width)
                if overlap_left < overlap_right:
                    if road_y + road_height <= sidewalk_y:
                        gap = sidewalk_y - (road_y + road_height)
                        gap_bounds = (overlap_left, road_y + road_height, overlap_right - overlap_left, gap)
                    elif sidewalk_y + sidewalk_height <= road_y:
                        gap = road_y - (sidewalk_y + sidewalk_height)
                        gap_bounds = (overlap_left, sidewalk_y + sidewalk_height, overlap_right - overlap_left, gap)
                    else:
                        gap = 0
                        gap_bounds = (0, 0, 0, 0)

                    if 0 < gap <= self.road_sidewalk_gap_limit:
                        pygame.draw.rect(surface, road_color, self._rect_to_screen(gap_bounds))

                overlap_top = max(road_y, sidewalk_y)
                overlap_bottom = min(road_y + road_height, sidewalk_y + sidewalk_height)
                if overlap_top < overlap_bottom:
                    if road_x + road_width <= sidewalk_x:
                        gap = sidewalk_x - (road_x + road_width)
                        gap_bounds = (road_x + road_width, overlap_top, gap, overlap_bottom - overlap_top)
                    elif sidewalk_x + sidewalk_width <= road_x:
                        gap = road_x - (sidewalk_x + sidewalk_width)
                        gap_bounds = (sidewalk_x + sidewalk_width, overlap_top, gap, overlap_bottom - overlap_top)
                    else:
                        gap = 0
                        gap_bounds = (0, 0, 0, 0)

                    if 0 < gap <= self.road_sidewalk_gap_limit:
                        pygame.draw.rect(surface, road_color, self._rect_to_screen(gap_bounds))

    def _crosswalk_road_color(self, bounds: tuple[int, int, int, int], village_map: VillageMap) -> Color:
        # return the road surface color beneath a crosswalk
        x, y, width, height = bounds
        for road in village_map.roads:
            road_x, road_y, road_width, road_height = road.bounds
            if (
                x < road_x + road_width
                and x + width > road_x
                and y < road_y + road_height
                and y + height > road_y
            ):
                return self.main_road_color if road.road_type == "main" else self.local_road_color
        return self.main_road_color

    def _draw_crosswalk_stripes(self, surface: pygame.Surface, bounds: tuple[int, int, int, int]) -> None:
        # evenly spaced zebra stripes across a crosswalk segment
        x, y, width, height = bounds
        step = self.crosswalk_stripe_size + self.crosswalk_stripe_gap

        if width >= height:
            start = x + self.crosswalk_margin
            end = x + width - self.crosswalk_margin
            while start + self.crosswalk_stripe_size <= end:
                stripe = (
                    start,
                    y + self.crosswalk_margin,
                    self.crosswalk_stripe_size,
                    max(1, height - self.crosswalk_margin * 2),
                )
                pygame.draw.rect(surface, self.crosswalk_color, self._rect_to_screen(stripe))
                start += step
        else:
            start = y + self.crosswalk_margin
            end = y + height - self.crosswalk_margin
            while start + self.crosswalk_stripe_size <= end:
                stripe = (
                    x + self.crosswalk_margin,
                    start,
                    max(1, width - self.crosswalk_margin * 2),
                    self.crosswalk_stripe_size,
                )
                pygame.draw.rect(surface, self.crosswalk_color, self._rect_to_screen(stripe))
                start += step

    def _draw_road_lines(
        self,
        surface: pygame.Surface,
        bounds: tuple[int, int, int, int],
        village_map: VillageMap,
    ) -> None:
        x, y, width, height = bounds

        dash_length = 48
        gap_length = 32
        line_width = max(1, round(4 * self.zoom))
        line_color = (255, 215, 0)
        horizontal = width >= height
        center = y + height // 2 if horizontal else x + width // 2
        axis_start = x if horizontal else y
        axis_end = x + width if horizontal else y + height
        road_rect = pygame.Rect(bounds)
        blocked: list[tuple[int, int]] = []

        for other in village_map.roads:
            if other.bounds == bounds:
                continue
            intersection = road_rect.clip(pygame.Rect(other.bounds))
            if intersection.width > 0 and intersection.height > 0:
                blocked.append((
                    intersection.left if horizontal else intersection.top,
                    intersection.right if horizontal else intersection.bottom,
                ))

        for sidewalk in village_map.sidewalks:
            if not sidewalk.id.startswith("crosswalk-"):
                continue
            crosswalk = pygame.Rect(sidewalk.bounds)
            covers_centerline = (
                crosswalk.top <= center < crosswalk.bottom
                if horizontal
                else crosswalk.left <= center < crosswalk.right
            )
            if covers_centerline:
                blocked.append((
                    crosswalk.left if horizontal else crosswalk.top,
                    crosswalk.right if horizontal else crosswalk.bottom,
                ))

        blocked.sort()
        merged_blocked: list[tuple[int, int]] = []
        for block_start, block_end in blocked:
            if merged_blocked and block_start <= merged_blocked[-1][1] + self.road_sidewalk_gap_limit:
                merged_blocked[-1] = (merged_blocked[-1][0], max(merged_blocked[-1][1], block_end))
            else:
                merged_blocked.append((block_start, block_end))

        def draw_segment(segment_start: int, segment_end: int) -> None:
            if segment_start >= segment_end:
                return
            start_point = (segment_start, center) if horizontal else (center, segment_start)
            end_point = (segment_end, center) if horizontal else (center, segment_end)
            pygame.draw.line(
                surface,
                line_color,
                self.world_to_screen(start_point),
                self.world_to_screen(end_point),
                line_width,
            )

        dash_start = axis_start
        while dash_start < axis_end:
            dash_end = min(dash_start + dash_length, axis_end)
            visible_start = dash_start
            for block_start, block_end in merged_blocked:
                if block_end <= visible_start:
                    continue
                if block_start >= dash_end:
                    break
                draw_segment(visible_start, min(block_start, dash_end))
                visible_start = max(visible_start, block_end)
                if visible_start >= dash_end:
                    break
            draw_segment(visible_start, dash_end)
            dash_start += dash_length + gap_length

    def _draw_tree(self, surface, position):
        x, y = self.world_to_screen(position)

        size = max(4, round(45 * self.zoom))

        # Shadow
        pygame.draw.ellipse(
            surface, (45, 75, 55),
            (x - size, y + size // 2, size * 2, size // 2)
        )

        # Tree trunk
        pygame.draw.rect(
            surface, (105, 70, 42),
            (x - size // 6, y, size // 3, size)
        )

        # Leaves
        pygame.draw.circle(surface, (55, 115, 55), (x, y - size // 2), size)
        pygame.draw.circle(surface, (75, 145, 60), (x - size // 2, y - size // 2), size // 2)
        pygame.draw.circle(surface, (75, 145, 60), (x + size // 2, y - size // 2), size // 2)

        # Small highlight
        pygame.draw.circle(
            surface, (105, 165, 65),
            (x - size // 3, y - size),
            max(2, size // 4)
        )

    def _draw_lamp(self, surface, position):
        x, y = self.world_to_screen(position)

        height = max(10, round(55 * self.zoom))
        pole_width = max(1, round(3 * self.zoom))

        # Pole
        pygame.draw.line(
            surface, (45, 45, 50),
            (x, y), (x, y - height),
            pole_width
        )

        # Top of the lamp
        pygame.draw.line(
            surface, (45, 45, 50),
            (x, y - height), (x + round(8 * self.zoom), y - height),
            pole_width
        )

        # Light
        pygame.draw.circle(
            surface, (255, 225, 120),
            (x + round(8 * self.zoom), y - height),
            max(2, round(5 * self.zoom))
        )

        # Dark outline around light
        pygame.draw.circle(
            surface, (65, 65, 60),
            (x + round(8 * self.zoom), y - height),
            max(2, round(5 * self.zoom)),
            max(1, round(2 * self.zoom))
        )

    def _draw_bench(self, surface, position):
        x, y = self.world_to_screen(position)

        width = max(12, round(55 * self.zoom))
        height = max(4, round(10 * self.zoom))

        # Bench legs
        pygame.draw.line(
            surface, (55, 45, 40),
            (x - width // 3, y), (x - width // 3, y + height),
            2
        )
        pygame.draw.line(
            surface, (55, 45, 40),
            (x + width // 3, y), (x + width // 3, y + height),
            2
        )

        # Seat
        pygame.draw.rect(
            surface, (135, 85, 48),
            (x - width // 2, y - height, width, height)
        )

        pygame.draw.rect(
            surface, (85, 55, 35),
            (x - width // 2, y - height, width, height),
            1
        )

    def _draw_building(
        self,
        surface: pygame.Surface,
        building: Building,
        *,
        show_labels: bool,
    ) -> None:
        bounds = self._rect_to_screen(building.bounds)
        
        color = self.building_colors.get(building.id, (145, 145, 145))
        border_color = self.building_border_colors.get(building.id, self.text_color)

        # 1. Shadow
        shadow = bounds.move(max(2, round(5 * self.zoom)), max(2, round(5 * self.zoom)))
        pygame.draw.rect(surface, self.shadow_color, shadow, border_radius=max(2, round(5 * self.zoom)))

        # 2. Background Color
        pygame.draw.rect(surface, color, bounds, border_radius=max(2, round(5 * self.zoom)))

        # 3. Windows
        self._draw_windows(surface, bounds)

        # 4. Border
        pygame.draw.rect(surface, border_color, bounds, width=max(1, round(2 * self.zoom)), border_radius=max(2, round(5 * self.zoom)))

        # 5. Icon
        icon_name = building.id
        if building.id.startswith("home"):
            icon_name = building.building_type
        if building.id in ("work", "office"):
            icon_name = "office"

        icon = self.building_icons.get(icon_name)
        if icon is not None:
            icon_size = max(1, int(min(bounds.width, bounds.height) * 0.45))
            scaled_icon = pygame.transform.smoothscale(icon, (icon_size, icon_size))
            icon_rect = scaled_icon.get_rect(center=bounds.center)
            surface.blit(scaled_icon, icon_rect)

        # 6. Door
        entrance = self.world_to_screen(building.entrance)
        door_width = max(4, round(12 * self.zoom))
        door_height = max(6, round(18 * self.zoom))
        door = pygame.Rect(
            entrance[0] - door_width // 2,
            entrance[1] - door_height,
            door_width,
            door_height,
        )
        pygame.draw.rect(surface, self.door_color, door)
        pygame.draw.circle(surface, self.entrance_color, entrance, max(2, round(4 * self.zoom)))

        # 7. Label
        if show_labels and self.zoom >= 0.45:
            label_text = building.id.replace("-", " ").title()
            if label_text not in self._label_cache:
                self._label_cache[label_text] = self.font.render(label_text, True, self.text_color)
            label = self._label_cache[label_text]
            label_rect = label.get_rect(midbottom=(bounds.centerx, bounds.top - 4))
            surface.blit(label, label_rect)

    def _draw_windows(self, surface: pygame.Surface, bounds: pygame.Rect) -> None:
        window_width = max(4, round(10 * self.zoom))
        window_height = max(4, round(8 * self.zoom))

        if bounds.width < window_width * 2 or bounds.height < window_height * 2:
            return

        spacing_x = max(window_width + 3, round(22 * self.zoom))
        spacing_y = max(window_height + 3, round(20 * self.zoom))

        start_x = bounds.left + round(15 * self.zoom)
        start_y = bounds.top + round(20 * self.zoom)

        y = start_y
        while y + window_height < bounds.bottom - round(18 * self.zoom):
            x = start_x
            while x + window_width < bounds.right - round(15 * self.zoom):
                window = pygame.Rect(x, y, window_width, window_height)
                pygame.draw.rect(surface, self.window_color, window)
                pygame.draw.rect(surface, self.text_color, window, width=1)
                x += spacing_x
            y += spacing_y

    def _draw_grid(self, surface: pygame.Surface, village_map: VillageMap) -> None:
        width, height = village_map.world_size
        cell_size = village_map.grid.cell_size

        left, top = self.world_to_screen((0, 0))
        right, bottom = self.world_to_screen((width, height))

        for x in range(0, width + cell_size, cell_size):
            screen_x, _ = self.world_to_screen((x, 0))
            pygame.draw.line(surface, self.grid_color, (screen_x, top), (screen_x, bottom))

        for y in range(0, height + cell_size, cell_size):
            _, screen_y = self.world_to_screen((0, y))
            pygame.draw.line(surface, self.grid_color, (left, screen_y), (right, screen_y))