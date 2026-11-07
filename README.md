# SoundSense

SoundSense helps Deaf and hard of hearing people know what is happening at home.
It hears a smoke alarm, doorbell, kettle or baby crying and turns it into a
flashing light, a vibration and a live alert on the dashboard. If a serious
alarm keeps going and nobody presses "I'm OK", it texts family, then a
neighbour, then the building.

Built at Hack the Change 2026.

## How it works

```
laptop mic -> YAMNet sound model -> listener ---USB---> Arduino (light, vibration, "I'm OK" button)
                                        |
                                        v
                                    API server ---> escalation texts (family, neighbour, building)
                                        |
                                        v
                                  dashboard (live)
```

1. The listener records the laptop mic and scores every half second with YAMNet
   (a free sound model from Google that knows 521 sounds).
2. A sound must be heard twice in a row to count, and then it rests for 20 seconds,
   so one alarm is one alert.
3. The Arduino lights up straight away, even if the internet is down.
4. The event goes to the API, which pushes it live to the dashboard.
5. For a smoke alarm (60 s) or a baby crying (3 min), a timer starts. No "I'm OK"
   in time means texts go out, one group at a time, 60 s apart.
6. "I'm OK" on the button or the dashboard stops everything.

In a real product the laptop would be a small $10 to $20 Wi-Fi board (like an ESP32).

## Folders

| Folder | What | Owner |
| --- | --- | --- |
| `listener/` | Mic, sound model, detection, Arduino link | Primel |
| `arduino/` | Light, vibration and button sketch | Primel |
| `dashboard/` | Dashboard, API (port 5000) and text alerts | Alisha |
| `server/` | Backup API with the family, neighbour, building escalation chain | Primel |

The listener talks to Alisha's dashboard API by default. The `server/` folder is a
backup that does the same job and can be used with `--backend soundsense`.

## Run it

### 1. Dashboard and API

Start Alisha's dashboard first (see `dashboard/`). It listens on `http://localhost:5000`.

### 1b. Backup server (only if you are not using the dashboard API)

```bash
cd server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
TIME_SCALE=0.2 uvicorn app.main:app --reload     # 0.2 = waits are 5x faster for demos
```

API docs: http://localhost:8000/docs

### 2. Arduino

1. Open `arduino/soundsense_alerts/soundsense_alerts.ino`, pick **Arduino Uno** and the port, upload.
2. The light blinks green once when it boots.
3. Check: Serial Monitor at 115200, type `TEST`. Every pattern plays. Press the button and `ACK` shows up.

The sketch uses the starter kit's RGB LED by default (pins 3, 5, 6). To use a WS2812B
LED strip on pin 6 instead, set `USE_STRIP` to `1` and install **Adafruit NeoPixel**
from the Library Manager.

**Wiring**

| Part | Arduino pin |
| --- | --- |
| RGB LED red, green, blue (each through 220 ohm) | 3, 5, 6 |
| RGB LED longest leg | GND |
| Motor, through a PN2222 transistor (1k ohm on the base) and a 1N4007 diode across it | 9 |
| "I'm OK" button (other leg to GND) | 2 |

**Breadboard holes** (letter = column, number = row, as printed on the board)

| Part | Holes |
| --- | --- |
| Arduino 5V and GND | rail next to column a: 5V in the red-line row, GND in the blue-line row |
| Arduino second GND | rail next to column j, blue-line row |
| Button | e1, e3, f1, f3 (across the middle gap) |
| Pin 2 / button ground | a1 / a3 to the blue-line rail by column a |
| RGB LED (red, longest, green, blue) | h10, h11, h12, h13 |
| LED ground | j11 to the blue-line rail by column j |
| 220 ohm resistors | i10 to i6, f12 to e12, i13 to i17 |
| Pin 3 / pin 5 / pin 6 | j6 / a12 / j17 |
| PN2222 (E, B, C) | d20, d21, d22 |
| 1k ohm | b21 to b25 |
| Pin 9 | a25 |
| Emitter to ground | a20 to the blue-line rail by column a |
| Motor leads | e22 and e28 |
| 1N4007 diode (stripe at row 28) | c22 to c28 |
| Motor power | b28 to the red-line rail by column a |

### 3. Listener

```bash
cd listener
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python listener.py                      # finds the Arduino, sends to localhost:5000
```

When a sound is heard it sends `POST /api/events` with `{"sound": "smoke alarm", "confidence": 0.94}`.
When the button is pressed it sends `POST /api/events/latest/ack`. Sound names are set in
`ALISHA_NAMES` at the bottom of `listener/api_client.py`.

Useful options:

| Command | What it does |
| --- | --- |
| `python listener.py --show-scores` | Prints live scores. Use this to set thresholds in the demo room |
| `python listener.py --threshold smoke_alarm=0.4` | Raise a threshold if a noisy room causes false alerts |
| `python listener.py --list-mics` then `--mic 2` | Pick a different microphone |
| `python listener.py --no-arduino` | Run without the board |
| `python listener.py --simulate` | Type `smoke`, `baby`, `door`, `kettle`, `ok`. Demo backup if the room is too loud |
| `--api https://your-server` | Point at a deployed API |
| `--backend soundsense` | Use the backup `server/` (port 8000) instead of the dashboard API |

## Contracts

Everyone builds against these.

**Event (listener to API):** `POST /events`

```json
{"device_id": "home-01", "sound": "smoke_alarm", "confidence": 0.91, "ts": "2026-11-07T14:02:11Z"}
```

`sound` is one of `smoke_alarm`, `baby_cry`, `doorbell`, `kettle`.

**Endpoints**

| Method | Path | Use |
| --- | --- | --- |
| POST | `/events` | New sound event. Repeats of an open alert return the same event with `"duplicate": true` |
| POST | `/events/{id}/ack` | "I'm OK". Body `{"by": "device"}` or `{"by": "dashboard"}` |
| GET | `/events/{id}` | One event with every text that went out (`steps`) |
| GET | `/events` | Event log (Alisha) |
| GET, PUT | `/contacts` | Contacts and their order (Alisha) |
| GET | `/sounds` | Sound names, labels, and which ones escalate |
| GET | `/health` | Is the server up |
| WS | `/live` | Live updates for the dashboard |

**Event object** (what every endpoint returns)

```json
{
  "id": 7, "device_id": "home-01", "sound": "smoke_alarm", "label": "Smoke alarm",
  "confidence": 0.91, "ts": "...", "status": "escalating", "escalates": true,
  "escalation_level": 1, "acked_by": null, "acked_at": null,
  "steps": [{"level": 1, "role": "family", "contact_name": "Mom", "sent_at": "...", "ok": true, "note": null}],
  "duplicate": false
}
```

`status` is one of: `info` (doorbell, kettle: heads up only), `active` (waiting for "I'm OK"),
`escalating` (texts have gone out), `unanswered` (everyone was texted), `acked`.

**Live messages** on `/live` (JSON, one per change)

| `type` | Extra fields | Dashboard should |
| --- | --- | --- |
| `snapshot` | `open_events` | Draw any alerts already going on connect |
| `event_created` | `event` | Show the big alert screen |
| `escalation_timer` | `event_id`, `next_role`, `seconds` | Show a countdown to the first text |
| `escalation_step` | `event_id`, `level`, `role`, `contacts`, `next_role`, `seconds` | Show who was texted, next countdown |
| `escalation_done` | `event_id` | Show "everyone has been contacted" |
| `event_acked` | `event` | Clear the alert |

**Serial (laptop and Arduino, 115200 baud, one line each)**

| Direction | Message |
| --- | --- |
| Laptop to Arduino | `ALERT smoke_alarm`, `ALERT baby_cry`, `ALERT doorbell`, `ALERT kettle`, `CLEAR`, `PING`, `TEST` |
| Arduino to laptop | `READY` on boot, `ACK` when "I'm OK" is pressed, `PONG` |

**Alert patterns**

| Sound | Light | Vibration | Texts people? |
| --- | --- | --- | --- |
| Smoke alarm | Red, fast flash | Long pulses | Yes, after 60 s |
| Baby crying | Purple, slow pulse | Short pulses | Yes, after 3 min |
| Doorbell or knock | Blue, two flashes | Two taps | No, turns off after 10 s |
| Kettle or whistle | Amber, steady | One tap | No, turns off after 15 s |

A more serious alert always wins: a doorbell never hides a smoke alarm.

## Settings (server)

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./soundsense.db` | Use a Postgres URL in production |
| `TIME_SCALE` | `1.0` | Speeds up every wait. `0.1` = 10x faster |
| `HOME_NAME` | `the home` | Used in text messages |
| `SEED_CONTACTS_FILE` | `seed_contacts.json` | Demo contacts loaded when the table is empty |

## Deploy (AWS Elastic Beanstalk)

The server has a Dockerfile. Elastic Beanstalk supports WebSockets through its load balancer.

```bash
cd server
pip install awsebcli
eb init -p docker soundsense --region ca-central-1
eb create soundsense-api --single
eb setenv TIME_SCALE=0.2 HOME_NAME="the apartment"
eb open
```

SQLite resets on every deploy, which is fine for a demo. Set `DATABASE_URL` to an
RDS Postgres URL to keep data.

## Tests

```bash
cd server && python -m pytest -q      # events, "I'm OK", escalation order, live feed
cd listener && python -m pytest -q    # detection rules, sound mapping, controller
```

## Commit rules

Commits are authored by team members only. No AI tool is ever listed as an author,
co-author or contributor. Turn on the checks once after cloning:

```bash
git config core.hooksPath .githooks
```

The hooks block a commit if its message has a co-author line or names an AI tool,
if the added code names one, or if your git email is not your own.

## License

MIT. See [LICENSE](LICENSE).
