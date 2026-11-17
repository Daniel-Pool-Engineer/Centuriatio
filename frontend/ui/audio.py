import pygame
from pathlib import Path

class AudioManager:
    def __init__(self):
        # Load the audio files from the assets folder.
        audio_folder = Path(__file__).resolve().parent.parent / "assets" / "audio"

        self.daytime = pygame.mixer.Sound(str(audio_folder / "daytime_ambience.mp3"))
        self.nighttime = pygame.mixer.Sound(str(audio_folder / "night_ambience.mp3"))
        self.power_outage = pygame.mixer.Sound(str(audio_folder / "power_down.mp3"))
        self.power_restored = pygame.mixer.Sound(str(audio_folder / "power_up.mp3"))

        self.volume_level = "High"
        self.daytime.set_volume(0.5)
        self.nighttime.set_volume(0.5)
        self.power_outage.set_volume(0.6)
        self.power_restored.set_volume(0.5)

        # Use separate channels for background music and sound effects.
        self.ambience_channel = pygame.mixer.Channel(0)
        self.effects_channel = pygame.mixer.Channel(1)

        self.current_ambience = None
        self.enabled = True

    def set_level(self, level):
        # Change the volume level or turn all audio off.
        self.volume_level = level
        self.enabled = level != "Off"

        if level == "High":
            volumes = (0.5, 0.5, 0.6, 0.5)
        elif level == "Low":
            volumes = (0.2, 0.2, 0.25, 0.2)
        else:
            volumes = (0, 0, 0, 0)

        self.daytime.set_volume(volumes[0])
        self.nighttime.set_volume(volumes[1])
        self.power_outage.set_volume(volumes[2])
        self.power_restored.set_volume(volumes[3])

        if not self.enabled:
            self.stop_all()
        elif self.current_ambience == "day":
            self.ambience_channel.stop()
            self.ambience_channel.play(self.daytime, loops=-1)
        elif self.current_ambience == "night":
            self.ambience_channel.stop()
            self.ambience_channel.play(self.nighttime, loops=-1)

    def play_daytime(self):
        # Play the daytime ambience on a loop.
        if self.enabled and self.current_ambience != "day":
            self.ambience_channel.stop()
            self.ambience_channel.play(self.daytime, loops=-1)
            self.current_ambience = "day"

    def play_nighttime(self):
        # Play the nighttime ambience on a loop.
        if self.enabled and self.current_ambience != "night":
            self.ambience_channel.stop()
            self.ambience_channel.play(self.nighttime, loops=-1)
            self.current_ambience = "night"

    def play_power_outage(self):
        # Play the sound when the power goes out.
        if self.enabled:
            self.effects_channel.play(self.power_outage)

    def play_power_restored(self):
        # Play the sound when the power is restored.
        if self.enabled:
            self.effects_channel.play(self.power_restored)

    def stop_all(self):
        # Stop all audio and reset the current ambience.
        self.ambience_channel.stop()
        self.effects_channel.stop()
        self.current_ambience = None