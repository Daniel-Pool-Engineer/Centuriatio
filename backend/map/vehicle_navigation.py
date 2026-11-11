from __future__ import annotations
from frontend.village.map import VillageMap

Point = tuple[float, float]

class VehicleNetwork:
    # Purpose: finds driving routes for vehicles (the fire truck).

    def __init__(self, village_map: VillageMap) -> None:
        self.horizontal_y = 0.0
        self.vertical_x = 0.0
        self.LANE_OFFSET = 32.0 # Drives on the right side of the road
        
        # Get map bounds for U-turns
        self.map_width, self.map_height = village_map.world_size

        #find the centerline of the main roads
        for road in village_map.roads:
            if road.road_type == "main":
                x,y,w,h = road.bounds
                if w >h: 
                    self.horizontal_y = y + (h/2.0)
                else:
                    self.vertical_x = x + (w/2.0)

    def _nearest_road_point(self, pos: Point, target_pos: Point | None = None) -> Point:
        # Snaps a raw (x,y) coordinate onto the nearest valid driving lane.
        x,y = pos

        # Determine if the position is close to the horizontal or vertical road centerline
        is_horizontal = abs(y - self.horizontal_y) < abs(x - self.vertical_x)

        if is_horizontal:
            lane_y = self.horizontal_y
            if target_pos is not None:
                tx, ty = target_pos

                # Drive in the bottom lane if moving right, top lane if moving left.
                lane_y += self.LANE_OFFSET if tx >= x else -self.LANE_OFFSET
            else:
                lane_y += self.LANE_OFFSET
            return (x, lane_y)
        else:
            lane_x = self.vertical_x
            if target_pos is not None:
                tx, ty = target_pos
                # Drive in the right lane if moving down, left lane if moving up.
                lane_x += self.LANE_OFFSET if ty >= y else -self.LANE_OFFSET
            else:
                lane_x += self.LANE_OFFSET
            return (lane_x, y)

    def route(self, start_pos: Point, end_pos: Point) -> list[Point]:
        # Calculates a multi-point path from start to end, respecting lane rules and intersections.

        # Determine if start and end are on horizontal or vertical roads
        is_start_horiz = abs(start_pos[1] - self.horizontal_y) < abs(start_pos[0] - self.vertical_x)
        is_end_horiz = abs(end_pos[1] - self.horizontal_y) < abs(end_pos[0] - self.vertical_x)

        # Determine the exact lane the truck MUST be in at the destination
        if is_end_horiz:
            target_lane_y = self.horizontal_y - self.LANE_OFFSET if end_pos[1] < self.horizontal_y else self.horizontal_y + self.LANE_OFFSET
            end_road = (end_pos[0], target_lane_y)
        else:
            target_lane_x = self.vertical_x - self.LANE_OFFSET if end_pos[0] < self.vertical_x else self.vertical_x + self.LANE_OFFSET
            end_road = (target_lane_x, end_pos[1])

        # Snap the start position to the lane it is CURRENTLY in
        if is_start_horiz:
            current_lane_y = self.horizontal_y - self.LANE_OFFSET if start_pos[1] < self.horizontal_y else self.horizontal_y + self.LANE_OFFSET
            start_road = (start_pos[0], current_lane_y)
        else:
            current_lane_x = self.vertical_x - self.LANE_OFFSET if start_pos[0] < self.vertical_x else self.vertical_x + self.LANE_OFFSET
            start_road = (current_lane_x, start_pos[1])

        # Build the path
        if is_start_horiz == is_end_horiz:
            if is_start_horiz:

                # Horizontal to Horizontal 
                current_offset = start_road[1] - self.horizontal_y
                target_offset  = target_lane_y - self.horizontal_y
                target_dir = 1 if target_offset > 0 else -1   # +1 east (bottom lane), -1 west (top lane)

                far_east = self.map_width - 50
                far_west = 50
                opposite_lane_y = self.horizontal_y - target_offset

                if current_offset == target_offset:
                    # Already on the destination's lane
                    if (target_dir > 0 and start_road[0] <= end_road[0]) or \
                       (target_dir < 0 and start_road[0] >= end_road[0]):
                        return [(end_road[0], start_road[1])]
                    # Same lane, destination is behind then full loop
                    if target_dir > 0:
                        return [
                            (far_east, start_road[1]), # Drive to far east
                            (far_east, opposite_lane_y), # Cross over to opposite lane
                            (far_west, opposite_lane_y), # Drive back to far west
                            (far_west, start_road[1]), # Cross over to original lane
                            (end_road[0], start_road[1]), # Arrive at destination
                        ]
                    else:
                        return [
                            (far_west, start_road[1]),
                            (far_west, opposite_lane_y),
                            (far_east, opposite_lane_y),
                            (far_east, start_road[1]),
                            (end_road[0], start_road[1]),
                        ]
                else:
                    # Opposite lane then one U-turn at the far bound
                    if target_dir > 0:
                        return [
                            (far_west, start_road[1]),
                            (far_west, target_lane_y),
                            (end_road[0], target_lane_y),
                        ]
                    else:
                        return [
                            (far_east, start_road[1]),
                            (far_east, target_lane_y),
                            (end_road[0], target_lane_y),
                        ]