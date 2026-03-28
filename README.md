# osu!relax

relax/assist bot for osu!lazer on windows. connects to [tosu](https://github.com/KotRikD/tosu) to read the current map in real time, then handles cursor movement and keypresses using win32 `SendInput` directly.

---

## what it does

- smooth cursor movement between notes with easing, optional sine-wave arcing between objects
- follows slider curves properly (bezier, linear, passthrough) including repeats
- spinners work via parametric circle at a configurable RPM
- DT/HT detection, it picks up speed mods from tosu and adjusts timing automatically
- precision timing via busy-wait loop (bypasses the ~15ms resolution of `time.sleep`)
- auto-reloads when you switch maps

---

## requirements

- windows (uses SendInput + GetSystemMetrics)
- python 3.8+
- [tosu](https://github.com/KotRikD/tosu) running on `localhost:24050`

### Inside your folder should look like this:
<img width="140" height="196" alt="image" src="https://github.com/user-attachments/assets/b1a54fa7-1f77-401e-9020-6f2482a22cd3" />

### python deps

```bash
pip install -r requirements.txt
```

```
websocket-client
keyboard
```

tosu is a separate app, not bundled here, grab it from its own repo and have it running before you start this.

---

## setup

open the script and set your actual screen resolution at the top:

```python
SCREEN_W = 2560
SCREEN_H = 1440
```

then just run it:

```bash
python relax.py
```

---

## hotkeys

| key | action |
|-----|--------|
| `Q` | sync and start from the first note |
| `W` | stop |

hit Q on the first circle, it locks timing from that moment and starts from the top of the map.

---

## config

all at the top of the file.

| setting | default | what it does |
|---------|---------|-------------|
| `SYNC_HOTKEY` | `q` | start/sync key |
| `STOP_HOTKEY` | `w` | stop key |
| `CLICK_KEYS` | `["z", "x"]` | keys used to hit notes, set to something unused for cursor-only/relax mode |
| `CURSOR_SENS` | `1.51` | scales movement inward from playfield edges |
| `SPINNER_RPM` | `390` | spinner speed (~510rpm in-game) |
| `SPINNER_RADIUS` | `110` | spinner circle radius in pixels |
| `ARC_MODE` | `True` | sine-wave cursor arc between notes |
| `ARC_AMPLITUDE` | `60` | arc width in pixels perpendicular to the path |
| `ARC_CYCLES` | `0.5` | sine cycles between notes |
| `SCREEN_W` / `SCREEN_H` | `2560` / `1440` | **set this to your actual resolution or nothing will work** |
| `PF_HEIGHT_PCT` | `0.80` | playfield height as fraction of screen |
| `PF_TOP_PCT` | `0.095` | playfield top as fraction of screen |
| `PF_Y_OFFSET` | `15` | tweak if notes feel too high or low |

---

## how it works

tosu streams beatmap state over websocket. when a new map loads, the script parses the `.osu` file directly to get hit objects, slider curves, and timing points. on sync, it builds a full timeline of cursor positions and key events for the whole map, then runs two threads, one for cursor, one for keys, both on the busy-wait timer for accuracy.

---

## notes

- osu!lazer only
- don't use this on ranked or multiplayer, obviously
- leave `EARLY_HIT_MS` at 0, trust me
