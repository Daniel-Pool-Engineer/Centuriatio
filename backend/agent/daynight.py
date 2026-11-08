from typing import Tuple, List

class Clock:
    # 1 min for day, 30 min for night (in seconds)
    day_length = 60
    night_length = 30

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.day_number = 1
        self.day_night = "Day"
        self.time_passed = 0
        self.speed = 1
        self.paused = False

    @property
    def day_night_len(self) -> float:
        if self.day_night == "Day":
            return self.day_length
        else:
            return self.night_length

    def speedup(self, speed: int) -> None:
        # for 1x and 2x
        if speed in (1, 2):
            self.speed = speed

    def control_pause(self) -> None:
        self.paused = not self.paused

    def update(self, real_sec: float) -> List[Tuple[str, int]]:
        if self.paused:
            return []

        self.time_passed += real_sec*self.speed
        days_passed = []

        while self.time_passed >= self.day_night_len:
            self.time_passed -= self.day_night_len

            if self.day_night == "Day":
                self.day_night = "Night"
            else:
                self.day_night = "Day"
                self.day_number += 1
            days_passed.append((self.day_night, self.day_number))

        return days_passed

    def get_time(self) -> str:
        if self.day_night == "Day":
            start = 6 * 60
        else:
            start = 18 * 60

        progress = self.time_passed / self.day_night_len
        passed = int(progress * 12 * 60)
        minutes = start + passed
        if minutes >= 24*60:
            minutes -= 24*60
        
        hours = minutes // 60
        left_over_min = minutes % 60
        
        return f"{hours:02d}:{left_over_min:02d}"
