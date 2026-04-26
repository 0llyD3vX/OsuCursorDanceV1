# osu!relax v0.2.0

Advanced relax/assist bot for osu!lazer on Windows. Features predictive movement, stream detection, a dynamic arc system, and configurable click jitter for human-like patterns.

> **Note:** v0.2.0 has more features but is slightly less reliable on extremely fast jumps compared to v0.1.0. Use this version for QOL improvements if you can accept a small accuracy trade-off. A stability update is coming in v0.2.1. (you can access older versions in the release tab somewhere over to the right ->>)

---

## Showcase (v0.1.0)

https://www.youtube.com/watch?v=qWbWlwr2LFs

---

## What's New in v0.2.0

- **Predictive movement** - anticipates note patterns for smoother cursor flow
- **Intelligent stream detection** - identifies and smooths stream patterns automatically
- **Adaptive arc system** - dynamic arc amplitude based on note distance
- **Configurable click jitter** - adjustable timing variation (±9ms default) for human-like tapping
- **Stream smoothing** - configurable passes and alpha for curved stream paths
- **Relax mode toggle** - press `R` to switch between cursor-only and full auto mid-session
- **Auto-start** - automatically syncs when the map begins playing
- **Predictive direction calculation** - looks ahead up to 5 notes for better pathing
- **Velocity capping** - configurable cursor speed limit to prevent teleporting
- **Improved slider handling** - better accuracy for complex slider shapes (P and C curves)
- **osu! pixel coordinate accuracy** - correct conversion between screen and osu! coordinates
- **Hit bias adjustment** - fine-tune tap timing with a configurable offset
- **Spinner optimizations** - configurable RPM and radius with smooth circular motion

---

## Requirements

- Windows (uses `SendInput` + `GetSystemMetrics`)
- Python 3.8+
- [tosu](https://github.com/KotRikD/tosu) running on `localhost:24050`

### Python dependencies

```bash
pip install -r requirements.txt
```

```
websocket-client
keyboard
```

tosu is a separate application. Grab it from its own repo and have it running before starting the bot.

Your folder should contain these 4 files:

```
relax.py
requirements.txt
README.md
(tosu running separately)
```

---

## Setup

**CRITICAL: Set your screen resolution at the top of the script:**

```python
SCREEN_W = 2560  # your monitor width
SCREEN_H = 1440  # your monitor height
```

Optional adjustments:

- `PF_Y_OFFSET` - tweak if notes feel too high or too low
- `CURSOR_SENS` - adjust if cursor position feels off (1.52 is default)

Run `tosu.exe` and leave it running in the background (you can close the browser tab it opens), then:

```bash
python relax.py
```

---

## Hotkeys

| Key | Action |
|-----|--------|
| `Q` | Arm the bot (ready to auto-start) |
| `W` | Emergency stop. Kills all movement immediately |
| `R` | Toggle RELAX\_MODE (cursor-only vs full auto) |

With `AUTO_START = True` (default), pressing `Q` arms the bot and it starts automatically when the map begins.

---

## Configuration

### Display Settings — Set These First

| Setting | Default | Description |
|---------|---------|-------------|
| `SCREEN_W` / `SCREEN_H` | `2560` / `1440` | **Must match your actual resolution** |
| `PF_HEIGHT_PCT` | `0.80` | Playfield height as fraction of screen |
| `PF_TOP_PCT` | `0.095` | Playfield top position |
| `PF_Y_OFFSET` | `15` | Fine tune vertical alignment |
| `CURSOR_SENS` | `1.52` | Cursor sensitivity scaling |

### Movement Tuning

| Setting | Default | Description |
|---------|---------|-------------|
| `MOVEMENT_MODE` | `"predictive"` | `linear` / `arc` / `predictive` |
| `ARC_MODE` | `True` | Enable sine-wave cursor arcs |
| `ARC_MAX_AMPLITUDE` | `25` | Maximum arc size in pixels |
| `ARC_CYCLES` | `0.5` | Sine cycles between notes |
| `ARC_STREAM_THRESH_PX` | `100` | Distance threshold for arc reduction |
| `ARC_EXP_BASE` | `0.12` | Arc falloff rate |
| `SPINNER_RPM` | `350` | Spinner speed (experimental) |
| `SPINNER_RADIUS` | `90` | Spinner circle radius |

### Features

| Setting | Default | Description |
|---------|---------|-------------|
| `RELAX_MODE` | `False` | `True` = cursor only, `False` = full auto |
| `AUTO_START` | `True` | Auto-sync when the map starts |
| `PREDICT_NOTES` | `5` | Notes ahead to predict (2-5 recommended) |
| `STREAM_MS_THRESH` | `250` | Timing threshold for stream detection (ms) |
| `STREAM_SMOOTH` | `True` | Enable stream path smoothing |
| `STREAM_SMOOTH_PASSES` | `2` | Smoothing iterations (1–3) |
| `STREAM_SMOOTH_ALPHA` | `0.28` | Smoothing strength (0–1) |
| `STREAM_SAMPLES_PER_OSUPX` | `0.4` | Stream sampling density |

### Timing & Input

| Setting | Default | Description |
|---------|---------|-------------|
| `SYNC_HOTKEY` | `q` | Arm the bot |
| `STOP_HOTKEY` | `w` | Emergency stop |
| `CLICK_KEYS` | `["z", "x"]` | Keys used for tapping |
| `HIT_BIAS_MS` | `-10` | Tap timing offset (negative = earlier) |
| `CLICK_VARIATION_MS` | `9.0` | Tap timing variation (±ms) |
| `GAME_OFFSET_MS` | `0` | Universal offset. leave at 0 |

### Performance Tuning

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_CURSOR_DELTA_PX` | `110.0` | Max cursor movement per frame. Increase for faster jumps |
| `TIMING_SPIN_WINDOW` | `0.0005` | Final busy-wait window for precision (seconds) |
| `SEGMENT_MIN_DUR` | `0.005` | Minimum movement segment duration (seconds) |

---

## Recommended Presets

**Maximum accuracy. Coming properly in v0.2.1:**
```python
MAX_CURSOR_DELTA_PX = 999999
CLICK_VARIATION_MS  = 0
PREDICT_NOTES       = 3
STREAM_SMOOTH       = False
ARC_MODE            = False
```

**Human-like / relaxed play:**
```python
ARC_MODE            = True
ARC_MAX_AMPLITUDE   = 60
CLICK_VARIATION_MS  = 9.0
STREAM_SMOOTH       = True
PREDICT_NOTES       = 5
```

**Low-end devices:**
```python
PREDICT_NOTES       = 2
STREAM_SMOOTH       = False
ARC_MODE            = False
MAX_CURSOR_DELTA_PX = 150
```

---

## How It Works

**tosu integration** - connects to the tosu WebSocket at `localhost:24050` for real-time map data.

**Beatmap parsing** - reads `.osu` files directly to extract hit objects, slider curves (L/P/B/C), and timing points.

**Timeline building** - pre computes cursor positions and key events for the entire map before playback begins.

**Stream detection** - analyses note timing and spacing to identify streams and apply smoothing.

**Predictive movement** - looks ahead `PREDICT_NOTES` notes to anticipate direction changes before they happen.

**Dual-thread execution** - cursor movement and key presses run on separate threads to avoid blocking each other.

**Precision timing** - hybrid sleep/busy-wait loop for sub-millisecond accuracy on note hits.

**Direct input** - uses `SendInput` for the lowest latency mouse and keyboard events possible.

### Movement Types

| Mode | Behaviour |
|------|-----------|
| `linear` | Straight line with smooth easing |
| `arc` | Sine-wave perpendicular oscillation |
| `predictive` | Arc with look-ahead direction prediction |

### Supported Curve Types

| Type | Description |
|------|-------------|
| `L` | Linear - straight line segments |
| `P` | Perfect - circular arc through 3 points |
| `B` | Bézier - single or compound curves |
| `C` | Catmull Rom splines |

---

## Troubleshooting

**Cursor feels laggy or slow on fast jumps**
- Increase `MAX_CURSOR_DELTA_PX` (try 300–500)
- Disable `ARC_MODE` for direct movement
- Reduce `PREDICT_NOTES` to 2–3

**Tapping feels early or late**
- Adjust `HIT_BIAS_MS` (more negative = earlier taps)
- Lower `CLICK_VARIATION_MS` to reduce jitter

**Notes being hit too high or too low**
- Adjust `PF_Y_OFFSET` (increase = lower, decrease = higher)
- Check `PF_TOP_PCT` and `PF_HEIGHT_PCT`

**Bot doesn't start automatically**
- Make sure `AUTO_START = True`
- Press `Q` to arm before the map starts
- Verify tosu is running and connected

**Streams feel choppy**
- Enable `STREAM_SMOOTH`
- Increase `STREAM_SMOOTH_PASSES` to 2–3
- Lower `STREAM_SMOOTH_ALPHA` to 0.2–0.3

**High CPU usage**
- Reduce `PREDICT_NOTES` to 2
- Disable `STREAM_SMOOTH`
- Lower `MAX_CURSOR_DELTA_PX`

---

## Version Comparison

| Feature | v0.1.0 | v0.2.0 |
|---------|--------|--------|
| Basic movement | ✅ | ✅ |
| Arc mode | ✅ | ✅ improved |
| Slider support (L/B) | ✅ | ✅ |
| Slider support (P/C) | ❌ | ✅ |
| Stream detection | ❌ | ✅ |
| Stream smoothing | ❌ | ✅ |
| Click jitter | ❌ | ✅ |
| Predictive movement | ❌ | ✅ |
| Auto-start | ❌ | ✅ |
| Relax mode toggle | ❌ | ✅ |
| Velocity capping | ❌ | ✅ |
| Fast jump accuracy | Excellent | Good (fix in v0.2.1) |
| Stability | Rock solid | Slightly less reliable |

**Recommendation:** Use v0.1.0 for maximum accuracy on extremely hard maps. Use v0.2.0 for everyday play and the expanded feature set.

---

## Known Issues in v0.2.0

- **Fast jump accuracy** - may occasionally miss notes on extremely fast sections (16★) due to velocity capping and arc prediction overhead
- **Stream detection** - some complex or irregular stream patterns may be misidentified
- **Memory usage** - the pre-baked curve system uses more RAM than v0.1.0

---

## Roadmap (v0.2.1)

- Fix fast jump velocity capping
- Smart arc disabling for high speed sections
- Improved stream detection consistency
- Performance profiling
- Optimised memory usage
- Jump pre-computation

---

## Notes

- **osu!lazer only** - does not work with osu!stable
- Don't use this on ranked or multiplayer
- I'm not responsible for any bans or consequences
- Leave `GAME_OFFSET_MS` at 0 unless you know what you're doing
- `EARLY_HIT_MS` is deprecated, use `HIT_BIAS_MS` instead

---

## Contributing

Issues and PRs welcome, especially for:

- Performance optimisations
- Additional curve types
- Improved prediction algorithms
- Fast jump accuracy fixes

---

## License

Do whatever you want with it — just don't use it to cheat on leaderboards. This is for personal education and experimentation only.
