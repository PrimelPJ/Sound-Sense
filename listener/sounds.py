"""Which YAMNet (AudioSet) classes count as each SoundSense sound.

YAMNet knows 521 sounds. We only care about 4, so each of ours is a group of
AudioSet class names. A sound's score is the highest score in its group.

If a name here is not in the model's class list, the listener prints a warning
and skips it, so a typo never crashes anything.
"""

SOUND_CLASSES = {
    "smoke_alarm": ["Smoke detector, smoke alarm", "Fire alarm", "Alarm"],
    "baby_cry": ["Baby cry, infant cry", "Crying, sobbing"],
    "doorbell": ["Doorbell", "Ding-dong", "Knock"],
    "kettle": ["Kettle whistle", "Whistle", "Steam whistle", "Boiling"],
}

# Default confidence needed (0 to 1). Tune these in the demo room with --show-scores.
DEFAULT_THRESHOLDS = {
    "smoke_alarm": 0.25,
    "baby_cry": 0.30,
    "doorbell": 0.30,
    "kettle": 0.30,
}

# Higher number wins when two sounds are going at once.
PRIORITY = {"smoke_alarm": 4, "baby_cry": 3, "doorbell": 2, "kettle": 1}

# Sounds that start the escalation timer on the server. The others are just a heads up.
ESCALATING = {"smoke_alarm", "baby_cry"}
