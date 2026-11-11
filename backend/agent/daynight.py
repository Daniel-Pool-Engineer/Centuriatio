from typing import Tuple, List

class Clock:
    """ Manages the simulation time and tracks the Day/Night cycle."""

    # 1 min for day, 30 min for night (in seconds)
    day_length = 60
    night_length = 30

    def __init__(self) -> None:
        self.reset()


    def reset(self) -> None:
        # Restore the clock to the start of the simulation
        self.day_number = 1
        self.day_night = "Day"
        self.time_passed = 0
        self.speed = 1
        self.paused = False


    @property
    def day_night_len(self) -> float:
        # Helper to get the duration of the current phase.
        if self.day_night == "Day":
            return self.day_length
        else:
            return self.night_length


    def speedup(self, speed: int) -> None:
        # Changes the simulation speed. Only options are: 1x and 2x
        if speed in (1, 2):
            self.speed = speed


    def control_pause(self) -> None:
        # Toggle the paused state.
        self.paused = not self.paused


    def update(self, real_sec: float) -> List[Tuple[str, int]]:
        # Advanced the clock. Returns a list of phase changes that occurred during this frame.
        if self.paused:
            return []

        self.time_passed += real_sec*self.speed
        days_passed = []

        # Loop in case the elapsed time crosses multiple phase boundaries at once.
        while self.time_passed >= self.day_night_len:
            self.time_passed -= self.day_night_len

            # Swap between Day and Night.
            if self.day_night == "Day":
                self.day_night = "Night"
            else:
                self.day_night = "Day"
                self.day_number += 1

            # Log the new phase and day number.
            days_passed.append((self.day_night, self.day_number))

        return days_passed


    def get_time(self) -> str:
        # Maps the internal time progression to a 24-hour clock format for the UI
        # Day starts at 06:00, Night starts at 18:00.
        if self.day_night == "Day":
            start = 6 * 60
        else:
            start = 18 * 60

        # Calculate how much time has passed within the current phase.
        progress = self.time_passed / self.day_night_len
        passed = int(progress * 12 * 60)
        minutes = start + passed
        if minutes >= 24*60:
            minutes -= 24*60

        # Wrap aroung midnight.
        hours = minutes // 60
        left_over_min = minutes % 60

        return f"{hours:02d}:{left_over_min:02d}"
