"""USB serial link to the Arduino Uno.

Laptop -> Arduino:   ALERT <sound>   show that sound's light and vibration
                     CLEAR           turn everything off
                     PING            Arduino replies PONG
Arduino -> laptop:   READY           sent once after boot
                     ACK             the "I'm OK" button was pressed
                     PONG

Every message is one line ending in a newline. Baud rate is 115200.
"""

import logging
import queue
import threading
import time

log = logging.getLogger("soundsense.serial")

BAUD = 115200
PORT_HINTS = ("usbmodem", "usbserial", "ttyacm", "ttyusb", "arduino", "ch340", "wchusbserial")


def find_port() -> str | None:
    """Guess which serial port is the Arduino."""
    from serial.tools import list_ports

    for p in list_ports.comports():
        text = f"{p.device} {p.description} {p.manufacturer or ''}".lower()
        if any(h in text for h in PORT_HINTS):
            return p.device
    return None


class ArduinoLink:
    def __init__(self, port: str | None = None) -> None:
        import serial

        self.port = port or find_port()
        if not self.port:
            raise RuntimeError("No Arduino found. Plug it in, or pass --port, or use --no-arduino.")
        self.ser = serial.Serial(self.port, BAUD, timeout=0.2)
        self.lines: "queue.Queue[str]" = queue.Queue()
        self._running = True
        self._write_lock = threading.Lock()
        threading.Thread(target=self._read_loop, daemon=True).start()
        self._wait_ready()

    def _wait_ready(self, timeout: float = 4.0) -> None:
        # Opening the port resets the Uno, which takes about 2 seconds.
        end = time.time() + timeout
        while time.time() < end:
            try:
                if self.lines.get(timeout=0.2) == "READY":
                    log.info("Arduino ready on %s", self.port)
                    return
            except queue.Empty:
                pass
        log.warning("Arduino on %s did not say READY, carrying on anyway", self.port)

    def _read_loop(self) -> None:
        while self._running:
            try:
                raw = self.ser.readline()
            except Exception as exc:
                log.error("serial read failed: %s", exc)
                time.sleep(1)
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            if line:
                log.debug("arduino -> %s", line)
                self.lines.put(line)

    def send(self, line: str) -> None:
        with self._write_lock:
            self.ser.write((line + "\n").encode())
        log.info("-> arduino: %s", line)

    def read(self) -> str | None:
        """Next line from the Arduino, or None if nothing waiting."""
        try:
            return self.lines.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        self._running = False
        self.ser.close()


class NoArduino:
    """Stand-in when no board is plugged in. Prints what it would have shown."""

    port = None

    def __init__(self) -> None:
        self.lines: "queue.Queue[str]" = queue.Queue()

    def send(self, line: str) -> None:
        log.info("(no arduino) would send: %s", line)

    def read(self) -> str | None:
        try:
            return self.lines.get_nowait()
        except queue.Empty:
            return None

    def press_button(self) -> None:
        self.lines.put("ACK")

    def close(self) -> None:
        pass
