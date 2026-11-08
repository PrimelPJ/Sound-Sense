"""Which YAMNet (AudioSet) classes count as each SoundSense sound.

YAMNet knows 521 sounds. We only care about 7, so each of ours is a group of
AudioSet class names. A sound's score is the highest score in its group.

If a name here is not in the model's class list, the listener prints a warning
and skips it, so a typo never crashes anything.
"""

SOUND_CLASSES = {
    "smoke_alarm": ["Smoke detector, smoke alarm", "Fire alarm", "Alarm"],
    "glass_break": ["Shatter", "Glass", "Breaking", "Smash, crash"],
    "baby_cry": ["Baby cry, infant cry", "Crying, sobbing"],
    "siren": ["Siren", "Civil defense siren", "Emergency vehicle", "Police car (siren)",
              "Ambulance (siren)", "Fire engine, fire truck (siren)"],
    "doorbell": ["Doorbell", "Ding-dong", "Ding", "Chime"],
    "phone": ["Telephone", "Telephone bell ringing", "Ringtone"],
    "kettle": ["Whistle", "Steam whistle", "Boiling"],
}

DEFAULT_THRESHOLDS = {
    "smoke_alarm": 0.25,
    "glass_break": 0.25,
    "baby_cry": 0.30,
    "siren": 0.30,
    "doorbell": 0.15,
    "phone": 0.30,
    "kettle": 0.30,
}

# Higher number wins when two sounds are going at once.
# "help" is not a sound: it is sent when the "Get help" button is pressed.
PRIORITY = {"help": 8, "smoke_alarm": 7, "glass_break": 6, "baby_cry": 5, "siren": 4,
            "doorbell": 3, "phone": 2, "kettle": 1}

# Sounds that start the escalation timer on the server. The others are just a heads up.
ESCALATING = {"help", "smoke_alarm", "glass_break", "baby_cry"}
