"""Settings for the SoundSense server. Change them with environment variables."""

import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./soundsense.db")

# Name used in text messages, for example "Primel's apartment".
HOME_NAME = os.getenv("HOME_NAME", "the home")

# Multiplies every wait time. 1.0 = real timings, 0.1 = 10x faster for demos.
TIME_SCALE = float(os.getenv("TIME_SCALE", "1.0"))

# The four sounds SoundSense knows about.
# first_wait: seconds with no "I'm OK" before the first text goes out.
# None means this sound never escalates (it is just a heads up).
SOUNDS = {
    "smoke_alarm": {"label": "Smoke alarm", "first_wait": 60},
    "baby_cry": {"label": "Baby crying", "first_wait": 180},
    "doorbell": {"label": "Doorbell or knock", "first_wait": None},
    "kettle": {"label": "Kettle or whistle", "first_wait": None},
}

# Who gets texted, in order, and how long to wait between each group.
ESCALATION_ORDER = ["family", "neighbour", "building"]
STEP_WAIT = 60

# Ignore a repeat of the same sound from the same device within this window.
DUPLICATE_WINDOW = 120

# Where demo contacts are loaded from when the contacts table is empty.
SEED_CONTACTS_FILE = os.getenv("SEED_CONTACTS_FILE", "seed_contacts.json")
