# centered menu panels for application-level screens

from __future__ import annotations

from collections.abc import Callable

import pygame

from frontend.ui.button import Button


class MenuPanel:
    # titled panel with vertically stacked buttons

    def __init__(
        self,
        title: str,
        actions: list[tuple[str, Callable[[], None]]],
        subtitle: str = "",
    ) -> None:
        self.title = title
        self.subtitle = subtitle
        self.title_font = pygame.font.Font(None, 44)
        self.subtitle_font = pygame.font.Font(None, 24)
        self.background = (31, 35, 48)
        self.border = (125, 140, 170)
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.buttons = [
            Button(
                label,
                callback,
                background=(55, 64, 82),
                hover_background=(75, 88, 112),
                pressed_background=(42, 50, 66),
                border=(125, 140, 170),
                text_color=(240, 242, 245),
            )
            for label, callback in actions
        ]

    def draw(self, surface: pygame.Surface) -> None:
        width = min(460, surface.get_width() - 32)
        button_height = 48
        button_gap = 12
        title_height = self.title_font.get_linesize()
        subtitle_height = self.subtitle_font.get_linesize() if self.subtitle else 0
        subtitle_gap = 8 if self.subtitle else 0
        content_height = (
            title_height
            + subtitle_gap
            + subtitle_height
            + 24
            + len(self.buttons) * button_height
            + max(0, len(self.buttons) - 1) * button_gap
        )
        height = min(surface.get_height() - 32, content_height + 48)
        self.rect = pygame.Rect(0, 0, width, height)
        self.rect.center = surface.get_rect().center

        pygame.draw.rect(surface, self.background, self.rect, border_radius=14)
        pygame.draw.rect(surface, self.border, self.rect, width=2, border_radius=14)

        title = self.title_font.render(self.title, True, (245, 246, 250))
        title_rect = title.get_rect(midtop=(self.rect.centerx, self.rect.top + 20))
        surface.blit(title, title_rect)
        y = title_rect.bottom + subtitle_gap

        if self.subtitle:
            subtitle = self.subtitle_font.render(self.subtitle, True, (190, 198, 214))
            subtitle_rect = subtitle.get_rect(midtop=(self.rect.centerx, y))
            surface.blit(subtitle, subtitle_rect)
            y = subtitle_rect.bottom

        y += 24
        button_width = self.rect.width - 64
        for button in self.buttons:
            button.rect = pygame.Rect(
                self.rect.centerx - button_width // 2,
                y,
                button_width,
                button_height,
            )
            button.draw(surface)
            y += button_height + button_gap

    def handle_event(self, event: pygame.event.Event) -> None:
        for button in self.buttons:
            button.handle_event(event)
