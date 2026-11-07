"""YAMNet sound model.

YAMNet is a free, pretrained model from Google trained on AudioSet. It takes
16 kHz mono audio and scores 521 kinds of sound. It runs on a normal laptop CPU
in a few milliseconds per second of audio.
"""

import csv
import io
import logging

import numpy as np

from sounds import SOUND_CLASSES

log = logging.getLogger("soundsense.model")

YAMNET_URL = "https://tfhub.dev/google/yamnet/1"
SAMPLE_RATE = 16000


def group_indices(class_names: list[str]) -> dict[str, list[int]]:
    """Map each SoundSense sound to the column numbers of its AudioSet classes."""
    lookup = {name: i for i, name in enumerate(class_names)}
    groups = {}
    for sound, names in SOUND_CLASSES.items():
        idx = []
        for name in names:
            if name in lookup:
                idx.append(lookup[name])
            else:
                log.warning("AudioSet class '%s' (for %s) not found, skipping", name, sound)
        if not idx:
            log.error("no AudioSet classes found for %s, it will never fire", sound)
        groups[sound] = idx
    return groups


def sound_scores(class_scores: np.ndarray, groups: dict[str, list[int]]) -> dict[str, float]:
    """521 class scores -> one score per SoundSense sound (the max in each group)."""
    return {
        sound: float(class_scores[idx].max()) if idx else 0.0
        for sound, idx in groups.items()
    }


class Yamnet:
    def __init__(self) -> None:
        import tensorflow as tf  # imported here so tests and --simulate don't need TensorFlow
        import tensorflow_hub as hub

        log.info("loading YAMNet (first run downloads about 15 MB)...")
        self._model = hub.load(YAMNET_URL)
        self._tf = tf
        class_map = tf.io.read_file(self._model.class_map_path()).numpy().decode("utf-8")
        self.class_names = [row["display_name"] for row in csv.DictReader(io.StringIO(class_map))]
        self.groups = group_indices(self.class_names)
        log.info("YAMNet ready, %d classes", len(self.class_names))

    def classify(self, waveform: np.ndarray) -> tuple[dict[str, float], list[tuple[str, float]]]:
        """Score one chunk of audio.

        Returns (our 4 sound scores, top 3 AudioSet guesses for debugging).
        """
        scores, _embeddings, _spectrogram = self._model(waveform.astype(np.float32))
        mean = scores.numpy().mean(axis=0)  # average over YAMNet's internal frames
        top = mean.argsort()[-3:][::-1]
        top3 = [(self.class_names[i], round(float(mean[i]), 2)) for i in top]
        return sound_scores(mean, self.groups), top3
