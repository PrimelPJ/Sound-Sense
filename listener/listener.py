"""SoundSense listener: hears sounds on the laptop mic and drives the Arduino.

Normal run:        python listener.py
Tune thresholds:   python listener.py --show-scores
No board:          python listener.py --no-arduino
Demo backup:       python listener.py --simulate   (type smoke, baby, door, kettle, ok, q)
"""

import argparse
import logging
import os
import queue
import sys
import threading
import time

from api_client import AlishaApi, Api
from controller import Controller
from detector import Detector
from serial_link import ArduinoLink, NoArduino
from sounds import DEFAULT_THRESHOLDS

WINDOW = 0.975  # seconds of audio per guess (YAMNet's frame size)
HOP = 0.5  # how often we guess

SHORT = {"smoke": "smoke_alarm", "baby": "baby_cry", "door": "doorbell", "kettle": "kettle"}

log = logging.getLogger("soundsense")


def parse_args():
    p = argparse.ArgumentParser(description="SoundSense listener")
    p.add_argument("--backend", choices=["alisha", "soundsense"],
                   default=os.getenv("SOUNDSENSE_BACKEND", "alisha"),
                   help="alisha = Alisha's dashboard API (default), soundsense = server/ folder")
    p.add_argument("--api", default=os.getenv("SOUNDSENSE_API"),
                   help="API address (default localhost:5000 for alisha, localhost:8000 for soundsense)")
    p.add_argument("--device", default=os.getenv("SOUNDSENSE_DEVICE", "home-01"))
    p.add_argument("--port", help="Arduino serial port (found automatically if left out)")
    p.add_argument("--no-arduino", action="store_true", help="run without the board")
    p.add_argument("--simulate", action="store_true", help="type sounds instead of using the mic")
    p.add_argument("--show-scores", action="store_true", help="print live scores to tune thresholds")
    p.add_argument("--list-mics", action="store_true", help="list microphones and quit")
    p.add_argument("--mic", type=int, help="microphone number from --list-mics")
    p.add_argument("--threshold", action="append", default=[], metavar="SOUND=VALUE",
                   help="override a threshold, e.g. --threshold smoke_alarm=0.4")
    p.add_argument("--hits", type=int, default=2, help="windows in a row needed to fire")
    p.add_argument("--cooldown", type=float, default=20.0, help="seconds before the same sound can fire again")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def build_thresholds(overrides: list[str]) -> dict[str, float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    for item in overrides:
        sound, _, value = item.partition("=")
        sound = SHORT.get(sound, sound)
        if sound not in thresholds:
            sys.exit(f"unknown sound in --threshold: {sound}")
        thresholds[sound] = float(value)
    return thresholds


def connect_arduino(args):
    if args.no_arduino:
        return NoArduino()
    try:
        return ArduinoLink(args.port)
    except Exception as exc:
        log.error("%s Running without the board.", exc)
        return NoArduino()


def run_simulate(ctrl: Controller, link) -> None:
    print("Simulate mode. Type: smoke, baby, door, kettle, ok, q")
    commands: "queue.Queue[str]" = queue.Queue()

    def read_stdin():
        for line in sys.stdin:
            commands.put(line.strip().lower())
        commands.put("q")

    threading.Thread(target=read_stdin, daemon=True).start()
    while True:
        try:
            cmd = commands.get(timeout=0.1)
        except queue.Empty:
            ctrl.tick()
            continue
        if cmd in ("q", "quit", "exit"):
            return
        if cmd == "ok":
            ctrl.on_button()
        elif cmd in SHORT or cmd in SHORT.values():
            ctrl.on_detect(SHORT.get(cmd, cmd), 0.99)
        elif cmd:
            print("unknown, use: smoke, baby, door, kettle, ok, q")
        ctrl.tick()


def run_mic(ctrl: Controller, detector: Detector, args) -> None:
    from audio import Mic
    from model import Yamnet

    model = Yamnet()
    mic = Mic(device=args.mic)
    mic.start()
    log.info("listening... (Ctrl+C to stop)")
    time.sleep(WINDOW)
    try:
        while True:
            started = time.monotonic()
            scores, top3 = model.classify(mic.last(WINDOW))
            if args.show_scores:
                bar = " | ".join(f"{s.split('_')[0]:6} {v:.2f}" for s, v in scores.items())
                guesses = ", ".join(f"{n} {v}" for n, v in top3)
                print(f"{bar} || level {mic.level:.3f} || {guesses}", flush=True)
            for sound, conf in detector.update(scores):
                ctrl.on_detect(sound, conf)
            ctrl.tick()
            time.sleep(max(0.0, HOP - (time.monotonic() - started)))
    finally:
        mic.stop()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
    )
    if args.list_mics:
        from audio import list_mics
        print(list_mics())
        return

    if args.backend == "alisha":
        args.api = args.api or "http://localhost:5000"
        api = AlishaApi(args.api)
    else:
        args.api = args.api or "http://localhost:8000"
        api = Api(args.api)
    if api.health():
        log.info("API ok at %s", args.api)
    else:
        log.warning("API not reachable at %s, alerts will be local only until it is", args.api)

    detector = Detector(build_thresholds(args.threshold), hits_needed=args.hits, cooldown=args.cooldown)
    link = connect_arduino(args)
    ctrl = Controller(api, link, args.device, detector)
    try:
        if args.simulate:
            run_simulate(ctrl, link)
        else:
            run_mic(ctrl, detector, args)
    except KeyboardInterrupt:
        pass
    finally:
        link.send("CLEAR")
        link.close()
        log.info("stopped")


if __name__ == "__main__":
    main()
