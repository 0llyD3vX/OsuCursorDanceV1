import sys
sys.stdout.reconfigure(encoding='utf-8')

import ctypes
import ctypes.wintypes
import json
import math
import os
import threading
import time
import websocket
import keyboard

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

#Config CHANGE THESE TO YOUR LIKING, BUT THE DEFAULTS ARE GOOD


TOSU_WS_URL    = "ws://localhost:24050/websocket/v2"
SYNC_HOTKEY    = "q"
STOP_HOTKEY    = "w"
CLICK_KEYS     = ["z", "x"]  #if you dont want the bot to click, just set these to some unused keys and it will still move the cursor properly for relax play
EARLY_HIT_MS   = 0         #dont even, ts caused me TWO HOURS of pain, just leave it at 0 :D
CURSOR_SENS    = 1.51
SPINNER_RPM    = 390       #i dont really understand how this works, but this causes ~ 510RPM
SPINNER_RADIUS = 110
ARC_MODE       = True      #cursor dances in sine wave between notes
ARC_AMPLITUDE  = 60        #pixels of oscillation perpendicular to path (60 is good)
ARC_CYCLES     = 0.5         #how many sine wave cycles between notes (0.5 is good)'

SCREEN_W = 2560              #MAKE SRE TO SET THIS TO YOUR ACTUAL SCREEN RESOLUTION OTHERWISE THIS WONT WORK AT ALL
SCREEN_H = 1440

PF_HEIGHT_PCT = 0.80
PF_TOP_PCT    = 0.095
PF_Y_OFFSET   = 15    #tweak playfield height offset (if notes are too high/low, adjust this)
OSU_W, OSU_H  = 512, 384


# END OF CONFIG

#Playfield

def _pf():
    h = SCREEN_H * PF_HEIGHT_PCT
    w = h * (OSU_W / OSU_H)
    l = (SCREEN_W - w) / 2
    t = SCREEN_H * PF_TOP_PCT + PF_Y_OFFSET
    return l, t, w, h

PF_LEFT, PF_TOP, PF_W, PF_H = _pf()

def osu_to_screen(ox, oy):
    #keep coords in bounds (osu sliders are fucky)
    ox = max(0.0, min(OSU_W, float(ox)))
    oy = max(0.0, min(OSU_H, float(oy)))

    tx = PF_LEFT + (ox / OSU_W) * PF_W
    ty = PF_TOP  + (oy / OSU_H) * PF_H
    if CURSOR_SENS != 1.0:
        cx = PF_LEFT + PF_W / 2
        cy = PF_TOP  + PF_H / 2
        tx = cx + (tx - cx) / CURSOR_SENS
        ty = cy + (ty - cy) / CURSOR_SENS
    return int(tx), int(ty)


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    t = max(0.0, min(1.0, t))
    return 3 * t * t - 2 * t * t * t


def smooth_easing(phase):
    """Smooth ease-in-out from 0 to 1"""
    phase = max(0.0, min(1.0, phase))
    # cubic ease-in-out
    if phase < 0.65:
        return 2 * phase**2  # accelerate
    else:
        return 1 - 2 * (1 - phase)**2  # decelerate


def apply_arc(elapsed, dt, x1, y1, x2, y2):
    """Apply sine wave motion perpendicular to line between points with smooth easing"""
    if dt <= 0: return x1, y1
    phase = elapsed / dt
    phase = max(0.0, min(1.0, phase))
    
    dx = x2 - x1
    dy = y2 - y1
    dist = math.sqrt(dx*dx + dy*dy)
    
    #apply smooth easing to position
    eased_phase = smooth_easing(phase)
    x = x1 + dx * eased_phase
    y = y1 + dy * eased_phase
    
    if dist > 0:
        perp_x = -dy / dist
        perp_y = dx / dist
        wave = math.sin(phase * 2 * math.pi * ARC_CYCLES)
        offset = wave * ARC_AMPLITUDE
        x += perp_x * offset
        y += perp_y * offset
    
    return int(x), int(y)


def evaluate_bezier(points, t):
    pts = [(float(x), float(y)) for x, y in points]
    while len(pts) > 1:
        pts = [
            (lerp(pts[i][0], pts[i + 1][0], t), lerp(pts[i][1], pts[i + 1][1], t))
            for i in range(len(pts) - 1)
        ]
    return pts[0]


def sample_curve(curve_type, points, steps=40):
    if not points:
        return []
    if steps < 2:
        return points[:]

    if curve_type == "L":
        #straight line between points
        out = []
        total = len(points) - 1
        if total <= 0:
            return [points[0]]

        for i in range(steps):
            raw_t = i / (steps - 1)
            scaled = raw_t * total
            idx = min(int(scaled), total - 1)
            local_t = scaled - idx
            x1, y1 = points[idx]
            x2, y2 = points[idx + 1]
            x1 = max(0, min(OSU_W, x1)); y1 = max(0, min(OSU_H, y1))
            x2 = max(0, min(OSU_W, x2)); y2 = max(0, min(OSU_H, y2))
            out.append((int(lerp(x1, x2, local_t)), int(lerp(y1, y2, local_t))))
        return out

    #P/B/whatever -> just bezier it
    out = []
    for i in range(steps):
        raw_t = i / (steps - 1)
        x, y = evaluate_bezier(points, raw_t)
        x = max(0.0, min(float(OSU_W), x))
        y = max(0.0, min(float(OSU_H), y))
        out.append((int(x), int(y)))
    return out


#ctypes SendInput
#Bypasses pydirectinput entirely. SendInput is the lowest-latency way to send
#mouse/keyboard events on Windows without a kernel driver.

MOUSEEVENTF_MOVE        = 0x0001
MOUSEEVENTF_ABSOLUTE    = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000  #multiple monitors
KEYEVENTF_KEYDOWN       = 0x0000
KEYEVENTF_KEYUP         = 0x0002
KEYEVENTF_SCANCODE      = 0x0008

#actual key codes that work
SC = {"z": 0x2C, "x": 0x2D}

#old vk codes (don't use)
VK = {"z": 0x5A, "x": 0x58}

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT_UNION)]

INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1

#total screen size (all monitors combined)
VDESK_W = ctypes.windll.user32.GetSystemMetrics(78)   #width
VDESK_H = ctypes.windll.user32.GetSystemMetrics(79)   #height
VDESK_X = ctypes.windll.user32.GetSystemMetrics(76)   #x offset
VDESK_Y = ctypes.windll.user32.GetSystemMetrics(77)   #y offset


def _send(inputs):
    arr = (INPUT * len(inputs))(*inputs)
    ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def mouse_move(x, y):
    """slide cursor to screen position"""
    #normalize to 0-65535 for SendInput
    nx = int((x - VDESK_X) * 65535 / VDESK_W)
    ny = int((y - VDESK_Y) * 65535 / VDESK_H)
    inp = INPUT(
        type=INPUT_MOUSE,
        _input=_INPUT_UNION(mi=MOUSEINPUT(
            dx=nx, dy=ny, mouseData=0,
            dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
            time=0, dwExtraInfo=0,
        ))
    )
    _send([inp])


def key_down(k):
    inp = INPUT(
        type=INPUT_KEYBOARD,
        _input=_INPUT_UNION(ki=KEYBDINPUT(
            wVk=0,
            wScan=SC[k],
            dwFlags=KEYEVENTF_SCANCODE,
            time=0,
            dwExtraInfo=0,
        ))
    )
    _send([inp])


def key_up(k):
    inp = INPUT(
        type=INPUT_KEYBOARD,
        _input=_INPUT_UNION(ki=KEYBDINPUT(
            wVk=0,
            wScan=SC[k],
            dwFlags=KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP,
            time=0,
            dwExtraInfo=0,
        ))
    )
    _send([inp])


#Precision sleep
#time.sleep() on Windows has ~15ms resolution by default.
#We busy-wait the last 5ms for sub-millisecond accuracy.

def sleep_until(wall):
    while True:
        now = time.perf_counter()
        remaining = wall - now
        if remaining <= 0:
            break
        elif remaining > 0.005:
            time.sleep(remaining - 0.002)  #snooze until almost there
        else:
            pass  #then spin until we hit it exactly


#.osu parsing

def parse_timing_points(lines):
    pts, in_sec = [], False
    for line in lines:
        s = line.strip()
        if s == "[TimingPoints]": in_sec = True; continue
        if in_sec:
            if s.startswith("["): break
            if not s: continue
            p = s.split(",")
            if len(p) < 2: continue
            try:
                offset, beat_len = float(p[0]), float(p[1])
                if beat_len > 0:
                    pts.append({"offset": offset, "ms_per_beat": beat_len,
                                "sv_mult": 1.0, "inherited": False})
                else:
                    pts.append({"offset": offset, "ms_per_beat": None,
                                "sv_mult": -100.0 / beat_len, "inherited": True})
            except ValueError: continue
    pts.sort(key=lambda x: x["offset"])
    return pts

#next like 3 functions are all ai bruh
def get_timing_at(pts, t):
    mpb, sv = 500.0, 1.0
    last_pt = None
    for p in pts:
        if p["offset"] > t:
            if last_pt is None:
                break
            # optional: interpolate BPM if inherited?
            if p["inherited"] and last_pt["inherited"]:
                # simple linear SV interpolation
                sv = last_pt["sv_mult"] + (p["sv_mult"] - last_pt["sv_mult"]) * ((t - last_pt["offset"]) / (p["offset"] - last_pt["offset"]))
            return mpb, sv
        if not p["inherited"]: mpb = p["ms_per_beat"]; sv = 1.0
        else: sv = p["sv_mult"]
        last_pt = p
    return mpb, sv


def slider_duration(t, length, smult, pts):
    mpb, sv = get_timing_at(pts, t)
    base = (length / (smult * 100.0 * sv)) * mpb
    # optional easing tweak for "soft start, soft stop"
    return base


def slider_endpoint(parts, repeats=1):
    try:
        tokens = parts[5].split("|")[1:]
        if not tokens: return None
        # build full path with repeats
        points = [tuple(map(int, tok.split(":"))) for tok in tokens]
        if repeats % 2 == 0:
            return points[0]  # even repeat, endpoint is start
        return points[-1]  # odd repeat, endpoint is last
    except (IndexError, ValueError):
        return None


def parse_osu_file(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    smult = 1.4
    for line in lines:
        if line.strip().startswith("SliderMultiplier"):
            try: smult = float(line.split(":")[1].strip())
            except: pass
            break

    pts  = parse_timing_points(lines)
    objs = []
    in_h = False

    for line in lines:
        s = line.strip()
        if s == "[HitObjects]": in_h = True; continue
        if not in_h: continue
        if s.startswith("["): break
        if not s: continue
        p = s.split(",")
        if len(p) < 5: continue
        try:
            ox, oy = int(p[0]), int(p[1])
            t      = int(p[2])
            otype  = int(p[3])
            is_sl  = bool(otype & 2)
            is_sp  = bool(otype & 8)
            end_t  = None
            end_xy = (ox, oy)

            slider_curve_type = None
            slider_curve_points = None
            slider_repeats = 1

            if is_sp:
                if len(p) >= 6: end_t = int(p[5].split(":")[0])
                end_xy = (OSU_W // 2, OSU_H // 2)
            elif is_sl:
                slen  = float(p[7]) if len(p) >= 8 else 0.0
                slider_repeats = int(p[6]) if len(p) >= 7 else 1
                #DON'T FORGET TO MULTIPLY BY REPEATS
                end_t = int(t + slider_duration(t, slen, smult, pts) * slider_repeats)
                ep    = slider_endpoint(p)
                end_xy = ep if ep else (ox, oy)

                if len(p) >= 6:
                    raw_curve = p[5]
                    tokens = raw_curve.split("|")
                    if tokens:
                        slider_curve_type = tokens[0].upper()
                        pts_list = [(ox, oy)]
                        for token in tokens[1:]:
                            try:
                                px, py = map(int, token.split(":"))
                                pts_list.append((px, py))
                            except ValueError:
                                continue
                        if len(pts_list) > 1:
                            slider_curve_points = pts_list

            objs.append({
                "time_ms": t, "end_time_ms": end_t,
                "x": ox, "y": oy,
                "end_x": end_xy[0], "end_y": end_xy[1],
                "is_slider": is_sl, "is_spinner": is_sp,
                "slider_curve_type": slider_curve_type,
                "slider_curve_points": slider_curve_points,
                "slider_repeats": slider_repeats,
            })
        except (ValueError, IndexError): continue

    objs.sort(key=lambda o: o["time_ms"])
    return objs


def resolve_path(data):
    try:
        path = os.path.join(data["folders"]["songs"], data["files"]["beatmap"])
        return path if os.path.isfile(path) else None
    except (KeyError, TypeError):
        return None


#Global state

current_path = None
hit_objects  = []
speed_change = 1.0   #DT/HT speed
stop_event   = threading.Event()
relax_thread = None


#Spinner

def do_spinner(cx, cy, end_wall, rate=1.0):
    """Parametric circle spinner: t → (cx + r*cos(θ), cy + r*sin(θ))"""
    start_wall = time.perf_counter()
    angular_velocity = (SPINNER_RPM / 60.0) * 2 * math.pi * rate  #sync to speed_change
    angle = 0.0
    
    while time.perf_counter() < end_wall:
        if stop_event.is_set():
            return
        now = time.perf_counter()
        elapsed = now - start_wall
        angle = angular_velocity * elapsed
        
        x = int(cx + SPINNER_RADIUS * math.cos(angle))
        y = int(cy + SPINNER_RADIUS * math.sin(angle))
        mouse_move(x, y)
        
        sleep_until(now + 0.001)


#Relax loop

def relax_loop(objects, sync_wall, first_note_ms, rate):
    stop_event.clear()

    moves = []  #(wall, x, y)
    keys  = []  #(press_wall, end_wall, key, is_spinner, is_slider, sx, sy)
    spinner_periods = []  #(start_wall, end_wall)
    slider_periods = []   #(start_wall, end_wall)

    key_idx = 0
    for obj in objects:
        #account for speed mods (DT/HT)
        hit_wall = sync_wall + (obj["time_ms"]     - first_note_ms) / 1000.0 / rate
        end_wall = sync_wall + (obj["end_time_ms"] - first_note_ms) / 1000.0 / rate \
                   if obj["end_time_ms"] is not None else None

        tx, ty = osu_to_screen(obj["x"], obj["y"])
        moves.append((hit_wall, tx, ty))

        if obj["is_spinner"] and end_wall:
            spinner_periods.append((hit_wall, end_wall))
        
        if obj["is_slider"] and end_wall:
            slider_periods.append((hit_wall, end_wall))
        
        if obj["is_slider"] and end_wall:
            curve_points = obj.get("slider_curve_points")
            curve_type = obj.get("slider_curve_type") or "L"
            repeats = obj.get("slider_repeats", 1)
            if curve_points and len(curve_points) > 1:
                #smooth slider sampling (200pts/sec)
                total_duration_sec = (end_wall - hit_wall)
                num_points = max(40, int(total_duration_sec * 200))  #200 pts/sec, min 40
                sampled = sample_curve(curve_type, curve_points, steps=num_points)
                total_duration = end_wall - hit_wall
                span_duration = total_duration / repeats
                for span in range(repeats):
                    span_start = hit_wall + span * span_duration
                    span_end = span_start + span_duration
                    #reverse the direction on bounces
                    pts = sampled if span % 2 == 0 else list(reversed(sampled))
                    for i in range(len(pts) - 1):
                        seg_t1 = i / (len(pts) - 1)
                        seg_t2 = (i + 1) / (len(pts) - 1)
                        seg_start = span_start + seg_t1 * span_duration
                        seg_end = span_start + seg_t2 * span_duration
                        osux1, osuy1 = pts[i]
                        osux2, osuy2 = pts[i + 1]
                        sx1, sy1 = osu_to_screen(osux1, osuy1)
                        sx2, sy2 = osu_to_screen(osux2, osuy2)
                        moves.append((seg_start, sx1, sy1))
                    #land exactly on endpoint
                    osux_end, osuy_end = pts[-1]
                    sx_end, sy_end = osu_to_screen(osux_end, osuy_end)
                    moves.append((span_end, sx_end, sy_end))
            else:
                ex, ey = osu_to_screen(obj["end_x"], obj["end_y"])
                moves.append((end_wall, ex, ey))

        key = CLICK_KEYS[key_idx % 2]
        key_idx += 1
        keys.append((
            hit_wall - EARLY_HIT_MS / 1000.0,
            end_wall, key,
            obj["is_spinner"], obj["is_slider"],
            tx, ty,
        ))

    #Build strict movement segments between successive timestamps
    #Matches the "start now, arrive exactly at next note time" behavior.
    segments = []  #(start_wall, end_wall, (x1,y1), (x2,y2))
    if len(moves) > 1:
        moves.sort(key=lambda m: m[0])
        for i in range(len(moves) - 1):
            start_wall, x1, y1 = moves[i]
            end_wall,   x2, y2 = moves[i + 1]
            if end_wall <= start_wall:
                continue
            segments.append((start_wall, end_wall, (x1, y1), (x2, y2)))
    
    def is_in_slider_or_spinner(wall):
        #check if cursor is currently in a slider or spinner
        for sp_start, sp_end in spinner_periods:
            if sp_start <= wall < sp_end:
                return True
        for sl_start, sl_end in slider_periods:
            if sl_start <= wall < sl_end:
                return True
        return False

    def cursor_worker():
        if not segments:
            #just go point by point if segments fail
            for wall, x, y in moves:
                if stop_event.is_set(): return
                sleep_until(wall)
                mouse_move(x, y)
            return

        seg_i = 0
        total = len(segments)
        while seg_i < total and not stop_event.is_set():
            start_wall, end_wall, (x1, y1), (x2, y2) = segments[seg_i]
            now = time.perf_counter()

            if now < start_wall:
                sleep_until(start_wall)
                now = time.perf_counter()

            #skip if spinning (key worker got this)
            in_spinner = any(sp_start <= now < sp_end for sp_start, sp_end in spinner_periods)
            if in_spinner:
                seg_i += 1
                continue

            while now < end_wall and not stop_event.is_set():
                #watch for spinners
                in_spinner = any(sp_start <= now < sp_end for sp_start, sp_end in spinner_periods)
                if in_spinner:
                    break

                #velocity-based motion with optional arc (disabled during sliders/spinners)
                dt = end_wall - start_wall
                elapsed = now - start_wall
                phase = elapsed / dt if dt > 0 else 0
                
                if ARC_MODE and not is_in_slider_or_spinner(elapsed + start_wall):
                    x, y = apply_arc(elapsed, dt, x1, y1, x2, y2)
                else:
                    #straight motion with smooth easing
                    eased_phase = smooth_easing(phase)
                    dx = x2 - x1
                    dy = y2 - y1
                    x = int(x1 + dx * eased_phase)
                    y = int(y1 + dy * eased_phase)
                mouse_move(x, y)
                sleep_until(now + 0.001)
                now = time.perf_counter()

            #snap to end if not spinning
            if now >= end_wall:
                in_spinner = any(sp_start <= now < sp_end for sp_start, sp_end in spinner_periods)
                if not in_spinner:
                    mouse_move(x2, y2)
            seg_i += 1

    def key_worker():
        for press_wall, end_wall, key, is_spinner, is_slider, sx, sy in keys:
            if stop_event.is_set(): return
            sleep_until(press_wall)
            key_down(key)

            if is_spinner and end_wall:
                cx, cy = osu_to_screen(OSU_W // 2, OSU_H // 2)
                do_spinner(cx, cy, end_wall, rate)
            elif is_slider and end_wall:
                sleep_until(end_wall)
            else:
                sleep_until(press_wall + 0.020)  # quick tap

            key_up(key)
        print("[relax] Map finished.")

    threading.Thread(target=cursor_worker, daemon=True).start()
    threading.Thread(target=key_worker,    daemon=True).start()


#Hotkeys

def on_f1():
    global relax_thread
    if not hit_objects:
        print("[relax] No map loaded.")
        return
    stop_event.set()
    if relax_thread and relax_thread.is_alive():
        relax_thread.join(timeout=0.5)
    first = hit_objects[0]["time_ms"]
    print(f"[relax] Synced! {len(hit_objects)} objects, first note @ {first}ms")
    relax_thread = threading.Thread(
        target=relax_loop,
        args=(hit_objects, time.perf_counter(), first, speed_change),
        daemon=True,
    )
    relax_thread.start()

def on_f2():
    stop_event.set()
    print("[relax] Stopped.")


#tosu WebSocket

def on_message(ws, message):
    global current_path, hit_objects, speed_change
    try: data = json.loads(message)
    except json.JSONDecodeError: return

    #check if DT/HT is on
    new_rate = 1.0
    for mod in data.get("play", {}).get("mods", {}).get("array", []):
        sc = mod.get("settings", {}).get("speed_change")
        if sc is not None:
            new_rate = float(sc)
            break
    if new_rate != speed_change:
        speed_change = new_rate
        print(f"[tosu] Rate: {speed_change}x")

    path = resolve_path(data)
    if path and path != current_path:
        current_path = path
        try:
            hit_objects = parse_osu_file(path)
            bm = data.get("beatmap", {})
            print(f"[tosu] {bm.get('artist','?')} - {bm.get('title','?')} "
                  f"[{bm.get('version','?')}]  |  {len(hit_objects)} objects  |  {speed_change}x")
        except Exception as e:
            print(f"[tosu] Parse error: {e}")

def on_error(ws, e): print(f"[tosu] Error: {e}")
def on_close(ws, *_):
    print("[tosu] Disconnected, retrying in 3s...")
    time.sleep(3); start_ws()

def start_ws():
    ws = websocket.WebSocketApp(TOSU_WS_URL,
        on_message=on_message, on_error=on_error, on_close=on_close)
    threading.Thread(target=ws.run_forever, daemon=True).start()


#Main

if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║    osu!lazer Relax  — ctypes SendInput   ║")
    print("║  F1 = sync on first note   F2 = stop     ║")
    print("╚══════════════════════════════════════════╝")
    print(f"  Virtual desktop: {VDESK_W}x{VDESK_H} @ ({VDESK_X},{VDESK_Y})")
    print(f"  Playfield: x={int(PF_LEFT)} y={int(PF_TOP)} "
          f"w={int(PF_W)} h={int(PF_H)}")

    keyboard.add_hotkey(SYNC_HOTKEY, on_f1)
    keyboard.add_hotkey(STOP_HOTKEY, on_f2)
    start_ws()
    print("[relax] Waiting for tosu...")
    keyboard.wait()
