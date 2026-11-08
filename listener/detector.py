"""Turns a stream of scores into clean events.

Rules:
  - A sound must be above its threshold for `hits_needed` windows in a row.
    One loud clap or a single noisy window never fires an alert.
  - After firing, the same sound is ignored for `cooldown` seconds, so one
    smoke alarm that beeps for a minute is one event, not sixty.
"""

import time
from typing import Callable


class Detector:
    def __init__(
        self,
        thresholds: dict[str, float],
        hits_needed: int = 2,
        cooldown: float = 20.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.thresholds = dict(thresholds)
        self.hits_needed = hits_needed
        self.cooldown = cooldown
        self.clock = clock
        self.streak = {s: 0 for s in thresholds}
        self.last_fired: dict[str, float] = {}

    def update(self, scores: dict[str, float]) -> list[tuple[str, float]]:
        """Feed one window of scores. Returns the sounds that just fired, with confidence."""
        now = self.clock()
        fired = []
        for sound, threshold in self.thresholds.items():
            score = scores.get(sound, 0.0)
            if score >= threshold:
                self.streak[sound] += 1
            else:
                self.streak[sound] = 0
                continue

            cooling = now - self.last_fired.get(sound, float("-inf")) < self.cooldown
            if self.streak[sound] >= self.hits_needed and not cooling:
                fired.append((sound, round(float(score), 3)))
                self.last_fired[sound] = now
                self.streak[sound] = 0
        return fired

    def reset(self, sound: str) -> None:
        """Forget the cooldown for a sound (after "I'm OK", so a new alarm is caught)."""
        self.last_fired.pop(sound, None)
        self.streak[sound] = 0
