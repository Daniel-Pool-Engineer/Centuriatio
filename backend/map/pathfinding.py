from __future__ import annotations

from collections import deque
from math import hypot
from typing import Any

from frontend.village.map import Building, Sidewalk, VillageMap

Vec = tuple[float, float]
CROSSWALK_GAP = 100    # sidewalks this close are connected by a road crossing

def _rect_gap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    # distance between two rectangles (0 if they touch)
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = max(0, bx - (ax + aw), ax - (bx + bw))
    dy = max(0, by - (ay + ah), ay - (by + bh))
    return max(dx, dy)

def centerline_point(sidewalk: Sidewalk, point: Vec) -> Vec:
    # closest point on the middle line of a sidewalk
    x, y, width, height = sidewalk.bounds
    px, py = point
    if width >= height:
        return (min(max(px, x), x + width), y + height / 2)
    return (x + width / 2, min(max(py, y), y + height))


class SidewalkNetwork:
    """finds walking routes between buildings"""

    def __init__(self, village_map: VillageMap) -> None:
        self.by_id = {s.id: s for s in village_map.sidewalks}
        self.adjacency: dict[str, set[str]] = {s.id: set() for s in village_map.sidewalks}

        # connections listed in the map
        for sidewalk in village_map.sidewalks:
            for other_id in sidewalk.connections:
                self.adjacency[sidewalk.id].add(other_id)
                self.adjacency[other_id].add(sidewalk.id)

        # sidewalks on opposite sides of a road act as crosswalks
        for a in village_map.sidewalks:
            for b in village_map.sidewalks:
                if a.id != b.id and _rect_gap(a.bounds, b.bounds) <= CROSSWALK_GAP:
                    self.adjacency[a.id].add(b.id)

    def sidewalk_path(self, start: str, goal: str) -> list[str]:
        # shortest list of sidewalks from start to goal
        if start == goal:
            return [start]
        seen = {start}
        queue = deque([[start]])
        while queue:
            route = queue.popleft()
            for next_id in self.adjacency[route[-1]]:
                if next_id == goal:
                    return route + [next_id]
                if next_id not in seen:
                    seen.add(next_id)
                    queue.append(route + [next_id])
        return [start, goal]

    def route(self, start: Vec, start_sidewalk: str, building: Building) -> list[tuple[Vec, str]]:
        # list of (point, sidewalk id) to walk through to reach a building
        waypoints: list[tuple[Vec, str]] = []
        point = start
        for sidewalk_id in self.sidewalk_path(start_sidewalk, building.sidewalk_id):
            point = centerline_point(self.by_id[sidewalk_id], point)
            waypoints.append((point, sidewalk_id))

        # walk to the spot beside the entrance, then step inside
        final = self.by_id[building.sidewalk_id]
        waypoints.append((centerline_point(final, building.entrance), final.id))
        waypoints.append(((float(building.entrance[0]), float(building.entrance[1])), final.id))
        return waypoints

