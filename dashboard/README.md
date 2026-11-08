# SoundSense dashboard

Home sound alerts for Deaf and hard-of-hearing people that make sure someone responds.
This folder is the dashboard, the event and contacts API, and the SMS helper.
The listener in `../listener` sends alerts here.

## Run it

```
cd dashboard
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 and press a button under "Demo controls" to fake an alert.
If nobody presses "I'm OK", backup contacts get a text when the timer runs out.
"Skip timer" escalates right away, and "Clear log" resets between demo runs.

To test without the listener, open a second terminal and run `python simulate.py`
(s = smoke alarm, o = I'm OK).

## Settings (optional, set before `python app.py`)

| Setting | What it does | Default |
|---|---|---|
| `ESCALATE_AFTER` | Seconds before backup contacts are texted | `60` |
| `AUTO_ESCALATE` | `0` if the listener should decide when to escalate | `1` |
| `HOME_NAME` | Name shown on the dashboard and in texts | `Maria` |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` | Send real texts | not set = demo mode |

Windows (PowerShell): `$env:ESCALATE_AFTER="15"; python app.py`

## The alert text

The text comes from a fixed template that uses only the event facts (who, what sound,
when, how long with no response), so it always sends and never invents anything.

## How the listener talks to this

When it hears something: `POST /api/events` with `{"sound": "smoke alarm", "confidence": 0.94}`.
The same sound again while an alert is open counts as a repeat, not a new alert.

| Listener does | Request |
|---|---|
| Hears a sound | `POST /api/events` with `{"sound": "smoke alarm", "confidence": 0.94}` |
| "I'm OK" button pressed | `POST /api/events/<id>/ack` |
| "Get help" button pressed | `POST /api/events/<id>/escalate` with `{"by": "button"}` |
| Checks if "I'm OK" was pressed on the dashboard | `GET /api/events/<id>` |
