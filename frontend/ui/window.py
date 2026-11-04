from dataclasses import dataclass
from enum import Enum, auto
from math import hypot
from pathlib import Path

import pygame

# backend imports
from backend.agent.daynight import Clock
from backend.agent.agent import VillagerContext
from backend.simulation_state import WorldState
from backend.simulation_loop import BackendSimulation

# frontend imports
from frontend.ui.app_menu import MenuPanel
from frontend.ui.menu_bars import BottomMenuBar, RightMenuBar
from frontend.village.map import create_test_map
from frontend.village.renderer import VillageMapRenderer
from frontend.village.villagers import Villager, VillagerManager

pygame.init()


class AppState(Enum):
    MAIN_MENU = auto()
    RUNNING = auto()


class OverlayState(Enum):
    NONE = auto()
    SETTINGS = auto()
    PAUSE_MENU = auto()
    CONFIRM_EXIT = auto()


# The LLM needs the keys in .env; without them villagers use their fallback actions.
try:
    from backend.agent.client import LLMClient
    llm_client = LLMClient()
except Exception as exc:
    print(f"LLM not available; villagers will use fallback actions: {exc}")
    llm_client = None

OUTAGE_DURATION_DAYS = 3        # fixed for now, a duration selector can replace this later
OUTAGE_AREA = "whole village"
VILLAGER_DECISION_COOLDOWN = 5.0

world_state = WorldState()
backend_sim = BackendSimulation(world_state, llm_client)
backend_started = False

village_map = create_test_map()

screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
icon_path = Path(__file__).resolve().parent.parent / "assets" / "Icon.png"
pygame.display.set_icon(pygame.image.load(icon_path).convert_alpha())
pygame.display.set_caption("Centuriatio")

renderer = VillageMapRenderer()

clock = pygame.time.Clock()   # frame timer (60 FPS)
sim_clock = Clock()           # in-game day/night clock from the backend
is_panning = False
last_mouse_position: tuple[int, int] | None = None
MAX_ZOOM = 1.0
ZOOM_STEP = 1.1
info_font = pygame.font.Font(None, 20)
app_state = AppState.MAIN_MENU
overlay_state = OverlayState.NONE
settings_return_overlay = OverlayState.NONE
confirm_return_overlay = OverlayState.PAUSE_MENU
app_running = True
show_grid = True
show_labels = True

# the disruption currently injected into the village (None = normal day)
active_disruption: str | None = None
outage_start_day = 1  # in-game day the outage started on

right_menu = RightMenuBar()
villagers = VillagerManager(village_map, llm_client=llm_client)

selected_villager_id: str | None = None


@dataclass(frozen=True)
class VillagerPresentation:
    villager: Villager
    role: str
    screen_position: tuple[int, int]
    radius: int

    @property
    def villager_id(self) -> str:
        return self.villager.agent_id


def outage_day() -> int:
    # 1 on the day the outage started
    return sim_clock.day_number - outage_start_day + 1


def period_label() -> str:
    # e.g. "Normal Day 1" or "Outage Night 2"
    if active_disruption == "Power Outage":
        return f"Outage {sim_clock.day_night} {outage_day()}"
    return f"Normal {sim_clock.day_night} {sim_clock.day_number}"


def log(text: str) -> None:
    # add a line to the journal with the in-game time
    right_menu.add_entry(f"[{sim_clock.get_time()}] {text}")


def log_period() -> None:
    # add a header when a new period starts
    right_menu.add_entry(f"--- {period_label()} ---")


def handle_disruption(name: str, is_active: bool) -> None:
    # called by the X-Factor menu when a disruption starts or ends
    global active_disruption, outage_start_day
    if is_active:
        active_disruption = name
        outage_start_day = sim_clock.day_number
        log_period()
        log(f"X-Factor injected: {name}")
    else:
        log(f"{name} has ended")
        active_disruption = None
        log_period()

    if name == "Power Outage":
        # Villagers log their own departure individually
        for message in villagers.set_power_outage(is_active):
            log(message)
        for villager in villagers.villagers:
            if villager.agent is not None:
                villager.decision_cooldown = 0.0
        if not is_active:
            log("Power restored, villagers go back to their routine")


def reset_simulation() -> None:
    # start everything over from Normal Day 1
    global villagers, active_disruption, selected_villager_id
    sim_clock.reset()
    villagers = VillagerManager(village_map, llm_client=llm_client)
    selected_villager_id = None
    active_disruption = None
    bottom_menu.clear_disruption()
    right_menu.clear()
    log_period()
    log("Simulation started")


def handle_control(name: str) -> None:
    # called by the Freeze / Speed / Reset buttons
    if name == "freeze":
        sim_clock.control_pause()
    elif name == "speed":
        sim_clock.speedup(2 if sim_clock.speed == 1 else 1)
    elif name == "reset":
        reset_simulation()
    bottom_menu.set_control_state(sim_clock.paused, sim_clock.speed)


bottom_menu = BottomMenuBar(on_disruption=handle_disruption, on_control=handle_control)


def start_simulation() -> None:
    global app_state, backend_started
    if not backend_started:
        # Keep the worker idle until the user actually starts the simulation.
        backend_sim.start()
        backend_started = True
    reset_simulation()
    app_state = AppState.RUNNING


def toggle_pause() -> None:
    global overlay_state
    if not sim_clock.paused:
        sim_clock.paused = True
    else:
        sim_clock.paused = False
        overlay_state = OverlayState.NONE
    bottom_menu.set_control_state(sim_clock.paused, sim_clock.speed)


def open_settings() -> None:
    global overlay_state, settings_return_overlay
    settings_return_overlay = overlay_state
    overlay_state = OverlayState.SETTINGS


def return_from_settings() -> None:
    global overlay_state
    overlay_state = settings_return_overlay


def request_exit() -> None:
    global overlay_state, confirm_return_overlay
    confirm_return_overlay = overlay_state
    overlay_state = OverlayState.CONFIRM_EXIT


def cancel_exit() -> None:
    global overlay_state
    overlay_state = confirm_return_overlay


def quit_application() -> None:
    global app_running
    app_running = False


def toggle_grid() -> None:
    global show_grid
    show_grid = not show_grid
    settings_menu.buttons[0].label = f"Show Grid: {'On' if show_grid else 'Off'}"


def toggle_labels() -> None:
    global show_labels
    show_labels = not show_labels
    settings_menu.buttons[1].label = f"Building Labels: {'On' if show_labels else 'Off'}"


main_menu = MenuPanel(
    "Centuriatio",
    [("Start Simulation", start_simulation), ("Settings", open_settings), ("Quit", quit_application)],
    "A village simulation",
)
pause_menu = MenuPanel(
    "Paused",
    [("Resume", toggle_pause), ("Settings", open_settings), ("End Simulation", request_exit)],
)
settings_menu = MenuPanel(
    "Settings",
    [
        (f"Show Grid: {'On' if show_grid else 'Off'}", toggle_grid),
        (f"Building Labels: {'On' if show_labels else 'Off'}", toggle_labels),
        ("Back", return_from_settings),
    ],
)
exit_menu = MenuPanel(
    "End Simulation?",
    [("End Simulation", quit_application), ("Cancel", cancel_exit)],
    "The current simulation will end.",
)


def resize_menus() -> None:
    # keep menu bars proportional when the window changes size
    size = screen.get_size()
    right_menu.resize(size)
    bottom_menu.resize(size, right_edge=right_menu.rect.left)


def map_view_size() -> tuple[int, int]:
    """return the unobstructed viewport size above and left of the menus"""
    return max(1, right_menu.rect.left), max(1, bottom_menu.rect.top)


def minimum_zoom() -> float:
    """fit the map's horizontal boundaries to the unobstructed viewport"""
    viewport_width, _ = map_view_size()
    map_width, _ = village_map.world_size
    return viewport_width / map_width


def clamp_camera() -> None:
    """keep the map within the unobstructed viewport at the current zoom"""
    min_zoom = minimum_zoom()
    renderer.set_zoom(min(max(renderer.zoom, min_zoom), max(MAX_ZOOM, min_zoom)))
    viewport_width, viewport_height = map_view_size()
    map_width, map_height = village_map.world_size
    visible_width = viewport_width / renderer.zoom
    visible_height = viewport_height / renderer.zoom
    if visible_width >= map_width:
        camera_x = (map_width - visible_width) / 2
    else:
        camera_x = min(max(renderer.camera_x, 0.0), map_width - visible_width)
    if visible_height >= map_height:
        camera_y = (map_height - visible_height) / 2
    else:
        camera_y = min(max(renderer.camera_y, 0.0), map_height - visible_height)
    renderer.set_camera(
        camera_x,
        camera_y,
    )


def center_camera() -> None:
    """center the map within the unobstructed viewport"""
    viewport_width, viewport_height = map_view_size()
    map_width, map_height = village_map.world_size
    renderer.set_camera(
        (map_width - viewport_width / renderer.zoom) / 2,
        (map_height - viewport_height / renderer.zoom) / 2,
    )
    clamp_camera()


def zoom_at(position: tuple[int, int], direction: int) -> None:
    """zoom around a screen position while keeping its world location fixed"""
    old_zoom = renderer.zoom
    new_zoom = old_zoom * (ZOOM_STEP if direction > 0 else 1 / ZOOM_STEP)
    min_zoom = minimum_zoom()
    new_zoom = min(max(new_zoom, min_zoom), max(MAX_ZOOM, min_zoom))
    if new_zoom == old_zoom:
        return

    mouse_x, mouse_y = position
    world_x = renderer.camera_x + mouse_x / old_zoom
    world_y = renderer.camera_y + mouse_y / old_zoom
    renderer.set_zoom(new_zoom)
    renderer.set_camera(
        world_x - mouse_x / new_zoom,
        world_y - mouse_y / new_zoom,
    )
    clamp_camera()

_overlay_surface = None

def draw_overlay(alpha: int) -> None:
    global _overlay_surface
    if _overlay_surface is None or _overlay_surface.get_size() != screen.get_size():
        _overlay_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    
    _overlay_surface.fill((10, 15, 40, alpha))
    screen.blit(_overlay_surface, (0, 0))


def update_agents(sim_dt: float) -> None:
    for villager in villagers.villagers:
        villager.decision_cooldown = max(0.0, villager.decision_cooldown - sim_dt)

    # Process results from the backend AI, the output of the batch system
    with world_state.lock:
        if world_state.is_data_ready:
            for v_id, action in world_state.new_actions.items():
                villager = villagers.get_villager(v_id)
                if villager is None:
                    continue

                print(f"{villager.name}: {action.action} -> {action.target_location}")
                if action.journal:
                    log(f"{villager.name}: {action.journal}")

                villager.previous_action = action.action
                villager.current_task = action.action.replace("_", " ").title()
                if action.target_location:
                    destination = action.target_location.replace("_", " ").title()
                    villager.current_task = f"{villager.current_task} - {destination}"

                if action.target_location and action.target_location != villager.location_id:
                    try:
                        villagers.send_to(villager, action.target_location)
                        villager.wait_time = 999.0
                    except (ValueError, KeyError) as exc:
                        print(f"  route failed for {villager.name}: {exc}")
                        villager.wait_time = 5.0
                elif (
                    villager.agent is not None
                    and villager.agent.profile.role == "first_responder"
                    and villager.location_id != "school"
                ):
                    choices = [b for b in villagers.buildings if b != villager.location_id]
                    next_patrol = villagers.rng.choice(choices)
                    try:
                        villagers.send_to(villager, next_patrol)
                        villager.wait_time = 999.0
                    except (ValueError, KeyError) as exc:
                        print(f"  route failed for {villager.name}: {exc}")
                        villager.wait_time = 5.0
                else:
                    villager.wait_time = 5.0
            
            world_state.is_data_ready = False
            world_state.new_actions.clear()

    if sim_clock.paused:
        return

    for villager in villagers.villagers:
        if villager.is_scripted or villager.agent is None:
            continue
        if (
            not villager.is_walking
            and villager.wait_time <= 0
            and villager.decision_cooldown <= 0
        ):
            if not backend_sim.is_queued(villager.agent_id):
                outage = active_disruption == "Power Outage"
                ctx = VillagerContext(
                    villager_id=villager.agent_id, 
                    name=villager.name, 
                    location_id=villager.location_id or "unknown",
                    day=sim_clock.day_number, 
                    phase=sim_clock.day_night.lower(),
                    crisis_active=outage, 
                    crisis_day=outage_day() if outage else 0,
                    crisis_duration=OUTAGE_DURATION_DAYS if outage else 0,
                    crisis_area=OUTAGE_AREA if outage else None,
                    power_on=not outage, 
                    previous_action=villager.previous_action,
                )
                # Send them to the backend queue
                backend_sim.queue_agent(villager.agent_id, villager.agent, ctx)
                villager.wait_time = 999.0
                villager.decision_cooldown = VILLAGER_DECISION_COOLDOWN


def villager_presentations() -> list[VillagerPresentation]:
    presentations = []
    for villager in villagers.villagers:
        role = "NPC" if villager.agent is None else villager.agent.profile.role
        position = renderer.world_to_screen(
            (
                int(villager.position[0] + villager.offset[0]),
                int(villager.position[1] + villager.offset[1]),
            )
        )
        presentations.append(
            VillagerPresentation(villager, role, position, max(5, round(9 * renderer.zoom)))
        )
    return presentations


def villager_at(
    position: tuple[int, int],
    presentations: list[VillagerPresentation] | None = None,
) -> VillagerPresentation | None:
    if bottom_menu.rect.collidepoint(position) or right_menu.rect.collidepoint(position):
        return None

    if presentations is None:
        presentations = villager_presentations()
    for villager in reversed(presentations):
        sprite_x, sprite_y = villager.screen_position
        if hypot(position[0] - sprite_x, position[1] - sprite_y) <= villager.radius + 5:
            return villager
    return None


def draw_villager_info(villager: VillagerPresentation) -> None:
    lines = (
        villager.villager.name,
        f"Role: {villager.role.replace('_', ' ').title()}",
        f"Task: {villager.villager.current_task}",
    )
    padding = 8
    line_height = info_font.get_linesize()
    text_surfaces = [info_font.render(line, True, (245, 246, 250)) for line in lines]
    width = max(text.get_width() for text in text_surfaces) + padding * 2
    height = line_height * len(lines) + padding * 2
    viewport_width, viewport_height = map_view_size()
    width = min(width, max(1, viewport_width - 8))
    height = min(height, max(1, viewport_height - 8))

    sprite_x, sprite_y = villager.screen_position
    left = min(
        max(sprite_x - width // 2, 4),
        viewport_width - width - 4,
    )
    top = min(
        max(sprite_y - villager.radius - height - 8, 4),
        viewport_height - height - 4,
    )
    popup = pygame.Rect(left, top, width, height)
    pygame.draw.rect(screen, (31, 35, 48), popup, border_radius=6)
    pygame.draw.rect(screen, (180, 190, 210), popup, width=1, border_radius=6)
    for index, text in enumerate(text_surfaces):
        screen.blit(text, (left + padding, top + padding + index * line_height))


resize_menus()
center_camera()

while app_running:
    # real seconds since the last frame (also caps the game at 60 FPS)
    dt = clock.tick(60) / 1000

    # Process player inputs.
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            app_running = False
            break
        if event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            resize_menus()
            clamp_camera()
            continue

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if app_state == AppState.MAIN_MENU:
                if overlay_state == OverlayState.SETTINGS:
                    return_from_settings()
            elif overlay_state == OverlayState.NONE:
                sim_clock.paused = True
                bottom_menu.set_control_state(sim_clock.paused, sim_clock.speed)
                overlay_state = OverlayState.PAUSE_MENU
            elif overlay_state == OverlayState.PAUSE_MENU:
                toggle_pause()
            elif overlay_state == OverlayState.SETTINGS:
                return_from_settings()
            elif overlay_state == OverlayState.CONFIRM_EXIT:
                cancel_exit()
            continue

        if app_state == AppState.MAIN_MENU:
            if overlay_state == OverlayState.SETTINGS:
                settings_menu.handle_event(event)
            else:
                main_menu.handle_event(event)
            continue

        if overlay_state == OverlayState.SETTINGS:
            settings_menu.handle_event(event)
            continue
        if overlay_state == OverlayState.PAUSE_MENU:
            pause_menu.handle_event(event)
            continue
        if overlay_state == OverlayState.CONFIRM_EXIT:
            exit_menu.handle_event(event)
            continue

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == pygame.BUTTON_LEFT:
            clicked_villager = villager_at(event.pos)
            selected_villager_id = (
                clicked_villager.villager_id if clicked_villager is not None else None
            )
            over_menu = (
                bottom_menu.rect.collidepoint(event.pos)
                or right_menu.rect.collidepoint(event.pos)
            )
            if clicked_villager is None and not over_menu:
                is_panning = True
                last_mouse_position = event.pos
        if event.type == pygame.MOUSEBUTTONUP and event.button == pygame.BUTTON_LEFT:
            is_panning = False
            last_mouse_position = None
        if event.type == pygame.MOUSEMOTION and is_panning and last_mouse_position is not None:
            previous_x, previous_y = last_mouse_position
            mouse_x, mouse_y = event.pos
            renderer.set_camera(
                renderer.camera_x - (mouse_x - previous_x) / renderer.zoom,
                renderer.camera_y - (mouse_y - previous_y) / renderer.zoom,
            )
            clamp_camera()
            last_mouse_position = event.pos

        if event.type == pygame.MOUSEWHEEL:
            mouse_position = pygame.mouse.get_pos()
            over_menu = (
                bottom_menu.rect.collidepoint(mouse_position)
                or right_menu.rect.collidepoint(mouse_position)
            )
            if not over_menu:
                zoom_at(mouse_position, event.y)

        bottom_menu.handle_event(event)
        right_menu.handle_event(event)

    # Do logical updates here.
    if app_state == AppState.RUNNING and not sim_clock.paused:
        # Advance the clock and villagers only while the simulation is active.
        for phase, _day in sim_clock.update(dt):
            villagers.set_night(phase == "Night")
            for villager in villagers.villagers:
                if villager.agent is not None:
                    villager.decision_cooldown = 0.0
            log_period()
            log("Night falls, villagers head home" if phase == "Night" else "Morning, villagers start their day")

        sim_dt = dt * sim_clock.speed
        for message in villagers.update(sim_dt):
            log(message)
        update_agents(sim_dt)

    status = f"{period_label()}  ·  {sim_clock.get_time()}"
    if sim_clock.paused and overlay_state == OverlayState.NONE:
        status += "  ·  Frozen"
    elif sim_clock.paused:
        status += "  ·  Paused"
    bottom_menu.set_status(status)

    # Render the graphics here.
    if app_state == AppState.RUNNING:
        renderer.draw(
            screen,
            village_map,
            show_grid=show_grid,
            show_labels=show_labels,
        )
        if sim_clock.day_night == "Night":
            draw_overlay(90)
        if active_disruption == "Power Outage":
            draw_overlay(140)
        villagers.draw(screen, renderer)
        villager_views = villager_presentations()
        hovered_villager = villager_at(pygame.mouse.get_pos(), villager_views)
        selected_villager = next(
            (
                villager
                for villager in villager_views
                if villager.villager_id == selected_villager_id
            ),
            None,
        )
        info_villager = selected_villager or hovered_villager
        if info_villager is not None:
            draw_villager_info(info_villager)
        right_menu.draw(screen)
        bottom_menu.draw(screen)

        if overlay_state != OverlayState.NONE:
            draw_overlay(150)

        if overlay_state == OverlayState.PAUSE_MENU:
            pause_menu.draw(screen)
        elif overlay_state == OverlayState.SETTINGS:
            settings_menu.draw(screen)
        elif overlay_state == OverlayState.CONFIRM_EXIT:
            exit_menu.draw(screen)
    else:
        screen.fill((20, 24, 34))
        if overlay_state == OverlayState.SETTINGS:
            settings_menu.draw(screen)
        else:
            main_menu.draw(screen)

    pygame.display.flip()  # Refresh on-screen display

pygame.quit()