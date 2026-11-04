"""floating menu bars rendered on top of the application surface"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from frontend.ui.button import Button


Color = tuple[int, int, int]

# only one x-factor for now, add more names here later if needed
DEFAULT_DISRUPTIONS: tuple[str, ...] = ("Power Outage",)


class FloatingMenuBar:
    """base class for a rounded menu bar"""

    def __init__(
        self,
        *,
        background: Color = (31, 35, 48),
        border: Color = (92, 101, 125),
        text_color: Color = (240, 242, 245),
    ) -> None:
        self.background = background
        self.border = border
        self.text_color = text_color
        self.font = pygame.font.Font(None, 24)
        self.rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surface: pygame.Surface) -> None:
        """draw the bar and its labels on the supplied surface"""
        pygame.draw.rect(
            surface,
            self.background,
            self.rect,
            border_radius=12,
        )
        pygame.draw.rect(
            surface,
            self.border,
            self.rect,
            width=2,
            border_radius=12,
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        """handle menu input, subclasses can add interactive controls"""


class BottomMenuBar(FloatingMenuBar):
    """menu bar spanning the bottom fifteen percent of the window"""

    height_ratio = 0.15
    padding = 10
    button_gap = 12
    max_button_width = 170
    max_button_height = 44

    def __init__(
        self,
        on_disruption: Callable[[str, bool], None] | None = None,
        on_control: Callable[[str], None] | None = None,
        disruptions: tuple[str, ...] = DEFAULT_DISRUPTIONS,
    ) -> None:
        super().__init__(
            background=(55, 64, 82),
            border=(125, 140, 170),
        )
        # called as on_disruption(name, is_active) when a disruption starts or ends
        self.on_disruption = on_disruption
        # called as on_control("freeze" | "speed" | "reset")
        self.on_control = on_control
        self.active_disruption: str | None = None
        self.status_text = ""
        self._title_surface = None
        self._status_surface = None
        self._last_status_text = ""

        self.disruption_buttons = [
            Button(name, on_click=lambda name=name: self.toggle_disruption(name))
            for name in disruptions
        ]

        # simulation controls
        self.freeze_button = Button("Freeze", on_click=lambda: self._control("freeze"))
        self.speed_button = Button("Speed 1x", on_click=lambda: self._control("speed"))
        self.reset_button = Button("Reset", on_click=lambda: self._control("reset"))

        self.buttons = [
            *self.disruption_buttons,
            self.freeze_button,
            self.speed_button,
            self.reset_button,
        ]

    def toggle_disruption(self, name: str) -> None:
        """start the clicked disruption, or end it if it is already active"""
        previous = self.active_disruption

        if previous is not None:
            self.active_disruption = None
            self._notify(previous, False)

        if previous != name:
            self.active_disruption = name
            self._notify(name, True)

        for button in self.disruption_buttons:
            button.is_active = button.label == self.active_disruption

    def clear_disruption(self) -> None:
        # turn off the active disruption without sending a notification (used by reset)
        self.active_disruption = None
        for button in self.disruption_buttons:
            button.is_active = False

    def set_control_state(self, paused: bool, speed: int) -> None:
        # update the control button labels to match the clock
        self.freeze_button.label = "Unfreeze" if paused else "Freeze"
        self.speed_button.label = f"Speed {speed}x"

    def set_status(self, text: str) -> None:
        # text shown in the top-left corner, e.g. "Normal Day 1 · 10:30"
        self.status_text = text

    def _control(self, name: str) -> None:
        if self.on_control is not None:
            self.on_control(name)

    def _notify(self, name: str, is_active: bool) -> None:
        if self.on_disruption is not None:
            self.on_disruption(name, is_active)

    def resize(
        self,
        surface_size: tuple[int, int],
        right_edge: int | None = None,
    ) -> None:
        width, height = surface_size
        bar_height = max(1, round(height * self.height_ratio))
        margin = max(8, round(height * 0.015))
        bar_width = width - margin * 2
        if right_edge is not None:
            bar_width = min(bar_width, right_edge - margin * 2)
        self.rect = pygame.Rect(
            margin,
            height - bar_height - margin,
            max(1, bar_width),
            bar_height,
        )
        self._layout_buttons()

    def _layout_buttons(self) -> None:
        """place the buttons in a centered row under the menu title"""
        if not self.buttons:
            return

        title_height = self.font.get_linesize()
        top = self.rect.top + self.padding + title_height
        available_height = self.rect.bottom - self.padding - top
        button_height = max(1, min(self.max_button_height, available_height))

        count = len(self.buttons)
        available_width = self.rect.width - (self.padding * 2)
        button_width = (available_width - self.button_gap * (count - 1)) / count
        button_width = max(1, min(self.max_button_width, int(button_width)))

        row_width = button_width * count + self.button_gap * (count - 1)
        x = self.rect.centerx - row_width // 2
        y = top + (available_height - button_height) // 2

        for button in self.buttons:
            button.rect = pygame.Rect(x, y, button_width, button_height)
            x += button_width + self.button_gap

    def handle_event(self, event: pygame.event.Event) -> None:
        for button in self.buttons:
            button.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)

        if self._title_surface is None:
            self._title_surface = self.font.render("X-Factor menu", True, self.text_color)

        label_rect = self._title_surface.get_rect(
            midtop=(self.rect.centerx, self.rect.top + self.padding // 2)
        )
        surface.blit(self._title_surface, label_rect)

        # day/time status on the left
        if self.status_text:
            if self.status_text != self._last_status_text:
                self._status_surface = self.font.render(self.status_text, True, self.text_color)
                self._last_status_text = self.status_text

                
            surface.blit(self._status_surface, (self.rect.left + self.padding * 2, self.rect.top + self.padding // 2))

        for button in self.buttons:
            button.draw(surface)


class RightMenuBar(FloatingMenuBar):
    """menu bar spanning twenty percent of the window along the right edge"""

    width_ratio = 0.20
    padding = 12
    entry_gap = 6

    def __init__(self, max_entries: int = 100) -> None:
        super().__init__(
            background=(55, 64, 82),
            border=(125, 140, 170),
        )
        self.entry_font = pygame.font.Font(None, 20)
        self.max_entries = max_entries
        self.entries: list[str] = []  # newest entry first

        self._title_surface = None
        self._entry_cache: dict [ str, pygame.Surface] ={}
        self.scroll_offset = 0
        self._max_scroll_offset = 0
        self._scrollbar_drag_offset: int | None = None
        self._scrollbar_track = pygame.Rect(0, 0, 0, 0)
        self._scrollbar_thumb = pygame.Rect(0, 0, 0, 0)

    def add_entry(self, text: str) -> None:
        """add a line to the bottom of the villager journal"""
        appended_height = self._entry_height(text)
        self.entries.append(text)
        removed_height = 0
        # Remove the oldest entry if we exceed the max
        if len(self.entries) > self.max_entries:
            removed_height = self._entry_height(self.entries.pop(0))
        height_change = appended_height - removed_height
        self._max_scroll_offset = max(0, self._max_scroll_offset + height_change)
        if self.scroll_offset > 0:
            self.scroll_offset += appended_height
            self.scroll_offset = min(self.scroll_offset, self._max_scroll_offset)

    def clear(self) -> None:
        # remove every journal entry and reset scrolling (used by simulation reset)
        self.entries.clear()
        self._entry_cache.clear()
        self.scroll_offset = 0
        self._max_scroll_offset = 0
        self._scrollbar_drag_offset = None

    def resize(self, surface_size: tuple[int, int]) -> None:
        width, height = surface_size
        bar_width = max(1, round(width * self.width_ratio))
        margin = max(8, round(width * 0.015))
        self.rect = pygame.Rect(
            width - bar_width - margin,
            margin,
            bar_width,
            height - (margin * 2),
        )

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """split text into lines that fit inside max_width pixels"""
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = word if not current else f"{current} {word}"
            if self.entry_font.size(candidate)[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _content_height(self) -> int:
        """Return the total height of all wrapped journal entries."""
        return sum(
            self._entry_height(entry)
            for entry in self.entries
        )

    def _entry_height(self, entry: str) -> int:
        """Measure an entry, including its wrapped lines and trailing gap."""
        text_width = max(1, self.rect.width - self.padding * 2 - 12)
        wrapped = self._wrap_text(entry, text_width)
        return self.entry_font.get_linesize() * len(wrapped) + self.entry_gap

    def handle_event(self, event: pygame.event.Event) -> None:
        """Scroll the journal with the wheel or by dragging its scrollbar."""
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                # Positive offsets reveal older entries above the newest ones.
                self.scroll_offset = min(
                    self._max_scroll_offset,
                    max(
                        0,
                        self.scroll_offset
                        - event.y * self.entry_font.get_linesize() * 3,
                    ),
                )
                return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == pygame.BUTTON_LEFT:
            if self._scrollbar_thumb.collidepoint(event.pos):
                self._scrollbar_drag_offset = event.pos[1] - self._scrollbar_thumb.top
                return
            if self._scrollbar_track.collidepoint(event.pos):
                self._scrollbar_drag_offset = self._scrollbar_thumb.height // 2
                self._move_scrollbar_thumb(event.pos[1])

        elif event.type == pygame.MOUSEBUTTONUP and event.button == pygame.BUTTON_LEFT:
            self._scrollbar_drag_offset = None

        elif event.type == pygame.MOUSEMOTION and self._scrollbar_drag_offset is not None:
            self._move_scrollbar_thumb(event.pos[1])

    def _move_scrollbar_thumb(self, mouse_y: int) -> None:
        """Map the thumb's vertical position to the journal's scroll offset."""
        track_range = self._scrollbar_track.height - self._scrollbar_thumb.height
        if track_range <= 0:
            self.scroll_offset = 0
            return

        thumb_top = min(
            max(mouse_y - (self._scrollbar_drag_offset or 0), self._scrollbar_track.top),
            self._scrollbar_track.bottom - self._scrollbar_thumb.height,
        )
        fraction = (thumb_top - self._scrollbar_track.top) / track_range
        self.scroll_offset = round((1 - fraction) * self._max_scroll_offset)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        
        if self._title_surface is None:
            self._title_surface = self.font.render("Villager Journal", True, self.text_color)
            
        label_rect = self._title_surface.get_rect(
            midtop=(self.rect.centerx, self.rect.top + self.font.get_linesize() // 2)
        )
        surface.blit(self._title_surface, label_rect)

        text_width = self.rect.width - self.padding * 2 - 12
        line_height = self.entry_font.get_linesize()
        start_y = label_rect.bottom + self.padding
        max_y = self.rect.bottom - self.padding
        viewport = pygame.Rect(
            self.rect.left + self.padding,
            start_y,
            max(1, text_width),
            max(1, max_y - start_y),
        )
        
        # 1. Flatten entries into wrapped lines (keeping track of where gaps go)
        all_lines: list[tuple[str, bool]] = []
        for entry in self.entries:
            wrapped = self._wrap_text(entry, text_width)
            for i, line in enumerate(wrapped):
                all_lines.append((line, i == len(wrapped) - 1))

        # 2. Compute the scroll range from the visible area and all journal content.
        content_height = self._content_height()
        self._max_scroll_offset = max(0, content_height - viewport.height)
        self.scroll_offset = min(self.scroll_offset, self._max_scroll_offset)

        # 3. Size the thumb to see which lines fit on screen
        self._scrollbar_track = pygame.Rect(
            self.rect.right - self.padding - 6,
            viewport.top,
            6,
            viewport.height,
        )
        if self._max_scroll_offset:
            thumb_height = max(
                min(18, self._scrollbar_track.height),
                round(self._scrollbar_track.height * viewport.height / content_height),
            )
            thumb_travel = self._scrollbar_track.height - thumb_height
            thumb_top = self._scrollbar_track.top + round(
                thumb_travel
                * (1 - self.scroll_offset / self._max_scroll_offset)
            )
            self._scrollbar_thumb = pygame.Rect(
                self._scrollbar_track.left,
                thumb_top,
                self._scrollbar_track.width,
                thumb_height,
            )
        else:
            self._scrollbar_thumb = self._scrollbar_track.copy()

        previous_clip = surface.get_clip()
        surface.set_clip(viewport)
        # 4. Offset from the bottom so new entries remain visible at scroll position zero.
        y = viewport.bottom - content_height + self.scroll_offset
        for line, is_last in all_lines:
            if line not in self._entry_cache:
                self._entry_cache[line] = self.entry_font.render(line, True, self.text_color)
            
            surface.blit(self._entry_cache[line], (viewport.left, y))
            y += line_height
            if is_last:
                y += self.entry_gap

        surface.set_clip(previous_clip)

        pygame.draw.rect(surface, self.border, self._scrollbar_track, border_radius=3)
        if self._max_scroll_offset:
            pygame.draw.rect(surface, self.text_color, self._scrollbar_thumb, border_radius=3)