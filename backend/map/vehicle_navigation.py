from __future__ import annotations
from frontend.village.map import VillageMap

Point = tuple[float, float]

class VehicleNetwork:
    #purpose: finds driving routes for vehicles

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
        x,y = pos
        is_horizontal = abs(y - self.horizontal_y) < abs(x - self.vertical_x)

        if is_horizontal:
            lane_y = self.horizontal_y
            if target_pos is not None:
                tx, ty = target_pos
                # Bottom lane if moving right, Top lane if moving left
                lane_y += self.LANE_OFFSET if tx >= x else -self.LANE_OFFSET
            else:
                lane_y += self.LANE_OFFSET
            return (x, lane_y)
        else:
            lane_x = self.vertical_x
            if target_pos is not None:
                tx, ty = target_pos
                # Right lane if moving down, Left lane if moving up
                lane_x += self.LANE_OFFSET if ty >= y else -self.LANE_OFFSET
            else:
                lane_x += self.LANE_OFFSET
            return (lane_x, y)

    def route(self, start_pos: Point, end_pos: Point) -> list[Point]:

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
                            (far_east, start_road[1]),
                            (far_east, opposite_lane_y),
                            (far_west, opposite_lane_y),
                            (far_west, start_road[1]),
                            (end_road[0], start_road[1]),
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
            else:
                # Vertical to Vertical
                # Note: this part of the code won't be triggered. However, it would be useful for future implementations
                current_offset = start_road[0] - self.vertical_x
                target_offset  = target_lane_x - self.vertical_x
                target_dir = 1 if target_offset > 0 else -1   # +1 south (east lane), -1 north (west lane)

                far_south = self.map_height - 50
                far_north = 50
                opposite_lane_x = self.vertical_x - target_offset

                if current_offset == target_offset:
                    # Already on the destination's lane
                    if (target_dir > 0 and start_road[1] <= end_road[1]) or \
                       (target_dir < 0 and start_road[1] >= end_road[1]):
                        return [(start_road[0], end_road[1])]
                    # Same lane, destination is behind then full loop
                    if target_dir > 0:
                        return [
                            (start_road[0], far_south),
                            (opposite_lane_x, far_south),
                            (opposite_lane_x, far_north),
                            (start_road[0], far_north),
                            (start_road[0], end_road[1]),
                        ]
                    else:
                        return [
                            (start_road[0], far_north),
                            (opposite_lane_x, far_north),
                            (opposite_lane_x, far_south),
                            (start_road[0], far_south),
                            (start_road[0], end_road[1]),
                        ]
                else:
                    # Opposite lane then one U-turn at the far bound
                    if target_dir > 0:
                        return [
                            (start_road[0], far_north),
                            (target_lane_x, far_north),
                            (target_lane_x, end_road[1]),
                        ]
                    else:
                        return [
                            (start_road[0], far_south),
                            (target_lane_x, far_south),
                            (target_lane_x, end_road[1]),
                        ]
        else:
            # Turning at intersection
            if is_start_horiz and not is_end_horiz:
                direction_x = 1 if self.vertical_x >= start_road[0] else -1
                expected_y = self.horizontal_y + (self.LANE_OFFSET * direction_x)
                
                current_lane_offset = start_road[1] - self.horizontal_y
                if abs(current_lane_offset - (self.LANE_OFFSET * direction_x)) > 1:
                    turn_x = max(start_road[0], self.map_width - 50) if current_lane_offset > 0 else min(start_road[0], 50)
                    return [
                        (turn_x, start_road[1]),
                        (turn_x, expected_y),
                        (end_road[0], expected_y),
                        (end_road[0], end_road[1])
                    ]
                return [(end_road[0], expected_y), (end_road[0], end_road[1])]
            else:
                direction_y = 1 if self.horizontal_y >= start_road[1] else -1
                expected_x = self.vertical_x + (self.LANE_OFFSET * direction_y)
                
                current_lane_offset = start_road[0] - self.vertical_x
                if abs(current_lane_offset - (self.LANE_OFFSET * direction_y)) > 1:
                    turn_y = max(start_road[1], self.map_height - 50) if current_lane_offset > 0 else min(start_road[1], 50)
                    return [
                        (start_road[0], turn_y),
                        (expected_x, turn_y),
                        (expected_x, end_road[1]),
                        (end_road[0], end_road[1])
                    ]
                return [(expected_x, end_road[1]), (end_road[0], end_road[1])]

