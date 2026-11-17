# static village-map data and the coordinate system used by the game world

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


CELL_SIZE = 16
"""world units per map cell"""

DEFAULT_MAP_CELLS = (200, 150)
# width and height of the starter map in cells

Point = tuple[int, int]
Rect = tuple[int, int, int, int]
RoadType = Literal["main", "local"]
BuildingType = Literal["house", "apartment", "shop", "office", "public"]


@dataclass
class Grid:

    width: int
    height: int
    cell_size: int = CELL_SIZE
    left: int = 0
    top: int = 0
    grid: list[list[int]] = field(init=False)

    def __post_init__(self) -> None:
        # Checks the grid size and create the empty grid.
        if self.width <= 0 or self.height <= 0:
            raise ValueError("grid dimensions must be positive")
        if self.cell_size <= 0:
            raise ValueError("cell size must be positive")
        self.grid = [[0] * self.width for _ in range(self.height)]

    @property
    def world_size(self) -> tuple[int, int]:
        """return the grid dimensions in world units"""
        return self.width * self.cell_size, self.height * self.cell_size

    def set_view(self, left: int, top: int, cell_size: int) -> None:
        """set the grid's display offset and visual cell size"""
        if cell_size <= 0:
            raise ValueError("Cell size must be positive")
        self.left = left
        self.top = top
        self.cell_size = cell_size

    def cell_to_world(self, cell: Point) -> Point:
        """convert a cell coordinate to the cell's top-left world position"""
        x, y = cell
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError(f"Cell is outside the grid: {cell}")
        return x * self.cell_size, y * self.cell_size


@dataclass(frozen=True)
class Road:
    """a static road segment represented by a world-space rectangle"""
    id: str
    bounds: Rect
    road_type: RoadType


@dataclass(frozen=True)
class Sidewalk:
    """a walkable sidewalk segment and its neighboring segments"""
    id: str
    bounds: Rect
    connections: tuple[str, ...] = ()


@dataclass(frozen=True)
class Building:
    """a building footprint connected to the pedestrian network by an entrance"""
    id: str
    building_type: BuildingType
    bounds: Rect
    entrance: Point
    sidewalk_id: str
    capacity: int = 1

    @property
    def display_name(self) -> str:
        # Makes the building ID easier to read on the screen.
        return self.id.replace("_", " ").title()


@dataclass
class VillageMap:
    """the static world consumed by rendering and simulation systems"""
    grid: Grid
    roads: list[Road] = field(default_factory=list)
    sidewalks: list[Sidewalk] = field(default_factory=list)
    buildings: list[Building] = field(default_factory=list)
    villager_spawn: Point = (0, 0)

    @property
    def world_size(self) -> tuple[int, int]:
        # Gets the total map size from the grid.
        return self.grid.world_size

    def sidewalk(self, sidewalk_id: str) -> Sidewalk:
        """return a sidewalk by ID or raise a useful error"""
        for sidewalk in self.sidewalks:
            if sidewalk.id == sidewalk_id:
                return sidewalk
        raise KeyError(f"Unknown sidewalk: {sidewalk_id}")

    def building(self, building_id: str) -> Building:
        # return a building by ID or raise a useful error
        for building in self.buildings:
            if building.id == building_id:
                return building
        raise KeyError(f"Unknown building: {building_id}")

    def validate(self) -> None:
        # Checks that all map objects have valid positions and connections.
        sidewalk_ids = {sidewalk.id for sidewalk in self.sidewalks}
        building_ids = {building.id for building in self.buildings}
        if len(building_ids) != len(self.buildings):
            raise ValueError("Building IDs must be unique")
        if len(sidewalk_ids) != len(self.sidewalks):
            raise ValueError("Sidewalk IDs must be unique")

        map_width, map_height = self.world_size

        def is_inside(bounds: Rect) -> bool:
            x, y, width, height = bounds
            return (
                x >= 0
                and y >= 0
                and x + width <= map_width
                and y + height <= map_height
            )

        for road in self.roads:
            if not is_inside(road.bounds):
                raise ValueError(f"Road {road.id} extends outside the map")

        for sidewalk in self.sidewalks:
            if not is_inside(sidewalk.bounds):
                raise ValueError(f"Sidewalk {sidewalk.id} extends outside the map")
            unknown = set(sidewalk.connections) - sidewalk_ids
            if unknown:
                raise ValueError(
                    f"Sidewalk {sidewalk.id} references unknown segments: {unknown}"
                )
            for conn in sidewalk.connections:
                if sidewalk.id not in self.sidewalk(conn).connections:
                    raise ValueError(
                        f"Sidewalk {sidewalk.id} connects to {conn} but not vice versa"
                    )

        for building in self.buildings:
            if not is_inside(building.bounds):
                raise ValueError(f"Building {building.id} extends outside the map")
            if building.sidewalk_id not in sidewalk_ids:
                raise ValueError(
                    f"Building {building.id} references unknown sidewalk "
                    f"{building.sidewalk_id}"
                )
            if building.capacity <= 0:
                raise ValueError(f"Building {building.id} must have capacity")


def create_test_map() -> VillageMap:
    # Creates the starter village with roads, sidewalks, and buildings.
    village_map = VillageMap(
        grid=Grid(*DEFAULT_MAP_CELLS),
        roads=[
            Road("main-east-west", (0, 1104, 3200, 128), "main"),
            Road("main-north-south", (1488, 0, 128, 2400), "main"),
        ],
        sidewalks=[
            Sidewalk("northwest-main", (0, 1048, 1488, 48), ("north-west", "crosswalk-north")),
            Sidewalk("northeast-main", (1616, 1048, 1584, 48), ("north-east", "crosswalk-north")),
            Sidewalk("southwest-main", (0, 1240, 1488, 48), ("south-west", "crosswalk-south")),
            Sidewalk("southeast-main", (1616, 1240, 1584, 48), ("south-east", "crosswalk-south")),
            Sidewalk("north-west", (1432, 0, 48, 1096), ("northwest-main", "crosswalk-west")),
            Sidewalk("north-east", (1624, 0, 48, 1096), ("northeast-main", "crosswalk-east")),
            Sidewalk("south-west", (1432, 1240, 48, 1160), ("southwest-main", "crosswalk-west")),
            Sidewalk("south-east", (1624, 1240, 48, 1160), ("southeast-main", "crosswalk-east")),
            Sidewalk("crosswalk-north", (1488, 1048, 128, 48), ("northwest-main", "northeast-main")),
            Sidewalk("crosswalk-south", (1488, 1240, 128, 48), ("southwest-main", "southeast-main")),
            Sidewalk("crosswalk-west", (1432, 1096, 48, 144), ("north-west", "south-west")),
            Sidewalk("crosswalk-east", (1624, 1096, 48, 144), ("north-east", "south-east")),
        ],
        buildings=[
            Building("home_a", "house", (400, 700, 200, 348), (500, 1048), "northwest-main", 4),
            Building("home_b", "apartment", (700, 700, 300, 348), (850, 1048), "northwest-main", 12),
            Building("hospital", "public", (1100, 688, 300, 360), (1250, 1048), "northwest-main", 20),
            Building("police", "public", (1700, 748, 300, 300), (1850, 1048), "northeast-main", 10),
            Building("school", "public", (2100, 668, 400, 380), (2300, 1048), "northeast-main", 30),
            Building("office", "office", (2700, 748, 400, 300), (2900, 1048), "northeast-main", 20),
            Building("fire", "public", (100, 1288, 360, 300), (280, 1288), "southwest-main", 10),
            Building("grocery", "shop", (620, 1288, 340, 320), (790, 1288), "southwest-main", 6),
            Building("electrical", "public", (1700, 1288, 360, 300), (1880, 1288), "southeast-main", 8),
            Building("home_c", "house", (2200, 1288, 280, 360), (2340, 1288), "southeast-main", 4),
            Building("home_d", "house", (2700, 1288, 280, 360), (2840, 1288), "southeast-main", 4),
        ],
        villager_spawn=(500, 1072),
    )
    village_map.validate()
    return village_map