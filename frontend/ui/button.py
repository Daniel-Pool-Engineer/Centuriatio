"""clickable button widget used inside the menu bars"""

from __future__ import annotations

from collections.abc import Callable

import pygame


Color = tuple[int, int, int]


class Button:
    """a rounded button that runs a callback when clicked"""
    """Sets up the button's text, colors, font, and starting state."""
    def __init__(
        self,
        label: str,
        on_click: Callable[[], None] | None = None,
        *,
        background: Color = (245, 245, 250),
        hover_background: Color = (220, 226, 255),
        pressed_background: Color = (190, 200, 250),
        active_background: Color = (127, 83, 246),
        disabled_background: Color = (200, 200, 200),
        border: Color = (127, 83, 246),
        text_color: Color = (0, 0, 0),
        active_text_color: Color = (255, 255, 255),
        disabled_text_color: Color = (120, 120, 120),
        font_size: int = 22,
    ) -> None:
        self.label = label
        self.on_click = on_click
        self.background = background
        self.hover_background = hover_background
        self.pressed_background = pressed_background
        self.active_background = active_background
        self.disabled_background = disabled_background
        self.border = border
        self.text_color = text_color
        self.active_text_color = active_text_color
        self.disabled_text_color = disabled_text_color
        self.font = pygame.font.Font(None, font_size)
        self.rect = pygame.Rect(0, 0, 0, 0)

        self.is_hovered = False
        self.is_pressed = False
        self.is_active = False  # stays highlighted, e.g. the selected disruption
        self.enabled = True

    def handle_event(self, event: pygame.event.Event) -> bool:
        """update button state, returns True if the event was used by this button"""
        if not self.enabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == pygame.BUTTON_LEFT:
            if self.rect.collidepoint(event.pos):
                self.is_pressed = True
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == pygame.BUTTON_LEFT:
            was_pressed = self.is_pressed
            self.is_pressed = False
            # only count a click if the mouse is released over the same button
            if was_pressed and self.rect.collidepoint(event.pos):
                if self.on_click is not None:
                    self.on_click()
                return True

        return False

    def draw(self, surface: pygame.Surface) -> None:
        """draw the button with a color that reflects its current state"""
        if not self.enabled:
            background = self.disabled_background
            text_color = self.disabled_text_color
        elif self.is_pressed:
            background = self.pressed_background
            text_color = self.text_color
        elif self.is_active:
            background = self.active_background
            text_color = self.active_text_color
        elif self.is_hovered:
            background = self.hover_background
            text_color = self.text_color
        else:
            background = self.background
            text_color = self.text_color

        pygame.draw.rect(surface, background, self.rect, border_radius=8)
        pygame.draw.rect(surface, self.border, self.rect, width=2, border_radius=8)

        label = self.font.render(self.label, True, text_color)
        surface.blit(label, label.get_rect(center=self.rect.center))