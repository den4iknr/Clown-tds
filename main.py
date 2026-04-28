import pygame
import math
import random
import sys
import os
import json
# ── Inline DevConsole (active only in dev-mode: dev_save_data.json must exist) ─
_IS_DEV_MODE = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dev_save_data.json"))

class DevConsole:
    """
    In-game developer console (F3 to toggle).
    Only functional when dev_save_data.json is present next to main.py.
    For regular players the file is absent → all methods are silent no-ops.
    """

    # ── Colours / layout ──────────────────────────────────────────────────────
    BG_COL     = (10, 12, 20, 210)
    BORDER_COL = (80, 120, 200)
    INPUT_COL  = (20, 25, 40)
    TEXT_COL   = (200, 220, 255)
    ERR_COL    = (255, 80,  80)
    OK_COL     = (80,  220, 120)
    HINT_COL   = (140, 160, 200)
    W, H       = 820, 340
    MAX_LOG    = 60

    def __init__(self):
        self.active      = False
        self.input_text  = ""
        self.log         = []          # list of (text, colour)
        self._pending    = []          # deferred callables executed on tick()
        self._font_sm    = None
        self._font_md    = None
        self._initialized = False

        if not _IS_DEV_MODE:
            return  # player build — no console

        self._log("Dev console ready — F3 to toggle", self.OK_COL)
        self._log("Commands: coins <n> | addcoins <n> | wave <n> | hp <n> | "
                  "godmode | killall | clownkey | clownunlock | givecoin | "
                  "boss | help", self.HINT_COL)

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _log(self, msg, col=None):
        col = col or self.TEXT_COL
        # word-wrap at ~90 chars
        while len(msg) > 90:
            self.log.append((msg[:90], col))
            msg = "  " + msg[90:]
        self.log.append((msg, col))
        if len(self.log) > self.MAX_LOG:
            self.log = self.log[-self.MAX_LOG:]

    def _ensure_fonts(self):
        if self._initialized:
            return
        self._font_sm = pygame.font.SysFont("consolas", 13)
        self._font_md = pygame.font.SysFont("consolas", 15, bold=True)
        self._initialized = True

    # ── Public API ────────────────────────────────────────────────────────────
    def handle_event(self, ev, game) -> bool:
        """
        Process a pygame event.
        Returns True if the event was consumed (game should ignore it).
        """
        if not _IS_DEV_MODE:
            return False

        if ev.type == pygame.KEYDOWN:
            # F3 — toggle console
            if ev.key == pygame.K_F3:
                self.active = not self.active
                self.input_text = ""
                return True

            if not self.active:
                return False

            # Console is open — capture keyboard
            if ev.key == pygame.K_RETURN:
                cmd = self.input_text.strip()
                self.input_text = ""
                if cmd:
                    self._execute(cmd, game)
                return True
            elif ev.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
                return True
            elif ev.key == pygame.K_ESCAPE:
                self.active = False
                self.input_text = ""
                return True
            else:
                ch = ev.unicode
                if ch and ch.isprintable():
                    self.input_text += ch
                return True

        # Block all mouse events while console is open
        if self.active and ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                                       pygame.MOUSEMOTION, pygame.MOUSEWHEEL):
            return True

        return False

    def tick(self, game):
        """Execute any deferred actions queued by commands."""
        if not _IS_DEV_MODE:
            return
        for fn in list(self._pending):
            try:
                fn(game)
            except Exception as e:
                self._log(f"[pending error] {e}", self.ERR_COL)
        self._pending.clear()

    def draw(self, surf, dt):
        if not _IS_DEV_MODE or not self.active:
            return
        self._ensure_fonts()

        sw, sh = surf.get_size()
        x = (sw - self.W) // 2
        y = sh - self.H - 10

        # Background
        bg = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        bg.fill(self.BG_COL)
        surf.blit(bg, (x, y))
        pygame.draw.rect(surf, self.BORDER_COL, (x, y, self.W, self.H), 2, border_radius=6)

        # Title bar
        pygame.draw.rect(surf, (30, 40, 70), (x, y, self.W, 24), border_radius=4)
        title = self._font_md.render("▶ DEV CONSOLE  (F3 close | Enter execute | Esc close)", True, (160, 180, 255))
        surf.blit(title, (x + 8, y + 4))

        # Log lines
        line_h = 16
        log_area_h = self.H - 24 - 30
        visible_lines = log_area_h // line_h
        visible = self.log[-visible_lines:] if len(self.log) > visible_lines else self.log
        for i, (msg, col) in enumerate(visible):
            rendered = self._font_sm.render(msg, True, col)
            surf.blit(rendered, (x + 6, y + 26 + i * line_h))

        # Input field
        inp_y = y + self.H - 28
        pygame.draw.rect(surf, self.INPUT_COL, (x, inp_y, self.W, 28))
        pygame.draw.rect(surf, self.BORDER_COL, (x, inp_y, self.W, 28), 1)
        prompt = self._font_md.render("> " + self.input_text + ("_" if int(pygame.time.get_ticks() / 500) % 2 == 0 else " "), True, (220, 240, 255))
        surf.blit(prompt, (x + 6, inp_y + 5))

    # ── Command execution ─────────────────────────────────────────────────────
    def _execute(self, raw: str, game):
        self._log(f"> {raw}", (180, 200, 255))
        parts = raw.strip().split()
        if not parts:
            return
        cmd, args = parts[0].lower(), parts[1:]

        try:
            if cmd == "help":
                cmds = [
                    "coins <n>       — set in-game money to n",
                    "addcoins <n>    — add n to in-game money",
                    "shopcoin <n>    — set shop coins (persistent)",
                    "wave <n>        — jump to wave n",
                    "hp <n>          — set player HP to n",
                    "godmode         — toggle infinite HP",
                    "killall         — kill all enemies on screen",
                    "clownkey        — collect one clown key fragment",
                    "clownunlock     — unlock clown tower immediately",
                    "boss            — force launch clown boss fight",
                    "speed <1|2>     — set game speed multiplier",
                    "help            — show this list",
                ]
                for c in cmds:
                    self._log(c, self.HINT_COL)

            elif cmd == "coins":
                n = int(args[0])
                game.money = n
                self._log(f"Money set to {n}", self.OK_COL)

            elif cmd == "addcoins":
                n = int(args[0])
                game.money += n
                self._log(f"Added {n} coins. Total: {game.money}", self.OK_COL)

            elif cmd == "shopcoin":
                n = int(args[0])
                data = load_save()
                data["shop_coins"] = n
                save_data(data)
                self._log(f"Shop coins set to {n}", self.OK_COL)

            elif cmd == "wave":
                n = int(args[0])
                if hasattr(game, "wave_mgr"):
                    game.wave_mgr.wave = max(1, min(n, MAX_WAVES))
                    game.wave_mgr.state = "between"
                    game.wave_mgr.prep_timer = 0.1
                    self._log(f"Jumped to wave {n}", self.OK_COL)
                else:
                    self._log("No wave_mgr on this game object", self.ERR_COL)

            elif cmd == "hp":
                n = int(args[0])
                if hasattr(game, "hp"):
                    game.hp = n
                    self._log(f"HP set to {n}", self.OK_COL)
                else:
                    self._log("This game mode has no HP attribute", self.ERR_COL)

            elif cmd == "godmode":
                current = getattr(game, "_godmode", False)
                game._godmode = not current
                # Patch HP loss: wrap update if not already patched
                if game._godmode:
                    self._log("God mode ON — HP won't drop below 1", self.OK_COL)
                    orig_update = game.__class__.update
                    def _god_update(self2, dt):
                        orig_update(self2, dt)
                        if hasattr(self2, "hp"):
                            self2.hp = max(1, self2.hp)
                    game.__class__._god_update_patched = _god_update
                    game.__class__.update = _god_update
                else:
                    self._log("God mode OFF", self.OK_COL)
                    if hasattr(game.__class__, "_god_update_patched"):
                        # Can't easily un-patch, just warn
                        self._log("Restart game to fully disable godmode", self.HINT_COL)

            elif cmd == "killall":
                count = 0
                for e in getattr(game, "enemies", []):
                    if e.alive:
                        e.alive = False
                        count += 1
                self._log(f"Killed {count} enemies", self.OK_COL)

            elif cmd == "clownkey":
                source = args[0] if args else "Easy"
                ok = collect_clown_key(source)
                if ok:
                    total = total_clown_keys()
                    self._log(f"Clown key collected from {source}. Total: {total}/{CLOWN_KEYS_TOTAL}", self.OK_COL)
                else:
                    self._log(f"Already at cap for source '{source}'", self.HINT_COL)

            elif cmd == "clownunlock":
                unlock_clown()
                self._log("Clown tower unlocked!", self.OK_COL)

            elif cmd == "boss":
                self._log("Launching clown boss fight...", self.OK_COL)
                def _launch_boss(g):
                    if hasattr(g, "running"):
                        g.running = False
                        g._dev_launch_boss = True
                self._pending.append(_launch_boss)

            elif cmd == "speed":
                n = int(args[0])
                if hasattr(game, "speed_x2"):
                    game.speed_x2 = (n == 2)
                    self._log(f"Speed x{n}", self.OK_COL)
                else:
                    self._log("No speed_x2 on this game object", self.ERR_COL)

            else:
                self._log(f"Unknown command: '{cmd}'. Type 'help' for list.", self.ERR_COL)

        except (IndexError, ValueError) as e:
            self._log(f"Bad arguments: {e}", self.ERR_COL)
        except Exception as e:
            self._log(f"Error: {e}", self.ERR_COL)

pygame.init()

# ── Asset path (works regardless of working directory) ─────────────────────────
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "image")

# ── Shop currency (persistent across sessions) ─────────────────────────────────
# ── Save file: use dev_save_data.json locally if it exists (add to .gitignore)
# On GitHub / fresh installs only save_data.json exists (starts at 0 coins).
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEV_SAVE  = os.path.join(_BASE_DIR, "dev_save_data.json")
_PROD_SAVE = os.path.join(_BASE_DIR, "save_data.json")
SAVE_PATH  = _DEV_SAVE if os.path.exists(_DEV_SAVE) else _PROD_SAVE

DIFF_COIN_REWARDS = {"Easy": 200, "Hard": 350, "Hell": 500}

# ── Clown unlock via mini-game ─────────────────────────────────────────────────
CLOWN_MINIGAME_KEY = "Clown"   # stored in purchased_towers when unlocked

def is_clown_unlocked():
    return CLOWN_MINIGAME_KEY in load_save().get("purchased_towers", [])

def unlock_clown():
    data = load_save()
    if CLOWN_MINIGAME_KEY not in data.get("purchased_towers", []):
        data.setdefault("purchased_towers", []).append(CLOWN_MINIGAME_KEY)
        save_data(data)

def load_save():
    try:
        with open(SAVE_PATH, "r") as f:
            data = json.load(f)
        return {
            "shop_coins":       int(data.get("shop_coins", 0)),
            "purchased_towers": data.get("purchased_towers", []),
            "clown_keys":       data.get("clown_keys", {}),
            "loadout":          data.get("loadout", None),
        }
    except Exception:
        return {"shop_coins": 0, "purchased_towers": [], "clown_keys": {}, "loadout": None}

def save_data(data):
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

_TOWER_NAME_MAP = None  # populated lazily after class definitions

def _tower_name_map():
    """Returns {class_name: class} mapping for loadout serialization."""
    global _TOWER_NAME_MAP
    if _TOWER_NAME_MAP is None:
        _TOWER_NAME_MAP = {c.__name__: c for c in [Assassin, Accelerator, Clown, Archer, Zigres, Gunner]}
    return _TOWER_NAME_MAP

def save_loadout(loadout):
    """Persist the 5-slot loadout to save file."""
    data = load_save()
    data["loadout"] = [t.__name__ if t is not None else None for t in loadout]
    save_data(data)

def load_loadout():
    """Load saved loadout. Returns list of tower classes (or None per slot)."""
    raw = load_save().get("loadout")
    if not raw:
        return None
    nm = _tower_name_map()
    result = [nm.get(name) for name in raw]  # unknown names become None
    return result

def add_shop_coins(amount):
    data = load_save()
    data["shop_coins"] += amount
    save_data(data)
    return data["shop_coins"]

def get_shop_coins():
    return load_save()["shop_coins"]

# ── Clown Key Fragment System ──────────────────────────────────────────────────
CLOWN_KEY_SOURCES = {"Easy": 2, "Hard": 3, "Hell": 4, "Sandbox": 3}
CLOWN_KEYS_TOTAL  = 12

def get_clown_keys():
    ck = load_save().get("clown_keys", {})
    total = sum(min(ck.get(src, 0), cap) for src, cap in CLOWN_KEY_SOURCES.items())
    return ck, total

def collect_clown_key(source):
    data = load_save()
    ck   = data.get("clown_keys", {})
    cap  = CLOWN_KEY_SOURCES.get(source, 0)
    if ck.get(source, 0) >= cap:
        return False
    ck[source] = ck.get(source, 0) + 1
    data["clown_keys"] = ck
    save_data(data)
    return True

def total_clown_keys():
    _, total = get_clown_keys()
    return total

def load_icon(name, size=None):
    """Load an icon from assets/image, optionally scale it. Returns None on error."""
    path = os.path.join(ASSETS_DIR, name)
    try:
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, (size, size))
        return img
    except Exception as e:
        print(f"[icon] failed to load {name}: {e}")
        return None

# ── Constants ──────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1920, 1080
FPS  = 60
TILE = 45

C_BG       = (18, 22, 30)
C_PATH     = (55, 60, 72)
C_WHITE    = (255, 255, 255)
C_BLACK    = (0,   0,   0)
C_RED      = (220, 60,  60)
C_GREEN    = (60,  200, 80)
C_GOLD     = (255, 200, 50)
C_CYAN     = (60,  220, 220)
C_ORANGE   = (255, 140, 40)
C_PURPLE   = (180, 80,  255)
C_DARKGRAY = (40,  45,  55)
C_PANEL    = (25,  30,  42)
C_PANEL2   = (32,  38,  52)
C_BORDER   = (70,  80,  110)
C_HP_BG    = (60,  20,  20)
C_HP_FG    = (220, 60,  60)
C_HP_FG2   = (60,  200, 80)
C_SLOT_BG  = (30,  35,  48)
C_SLOT_SEL = (60,  80,  130)
C_ASSASSIN = (180, 80,  255)
C_ACCEL    = (130, 60,  255)

PATH_Y      = 510
PATH_H      = 32
SLOT_AREA_Y = SCREEN_H - 124
SLOT_W, SLOT_H = 112, 101
MAX_WAVES   = 20

# ── Changelog ─────────────────────────────────────────────────────────────────
CHANGELOG = [
    {
        "version": "v2.1",
        "date": "28 Apr 2026",
        "title": "Hidden Detection Rework + Gunner Nerf + Console Fix",
        "entries": [
            ("CHANGE", C_GOLD,   "[v2.1] Hidden enemies now visible only inside range of HD towers"),
            ("CHANGE", C_GOLD,   "[v2.1] Hidden enemies outside all HD-tower ranges are fully invisible"),
            ("CHANGE", C_GOLD,   "[v2.1] Gunner nerf: DMG 18/26/38/55/80 → 14/20/30/44/62"),
            ("CHANGE", C_GOLD,   "[v2.1] Gunner nerf: fire rate 0.85→0.92s base"),
            ("FIX",    C_CYAN,   "[v2.1] Dev console (F3) now works in all game modes"),
        ],
    },
    {
        "version": "v2.0",
        "date": "28 Apr 2026",
        "title": "Clown Key Hunt System",
        "entries": [
            ("NEW",    C_GREEN,  "[v2.0] Clown tower is now LOCKED by default"),
            ("NEW",    C_GREEN,  "[v2.0] 12 Key Fragments scattered across all game modes"),
            ("NEW",    C_GREEN,  "[v2.0] Easy: 2 keys | Hard: 3 keys | Hell: 4 keys | Sandbox: 3 keys"),
            ("NEW",    C_GREEN,  "[v2.0] Keys appear in-game as clickable golden objects"),
            ("NEW",    C_GREEN,  "[v2.0] Collecting all 12 unlocks the Clown Boss fight"),
            ("NEW",    C_GREEN,  "[v2.0] Boss fight: 3-phase arena with projectile dodge mechanics"),
            ("NEW",    C_GREEN,  "[v2.0] Boss Phase 1: normal, Phase 2: enraged, Phase 3: final stand"),
            ("NEW",    C_GREEN,  "[v2.0] Click the Boss to damage — dodge colourful projectiles!"),
            ("NEW",    C_GREEN,  "[v2.0] Key progress shown in lobby button and in-game HUD"),
        ],
    },
    {
        "version": "v1.9",
        "date": "28 Apr 2026",
        "title": "Gunner Price Increase",
        "entries": [
            ("CHANGE", C_GOLD,  "[v1.9] Gunner shop price: 300 → 600 coins"),
        ],
    },
    {
        "version": "v1.8",
        "date": "28 Apr 2026",
        "title": "Shop, Gunner Tower & Save System",
        "entries": [
            ("NEW",    C_GREEN,  "[v1.8] Shop screen added — accessible from main lobby"),
            ("NEW",    C_GREEN,  "[v1.8] Shop displays animated coin counter (shop coins)"),
            ("NEW",    C_GREEN,  "[v1.8] Gunner tower added — rotating turret, 4 upgrade levels"),
            ("NEW",    C_GREEN,  "[v1.8] Gunner: DMG 18→80, range 5.5→7.5 tiles across levels"),
            ("NEW",    C_GREEN,  "[v1.8] Gunner: tracer bullet effect on each shot"),
            ("NEW",    C_GREEN,  "[v1.8] Gunner purchasable in Shop for 300 shop coins (raised to 600 in v1.9)"),
            ("NEW",    C_GREEN,  "[v1.8] Loadout: Gunner shows lock badge with coin price"),
            ("FIX",    C_CYAN,   "[v1.8] Shop: already-owned towers can no longer be bought again"),
            ("FIX",    C_CYAN,   "[v1.8] load_save() now preserves purchased_towers field"),
            ("NEW",    C_GREEN,  "[v1.8] Dev save system: dev_save_data.json for local testing"),
            ("NEW",    C_GREEN,  "[v1.8] .gitignore: dev save excluded — GitHub users start at 0 coins"),
        ],
    },
    {
        "version": "v1.7",
        "date": "27 Apr 2026",
        "title": "Loadout Redesign & Shadow Step Rework",
        "entries": [
            ("NEW",    C_GREEN,  "[v1.7] Loadout screen fully redesigned — modern TDS-style layout"),
            ("NEW",    C_GREEN,  "[v1.7] Loadout: left panel with tower list + right detail panel"),
            ("NEW",    C_GREEN,  "[v1.7] Loadout: stat bars (DMG/SPD/RNG) per tower in detail view"),
            ("NEW",    C_GREEN,  "[v1.7] Loadout: ability list shown in detail panel"),
            ("NEW",    C_GREEN,  "[v1.7] Loadout: tower tags (MELEE, AoE, HIDDEN etc.) displayed"),
            ("CHANGE", C_GOLD,   "[v1.7] Loadout: click tower row to preview, then Add/Remove"),
            ("CHANGE", C_GOLD,   "[v1.7] Loadout: bottom deck bar replaces old slot row"),
            ("CHANGE", C_GOLD,   "[v1.7] Assassin ability: Whirlwind Slash → Shadow Step"),
            ("NEW",    C_GREEN,  "[v1.7] Shadow Step: teleport to highest-HP enemy in range"),
            ("NEW",    C_GREEN,  "[v1.7] Shadow Step: marks target — double damage for 3s"),
            ("CHANGE", C_GOLD,   "[v1.7] Shadow Step base damage: 40 → 80"),
            ("CHANGE", C_GOLD,   "[v1.7] Shadow Step Lv3 bonus: +15 → +30"),
            ("CHANGE", C_GOLD,   "[v1.7] Shadow Step Lv4 bonus: +10 → +25"),
        ],
    },
    {
        "version": "v1.6",
        "date": "27 Apr 2026",
        "title": "Hell Difficulty Rebalance",
        "entries": [
            ("CHANGE", C_GOLD,  "[v1.6] Hell mode: enemy HP now scales progressively by wave"),
            ("CHANGE", C_GOLD,  "[v1.6] Hell wave 1-3:  enemy HP x0.55 (was x1.1)"),
            ("CHANGE", C_GOLD,  "[v1.6] Hell wave 4-6:  enemy HP x0.70"),
            ("CHANGE", C_GOLD,  "[v1.6] Hell wave 7-10: enemy HP x0.85"),
            ("CHANGE", C_GOLD,  "[v1.6] Hell wave 11-14: enemy HP x1.0 (full difficulty)"),
            ("CHANGE", C_GOLD,  "[v1.6] Hell wave 15-20: enemy HP x1.1 (brutal endgame)"),
        ],
    },
    {
        "version": "v1.5",
        "date": "26 Apr 2026",
        "title": "Assassin QoL",
        "entries": [
            ("CHANGE", C_GOLD,   "[v1.5] Assassin Shadow Step: teleport+mark ability"),
            ("CHANGE", C_GOLD,   "[v1.5] Assassin ability panel anchored above slot bar"),
            ("CHANGE", C_GOLD,   "[v1.5] Assassin range: 4 tiles at Lv1-Lv4 (was 3)"),
            ("CHANGE", C_GOLD,   "[v1.5] Assassin range: 5 tiles at Lv5 max (was 4)"),
            ("NEW",    C_GREEN,  "[v1.5] Assassin Shadow Step keybind: F"),
            ("NEW",    C_GREEN,  "[v1.5] F keybind works in Sandbox mode too"),
            ("CHANGE", C_GOLD,   "[v1.5] Ability button label now shows [F] hint when ready"),
            ("CHANGE", C_GOLD,   "[v1.5] Archer buff: dmg 4→5/6/7/10/12/15 across all levels"),
            ("CHANGE", C_GOLD,   "[v1.5] Archer buff: fire rate 0.65→0.58s base, 0.6→0.42s max"),
            ("CHANGE", C_GOLD,   "[v1.5] Archer buff: range 5.5→6.0 base, 6.5→7.5 tiles max"),
            ("CHANGE", C_GOLD,   "[v1.5] Archer buff: pierce +1 at Lv5 (6→7)"),
            ("CHANGE", C_GOLD,   "[v1.5] Hard wave structure fully redesigned (20 waves)"),
            ("CHANGE", C_GOLD,   "[v1.5] MirrorShield enters at wave 8, IronMaiden at wave 15"),
            ("CHANGE", C_GOLD,   "[v1.5] VoltCrawler, ShadowStepper, TimeBender in mid-late waves"),
            ("CHANGE", C_GOLD,   "[v1.5] New enemies now affected by difficulty hp/speed mult"),
            ("CHANGE", C_GOLD,   "[v1.5] Zigres sentinel guard radius increased"),
            ("NEW",    C_GREEN,  "[v1.5] Zigres sentinel armor: 10% at Lv2-4, 15% at Lv5, 10% at Lv6"),
            ("CHANGE", C_GOLD,   "[v1.5] Removed PulseSentinel and ChainSentinel from Zigres"),
            ("NEW",    C_GREEN,  "[v1.5] Easy waves: sandbox enemies (Blob, Glass, Regen, Phantom...)"),
            ("NEW",    C_GREEN,  "[v1.5] Hell waves: sandbox elites (AbyssLord, SteelGolem, Swarm...)"),

        ],
    },
    {
        "version": "v1.1 → v1.4",
        "date": "26 Apr 2026",
        "title": "Today's Updates",
        "entries": [
            ("NEW",    C_GREEN,  "[v1.4] MirrorShield: 40% armour, glinting spinning shield"),
            ("NEW",    C_GREEN,  "[v1.4] ShadowStepper: teleports +120px every 5s, goes hidden 2s"),
            ("NEW",    C_GREEN,  "[v1.4] VoltCrawler: fast centipede, chains zap on death (80px)"),
            ("NEW",    C_GREEN,  "[v1.4] IronMaiden: 50% armour, animated spikes, pushback immune"),
            ("NEW",    C_GREEN,  "[v1.4] TimeBender: halves tower fire-rate in 180px pulse / 6s"),
            ("NEW",    C_GREEN,  "[v1.3] Clown Lv5: Confetti Explosion on kill inside aura"),
            ("NEW",    C_GREEN,  "[v1.3] Clown Lv3: 5% pushback chance on enemy per frame"),
            ("NEW",    C_GREEN,  "[v1.3] Global Clown confusion cooldown system added"),
            ("CHANGE", C_GOLD,   "[v1.3] ClownProjectile: homing steer factor tuned to dt*10"),
            ("CHANGE", C_GOLD,   "[v1.3] ClownProjectile expires if 115% beyond tower range"),
            ("FIX",    C_CYAN,   "[v1.3] Confetti pieces no longer render outside screen bounds"),
            ("NEW",    C_GREEN,  "[v1.2] Zigres tower added: summons Static Sentinels"),
            ("NEW",    C_GREEN,  "[v1.2] Zigres Lv4: Sentinel Thorns — reflect damage"),
            ("NEW",    C_GREEN,  "[v1.2] Zigres Lv5: Death Explosion on sentinel kill"),
            ("NEW",    C_GREEN,  "[v1.2] Zigres Lv6: COLOSSUS form + Duck Throw projectile"),
            ("NEW",    C_GREEN,  "[v1.2] Resonance AoE at Lv3 hits all enemies in radius"),
            ("CHANGE", C_GOLD,   "[v1.2] Zigres hidden detection unlocked at Lv2"),
            ("NEW",    C_GREEN,  "[v1.1] Archer tower: placeable ON the road"),
            ("NEW",    C_GREEN,  "[v1.1] Ice Arrow (Archer Lv2): freeze on hit"),
            ("NEW",    C_GREEN,  "[v1.1] Flame Arrow (Archer Lv3): fire DOT effect"),
            ("NEW",    C_GREEN,  "[v1.1] Fire/Ice status effect visuals on enemies"),
            ("NEW",    C_GREEN,  "[v1.1] Archer Lv4: hidden detection"),
            ("CHANGE", C_GOLD,   "[v1.1] Pierce mechanic: arrow hits multiple enemies in line"),
            ("FIX",    C_CYAN,   "[v1.1] Arrow sprite angle now matches target direction"),
        ],
    },
    {
        "version": "v1.0",
        "date": "25 Apr 2026",
        "title": "Initial Release",
        "entries": [
            ("NEW",    C_GREEN,  "Tower Defense Simulator — first public release"),
            ("NEW",    C_GREEN,  "Assassin tower with Shadow Step ability"),
            ("NEW",    C_GREEN,  "Accelerator tower with laser beam mechanic"),
            ("NEW",    C_GREEN,  "20-wave progression system"),
            ("NEW",    C_GREEN,  "GraveDigger boss on Wave 20"),
            ("NEW",    C_GREEN,  "3 difficulty modes: Easy, Hard, Hell"),
            ("NEW",    C_GREEN,  "Lobby with loadout customisation (5 slots)"),
            ("NEW",    C_GREEN,  "Speed x2 and Skip Wave buttons in-game"),
            ("NEW",    C_GREEN,  "Pause menu with resume / exit"),
        ],
    },
]

font_sm = pygame.font.SysFont("consolas", 14)
font_md = pygame.font.SysFont("consolas", 17, bold=True)
font_lg = pygame.font.SysFont("consolas", 22, bold=True)
font_xl = pygame.font.SysFont("consolas", 29, bold=True)

# Global effects list for death particles (filled by Enemy.take_damage)
_GLOBAL_EFFECTS = []

# ── Icons — loaded lazily after display is ready ──────────────────────────────
ICO_DAMAGE = ICO_RANGE = ICO_FIRERATE = ICO_HIDDET = ICO_SLOW = None
ICO_FIRE = ICO_RDMG = ICO_ARROW = ICO_COIN = ICO_MONEY = None
STAT_ICONS_IMG = {}

def _load_all_icons():
    global ICO_DAMAGE, ICO_RANGE, ICO_FIRERATE, ICO_HIDDET, ICO_SLOW
    global ICO_FIRE, ICO_RDMG, ICO_ARROW, ICO_COIN, ICO_MONEY, STAT_ICONS_IMG
    ICO_DAMAGE   = load_icon("damage_ico.png",           20)
    ICO_RANGE    = load_icon("range_ico.png",            20)
    ICO_FIRERATE = load_icon("firerate_ico.png",         20)
    ICO_HIDDET   = load_icon("hidden_detection_ico.png", 20)
    ICO_SLOW     = load_icon("slow_ico.png",             20)
    ICO_FIRE     = load_icon("fire_ico.png",             20)
    ICO_RDMG     = load_icon("ranged_damage_ico.png",    20)
    ICO_ARROW    = load_icon("arrow_ico.png",            16)
    ICO_COIN     = load_icon("coin_ico.png",             32)
    ICO_MONEY    = load_icon("money_ico.png",            32)
    STAT_ICONS_IMG.update({
        "Damage":   ICO_DAMAGE,
        "Range":    ICO_RANGE,
        "Firerate": ICO_FIRERATE,
        "Dual":     ICO_RDMG,
        "Slow":     ICO_SLOW,
    })

def blit_icon(surf, ico, cx, cy):
    if ico is None:
        return
    surf.blit(ico, (cx - ico.get_width() // 2, cy - ico.get_height() // 2))

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def try_stun(enemy, duration):
    """Apply stun to enemy only if not currently immune (Zigres stun CD)."""
    if getattr(enemy, '_stun_immune_timer', 0) > 0:
        return False  # immune — skip stun
    enemy._stun_timer = max(getattr(enemy, '_stun_timer', 0), duration)
    return True

def txt(surf, text, pos, color=C_WHITE, f=font_md, center=False, right=False):
    s = f.render(str(text), True, color)
    r = s.get_rect()
    if center: r.center = pos
    elif right: r.right, r.centery = pos[0], pos[1]
    else: r.topleft = pos
    surf.blit(s, r)
    return r

def draw_rect_alpha(surf, color, rect, alpha=120, brad=0):
    s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(s, (*color[:3], alpha), (0,0,rect[2],rect[3]), border_radius=brad)
    surf.blit(s, (rect[0], rect[1]))

def draw_hidden_ghost(surf, cx, cy, radius):
    """Draw a ghostly semi-transparent silhouette for hidden enemies not yet detected.
    Shows the player something is there without revealing full details."""
    s = pygame.Surface((radius*4, radius*4), pygame.SRCALPHA)
    c = radius * 2
    # Faint pulsing ghost circle
    pygame.draw.circle(s, (180, 180, 220, 28), (c, c), radius + 4)
    pygame.draw.circle(s, (200, 200, 255, 18), (c, c), radius, 2)
    # Small question-mark dots
    for dx, dy in [(-3, -3), (3, -3), (0, 4)]:
        pygame.draw.circle(s, (200, 200, 255, 40), (c + dx, c + dy), 2)
    surf.blit(s, (cx - c, cy - c))

def draw_rect_gradient(surf, col_top, col_bot, rect, alpha=220, brad=0):
    """Vertical gradient rectangle."""
    w, h = int(rect[2]), int(rect[3])
    if w <= 0 or h <= 0: return
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(h):
        t = i / max(1, h - 1)
        r2 = int(col_top[0] + (col_bot[0] - col_top[0]) * t)
        g2 = int(col_top[1] + (col_bot[1] - col_top[1]) * t)
        b2 = int(col_top[2] + (col_bot[2] - col_top[2]) * t)
        pygame.draw.line(s, (r2, g2, b2, alpha), (0, i), (w, i))
    if brad > 0:
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255,255,255,255), (0,0,w,h), border_radius=brad)
        s.blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(s, (rect[0], rect[1]))

def draw_glow_circle(surf, color, center, radius, intensity=80):
    """Soft radial glow."""
    for r in range(radius, 0, -max(1, radius//6)):
        a = int(intensity * (r / radius) ** 0.5)
        s = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color[:3], a), (r+1, r+1), r)
        surf.blit(s, (center[0]-r-1, center[1]-r-1))

# ── Particle / floating-text effects ──────────────────────────────────────────
class DeathParticle:
    def __init__(self, x, y, color):
        self.x = float(x); self.y = float(y)
        self.vx = random.uniform(-120, 120)
        self.vy = random.uniform(-180, 60)
        self.color = color
        self.life = random.uniform(0.3, 0.7); self.t = 0.0
        self.size = random.randint(3, 7)
    def update(self, dt):
        self.t += dt; self.x += self.vx*dt; self.y += self.vy*dt
        self.vy += 200*dt; return self.t < self.life
    def draw(self, surf):
        a = int(255*(1-self.t/self.life))
        s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color[:3], a), (self.size, self.size), self.size)
        surf.blit(s, (int(self.x)-self.size, int(self.y)-self.size))

# ── Visual Effects ─────────────────────────────────────────────────────────────
class SwordEffect:
    def __init__(self, ox, oy, angle):
        self.ox=ox; self.oy=oy; self.angle=angle
        self.life=0.22; self.t=0.0; self.length=55
    def update(self, dt):
        self.t += dt; return self.t < self.life
    def draw(self, surf):
        progress=self.t/self.life; alpha=int(255*(1-progress)); sweep=60*progress
        s=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        for i in range(8):
            a=math.radians(self.angle-sweep*(i/7))
            ex=self.ox+math.cos(a)*self.length; ey=self.oy+math.sin(a)*self.length
            pygame.draw.line(s,(200,200,255,max(0,alpha-i*25)),
                             (int(self.ox),int(self.oy)),(int(ex),int(ey)),3)
        surf.blit(s,(0,0))

class ShadowStepEffect:
    """Dark teleport burst: vanish at origin, reappear at target."""
    def __init__(self, ox, oy, tx, ty):
        self.ox=ox; self.oy=oy; self.tx=tx; self.ty=ty
        self.life=0.7; self.t=0.0
    def update(self, dt):
        self.t+=dt; return self.t<self.life
    def draw(self, surf):
        p=self.t/self.life
        s=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        # vanish ring at origin
        if p<0.4:
            rp=p/0.4; a=int(180*(1-rp))
            rad=int(8+rp*30)
            pygame.draw.circle(s,(120,60,200,a),(int(self.ox),int(self.oy)),rad,3)
            for i in range(8):
                ang=math.radians(i*45+rp*360)
                px2=self.ox+math.cos(ang)*rad; py2=self.oy+math.sin(ang)*rad
                pygame.draw.circle(s,(200,120,255,max(0,a-40)),(int(px2),int(py2)),4)
        # travel trail line
        if 0.15<p<0.75:
            tp=(p-0.15)/0.6; a=int(120*(1-abs(tp-0.5)*2))
            mx2=self.ox+(self.tx-self.ox)*tp; my2=self.oy+(self.ty-self.oy)*tp
            for seg in range(5):
                frac=seg/5
                sx2=self.ox+(self.tx-self.ox)*max(0,tp-frac*0.3)
                sy2=self.oy+(self.ty-self.oy)*max(0,tp-frac*0.3)
                pygame.draw.circle(s,(140,70,220,max(0,a-seg*18)),(int(sx2),int(sy2)),max(1,4-seg))
        # impact burst at target
        if p>0.55:
            rp2=(p-0.55)/0.45; a2=int(220*(1-rp2))
            rad2=int(6+rp2*40)
            pygame.draw.circle(s,(80,30,160,max(0,a2//2)),(int(self.tx),int(self.ty)),rad2)
            pygame.draw.circle(s,(200,140,255,max(0,a2)),(int(self.tx),int(self.ty)),rad2,3)
            for i in range(6):
                ang=math.radians(i*60+rp2*180)
                ex2=self.tx+math.cos(ang)*(12+rp2*22)
                ey2=self.ty+math.sin(ang)*(12+rp2*22)
                pygame.draw.line(s,(220,160,255,max(0,a2)),
                    (int(self.tx),int(self.ty)),(int(ex2),int(ey2)),2)
        surf.blit(s,(0,0))

# ── Clown Effects ──────────────────────────────────────────────────────────────
class ConfettiExplosionEffect:
    """Visual confetti burst when a Clown Lv5 kills an enemy inside its aura."""
    _COLORS = [(220,60,60),(255,200,50),(60,220,220),(180,80,255),(60,200,80),(255,140,40)]

    def __init__(self, ox, oy):
        self.ox = ox; self.oy = oy
        self.life = 1.2; self.t = 0.0
        self._pieces = [
            {
                "angle": random.uniform(0, math.tau),
                "speed": random.uniform(80, 260),
                "color": random.choice(self._COLORS),
                "size":  random.randint(4, 10),
                "rot":   random.uniform(0, math.tau),
                "rspd":  random.uniform(-6, 6),
            }
            for _ in range(28)
        ]

    def update(self, dt):
        self.t += dt
        return self.t < self.life

    def draw(self, surf):
        progress = self.t / self.life
        alpha    = int(255 * (1 - progress))
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for p in self._pieces:
            d  = p["speed"] * self.t
            px = self.ox + math.cos(p["angle"]) * d
            py = self.oy + math.sin(p["angle"]) * d + 120 * self.t * self.t  # gravity
            rot = p["rot"] + p["rspd"] * self.t
            sz  = max(1, p["size"] - int(p["size"] * progress * 0.5))
            c   = (*p["color"], max(0, alpha))
            cos_r, sin_r = math.cos(rot), math.sin(rot)
            hw, hh = sz, sz // 2
            corners = [
                (px + cos_r*hw - sin_r*hh, py + sin_r*hw + cos_r*hh),
                (px - cos_r*hw - sin_r*hh, py - sin_r*hw + cos_r*hh),
                (px - cos_r*hw + sin_r*hh, py - sin_r*hw - cos_r*hh),
                (px + cos_r*hw + sin_r*hh, py + sin_r*hw - cos_r*hh),
            ]
            pygame.draw.polygon(s, c, [(int(x), int(y)) for x, y in corners])
        surf.blit(s, (0, 0))


class ClownProjectile:
    """A homing colourful ball shot by the Clown tower.
    * Never misses – steers toward target every frame.
    * Disappears if it travels beyond the tower's range with no living target.
    """
    _COLORS = [(220,60,60),(255,200,50),(60,220,220),(180,80,255),(255,140,40)]
    _SPD    = 520   # px/s base flight speed

    def __init__(self, ox, oy, target, damage, tower_range_px):
        self.x = float(ox); self.y = float(oy)
        self.ox = ox; self.oy = oy               # spawn point (for range check)
        self.tower_range_px = tower_range_px
        self.target  = target
        self.alive   = True
        self._color  = random.choice(self._COLORS)
        self._damage = damage
        # initial velocity toward target
        dx = target.x - ox; dy = target.y - oy
        d  = math.hypot(dx, dy) or 1
        self.vx = dx / d * self._SPD
        self.vy = dy / d * self._SPD

    def update(self, dt):
        if not self.alive: return False

        # If target is dead, keep flying straight – expire once out of range
        if not self.target.alive:
            self.x += self.vx * dt; self.y += self.vy * dt
            if dist((self.x, self.y), (self.ox, self.oy)) > self.tower_range_px:
                self.alive = False
            return self.alive

        # Steer toward current target position (homing)
        dx = self.target.x - self.x; dy = self.target.y - self.y
        d  = math.hypot(dx, dy)
        if d < 1:
            # Reached target – deal damage immediately
            self.target.take_damage(self._damage)
            self.target._clown_pushback = True
            self.alive = False
            return False
        # Blend velocity toward target direction (smooth homing)
        tx = dx / d * self._SPD; ty = dy / d * self._SPD
        steer = min(1.0, dt * 10)           # how fast it corrects course
        self.vx = self.vx + (tx - self.vx) * steer
        self.vy = self.vy + (ty - self.vy) * steer
        self.x += self.vx * dt; self.y += self.vy * dt

        # Hit check
        if math.hypot(self.x - self.target.x, self.y - self.target.y) < 18:
            self.target.take_damage(self._damage)
            self.target._clown_pushback = True
            self.alive = False

        # Expire if somehow went past range (shouldn't happen with homing, safety net)
        if dist((self.x, self.y), (self.ox, self.oy)) > self.tower_range_px * 1.15:
            self.alive = False

        return self.alive

    def draw(self, surf):
        if not self.alive: return
        pygame.draw.circle(surf, self._color, (int(self.x), int(self.y)), 7)
        pygame.draw.circle(surf, C_WHITE,     (int(self.x), int(self.y)), 7, 2)


# ── Enemy base ─────────────────────────────────────────────────────────────────
class Enemy:
    DISPLAY_NAME="Normal"
    BASE_HP=8; BASE_SPEED=110; KILL_REWARD=0
    IS_HIDDEN=False; ARMOR=0.0
    _DEATH_COLOR=(200,80,80)

    def __init__(self, wave=1):
        self.x=-60.0; self.y=float(PATH_Y)
        self.hp=max(1,self.BASE_HP+(wave-1)*2)
        self.maxhp=self.hp
        self.speed=self.BASE_SPEED+(wave-1)*6
        self.alive=True; self.radius=20
        self._bob=random.uniform(0,math.pi*2)
        self.free_kill=False
        # ── Clown debuffs ──────────────────────────────
        self._stun_timer        = 0.0   # seconds remaining frozen
        self._stun_immune_timer = 0.0   # stun immunity CD after being stunned (Zigres CD)
        self._slow_factor  = 1.0   # multiplier (< 1 = slower), reset each frame by aura
        self._laugh_debuff   = False  # takes 20% more damage from all towers
        self._shadow_marked  = 0.0     # Shadow Step: takes double dmg while > 0
        self._clown_pushback = False  # flag: Clown Lv3 pushback chance pending

    def update(self, dt):
        # Tick stun immunity cooldown
        if self._stun_immune_timer > 0:
            self._stun_immune_timer = max(0.0, self._stun_immune_timer - dt)
        # Apply stun: freeze movement
        if self._stun_timer > 0:
            self._stun_timer -= dt
            if self._stun_timer <= 0:
                self._stun_immune_timer = 5.0  # 5s immunity after stun wears off
            self._bob += dt * 4
            return False
        eff_speed = self.speed * self._slow_factor
        self.x += eff_speed * dt; self._bob += dt * 4
        # Reset slow each frame (aura re-applies it every tick)
        self._slow_factor = 1.0
        if self.x > SCREEN_W + 40: self.alive = False; return True
        return False

    def take_damage(self, dmg):
        # Laugh debuff: 20% extra damage from all sources
        if self._laugh_debuff:
            dmg *= 1.20
        # Shadow Step mark: double incoming damage
        if getattr(self, '_shadow_marked', 0) > 0:
            dmg *= 2.0
        self.hp -= dmg * (1.0 - self.ARMOR)
        if self.hp <= 0:
            self.alive = False
            try:
                col = getattr(self.__class__, '_DEATH_COLOR', (200,80,80))
                for _ in range(random.randint(5,10)):
                    _GLOBAL_EFFECTS.append(DeathParticle(self.x, self.y, col))
            except Exception:
                pass

    def _draw_hp_bar(self, surf, bw, bh, border_col=None):
        bob=math.sin(self._bob)*2; cx,cy=int(self.x),int(self.y+bob)
        bx=cx-bw//2; by=cy-self.radius-12
        # shadow
        pygame.draw.rect(surf,(0,0,0),(bx-1,by-1,bw+2,bh+2),border_radius=3)
        pygame.draw.rect(surf,(20,8,8),(bx,by,bw,bh),border_radius=3)
        fill=max(0,int(bw*self.hp/max(1,self.maxhp)))
        if fill:
            ratio = self.hp/max(1,self.maxhp)
            if ratio > 0.5:   c1,c2 = (80,230,100),(50,160,70)
            elif ratio > 0.25: c1,c2 = (230,180,30),(160,120,20)
            else:              c1,c2 = (230,60,60),(160,30,30)
            draw_rect_gradient(surf, c1, c2, (bx,by,fill,bh), alpha=255, brad=3)
            draw_rect_alpha(surf,(255,255,255),(bx,by,fill,max(1,bh//2)),30,brad=3)
        pygame.draw.rect(surf, border_col if border_col else (0,0,0),
                         (bx,by,bw,bh), 1, border_radius=3)

    def _hover_label(self, surf):
        bob=math.sin(self._bob)*2; cx,cy=int(self.x),int(self.y+bob)
        mods=[]
        if self.ARMOR>0: mods.append(f"Armor {int(self.ARMOR*100)}%")
        if self.IS_HIDDEN: mods.append("Hidden")
        label=self.DISPLAY_NAME+("  ["+", ".join(mods)+"]" if mods else "")
        txt(surf,label,(cx,cy-self.radius-40),C_GOLD,font_sm,center=True)
        txt(surf,f"HP {int(self.hp)}/{int(self.maxhp)}",(cx,cy-self.radius-22),C_WHITE,font_sm,center=True)

    def _draw_status_effects(self, surf):
        """Draw fire and ice status effect overlays on the enemy."""
        cx, cy = int(self.x), int(self.y)
        t = self._bob  # reuse bob timer for animation

        on_fire = getattr(self, '_fire_timer', 0.0) > 0
        on_ice  = getattr(self, '_ice_timer',  0.0) > 0

        if on_fire:
            s = pygame.Surface((self.radius*4, self.radius*4), pygame.SRCALPHA)
            sc = self.radius*2  # centre of surface
            # animated flame licks around the enemy
            for i in range(8):
                angle = math.radians(i * 45 + t * 200)
                flicker = abs(math.sin(t * 6 + i * 0.9))
                fx = sc + int(math.cos(angle) * (self.radius * 0.7))
                fy = sc + int(math.sin(angle) * (self.radius * 0.7))
                flame_h = int(12 + flicker * 14)
                # outer orange glow
                pygame.draw.circle(s, (255, 100, 0, int(80 * flicker)),
                                   (fx, fy - flame_h // 2), flame_h // 2 + 3)
                # inner yellow core
                pygame.draw.circle(s, (255, 220, 50, int(160 * flicker)),
                                   (fx, fy - flame_h // 2), flame_h // 3)
            # red-orange halo
            pygame.draw.circle(s, (220, 60, 0, 55), (sc, sc), self.radius + 4)
            surf.blit(s, (cx - sc, cy - sc))
            # 🔥 icon above enemy
            fire_f = pygame.font.SysFont("consolas", 22)
            fire_surf = fire_f.render("🔥", True, (255, 160, 30))
            surf.blit(fire_surf, (cx - fire_surf.get_width()//2,
                                  cy - self.radius - 46))

        if on_ice:
            s2 = pygame.Surface((self.radius*4, self.radius*4), pygame.SRCALPHA)
            sc2 = self.radius*2
            # icy blue overlay
            pygame.draw.circle(s2, (80, 180, 255, 70), (sc2, sc2), self.radius + 6)
            pygame.draw.circle(s2, (160, 230, 255, 40), (sc2, sc2), self.radius + 10)
            # snowflake-like spokes
            for i in range(6):
                angle = math.radians(i * 60 + t * 30)
                ex2 = sc2 + int(math.cos(angle) * (self.radius + 8))
                ey2 = sc2 + int(math.sin(angle) * (self.radius + 8))
                pygame.draw.line(s2, (160, 230, 255, 180),
                                 (sc2, sc2), (ex2, ey2), 2)
                # small diamonds at tips
                pygame.draw.circle(s2, (220, 245, 255, 200), (ex2, ey2), 3)
            surf.blit(s2, (cx - sc2, cy - sc2))
            # ❄ icon above enemy
            ice_f = pygame.font.SysFont("consolas", 22)
            ice_surf = ice_f.render("❄", True, (120, 210, 255))
            surf.blit(ice_surf, (cx - ice_surf.get_width()//2,
                                 cy - self.radius - 46))

    def draw(self, surf, hovered=False, detected=False):
        bob=math.sin(self._bob)*2; cx,cy=int(self.x),int(self.y+bob)
        pygame.draw.circle(surf,(160,50,50),(cx,cy),self.radius)
        pygame.draw.circle(surf,(220,100,100),(cx-8,cy-8),12)
        pygame.draw.circle(surf,C_WHITE,(cx,cy),self.radius,2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf,60,10)
        if hovered: self._hover_label(surf)

# ── Enemy subclasses ───────────────────────────────────────────────────────────
class TankEnemy(Enemy):
    DISPLAY_NAME="Slow"; BASE_HP=30; BASE_SPEED=56; KILL_REWARD=0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp=max(1,self.BASE_HP+(wave-1)*4); self.maxhp=self.hp
        self.speed=self.BASE_SPEED+(wave-1); self.radius=36
    def draw(self, surf, hovered=False, detected=False):
        bob=math.sin(self._bob); cx,cy=int(self.x),int(self.y+bob)
        pygame.draw.circle(surf,(100,60,20),(cx,cy),self.radius)
        pygame.draw.circle(surf,(160,110,60),(cx-10,cy-10),14)
        pygame.draw.circle(surf,(200,160,90),(cx,cy),self.radius,3)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf,72,10)
        if hovered: self._hover_label(surf)

class ScoutEnemy(Enemy):
    DISPLAY_NAME="Fast"; BASE_HP=10; BASE_SPEED=280; KILL_REWARD=0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp=max(1,self.BASE_HP+(wave-1)); self.maxhp=self.hp
        self.speed=self.BASE_SPEED+(wave-1)*10; self.radius=20
    def draw(self, surf, hovered=False, detected=False):
        bob=math.sin(self._bob*1.6)*3; cx,cy=int(self.x),int(self.y+bob)
        pygame.draw.circle(surf,(40,140,180),(cx,cy),self.radius)
        pygame.draw.circle(surf,(140,230,255),(cx-6,cy-6),8)
        pygame.draw.circle(surf,(180,240,255),(cx,cy),self.radius,2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf,44,8)
        if hovered: self._hover_label(surf)

class NormalBoss(Enemy):
    DISPLAY_NAME="Normal Boss"; BASE_HP=250; BASE_SPEED=110; KILL_REWARD=0
    _DEATH_COLOR=(220,180,40)
    def __init__(self, wave=1):
        super().__init__(wave)
        bonus=max(0,wave-6)*20
        self.hp=self.BASE_HP+bonus; self.maxhp=self.hp
        self.speed=self.BASE_SPEED; self.radius=44
    def draw(self, surf, hovered=False, detected=False):
        bob=math.sin(self._bob*0.8)*1.5; cx,cy=int(self.x),int(self.y+bob)
        draw_glow_circle(surf,(200,150,20),(cx,cy),self.radius+18,38)
        s=pygame.Surface((160,160),pygame.SRCALPHA)
        pygame.draw.circle(s,(180,20,20,35),(40,40),38); surf.blit(s,(cx-40,cy-40))
        pygame.draw.circle(surf,(180,140,20),(cx,cy),self.radius+3,3)
        pygame.draw.circle(surf,(130,20,20),(cx,cy),self.radius)
        pygame.draw.circle(surf,(200,50,50),(cx-12,cy-12),18)
        pygame.draw.circle(surf,(240,200,60),(cx,cy),self.radius,2)
        for i in range(5):
            a=math.radians(-90+i*36)
            sx2=cx+math.cos(a)*(self.radius+2); sy2=cy+math.sin(a)*(self.radius+2)
            ex=cx+math.cos(a)*(self.radius+10); ey=cy+math.sin(a)*(self.radius+10)
            pygame.draw.line(surf,(240,200,60),(int(sx2),int(sy2)),(int(ex),int(ey)),2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf,100,12,(240,200,60))
        if hovered: self._hover_label(surf)

class HiddenEnemy(Enemy):
    DISPLAY_NAME="Hidden"; BASE_HP=8; BASE_SPEED=110; KILL_REWARD=0; IS_HIDDEN=True
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp=max(1,self.BASE_HP+(wave-1)*2); self.maxhp=self.hp
    def draw(self, surf, hovered=False, detected=False):
        if not detected and not hovered:
            draw_hidden_ghost(surf, int(self.x), int(self.y), self.radius); return
        bob=math.sin(self._bob)*2; cx,cy=int(self.x),int(self.y+bob)
        alpha=180 if detected else 220
        s=pygame.Surface((100,100),pygame.SRCALPHA)
        pygame.draw.circle(s,(100,200,100,alpha),(25,25),self.radius)
        pygame.draw.circle(s,(180,255,180,alpha),(21,21),5)
        pygame.draw.circle(s,(200,255,200,alpha//2),(25,25),self.radius,2)
        surf.blit(s,(cx-25,cy-25))
        self._draw_status_effects(surf)
        if detected or hovered: self._draw_hp_bar(surf,60,10,(100,255,100))
        if hovered: self._hover_label(surf)

class BreakerEnemy(Enemy):
    DISPLAY_NAME="Breaker"; BASE_HP=30; BASE_SPEED=110; KILL_REWARD=0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp=30; self.maxhp=30; self.speed=self.BASE_SPEED; self.radius=22
    def draw(self, surf, hovered=False, detected=False):
        bob=math.sin(self._bob)*2; cx,cy=int(self.x),int(self.y+bob)
        pygame.draw.circle(surf,(140,100,20),(cx,cy),self.radius)
        pygame.draw.circle(surf,(220,180,60),(cx-8,cy-8),12)
        pygame.draw.circle(surf,(255,220,80),(cx,cy),self.radius,2)
        for i in range(3):
            a=math.radians(i*120+30)
            x1=cx+int(math.cos(a)*4); y1=cy+int(math.sin(a)*4)
            x2=cx+int(math.cos(a)*self.radius); y2=cy+int(math.sin(a)*self.radius)
            pygame.draw.line(surf,(60,40,0),(x1,y1),(x2,y2),2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf,60,10,(255,220,80))
        if hovered: self._hover_label(surf)

class ArmoredEnemy(Enemy):
    DISPLAY_NAME="Armored"; BASE_HP=25; BASE_SPEED=110; KILL_REWARD=0; ARMOR=0.20
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp=max(1,self.BASE_HP+(wave-1)*3); self.maxhp=self.hp; self.radius=23
    def draw(self, surf, hovered=False, detected=False):
        bob=math.sin(self._bob)*2; cx,cy=int(self.x),int(self.y+bob)
        pygame.draw.circle(surf,(80,90,110),(cx,cy),self.radius)
        pygame.draw.circle(surf,(140,160,190),(cx-8,cy-8),12)
        pygame.draw.circle(surf,(180,200,220),(cx,cy),self.radius,3)
        for i in range(4):
            a=math.radians(i*90+45)
            x1=cx+int(math.cos(a)*8); y1=cy+int(math.sin(a)*8)
            x2=cx+int(math.cos(a)*self.radius); y2=cy+int(math.sin(a)*self.radius)
            pygame.draw.line(surf,(200,220,255),(x1,y1),(x2,y2),2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf,64,10,(180,200,220))
        if hovered: self._hover_label(surf)

class SlowBoss(Enemy):
    DISPLAY_NAME="Slow Boss"; BASE_HP=1500; BASE_SPEED=56; KILL_REWARD=0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp=1500; self.maxhp=1500; self.speed=self.BASE_SPEED; self.radius=40
    def draw(self, surf, hovered=False, detected=False):
        bob=math.sin(self._bob*0.5); cx,cy=int(self.x),int(self.y+bob)
        s=pygame.Surface((180,180),pygame.SRCALPHA)
        pygame.draw.circle(s,(140,80,20,40),(45,45),44); surf.blit(s,(cx-45,cy-45))
        pygame.draw.circle(surf,(200,140,30),(cx,cy),self.radius+4,4)
        pygame.draw.circle(surf,(120,60,10),(cx,cy),self.radius)
        pygame.draw.circle(surf,(200,120,50),(cx-14,cy-14),20)
        pygame.draw.circle(surf,(240,180,60),(cx,cy),self.radius,2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf,120,14,(200,140,30))
        if hovered: self._hover_label(surf)

class HiddenBoss(NormalBoss):
    DISPLAY_NAME="Hidden Boss"; IS_HIDDEN=True
    def __init__(self, wave=1):
        super().__init__(wave)
    def draw(self, surf, hovered=False, detected=False):
        if not detected and not hovered:
            draw_hidden_ghost(surf, int(self.x), int(self.y), self.radius); return
        bob=math.sin(self._bob*0.8)*1.5; cx,cy=int(self.x),int(self.y+bob)
        s=pygame.Surface((160,160),pygame.SRCALPHA)
        pygame.draw.circle(s,(80,180,80,50),(40,40),38); surf.blit(s,(cx-40,cy-40))
        pygame.draw.circle(surf,(80,160,80),(cx,cy),self.radius+3,3)
        pygame.draw.circle(surf,(40,100,40),(cx,cy),self.radius)
        pygame.draw.circle(surf,(120,220,120),(cx-12,cy-12),18)
        pygame.draw.circle(surf,(180,240,180),(cx,cy),self.radius,2)
        for i in range(5):
            a=math.radians(-90+i*36)
            sx2=cx+math.cos(a)*(self.radius+2); sy2=cy+math.sin(a)*(self.radius+2)
            ex=cx+math.cos(a)*(self.radius+10); ey=cy+math.sin(a)*(self.radius+10)
            pygame.draw.line(surf,(180,240,180),(int(sx2),int(sy2)),(int(ex),int(ey)),2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf,100,12,(180,240,180))
        if hovered: self._hover_label(surf)

class Necromancer(Enemy):
    DISPLAY_NAME="Necromancer"; BASE_HP=360; BASE_SPEED=110; KILL_REWARD=0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp=360; self.maxhp=360; self.speed=self.BASE_SPEED
        self.radius=32; self._summon_timer=5.0
    def update(self, dt):
        self._summon_timer-=dt
        return super().update(dt)
    def should_summon(self):
        if self._summon_timer<=0: self._summon_timer=5.0; return True
        return False
    def draw(self, surf, hovered=False, detected=False):
        bob=math.sin(self._bob*0.8)*1.5; cx,cy=int(self.x),int(self.y+bob)
        s=pygame.Surface((160,160),pygame.SRCALPHA)
        pygame.draw.circle(s,(80,0,120,40),(40,40),38); surf.blit(s,(cx-40,cy-40))
        pygame.draw.circle(surf,(100,0,160),(cx,cy),self.radius+3,3)
        pygame.draw.circle(surf,(60,0,100),(cx,cy),self.radius)
        pygame.draw.circle(surf,(160,80,220),(cx-10,cy-10),14)
        pygame.draw.circle(surf,(200,100,255),(cx,cy),self.radius,2)
        for i in range(4):
            a=math.radians(i*90+self._bob*20)
            px2=cx+int(math.cos(a)*(self.radius+6)); py2=cy+int(math.sin(a)*(self.radius+6))
            pygame.draw.circle(surf,(220,220,255),(px2,py2),3)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf,100,12,(200,100,255))
        if hovered: self._hover_label(surf)

class GraveDigger(Enemy):
    DISPLAY_NAME="Grave Digger"; BASE_HP=15000; BASE_SPEED=90; KILL_REWARD=0
    _DEATH_COLOR=(80,255,80)
    def __init__(self):
        super().__init__(1)
        self.hp=15000; self.maxhp=15000; self.speed=self.BASE_SPEED; self.radius=46
        self._rot=0.0
    def update(self, dt):
        self._rot+=dt*90; return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob=math.sin(self._bob*0.6); cx,cy=int(self.x),int(self.y+bob)
        pulse=int(abs(math.sin(self._rot/90*math.pi))*20)
        draw_glow_circle(surf,(50,200,50),(cx,cy),self.radius+22+pulse//2,40)
        s=pygame.Surface((220,220),pygame.SRCALPHA)
        pygame.draw.circle(s,(50,150,50,30+pulse),(55,55),52); surf.blit(s,(cx-55,cy-55))
        for i in range(8):
            a=math.radians(self._rot+i*45)
            rx=cx+int(math.cos(a)*(self.radius+8)); ry=cy+int(math.sin(a)*(self.radius+8))
            pygame.draw.circle(surf,(100,220,100),(rx,ry),4)
        pygame.draw.circle(surf,(30,100,30),(cx,cy),self.radius+4,5)
        pygame.draw.circle(surf,(20,60,20),(cx,cy),self.radius)
        pygame.draw.circle(surf,(80,200,80),(cx-16,cy-16),24)
        pygame.draw.circle(surf,(140,255,140),(cx,cy),self.radius,2)
        shovel_a=math.radians(self._rot*0.5)
        sx2=cx+int(math.cos(shovel_a)*10); sy2=cy+int(math.sin(shovel_a)*10)
        ex=cx+int(math.cos(shovel_a)*(self.radius+5)); ey=cy+int(math.sin(shovel_a)*(self.radius+5))
        pygame.draw.line(surf,(200,180,100),(sx2,sy2),(ex,ey),4)
        self._draw_status_effects(surf)
        if hovered: self._hover_label(surf)

# ── Sandbox-only enemies ───────────────────────────────────────────────────────

# ── Sandbox-only enemies ───────────────────────────────────────────────────────

class GlassEnemy(Enemy):
    """Tiny, ultra-fragile enemy — 1 HP but extremely fast. Dies to any hit."""
    DISPLAY_NAME = "Glass"; BASE_HP = 1; BASE_SPEED = 380; KILL_REWARD = 0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 1; self.maxhp = 1
        self.speed = self.BASE_SPEED; self.radius = 10
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 2.2) * 4
        cx, cy = int(self.x), int(self.y + bob)
        s = pygame.Surface((60, 60), pygame.SRCALPHA)
        pygame.draw.circle(s, (180, 230, 255, 160), (15, 15), self.radius)
        pygame.draw.circle(s, (240, 250, 255, 220), (12, 12), 5)
        pygame.draw.circle(s, (200, 240, 255, 80),  (15, 15), self.radius, 2)
        surf.blit(s, (cx - 15, cy - 15))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 36, 6)
        if hovered: self._hover_label(surf)


class BlobEnemy(Enemy):
    """Wobbly green blob — 5 HP, average speed, bounces up and down wildly.
    Splits into 2 MicroBlobs on death (handled in update loop)."""
    DISPLAY_NAME = "Blob"; BASE_HP = 5; BASE_SPEED = 115; KILL_REWARD = 0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 5; self.maxhp = 5
        self.speed = self.BASE_SPEED; self.radius = 16
        self._squish = 0.0
    def update(self, dt):
        self._squish += dt * 7
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 1.8) * 5
        cx, cy = int(self.x), int(self.y + bob)
        sq = math.sin(self._squish)
        rw = int(self.radius * (1.0 + sq * 0.28))
        rh = int(self.radius * (1.0 - sq * 0.22))
        # gooey body
        s = pygame.Surface((rw*4, rh*4), pygame.SRCALPHA)
        sc = (rw*2, rh*2)
        pygame.draw.ellipse(s, (40, 200, 80, 220),
                            (sc[0]-rw, sc[1]-rh, rw*2, rh*2))
        pygame.draw.ellipse(s, (120, 255, 140, 180),
                            (sc[0]-rw//2, sc[1]-rh, rw, rh*2), 3)
        # shiny highlight
        pygame.draw.ellipse(s, (200, 255, 200, 160),
                            (sc[0]-rw//2, sc[1]-rh+2, rw//2, rh//2))
        # googly eye
        ex, ey = sc[0]+rw//4, sc[1]-rh//3
        pygame.draw.circle(s, (255, 255, 255, 230), (ex, ey), 5)
        pygame.draw.circle(s, (20,  20,  20,  255), (ex+1, ey+1), 2)
        surf.blit(s, (cx - rw*2, cy - rh*2))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 44, 7)
        if hovered: self._hover_label(surf)


class PaperEnemy(Enemy):
    """A literal piece of paper — 3 HP, drifts sideways, crinkles as it moves.
    Very slow, but towers often miss due to its erratic vertical drift."""
    DISPLAY_NAME = "Paper"; BASE_HP = 3; BASE_SPEED = 70; KILL_REWARD = 0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 3; self.maxhp = 3
        self.speed = self.BASE_SPEED; self.radius = 18
        self._drift = random.uniform(0, math.tau)
        self._crinkle = random.uniform(0, math.tau)
    def update(self, dt):
        self._drift   += dt * 2.2
        self._crinkle += dt * 8.0
        # vertical drift — zigzag off the path slightly
        self.y = PATH_Y + math.sin(self._drift) * 18
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        cx, cy = int(self.x), int(self.y)
        angle = math.sin(self._crinkle) * 18   # tilt
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        # draw a wavy rectangle (paper sheet)
        pts = []
        w, h = 30, 38
        for step in range(10):
            t2 = step / 9
            wave = math.sin(t2 * math.pi * 3 + self._crinkle) * 3
            pts.append((10 + t2 * w, 20 + wave))
        for step in range(10):
            t2 = 1 - step / 9
            wave = math.sin(t2 * math.pi * 3 + self._crinkle + 1) * 3
            pts.append((10 + t2 * w, 20 + h + wave))
        pygame.draw.polygon(s, (230, 225, 200, 220), pts)
        pygame.draw.polygon(s, (180, 170, 140, 180), pts, 2)
        # ruled lines
        for li in range(3):
            ly = 28 + li * 8
            pygame.draw.line(s, (160, 155, 130, 120), (14, ly), (36, ly), 1)
        rotated = pygame.transform.rotate(s, angle)
        surf.blit(rotated, (cx - rotated.get_width()//2,
                             cy - rotated.get_height()//2))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 44, 7)
        if hovered: self._hover_label(surf)


class ZombieEnemy(Enemy):
    """Shambling undead — 6 HP, very slow, but heals 1 HP every 4 seconds.
    Glows sickly green and wobbles with a lurching gait."""
    DISPLAY_NAME = "Zombie"; BASE_HP = 6; BASE_SPEED = 55; KILL_REWARD = 0
    _HEAL_INTERVAL = 4.0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 6; self.maxhp = 6
        self.speed = self.BASE_SPEED; self.radius = 19
        self._heal_timer = self._HEAL_INTERVAL
        self._lurch = 0.0
    def update(self, dt):
        self._lurch += dt * 3.5
        self._heal_timer -= dt
        if self._heal_timer <= 0 and self.alive:
            self.hp = min(self.maxhp, self.hp + 1)
            self._heal_timer = self._HEAL_INTERVAL
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        lurch_x = math.sin(self._lurch) * 4
        bob      = abs(math.sin(self._lurch * 0.5)) * 3
        cx, cy   = int(self.x + lurch_x), int(self.y + bob)
        # sickly glow aura
        s = pygame.Surface((90, 90), pygame.SRCALPHA)
        glow_r = int(self.radius + 6 + abs(math.sin(self._lurch)) * 4)
        pygame.draw.circle(s, (60, 180, 40, 35), (45, 45), glow_r)
        surf.blit(s, (cx - 45, cy - 45))
        # body
        pygame.draw.circle(surf, (60, 90, 45),  (cx, cy), self.radius)
        pygame.draw.circle(surf, (90, 140, 60),  (cx - 7, cy - 7), 11)
        pygame.draw.circle(surf, (130, 200, 80), (cx, cy), self.radius, 2)
        # X eyes
        for ex2, ey2 in [(cx-5, cy-5), (cx+5, cy-5)]:
            pygame.draw.line(surf, (200, 255, 100), (ex2-3, ey2-3), (ex2+3, ey2+3), 2)
            pygame.draw.line(surf, (200, 255, 100), (ex2+3, ey2-3), (ex2-3, ey2+3), 2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 50, 8)
        if hovered: self._hover_label(surf)


class BabyDragonEnemy(Enemy):
    """Tiny hatchling dragon — 8 HP, medium speed, leaves a tiny flame trail.
    Adorable but flammable. Has hidden detection immunity to Archer fire."""
    DISPLAY_NAME = "Baby Dragon"; BASE_HP = 8; BASE_SPEED = 130; KILL_REWARD = 0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 8; self.maxhp = 8
        self.speed = self.BASE_SPEED; self.radius = 17
        self._wing = 0.0
        self._flame_trail = []   # list of (x, y, t) for trail particles
    def update(self, dt):
        self._wing += dt * 9
        # spawn trail particle
        if self.alive and self._stun_timer <= 0:
            self._flame_trail.append([self.x, self.y + random.uniform(-4, 4), 0.5])
        # age trail
        self._flame_trail = [[x2, y2, t2-dt] for x2, y2, t2 in self._flame_trail if t2 > 0]
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        # flame trail first (behind dragon)
        for x2, y2, t2 in self._flame_trail:
            alpha = max(0, min(255, int(t2 / 0.5 * 160)))
            r2    = max(1, int(t2 / 0.5 * 8) + 2)
            fs = pygame.Surface((r2*4, r2*4), pygame.SRCALPHA)
            col = (255, max(0, min(255, int(100 + t2/0.5*120))), 0, alpha)
            pygame.draw.circle(fs, col, (r2*2, r2*2), r2)
            surf.blit(fs, (int(x2) - r2*2, int(y2) - r2*2))

        bob = math.sin(self._wing * 0.6) * 3
        cx, cy = int(self.x), int(self.y + bob)
        # wings (flapping)
        wing_spread = int(math.sin(self._wing) * 8 + 10)
        s = pygame.Surface((100, 80), pygame.SRCALPHA)
        sc = (50, 40)
        # left wing
        pygame.draw.ellipse(s, (180, 60, 20, 180),
            (sc[0]-self.radius-wing_spread, sc[1]-8, wing_spread+4, 14))
        # right wing
        pygame.draw.ellipse(s, (180, 60, 20, 180),
            (sc[0]+self.radius-4,           sc[1]-8, wing_spread+4, 14))
        # body
        pygame.draw.circle(s, (200, 80, 30),  sc, self.radius)
        pygame.draw.circle(s, (255, 140, 50), (sc[0]-5, sc[1]-5), 9)
        # snout
        pygame.draw.ellipse(s, (220, 100, 40),
                            (sc[0]+self.radius-6, sc[1]-4, 12, 8))
        # eye
        pygame.draw.circle(s, (255, 220, 0), (sc[0]+4, sc[1]-6), 4)
        pygame.draw.circle(s, (0, 0, 0),     (sc[0]+5, sc[1]-6), 2)
        surf.blit(s, (cx - 50, cy - 40))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 50, 8)
        if hovered: self._hover_label(surf)


class SteelGolem(Enemy):
    """Massive tank with 80% armour — extremely resistant but very slow."""
    DISPLAY_NAME = "Steel Golem"; BASE_HP = 800; BASE_SPEED = 30; KILL_REWARD = 0
    ARMOR = 0.80
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 800; self.maxhp = 800
        self.speed = self.BASE_SPEED; self.radius = 46
        self._rot = 0.0
    def update(self, dt):
        self._rot += dt * 40
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 0.4) * 0.5
        cx, cy = int(self.x), int(self.y + bob)
        # body plates
        pygame.draw.circle(surf, (60, 70, 85),  (cx, cy), self.radius + 5, 6)
        pygame.draw.circle(surf, (50, 55, 65),  (cx, cy), self.radius)
        pygame.draw.circle(surf, (120, 140, 160),(cx - 14, cy - 14), 18)
        pygame.draw.circle(surf, (180, 200, 220),(cx, cy), self.radius, 2)
        # rivets
        for i in range(6):
            a = math.radians(self._rot + i * 60)
            rx = cx + int(math.cos(a) * (self.radius - 8))
            ry = cy + int(math.sin(a) * (self.radius - 8))
            pygame.draw.circle(surf, (200, 210, 230), (rx, ry), 4)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 120, 14, (180, 200, 220))
        if hovered: self._hover_label(surf)


class RegeneratorEnemy(Enemy):
    """Mid-HP enemy that rapidly regenerates health over time."""
    DISPLAY_NAME = "Regenerator"; BASE_HP = 120; BASE_SPEED = 100; KILL_REWARD = 0
    _REGEN_RATE = 8.0   # HP per second
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 120; self.maxhp = 120
        self.speed = self.BASE_SPEED; self.radius = 24
        self._pulse = 0.0
    def update(self, dt):
        self._pulse += dt * 3
        if self.alive and self._stun_timer <= 0:
            self.hp = min(self.maxhp, self.hp + self._REGEN_RATE * dt)
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob) * 2
        cx, cy = int(self.x), int(self.y + bob)
        glow = int(abs(math.sin(self._pulse)) * 40)
        s = pygame.Surface((100, 100), pygame.SRCALPHA)
        pygame.draw.circle(s, (20, 180 + glow, 80, 50), (30, 30), self.radius + 6)
        surf.blit(s, (cx - 30, cy - 30))
        pygame.draw.circle(surf, (10, 120, 50),   (cx, cy), self.radius)
        pygame.draw.circle(surf, (40, 220, 100),  (cx - 8, cy - 8), 12)
        pygame.draw.circle(surf, (80, 255, 140),  (cx, cy), self.radius, 2)
        # cross regen symbol
        pygame.draw.rect(surf, (160, 255, 180), (cx - 2, cy - 8, 4, 16))
        pygame.draw.rect(surf, (160, 255, 180), (cx - 8, cy - 2, 16, 4))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 70, 10, (80, 255, 140))
        if hovered: self._hover_label(surf)


class PhantomBoss(Enemy):
    """Large boss that becomes fully invisible every 4 seconds for 1.5s.
    Requires hidden detection to hit during phase — otherwise invulnerable."""
    DISPLAY_NAME = "Phantom Boss"; BASE_HP = 2000; BASE_SPEED = 90; KILL_REWARD = 0
    IS_HIDDEN = False   # changes dynamically
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 2000; self.maxhp = 2000
        self.speed = self.BASE_SPEED; self.radius = 42
        self._phase_timer  = 4.0   # countdown to next phase switch
        self._phased        = False  # True = currently invisible+invulnerable
        self._phase_dur     = 1.5
        self._rot           = 0.0
    def update(self, dt):
        self._rot += dt * 60
        self._phase_timer -= dt
        if self._phased:
            if self._phase_timer <= 0:
                self._phased = False; self.IS_HIDDEN = False
                self._phase_timer = 4.0
        else:
            if self._phase_timer <= 0:
                self._phased = True; self.IS_HIDDEN = True
                self._phase_timer = self._phase_dur
        return super().update(dt)
    def take_damage(self, dmg):
        if self._phased: return   # invulnerable while phased
        super().take_damage(dmg)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 0.7) * 1.5
        cx, cy = int(self.x), int(self.y + bob)
        if self._phased and not detected and not hovered:
            return   # invisible
        alpha = 90 if self._phased else 255
        s = pygame.Surface((200, 200), pygame.SRCALPHA)
        pygame.draw.circle(s, (120, 0, 180, alpha // 2), (50, 50), self.radius + 8)
        surf.blit(s, (cx - 50, cy - 50))
        s2 = pygame.Surface((200, 200), pygame.SRCALPHA)
        pygame.draw.circle(s2, (80, 0, 130, alpha),   (50, 50), self.radius)
        pygame.draw.circle(s2, (160, 60, 220, alpha),  (36, 36), 20)
        pygame.draw.circle(s2, (220, 120, 255, alpha), (50, 50), self.radius, 3)
        surf.blit(s2, (cx - 50, cy - 50))
        # orbit dots
        for i in range(6):
            a = math.radians(self._rot + i * 60)
            orb_s = pygame.Surface((20, 20), pygame.SRCALPHA)
            pygame.draw.circle(orb_s, (200, 100, 255, alpha), (5, 5), 4)
            ox2 = cx + int(math.cos(a) * (self.radius + 10))
            oy2 = cy + int(math.sin(a) * (self.radius + 10))
            surf.blit(orb_s, (ox2 - 5, oy2 - 5))
        self._draw_status_effects(surf)
        if not self._phased or detected or hovered:
            self._draw_hp_bar(surf, 110, 14, (220, 120, 255))
        if hovered: self._hover_label(surf)


class SwarmBoss(Enemy):
    """Medium boss that spawns a small scout every 3 seconds while alive."""
    DISPLAY_NAME = "Swarm Queen"; BASE_HP = 600; BASE_SPEED = 75; KILL_REWARD = 0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 600; self.maxhp = 600
        self.speed = self.BASE_SPEED; self.radius = 38
        self._spawn_timer = 3.0
        self._rot = 0.0
    def update(self, dt):
        self._rot += dt * 80
        self._spawn_timer -= dt
        return super().update(dt)
    def should_spawn(self):
        if self._spawn_timer <= 0:
            self._spawn_timer = 3.0; return True
        return False
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 0.9) * 2
        cx, cy = int(self.x), int(self.y + bob)
        s = pygame.Surface((160, 160), pygame.SRCALPHA)
        pygame.draw.circle(s, (180, 80, 20, 40), (40, 40), 38)
        surf.blit(s, (cx - 40, cy - 40))
        pygame.draw.circle(surf, (160, 70, 10),  (cx, cy), self.radius)
        pygame.draw.circle(surf, (230, 130, 40), (cx - 12, cy - 12), 16)
        pygame.draw.circle(surf, (255, 170, 60), (cx, cy), self.radius, 3)
        # spinning legs
        for i in range(8):
            a = math.radians(self._rot + i * 45)
            lx = cx + int(math.cos(a) * (self.radius + 10))
            ly = cy + int(math.sin(a) * (self.radius + 10))
            pygame.draw.line(surf, (200, 120, 30),
                             (cx + int(math.cos(a) * self.radius),
                              cy + int(math.sin(a) * self.radius)),
                             (lx, ly), 2)
            pygame.draw.circle(surf, (255, 180, 80), (lx, ly), 3)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 100, 12, (255, 170, 60))
        if hovered: self._hover_label(surf)


class AbyssLord(Enemy):
    """Ultimate sandbox boss — massive HP, high armor, stun-immune, slow."""
    DISPLAY_NAME = "Abyss Lord"; BASE_HP = 50000; BASE_SPEED = 40; KILL_REWARD = 0
    ARMOR = 0.50
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = 50000; self.maxhp = 50000
        self.speed = self.BASE_SPEED; self.radius = 52
        self._rot = 0.0; self._pulse = 0.0
        self._stun_immune_timer = 9999.0   # permanently stun-immune
    def update(self, dt):
        self._rot += dt * 25; self._pulse += dt * 2
        self._stun_immune_timer = 9999.0   # never expires
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 0.3) * 1
        cx, cy = int(self.x), int(self.y + bob)
        glow = int(abs(math.sin(self._pulse)) * 30)
        s = pygame.Surface((260, 260), pygame.SRCALPHA)
        pygame.draw.circle(s, (10, 0, 30 + glow, 60), (65, 65), self.radius + 12)
        surf.blit(s, (cx - 65, cy - 65))
        # outer ring of dark spikes
        for i in range(10):
            a = math.radians(self._rot + i * 36)
            sx2 = cx + int(math.cos(a) * (self.radius + 2))
            sy2 = cy + int(math.sin(a) * (self.radius + 2))
            ex2 = cx + int(math.cos(a) * (self.radius + 18))
            ey2 = cy + int(math.sin(a) * (self.radius + 18))
            pygame.draw.line(surf, (80, 0, 120), (sx2, sy2), (ex2, ey2), 4)
        pygame.draw.circle(surf, (20,  0,  40),  (cx, cy), self.radius)
        pygame.draw.circle(surf, (60,  0, 100),  (cx - 16, cy - 16), 22)
        pygame.draw.circle(surf, (120, 0, 200),  (cx, cy), self.radius, 3)
        # glowing eye
        pygame.draw.circle(surf, (255, 0,  80 + glow), (cx + 4, cy + 2), 10)
        pygame.draw.circle(surf, (255, 180, 200), (cx + 6, cy), 4)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 140, 16, (120, 0, 200))
        if hovered: self._hover_label(surf)


# ── Mid-game enemies ──────────────────────────────────────────────────────────

class MirrorShield(Enemy):
    """Metallic enemy that reflects 30% of all damage back to the last attacking
    tower (visual only — deals no real damage to tower, but confuses the player).
    40% armour, medium speed. Rotates a glinting shield plate while walking."""
    DISPLAY_NAME = "Mirror Shield"; BASE_HP = 180; BASE_SPEED = 88; KILL_REWARD = 0
    ARMOR = 0.40
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 180 + (wave - 8) * 14); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 26
        self._shield_rot = 0.0
        self._flash_t    = 0.0   # glint flash timer
    def update(self, dt):
        self._shield_rot += dt * 120
        self._flash_t    = max(0.0, self._flash_t - dt)
        return super().update(dt)
    def take_damage(self, dmg):
        # trigger glint flash on hit
        self._flash_t = 0.18
        super().take_damage(dmg)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 0.9) * 2
        cx, cy = int(self.x), int(self.y + bob)
        # body
        pygame.draw.circle(surf, (80,  90, 110), (cx, cy), self.radius)
        pygame.draw.circle(surf, (150, 170, 200), (cx - 8, cy - 8), 12)
        pygame.draw.circle(surf, (200, 220, 240), (cx, cy), self.radius, 2)
        # spinning shield plate
        for i in range(3):
            a = math.radians(self._shield_rot + i * 120)
            sx2 = cx + int(math.cos(a) * (self.radius - 4))
            sy2 = cy + int(math.sin(a) * (self.radius - 4))
            ex2 = cx + int(math.cos(a) * (self.radius + 12))
            ey2 = cy + int(math.sin(a) * (self.radius + 12))
            col = (255, 255, 220) if self._flash_t > 0 else (180, 200, 220)
            pygame.draw.line(surf, col, (sx2, sy2), (ex2, ey2), 5)
            pygame.draw.circle(surf, col, (ex2, ey2), 4)
        # glint highlight when hit
        if self._flash_t > 0:
            s = pygame.Surface((self.radius * 4, self.radius * 4), pygame.SRCALPHA)
            alpha = int(200 * self._flash_t / 0.18)
            pygame.draw.circle(s, (255, 255, 200, alpha),
                               (self.radius * 2, self.radius * 2), self.radius + 8)
            surf.blit(s, (cx - self.radius * 2, cy - self.radius * 2))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 80, 10, (200, 220, 240))
        if hovered: self._hover_label(surf)


class ShadowStepper(Enemy):
    """Teleports forward by 120 px every 5 seconds — makes a dramatic void-burst
    visual when it blinks. IS_HIDDEN between blinks (2 s window).
    Medium HP, above-average speed."""
    DISPLAY_NAME = "Shadow Stepper"; BASE_HP = 140; BASE_SPEED = 120; KILL_REWARD = 0
    IS_HIDDEN = False
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 140 + (wave - 8) * 10); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 22
        self._blink_cd   = 5.0   # time until next teleport
        self._blink_t    = 0.0   # blink flash life (visual)
        self._hidden_cd  = 0.0   # seconds of forced IS_HIDDEN after blink
        self._trail      = []    # [(x, y, age)] afterimage trail
    def update(self, dt):
        self._blink_cd -= dt
        self._blink_t   = max(0.0, self._blink_t  - dt)
        self._hidden_cd = max(0.0, self._hidden_cd - dt)
        self.IS_HIDDEN  = (self._hidden_cd > 0)
        # spawn trail particles every frame
        if self._stun_timer <= 0 and self.alive:
            self._trail.append([self.x, self.y, 0.35])
        self._trail = [[x2, y2, t2 - dt] for x2, y2, t2 in self._trail if t2 > 0]
        # teleport!
        if self._blink_cd <= 0 and self._stun_timer <= 0:
            self.x += 120
            self._blink_cd  = 5.0
            self._blink_t   = 0.4
            self._hidden_cd = 2.0
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        # afterimage trail
        for x2, y2, t2 in self._trail:
            alpha = max(0, min(255, int(t2 / 0.35 * 90)))
            r_trail = self.radius - 4
            sz = (r_trail + 2) * 2
            s = pygame.Surface((sz, sz), pygame.SRCALPHA)
            pygame.draw.circle(s, (80, 0, 160, alpha), (sz//2, sz//2), r_trail)
            surf.blit(s, (int(x2) - sz//2, int(y2) - sz//2))
        # blink burst
        if self._blink_t > 0:
            progress = self._blink_t / 0.4
            s2 = pygame.Surface((120, 120), pygame.SRCALPHA)
            pygame.draw.circle(s2, (180, 60, 255, int(180 * progress)),
                               (60, 60), int(14 + (1 - progress) * 38))
            surf.blit(s2, (int(self.x) - 60, int(self.y) - 60))
        # body (invisible when hidden and not detected)
        if self.IS_HIDDEN and not detected and not hovered:
            return
        bob = math.sin(self._bob * 1.1) * 2
        cx, cy = int(self.x), int(self.y + bob)
        alpha_body = 140 if self.IS_HIDDEN else 255
        pad = 12
        sz3 = (self.radius + pad) * 2
        s3 = pygame.Surface((sz3, sz3), pygame.SRCALPHA)
        c3 = sz3 // 2
        pygame.draw.circle(s3, (50, 0, 100, alpha_body),   (c3, c3), self.radius)
        pygame.draw.circle(s3, (140, 60, 220, alpha_body), (c3 - 8, c3 - 8), 10)
        pygame.draw.circle(s3, (200, 120, 255, alpha_body),(c3, c3), self.radius, 2)
        surf.blit(s3, (cx - c3, cy - c3))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 70, 9, (180, 80, 255))
        if hovered: self._hover_label(surf)


class VoltCrawler(Enemy):
    """Electrified centipede that chains arc damage to nearby enemies on death —
    when killed, emits a lightning burst hitting all enemies within 80 px for 5 dmg.
    Quick, low HP, draws attention as a priority kill."""
    DISPLAY_NAME = "Volt Crawler"; BASE_HP = 60; BASE_SPEED = 160; KILL_REWARD = 0
    CHAIN_RADIUS = 80
    CHAIN_DAMAGE = 5
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 60 + (wave - 8) * 5); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 18
        self._spark = 0.0
        self._zap_flash = 0.0
        self._chain_triggered = False
    def update(self, dt):
        self._spark    += dt * 12
        self._zap_flash = max(0.0, self._zap_flash - dt)
        return super().update(dt)
    def take_damage(self, dmg):
        was_alive = self.alive
        super().take_damage(dmg)
        if was_alive and not self.alive and not self._chain_triggered:
            self._chain_triggered = True
            self._zap_flash = 0.5
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 1.5) * 3
        cx, cy = int(self.x), int(self.y + bob)
        # electric glow
        s = pygame.Surface((100, 100), pygame.SRCALPHA)
        glow_alpha = int(40 + abs(math.sin(self._spark)) * 50)
        pygame.draw.circle(s, (80, 200, 255, glow_alpha), (30, 30), self.radius + 8)
        surf.blit(s, (cx - 30, cy - 30))
        # body segments (mini centipede)
        for i in range(5):
            seg_x = cx - i * 8
            seg_y = cy + int(math.sin(self._spark + i * 0.9) * 3)
            r_seg = max(4, self.radius - i * 2)
            col = (60, 180, 255) if i == 0 else (30, 120, 200)
            pygame.draw.circle(surf, col, (seg_x, seg_y), r_seg)
        # legs (tiny lines)
        for i in range(4):
            lx = cx - i * 8 - 4
            ly = cy + int(math.sin(self._spark + i) * 3)
            pygame.draw.line(surf, (100, 220, 255),
                             (lx, ly), (lx - 5, ly + 7), 1)
            pygame.draw.line(surf, (100, 220, 255),
                             (lx, ly), (lx - 5, ly - 7), 1)
        # electric sparks on body
        for i in range(3):
            a = math.radians(self._spark * 120 + i * 120)
            ex2 = cx + int(math.cos(a) * self.radius)
            ey2 = cy + int(math.sin(a) * self.radius)
            pygame.draw.line(surf, (200, 240, 255), (cx, cy), (ex2, ey2), 1)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 60, 8, (100, 220, 255))
        if hovered: self._hover_label(surf)


class IronMaiden(Enemy):
    """A walking iron maiden trap — spiky, slow, 50% armour. Any tower that deals
    melee-range damage (within 60px) has a chance to trigger a visual spike burst.
    High HP, immune to push-back, very intimidating presence."""
    DISPLAY_NAME = "Iron Maiden"; BASE_HP = 500; BASE_SPEED = 50; KILL_REWARD = 0
    ARMOR = 0.50
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 500 + (wave - 9) * 30); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 34
        self._spike_rot  = 0.0
        self._spike_anim = 0.0   # spike extend animation (0-1)
        self._spike_dir  = 1     # 1 = extending, -1 = retracting
    def update(self, dt):
        self._spike_rot += dt * 18
        # animate spikes slowly in and out
        self._spike_anim += dt * self._spike_dir * 0.9
        if self._spike_anim >= 1.0: self._spike_anim = 1.0; self._spike_dir = -1
        if self._spike_anim <= 0.0: self._spike_anim = 0.0; self._spike_dir =  1
        # stun-immune
        self._clown_pushback = False
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 0.5) * 1
        cx, cy = int(self.x), int(self.y + bob)
        # outer spikes (animated extend)
        spike_reach = 8 + int(self._spike_anim * 18)
        for i in range(12):
            a = math.radians(self._spike_rot + i * 30)
            sx2 = cx + int(math.cos(a) * (self.radius - 2))
            sy2 = cy + int(math.sin(a) * (self.radius - 2))
            ex2 = cx + int(math.cos(a) * (self.radius + spike_reach))
            ey2 = cy + int(math.sin(a) * (self.radius + spike_reach))
            tip_col = (220, 210, 200) if self._spike_anim > 0.7 else (160, 150, 140)
            pygame.draw.line(surf, tip_col, (sx2, sy2), (ex2, ey2), 3)
            pygame.draw.circle(surf, (240, 230, 220), (ex2, ey2), 2)
        # body — heavy iron casing
        pygame.draw.circle(surf, (55, 55, 65),  (cx, cy), self.radius + 3, 5)
        pygame.draw.circle(surf, (45, 45, 55),  (cx, cy), self.radius)
        pygame.draw.circle(surf, (100, 100, 120),(cx - 12, cy - 12), 18)
        pygame.draw.circle(surf, (170, 170, 185),(cx, cy), self.radius, 2)
        # hinge rivets
        for i in range(4):
            a = math.radians(i * 90 + 45)
            rx = cx + int(math.cos(a) * (self.radius - 6))
            ry = cy + int(math.sin(a) * (self.radius - 6))
            pygame.draw.circle(surf, (200, 195, 185), (rx, ry), 4)
        # menacing eye slit
        pygame.draw.rect(surf, (200, 30, 30), (cx - 10, cy - 4, 20, 5), border_radius=2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 100, 12, (170, 170, 185))
        if hovered: self._hover_label(surf)


class TimeBender(Enemy):
    """Chronowarp unit — every 6 seconds it emits a time-slow pulse that halves
    the attack speed of all towers within 180 px for 2 seconds (applied via a
    _time_slow flag on nearby units, checked in the game's unit update loop).
    Draws a swirling clock-face pattern. Medium HP and speed."""
    DISPLAY_NAME = "Time Bender"; BASE_HP = 280; BASE_SPEED = 95; KILL_REWARD = 0
    PULSE_RADIUS = 180
    PULSE_INTERVAL = 6.0
    PULSE_DURATION = 2.0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 280 + (wave - 9) * 18); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 28
        self._pulse_cd  = self.PULSE_INTERVAL
        self._orbit     = 0.0
        self._ring_t    = 0.0   # expanding ring visual
        self.pulse_fired = False  # flag read by game loop to apply tower slow
    def update(self, dt):
        self._orbit  += dt * 90
        self._ring_t  = max(0.0, self._ring_t - dt)
        self.pulse_fired = False
        self._pulse_cd -= dt
        if self._pulse_cd <= 0:
            self._pulse_cd   = self.PULSE_INTERVAL
            self._ring_t     = 0.6
            self.pulse_fired = True   # game loop picks this up
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob * 0.8) * 2
        cx, cy = int(self.x), int(self.y + bob)
        # expanding time-pulse ring
        if self._ring_t > 0:
            progress = 1.0 - self._ring_t / 0.6
            ring_r   = int(progress * self.PULSE_RADIUS)
            alpha    = int(200 * self._ring_t / 0.6)
            s = pygame.Surface((ring_r * 2 + 20, ring_r * 2 + 20), pygame.SRCALPHA)
            sc = ring_r + 10
            pygame.draw.circle(s, (255, 220, 80, alpha), (sc, sc), ring_r, 3)
            surf.blit(s, (cx - sc, cy - sc))
        # clock face glow
        s2 = pygame.Surface((120, 120), pygame.SRCALPHA)
        pygame.draw.circle(s2, (200, 160, 20, 45), (40, 40), self.radius + 8)
        surf.blit(s2, (cx - 40, cy - 40))
        # body
        pygame.draw.circle(surf, (60, 50, 10),  (cx, cy), self.radius)
        pygame.draw.circle(surf, (180, 150, 30),(cx - 9, cy - 9), 14)
        pygame.draw.circle(surf, (240, 200, 60),(cx, cy), self.radius, 2)
        # clock tick marks
        for i in range(12):
            a = math.radians(i * 30)
            r1 = self.radius - 7
            r2 = self.radius - 2
            pygame.draw.line(surf,
                             (240, 220, 100),
                             (cx + int(math.cos(a) * r1), cy + int(math.sin(a) * r1)),
                             (cx + int(math.cos(a) * r2), cy + int(math.sin(a) * r2)), 1)
        # clock hand (orbiting)
        hand_a = math.radians(self._orbit)
        hx = cx + int(math.cos(hand_a) * (self.radius - 8))
        hy = cy + int(math.sin(hand_a) * (self.radius - 8))
        pygame.draw.line(surf, (255, 240, 120), (cx, cy), (hx, hy), 2)
        # orbiting hourglass dot
        orb_a = math.radians(self._orbit * 0.4)
        ox2 = cx + int(math.cos(orb_a) * (self.radius + 10))
        oy2 = cy + int(math.sin(orb_a) * (self.radius + 10))
        pygame.draw.circle(surf, (255, 200, 50), (ox2, oy2), 5)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 85, 10, (240, 200, 60))
        if hovered: self._hover_label(surf)


# ── Demonic enemies (Hell-exclusive) ──────────────────────────────────────────

class HellHound(Enemy):
    """Fast demonic dog — low HP but charges in packs. Leaves a scorched trail.
    Every 3 s dashes forward 80 px in a burst of fire."""
    DISPLAY_NAME = "Hell Hound"; BASE_HP = 25; BASE_SPEED = 155; KILL_REWARD = 0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 55 + (wave-1)*4); self.maxhp = self.hp
        self.speed = self.BASE_SPEED + (wave-1)*5; self.radius = 17
        self._dash_cd = random.uniform(4.0, 7.0)
        self._flame = 0.0; self._run = 0.0
    def update(self, dt):
        self._run += dt * 14; self._flame = max(0.0, self._flame - dt)
        self._dash_cd -= dt
        if self._dash_cd <= 0 and self._stun_timer <= 0:
            self.x += 50; self._dash_cd = 5.0; self._flame = 0.35
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._run * 0.7) * 4
        cx, cy = int(self.x), int(self.y + bob)
        # fire glow
        if self._flame > 0:
            gp = self._flame / 0.35
            gs = pygame.Surface((80, 80), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255, 100, 0, int(120*gp)), (30,30), int(14+gp*18))
            surf.blit(gs, (cx-30, cy-30))
        # body
        pygame.draw.ellipse(surf, (120, 30, 10), (cx-self.radius, cy-self.radius+4, self.radius*2, self.radius*2-4))
        pygame.draw.circle(surf, (180, 50, 15), (cx, cy-2), self.radius-3)
        # muzzle
        pygame.draw.ellipse(surf, (150, 40, 10), (cx+self.radius-7, cy-5, 12, 9))
        # ears
        pygame.draw.polygon(surf, (200, 60, 20),
            [(cx-8, cy-self.radius), (cx-14, cy-self.radius-12), (cx-2, cy-self.radius-2)])
        pygame.draw.polygon(surf, (200, 60, 20),
            [(cx+2, cy-self.radius), (cx+10, cy-self.radius-10), (cx+8, cy-self.radius-1)])
        # glowing red eyes
        pygame.draw.circle(surf, (255, 60, 0), (cx-5, cy-6), 4)
        pygame.draw.circle(surf, (255, 60, 0), (cx+5, cy-6), 4)
        pygame.draw.circle(surf, (255, 200, 0), (cx-5, cy-6), 2)
        pygame.draw.circle(surf, (255, 200, 0), (cx+5, cy-6), 2)
        # running legs
        for i in range(2):
            la = math.sin(self._run + i*math.pi) * 0.6
            lx = cx - 8 + i*16
            pygame.draw.line(surf, (100, 25, 8), (lx, cy+self.radius-6),
                             (lx + int(math.cos(la)*10), cy+self.radius+8), 3)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 54, 8, (255, 80, 20))
        if hovered: self._hover_label(surf)


class BrimstoneGolem(Enemy):
    """Slow lava golem with 60% armour. Periodically erupts, dealing AoE damage
    to any unit within 90 px (visual only — stuns all enemies near it for 0.3 s
    via lava splash flag). Very high HP."""
    DISPLAY_NAME = "Brimstone Golem"; BASE_HP = 1200; BASE_SPEED = 35; KILL_REWARD = 0
    ARMOR = 0.60
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 1200 + (wave-1)*50); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 40
        self._erupt_cd = 6.0; self._erupt_t = 0.0; self._rot = 0.0
        self.erupt_fired = False
    def update(self, dt):
        self._rot += dt*15; self._erupt_t = max(0.0, self._erupt_t - dt)
        self.erupt_fired = False
        self._erupt_cd -= dt
        if self._erupt_cd <= 0:
            self._erupt_cd = 6.0; self._erupt_t = 0.6; self.erupt_fired = True
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob*0.3)*0.5; cx, cy = int(self.x), int(self.y+bob)
        # lava glow
        gp = abs(math.sin(self._rot*0.1))
        s = pygame.Surface((160,160), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, int(80+gp*60), 0, int(40+gp*40)), (50,50), self.radius+12)
        surf.blit(s, (cx-50, cy-50))
        # eruption flash
        if self._erupt_t > 0:
            ep = self._erupt_t/0.6
            es = pygame.Surface((180,180), pygame.SRCALPHA)
            pygame.draw.circle(es, (255,140,0,int(160*ep)), (50,50), int(30+ep*60))
            surf.blit(es, (cx-50, cy-50))
        # rock body with lava cracks
        pygame.draw.circle(surf, (60,30,10), (cx,cy), self.radius+4, 6)
        pygame.draw.circle(surf, (50,25,8), (cx,cy), self.radius)
        pygame.draw.circle(surf, (80,35,10), (cx-14,cy-14), 22)
        # lava crack lines
        for i in range(6):
            a = math.radians(self._rot + i*60)
            x1 = cx+int(math.cos(a)*8); y1 = cy+int(math.sin(a)*8)
            x2 = cx+int(math.cos(a)*(self.radius-4)); y2 = cy+int(math.sin(a)*(self.radius-4))
            pygame.draw.line(surf, (255,80+int(gp*60),0), (x1,y1), (x2,y2), 2)
        pygame.draw.circle(surf, (255,60,0), (cx,cy), self.radius, 2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 120, 14, (255,80,0))
        if hovered: self._hover_label(surf)


class SoulReaper(Enemy):
    """Reaper with a scythe that steals life — every 4 s heals 40 HP from
    the damage it dealt. Hidden, medium speed, menacing silhouette."""
    DISPLAY_NAME = "Soul Reaper"; BASE_HP = 350; BASE_SPEED = 105; KILL_REWARD = 0
    IS_HIDDEN = True
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 350 + (wave-1)*18); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 26
        self._drain_cd = 4.0; self._drain_t = 0.0; self._rot = 0.0
    def update(self, dt):
        self._rot += dt*80; self._drain_t = max(0.0, self._drain_t - dt)
        self._drain_cd -= dt
        if self._drain_cd <= 0 and self.alive:
            self.hp = min(self.maxhp, self.hp + 40)
            self._drain_cd = 4.0; self._drain_t = 0.4
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        if not detected and not hovered:
            draw_hidden_ghost(surf, int(self.x), int(self.y), self.radius); return
        bob = math.sin(self._bob)*2; cx, cy = int(self.x), int(self.y+bob)
        alpha = 160 if not detected else 220
        # robe
        s = pygame.Surface((100,100), pygame.SRCALPHA)
        pygame.draw.circle(s, (10,0,20,alpha), (30,34), self.radius+4)
        pygame.draw.circle(s, (30,0,60,alpha), (30,30), self.radius)
        # hood highlight
        pygame.draw.circle(s, (60,0,100,alpha), (22,22), 10)
        # eye glow
        pygame.draw.circle(s, (200,0,80,alpha), (25,28), 4)
        pygame.draw.circle(s, (255,100,150,alpha), (25,28), 2)
        pygame.draw.circle(s, (200,0,80,alpha), (35,28), 4)
        pygame.draw.circle(s, (255,100,150,alpha), (35,28), 2)
        surf.blit(s, (cx-30, cy-30))
        # scythe
        a = math.radians(self._rot*0.5)
        hx = cx+int(math.cos(a)*self.radius); hy = cy+int(math.sin(a)*self.radius)
        pygame.draw.line(surf, (100,80,120), (cx,cy), (hx,hy), 3)
        pygame.draw.arc(surf, (180,160,200),
            pygame.Rect(hx-12,hy-12,24,24),
            a+math.pi*0.3, a+math.pi*1.0, 4)
        # drain flash
        if self._drain_t > 0:
            dp = self._drain_t/0.4
            ds = pygame.Surface((70,70), pygame.SRCALPHA)
            pygame.draw.circle(ds, (200,0,80,int(150*dp)), (25,25), int(8+dp*14))
            surf.blit(ds, (cx-25, cy-25))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 80, 10, (200,0,80))
        if hovered: self._hover_label(surf)


class DemonKnight(Enemy):
    """Heavily armoured demonic warrior — 45% armour, medium-slow speed.
    Periodically raises a dark shield making it briefly immune to damage (0.8 s
    every 5 s). Draws as a menacing horned knight."""
    DISPLAY_NAME = "Demon Knight"; BASE_HP = 600; BASE_SPEED = 72; KILL_REWARD = 0
    ARMOR = 0.45
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 600 + (wave-1)*30); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 30
        self._shield_cd = 5.0; self._shield_t = 0.0; self._rot = 0.0
        self.shielded = False
    def update(self, dt):
        self._rot += dt*30; self._shield_t = max(0.0, self._shield_t - dt)
        self.shielded = self._shield_t > 0
        self._shield_cd -= dt
        if self._shield_cd <= 0 and not self.shielded:
            self._shield_cd = 5.0; self._shield_t = 0.8
        self._clown_pushback = False  # immune to pushback
        return super().update(dt)
    def take_damage(self, dmg):
        if self.shielded: return
        super().take_damage(dmg)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob*0.6)*1; cx, cy = int(self.x), int(self.y+bob)
        # shield bubble
        if self.shielded:
            sp = self._shield_t/0.8
            ss = pygame.Surface((120,120), pygame.SRCALPHA)
            pygame.draw.circle(ss, (60,0,160,int(120*sp)), (40,40), self.radius+14)
            pygame.draw.circle(ss, (180,80,255,int(200*sp)), (40,40), self.radius+14, 3)
            surf.blit(ss, (cx-40, cy-40))
        # dark glow
        s = pygame.Surface((130,130), pygame.SRCALPHA)
        pygame.draw.circle(s, (40,0,80,35), (40,40), self.radius+8)
        surf.blit(s, (cx-40, cy-40))
        # body
        pygame.draw.circle(surf, (30,10,50), (cx,cy), self.radius+3, 5)
        pygame.draw.circle(surf, (25,8,45), (cx,cy), self.radius)
        pygame.draw.circle(surf, (60,20,100), (cx-10,cy-10), 16)
        pygame.draw.circle(surf, (100,40,180), (cx,cy), self.radius, 2)
        # horns
        for sign in (-1,1):
            pygame.draw.polygon(surf, (80,20,140), [
                (cx+sign*8, cy-self.radius+2),
                (cx+sign*18, cy-self.radius-18),
                (cx+sign*14, cy-self.radius+4)
            ])
        # glowing eyes
        for ex, ey in [(cx-8,cy-6),(cx+8,cy-6)]:
            pygame.draw.circle(surf, (180,0,255), (ex,ey), 4)
            pygame.draw.circle(surf, (255,200,255), (ex,ey), 2)
        # level pips
        for i in range(min(self.radius//10,3)):
            a = math.radians(self._rot + i*120)
            px2 = cx+int(math.cos(a)*(self.radius+6)); py2 = cy+int(math.sin(a)*(self.radius+6))
            pygame.draw.circle(surf, (150,50,255), (px2,py2), 3)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 90, 11, (120,40,220))
        if hovered: self._hover_label(surf)


class InfernoWyrm(Enemy):
    """Long serpentine fire wyrm — 5 body segments, medium HP each.
    Leaves a burning trail that deals DoT visual. Fast, no armour."""
    DISPLAY_NAME = "Inferno Wyrm"; BASE_HP = 70; BASE_SPEED = 145; KILL_REWARD = 0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 180 + (wave-1)*10); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 20
        self._wave2 = 0.0; self._trail = []
    def update(self, dt):
        self._wave2 += dt*11
        if self.alive and self._stun_timer <= 0:
            self._trail.append([self.x, self.y, 0.5])
        self._trail = [[x2,y2,t2-dt] for x2,y2,t2 in self._trail if t2>0]
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        # fire trail
        for x2,y2,t2 in self._trail:
            alpha = max(0, int(t2/0.5*100))
            r2 = max(1, int(t2/0.5*10)+2)
            fs = pygame.Surface((r2*4,r2*4), pygame.SRCALPHA)
            pygame.draw.circle(fs, (255,max(0,min(255,int(80+t2/0.5*100))),0,alpha), (r2*2,r2*2), r2)
            surf.blit(fs, (int(x2)-r2*2, int(y2)-r2*2))
        cx, cy = int(self.x), int(self.y)
        # body segments
        for i in range(5):
            seg_x = cx - i*12
            seg_y = cy + int(math.sin(self._wave2 + i*0.8) * 6)
            r_seg = max(5, self.radius - i*2)
            col = (220,60,0) if i==0 else (180,40,0) if i<3 else (140,30,0)
            pygame.draw.circle(surf, col, (seg_x, seg_y), r_seg)
            # scales highlight
            if i < 4:
                pygame.draw.circle(surf, (255,120,0), (seg_x-2, seg_y-4), r_seg//3)
        # head details
        # flared nostrils fire
        ns = pygame.Surface((50,50), pygame.SRCALPHA)
        pygame.draw.circle(ns, (255,180,0,160), (10,10), 5)
        surf.blit(ns, (cx+self.radius-10, cy-10))
        # eyes
        pygame.draw.circle(surf, (255,220,0), (cx+self.radius-8, cy-6), 4)
        pygame.draw.circle(surf, (0,0,0), (cx+self.radius-7, cy-6), 2)
        # horns
        pygame.draw.line(surf, (200,80,0), (cx+self.radius-10,cy-self.radius+4), (cx+self.radius+2,cy-self.radius-8), 2)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 64, 9, (255,100,0))
        if hovered: self._hover_label(surf)


class CursedWitch(Enemy):
    """A flying hex-caster. Every 5 s curses all towers within 160 px, doubling
    their cooldown for 1.5 s (same mechanic as TimeBender). Hidden by default.
    Medium HP, above average speed."""
    DISPLAY_NAME = "Cursed Witch"; BASE_HP = 220; BASE_SPEED = 118; KILL_REWARD = 0
    IS_HIDDEN = True
    PULSE_RADIUS = 160; PULSE_INTERVAL = 5.0; PULSE_DURATION = 1.5
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 220 + (wave-1)*12); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 22
        self._pulse_cd = self.PULSE_INTERVAL; self._spin = 0.0
        self.pulse_fired = False
        # vertical float
        self._float_phase = random.uniform(0, math.tau)
    def update(self, dt):
        self._spin += dt*140; self.pulse_fired = False
        self._float_phase += dt*2.8
        self.y = PATH_Y - 14 + math.sin(self._float_phase)*10
        self._pulse_cd -= dt
        if self._pulse_cd <= 0:
            self._pulse_cd = self.PULSE_INTERVAL; self.pulse_fired = True
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        if not detected and not hovered:
            draw_hidden_ghost(surf, int(self.x), int(self.y), self.radius); return
        cx, cy = int(self.x), int(self.y)
        alpha = 150 if not detected else 230
        # purple aura
        s = pygame.Surface((100,100), pygame.SRCALPHA)
        pygame.draw.circle(s, (120,0,200,int(40*(alpha/230))), (36,36), self.radius+10)
        surf.blit(s, (cx-36, cy-36))
        # body robe
        s2 = pygame.Surface((80,80), pygame.SRCALPHA)
        pygame.draw.circle(s2, (50,0,90,alpha), (28,30), self.radius)
        pygame.draw.circle(s2, (100,0,160,alpha), (22,22), 11)
        # hat
        hat_pts = [(28,8),(16,28),(40,28)]
        pygame.draw.polygon(s2, (15,0,30,alpha), hat_pts)
        pygame.draw.polygon(s2, (80,0,120,alpha), hat_pts, 2)
        # glowing eyes
        pygame.draw.circle(s2, (200,0,255,alpha), (22,30), 4)
        pygame.draw.circle(s2, (255,180,255,alpha), (22,30), 2)
        pygame.draw.circle(s2, (200,0,255,alpha), (34,30), 4)
        pygame.draw.circle(s2, (255,180,255,alpha), (34,30), 2)
        # orbiting stars
        for i in range(3):
            a = math.radians(self._spin + i*120)
            ox = 28+int(math.cos(a)*(self.radius+8)); oy = 28+int(math.sin(a)*(self.radius+8))
            pygame.draw.circle(s2, (255,220,0,alpha), (ox,oy), 4)
        surf.blit(s2, (cx-28, cy-28))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 68, 9, (200,0,255))
        if hovered: self._hover_label(surf)


class AbyssalSpawn(Enemy):
    """Tiny but numerous demonic imp. Very fast, low HP. Splits into 2 on death
    (like Breaker). Drawn as a small winged imp with a tail."""
    DISPLAY_NAME = "Abyssal Spawn"; BASE_HP = 12; BASE_SPEED = 170; KILL_REWARD = 0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 30 + (wave-1)*2); self.maxhp = self.hp
        self.speed = self.BASE_SPEED + (wave-1)*4; self.radius = 14
        self._wing = 0.0
    def update(self, dt):
        self._wing += dt*20
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._wing*0.5)*3; cx, cy = int(self.x), int(self.y+bob)
        # body
        pygame.draw.circle(surf, (160,20,30), (cx,cy), self.radius)
        pygame.draw.circle(surf, (220,60,50), (cx-4,cy-4), 7)
        # wings (flapping)
        ws = int(math.sin(self._wing)*7+9)
        pygame.draw.ellipse(surf, (120,10,20),
            (cx-self.radius-ws, cy-6, ws+4, 12))
        pygame.draw.ellipse(surf, (120,10,20),
            (cx+self.radius-4, cy-6, ws+4, 12))
        # horns
        pygame.draw.line(surf, (200,80,20),
            (cx-5,cy-self.radius+2),(cx-10,cy-self.radius-8),2)
        pygame.draw.line(surf, (200,80,20),
            (cx+5,cy-self.radius+2),(cx+10,cy-self.radius-8),2)
        # eyes
        pygame.draw.circle(surf, (255,180,0),(cx-4,cy-3),3)
        pygame.draw.circle(surf, (255,180,0),(cx+4,cy-3),3)
        # tail
        t_pts = [(cx+self.radius-2,cy+5),(cx+self.radius+8,cy+2),
                 (cx+self.radius+12,cy+8),(cx+self.radius+10,cy+12)]
        pygame.draw.lines(surf, (180,30,20), False, t_pts, 2)
        pygame.draw.circle(surf, (255,60,0),(t_pts[-1][0],t_pts[-1][1]),3)
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 46, 7, (255,60,20))
        if hovered: self._hover_label(surf)


class DoomBringer(Enemy):
    """Massive demon lord — 35% armour, huge HP, permanently stun-immune.
    Every 7 s releases a shockwave that deals 40 dmg to all enemies (ally fire)
    — nope, actually debuffs nearest tower for 3 s (doubled cooldown).
    Intimidating boss presence with wings and crown of fire."""
    DISPLAY_NAME = "Doom Bringer"; BASE_HP = 8000; BASE_SPEED = 55; KILL_REWARD = 0
    ARMOR = 0.35
    PULSE_RADIUS = 200; PULSE_INTERVAL = 7.0; PULSE_DURATION = 3.0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 8000 + (wave-1)*400); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 48
        self._rot = 0.0; self._pulse_cd = self.PULSE_INTERVAL
        self._pulse_t = 0.0; self.pulse_fired = False
        self._stun_immune_timer = 9999.0
        self._clown_pushback = False
    def update(self, dt):
        self._rot += dt*18; self._pulse_t = max(0.0, self._pulse_t - dt)
        self._stun_immune_timer = 9999.0; self.pulse_fired = False
        self._pulse_cd -= dt
        if self._pulse_cd <= 0:
            self._pulse_cd = self.PULSE_INTERVAL
            self._pulse_t = 0.7; self.pulse_fired = True
        self._clown_pushback = False
        return super().update(dt)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob*0.3)*1; cx, cy = int(self.x), int(self.y+bob)
        gp = abs(math.sin(self._rot*0.05))
        # outer dark halo
        s = pygame.Surface((280,280), pygame.SRCALPHA)
        pygame.draw.circle(s, (60,0,10,int(50+gp*30)), (70,70), self.radius+18)
        surf.blit(s, (cx-70, cy-70))
        # pulse flash
        if self._pulse_t > 0:
            pp = self._pulse_t/0.7
            ps = pygame.Surface((280,280), pygame.SRCALPHA)
            pygame.draw.circle(ps, (255,60,0,int(140*pp)), (70,70), int(self.radius+12+pp*50))
            surf.blit(ps, (cx-70, cy-70))
        # wings
        for sign in (-1,1):
            wing_pts = [
                (cx+sign*self.radius, cy-10),
                (cx+sign*(self.radius+40), cy-35),
                (cx+sign*(self.radius+30), cy+10),
                (cx+sign*(self.radius+10), cy+20),
            ]
            pygame.draw.polygon(surf, (80,5,15), wing_pts)
            pygame.draw.polygon(surf, (160,20,30), wing_pts, 2)
        # body
        pygame.draw.circle(surf, (40,5,10), (cx,cy), self.radius+4, 6)
        pygame.draw.circle(surf, (30,5,8), (cx,cy), self.radius)
        pygame.draw.circle(surf, (80,15,25), (cx-16,cy-16), 26)
        pygame.draw.circle(surf, (200,30,50), (cx,cy), self.radius, 3)
        # crown of fire spikes
        for i in range(6):
            a = math.radians(-90 + i*60 + gp*20)
            px2 = cx+int(math.cos(a)*(self.radius+2)); py2 = cy+int(math.sin(a)*(self.radius+2))
            ex2 = cx+int(math.cos(a)*(self.radius+18+i%2*8)); ey2 = cy+int(math.sin(a)*(self.radius+18+i%2*8))
            col = (255,int(80+gp*100),0)
            pygame.draw.line(surf, col, (px2,py2),(ex2,ey2),3)
            pygame.draw.circle(surf, (255,200,50),(ex2,ey2),3)
        # glowing eyes
        for ex3,ey3 in [(cx-14,cy-10),(cx+14,cy-10)]:
            pygame.draw.circle(surf, (255,0,60),(ex3,ey3),7)
            pygame.draw.circle(surf, (255,200,0),(ex3,ey3),3)
        # horns
        for sign in (-1,1):
            pygame.draw.polygon(surf, (100,15,30),[
                (cx+sign*12,cy-self.radius+4),
                (cx+sign*28,cy-self.radius-28),
                (cx+sign*22,cy-self.radius+6)
            ])
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 140, 16, (255,30,50))
        if hovered: self._hover_label(surf)


class AshWraith(Enemy):
    """Ghostly ash-cloud enemy. IS_HIDDEN, moderate HP, medium-fast speed.
    Periodically becomes fully invisible for 2 s (like Phantom but shorter CD).
    Flickers in and out of visibility in ash-grey tones."""
    DISPLAY_NAME = "Ash Wraith"; BASE_HP = 65; BASE_SPEED = 130; KILL_REWARD = 0
    IS_HIDDEN = True
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 160 + (wave-1)*9); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 20
        self._phase_cd = 3.0; self._phased = False; self._phase_t = 0.0
        self._drift = 0.0
    def update(self, dt):
        self._drift += dt*2.5
        self.y = PATH_Y + math.sin(self._drift)*14
        self._phase_t = max(0.0, self._phase_t - dt)
        self._phase_cd -= dt
        if self._phased:
            if self._phase_t <= 0:
                self._phased = False; self.IS_HIDDEN = True
                self._phase_cd = 3.0
        else:
            if self._phase_cd <= 0:
                self._phased = True; self.IS_HIDDEN = True
                self._phase_t = 2.0
        return super().update(dt)
    def take_damage(self, dmg):
        if self._phased: return
        super().take_damage(dmg)
    def draw(self, surf, hovered=False, detected=False):
        if not detected and not hovered:
            draw_hidden_ghost(surf, int(self.x), int(self.y), self.radius); return
        cx, cy = int(self.x), int(self.y)
        alpha = 60 if self._phased else 200
        # wispy ash cloud particles
        for i in range(6):
            a = math.radians(self._drift*40 + i*60)
            ox = cx+int(math.cos(a)*(self.radius-4)); oy = cy+int(math.sin(a)*(self.radius-4))
            s = pygame.Surface((40,40), pygame.SRCALPHA)
            pygame.draw.circle(s, (160,140,130,alpha//2), (12,12), 8)
            surf.blit(s, (ox-12, oy-12))
        # core body
        s2 = pygame.Surface((80,80), pygame.SRCALPHA)
        pygame.draw.circle(s2, (80,70,65,alpha), (26,26), self.radius)
        pygame.draw.circle(s2, (160,145,135,alpha),(20,20), 10)
        pygame.draw.circle(s2, (200,190,180,alpha//2),(26,26), self.radius, 2)
        # glowing ember eyes
        pygame.draw.circle(s2, (255,120,20,alpha),(20,24),4)
        pygame.draw.circle(s2, (255,200,80,alpha),(20,24),2)
        pygame.draw.circle(s2, (255,120,20,alpha),(32,24),4)
        pygame.draw.circle(s2, (255,200,80,alpha),(32,24),2)
        surf.blit(s2, (cx-26,cy-26))
        self._draw_status_effects(surf)
        self._draw_hp_bar(surf, 62, 8, (200,180,160))
        if hovered: self._hover_label(surf)


class HellGateKeeper(Enemy):
    """The ultimate Hell boss — massive demon guardian. 40% armour, permanently
    stun-immune. Two abilities: fire shockwave (pulse_fired) every 8 s doubling
    tower CDs for 2 s, AND dark shield every 6 s for 1 s (invulnerable).
    Drawn with full demonic regalia — chains, crown, molten core."""
    DISPLAY_NAME = "Hell Gate Keeper"; BASE_HP = 30000; BASE_SPEED = 44; KILL_REWARD = 0
    ARMOR = 0.40
    PULSE_RADIUS = 220; PULSE_INTERVAL = 8.0; PULSE_DURATION = 2.0
    def __init__(self, wave=1):
        super().__init__(wave)
        self.hp = max(1, 30000 + (wave-1)*2000); self.maxhp = self.hp
        self.speed = self.BASE_SPEED; self.radius = 54
        self._rot = 0.0; self._pulse_cd = self.PULSE_INTERVAL
        self._pulse_t = 0.0; self.pulse_fired = False
        self._shield_cd = 6.0; self._shield_t = 0.0; self.shielded = False
        self._stun_immune_timer = 9999.0; self._clown_pushback = False
    def update(self, dt):
        self._rot += dt*14; self._pulse_t = max(0.0,self._pulse_t-dt)
        self._shield_t = max(0.0,self._shield_t-dt)
        self._stun_immune_timer = 9999.0; self.pulse_fired = False
        self.shielded = self._shield_t > 0
        self._pulse_cd -= dt
        if self._pulse_cd <= 0:
            self._pulse_cd = self.PULSE_INTERVAL; self._pulse_t = 0.8; self.pulse_fired = True
        self._shield_cd -= dt
        if self._shield_cd <= 0 and not self.shielded:
            self._shield_cd = 6.0; self._shield_t = 1.0
        self._clown_pushback = False
        return super().update(dt)
    def take_damage(self, dmg):
        if self.shielded: return
        super().take_damage(dmg)
    def draw(self, surf, hovered=False, detected=False):
        bob = math.sin(self._bob*0.25)*0.5; cx, cy = int(self.x), int(self.y+bob)
        gp = abs(math.sin(self._rot*0.04))
        # shield
        if self.shielded:
            sp = self._shield_t
            ss = pygame.Surface((300,300), pygame.SRCALPHA)
            pygame.draw.circle(ss, (100,0,200,int(100*sp)), (80,80), self.radius+24)
            pygame.draw.circle(ss, (220,80,255,int(200*sp)), (80,80), self.radius+24, 4)
            surf.blit(ss, (cx-80,cy-80))
        # pulse flash
        if self._pulse_t > 0:
            pp = self._pulse_t/0.8
            ps = pygame.Surface((300,300), pygame.SRCALPHA)
            pygame.draw.circle(ps, (255,50,0,int(160*pp)),(80,80),int(self.radius+16+pp*60))
            surf.blit(ps, (cx-80,cy-80))
        # deep aura
        aura_s = pygame.Surface((300,300), pygame.SRCALPHA)
        pygame.draw.circle(aura_s, (80,0,15,int(55+gp*35)),(80,80),self.radius+20)
        surf.blit(aura_s, (cx-80,cy-80))
        # chains orbiting
        for i in range(6):
            a = math.radians(self._rot*0.8 + i*60)
            chain_r = self.radius+16
            px2=cx+int(math.cos(a)*chain_r); py2=cy+int(math.sin(a)*chain_r)
            nx=cx+int(math.cos(a+0.5)*chain_r); ny=cy+int(math.sin(a+0.5)*chain_r)
            pygame.draw.line(surf,(100,60,20),(px2,py2),(nx,ny),3)
            pygame.draw.circle(surf,(140,90,30),(px2,py2),4)
        # wings
        for sign in (-1,1):
            wing_pts = [
                (cx+sign*self.radius, cy-8),
                (cx+sign*(self.radius+50), cy-50),
                (cx+sign*(self.radius+60), cy-20),
                (cx+sign*(self.radius+40), cy+16),
                (cx+sign*(self.radius+8), cy+22),
            ]
            pygame.draw.polygon(surf,(60,3,8),wing_pts)
            pygame.draw.polygon(surf,(200,20,30),wing_pts,2)
            # wing membrane lines
            for j in range(1,4):
                frac = j/4
                px3=int(cx+sign*self.radius*(1-frac)+wing_pts[1][0]*frac)
                py3=int(cy*(-8/self.radius*(1-frac)) + wing_pts[1][1]*frac)
                pygame.draw.line(surf,(120,10,20),(cx+sign*self.radius,cy-8),(px3,py3),1)
        # body
        pygame.draw.circle(surf,(50,5,10),(cx,cy),self.radius+5,7)
        pygame.draw.circle(surf,(35,4,8),(cx,cy),self.radius)
        pygame.draw.circle(surf,(90,15,25),(cx-20,cy-20),32)
        pygame.draw.circle(surf,(220,25,50),(cx,cy),self.radius,3)
        # massive horns
        for sign in (-1,1):
            pygame.draw.polygon(surf,(110,15,30),[
                (cx+sign*16,cy-self.radius+4),
                (cx+sign*38,cy-self.radius-42),
                (cx+sign*30,cy-self.radius+8)
            ])
            # secondary small horn
            pygame.draw.polygon(surf,(100,12,25),[
                (cx+sign*28,cy-self.radius+2),
                (cx+sign*42,cy-self.radius-20),
                (cx+sign*38,cy-self.radius+4)
            ])
        # crown of molten spikes
        for i in range(8):
            a = math.radians(-90+i*45+gp*15)
            px4=cx+int(math.cos(a)*(self.radius+2)); py4=cy+int(math.sin(a)*(self.radius+2))
            ex4=cx+int(math.cos(a)*(self.radius+24+i%2*10))
            ey4=cy+int(math.sin(a)*(self.radius+24+i%2*10))
            pygame.draw.line(surf,(255,int(60+gp*100),0),(px4,py4),(ex4,ey4),4)
            pygame.draw.circle(surf,(255,220,80),(ex4,ey4),4)
        # eyes — massive glowing
        for ex5,ey5 in [(cx-18,cy-12),(cx+18,cy-12)]:
            pygame.draw.circle(surf,(255,0,50),(ex5,ey5),10)
            pygame.draw.circle(surf,(255,160,0),(ex5,ey5),5)
            pygame.draw.circle(surf,(255,255,200),(ex5,ey5),2)
        # mouth snarl
        pts_m = [(cx-20,cy+10),(cx-10,cy+16),(cx,cy+12),(cx+10,cy+16),(cx+20,cy+10)]
        pygame.draw.lines(surf,(255,30,0),False,pts_m,3)
        # HP bar — wide
        self._draw_hp_bar(surf, 160, 18, (255,20,40))
        if hovered: self._hover_label(surf)


# ── Wave data ──────────────────────────────────────────────────────────────────
BREAKER_POOL=[HiddenEnemy,Enemy,ScoutEnemy,TankEnemy,NormalBoss]
ABYSSAL_SPAWN_POOL=[HellHound,AbyssalSpawn,SoulReaper]

WAVE_DATA_EASY=[
    None,
    # 1-5: вводные волны с простыми врагами
    ([(BlobEnemy,4),(PaperEnemy,4)],                                                          200,  70),
    ([(BlobEnemy,5),(ZombieEnemy,3),(PaperEnemy,3)],                                          350, 122),
    ([(ZombieEnemy,5),(BlobEnemy,6),(Enemy,3)],                                               500, 175),
    ([(Enemy,5),(ZombieEnemy,6),(ScoutEnemy,3),(BabyDragonEnemy,2)],                          650, 227),
    ([(BabyDragonEnemy,4),(Enemy,6),(ZombieEnemy,5),(ScoutEnemy,4)],                          800, 280),
    # 6-8: первые боссы + легко бронированные
    ([(TankEnemy,4),(ScoutEnemy,8),(NormalBoss,1),(BabyDragonEnemy,4)],                       950, 332),
    ([(TankEnemy,6),(HiddenEnemy,4),(NormalBoss,1),(ZombieEnemy,8)],                         1100, 385),
    ([(GlassEnemy,4),(TankEnemy,6),(HiddenEnemy,5),(BabyDragonEnemy,5)],                     1250, 437),
    # 9-11: скрытые, Regen, Glass
    ([(RegeneratorEnemy,3),(NormalBoss,2),(HiddenEnemy,8),(ScoutEnemy,6)],                   1400, 489),
    ([(VoltCrawler,5),(BreakerEnemy,5),(RegeneratorEnemy,3),(GlassEnemy,4)],                 1550, 542),
    ([(ShadowStepper,3),(BreakerEnemy,6),(HiddenEnemy,6),(RegeneratorEnemy,4)],              1700, 595),
    # 12-14: средняя броня, SteelGolem
    ([(Necromancer,1),(VoltCrawler,5),(ArmoredEnemy,5),(RegeneratorEnemy,4),(Enemy,6)],      1850, 647),
    ([(SteelGolem,2),(ArmoredEnemy,6),(BreakerEnemy,6),(GlassEnemy,5)],                     2000, 700),
    ([(TimeBender,1),(SteelGolem,2),(ShadowStepper,4),(NormalBoss,2),(HiddenEnemy,6)],      2150, 752),
    # 15-17: тяжёлые, SwarmBoss, Phantom
    ([(IronMaiden,1),(ArmoredEnemy,8),(Necromancer,1),(SteelGolem,3)],                      2300, 805),
    ([(SlowBoss,1),(SwarmBoss,1),(VoltCrawler,6),(ShadowStepper,3)],                        2450, 857),
    ([(PhantomBoss,1),(ShadowStepper,4),(SteelGolem,3),(VoltCrawler,8)],                    2600, 909),
    # 18-20: финал
    ([(IronMaiden,2),(TimeBender,2),(ArmoredEnemy,10),(SteelGolem,3)],                      2750, 962),
    ([(IronMaiden,2),(SlowBoss,1),(Necromancer,2),(SwarmBoss,1),
      (TimeBender,1),(VoltCrawler,6),(PhantomBoss,1)],                                      2900,1014),
    ([(IronMaiden,3),(TimeBender,3),(ShadowStepper,6),(SteelGolem,4),
      (VoltCrawler,10),(SlowBoss,1),(NormalBoss,3),(ArmoredEnemy,12),
      (BreakerEnemy,10),(PhantomBoss,1),(Necromancer,1)],                                   4000,   0),
]

WAVE_DATA_HELL=[
    None,
    # 1-3: совсем мягкий старт — 1-2 башни справятся
    ([(HellHound,2),(AbyssalSpawn,2)],                                                               400,  80),
    ([(HellHound,3),(AbyssalSpawn,3)],                                                               520, 130),
    ([(InfernoWyrm,1),(HellHound,3),(AbyssalSpawn,3)],                                               640, 180),
    # 4-5: чуть сложнее
    ([(DemonKnight,1),(AshWraith,2),(HellHound,4),(AbyssalSpawn,3)],                                 760, 230),
    ([(DemonKnight,1),(SoulReaper,1),(InfernoWyrm,2),(HellHound,3)],                                 880, 280),
    # 6-8: ведьмы + первый голем
    ([(CursedWitch,1),(DemonKnight,2),(AshWraith,2),(AbyssalSpawn,5)],                              1000, 330),
    ([(BrimstoneGolem,1),(CursedWitch,1),(SoulReaper,1),(InfernoWyrm,3)],                           1120, 380),
    ([(BrimstoneGolem,1),(DemonKnight,2),(CursedWitch,1),(HellHound,5),(AshWraith,2)],              1240, 430),
    # 9-11: первый DoomBringer
    ([(DoomBringer,1),(SoulReaper,2),(BrimstoneGolem,1),(CursedWitch,1),(AbyssalSpawn,6)],          1400, 480),
    ([(DoomBringer,1),(DemonKnight,3),(InfernoWyrm,4),(AshWraith,3),(BrimstoneGolem,1)],            1560, 535),
    ([(DoomBringer,1),(SoulReaper,2),(CursedWitch,2),(HellHound,6),(DemonKnight,3)],                1720, 590),
    # 12-14: HellGateKeeper появляется
    ([(DoomBringer,1),(BrimstoneGolem,2),(AbyssalSpawn,8),(CursedWitch,2)],                         1880, 645),
    ([(HellGateKeeper,1),(DemonKnight,4),(SoulReaper,3),(AshWraith,4),(InfernoWyrm,4)],             2040, 700),
    ([(HellGateKeeper,1),(DoomBringer,1),(BrimstoneGolem,2),(CursedWitch,2),(HellHound,6)],         2200, 755),
    # 15-17: нарастает
    ([(HellGateKeeper,1),(DoomBringer,2),(SoulReaper,3),(DemonKnight,4),(BrimstoneGolem,2)],        2360, 810),
    ([(HellGateKeeper,1),(DoomBringer,2),(AshWraith,5),(CursedWitch,3),(AbyssalSpawn,10),
      (InfernoWyrm,5),(BrimstoneGolem,2)],                                                          2520, 865),
    ([(HellGateKeeper,1),(DoomBringer,2),(IronMaiden,2),(SoulReaper,4),(DemonKnight,5)],            2680, 920),
    # 18-20: апокалипсис
    ([(HellGateKeeper,2),(DoomBringer,3),(BrimstoneGolem,3),(CursedWitch,4),(AbyssalSpawn,12),
      (AshWraith,5),(HellHound,8)],                                                                 2840, 975),
    ([(HellGateKeeper,2),(DoomBringer,3),(SoulReaper,5),(DemonKnight,7),(InfernoWyrm,7),
      (CursedWitch,4),(BrimstoneGolem,3),(AbyssalSpawn,10)],                                        3000,1030),
    ([(HellGateKeeper,3),(DoomBringer,4),(BrimstoneGolem,4),(SoulReaper,5),(DemonKnight,7),
      (CursedWitch,4),(InfernoWyrm,7),(AshWraith,5),(HellHound,10),(AbyssalSpawn,14)],              7000,   0),
]

WAVE_DATA=[
    None,
    # Волна 1-5: знакомство, базовые враги
    ([(Enemy,3)],                                                                           200,  70),
    ([(Enemy,5),(ScoutEnemy,2)],                                                            350, 122),
    ([(Enemy,6),(ScoutEnemy,4)],                                                            500, 175),
    ([(ScoutEnemy,5),(TankEnemy,3),(Enemy,5)],                                              650, 227),
    ([(TankEnemy,5),(ScoutEnemy,6),(Enemy,4)],                                              800, 280),
    # Волна 6-7: первые боссы
    ([(TankEnemy,5),(ScoutEnemy,8),(NormalBoss,1)],                                         950, 332),
    ([(TankEnemy,6),(ScoutEnemy,10),(NormalBoss,1),(HiddenEnemy,4)],                       1100, 385),
    # Волна 8: появляется MirrorShield
    ([(MirrorShield,3),(TankEnemy,6),(HiddenEnemy,6)],                                     1250, 437),
    # Волна 9: скрытые + первый NormalBoss пачкой
    ([(NormalBoss,2),(HiddenEnemy,10),(ScoutEnemy,6),(MirrorShield,2)],                    1400, 489),
    # Волна 10: VoltCrawler врываются быстрой волной
    ([(VoltCrawler,8),(BreakerEnemy,6),(TankEnemy,5),(MirrorShield,2)],                    1550, 542),
    # Волна 11: ShadowStepper
    ([(ShadowStepper,4),(BreakerEnemy,8),(HiddenEnemy,8),(NormalBoss,1)],                  1700, 595),
    # Волна 12: Некромант + хаос
    ([(Necromancer,1),(VoltCrawler,6),(ShadowStepper,3),(ArmoredEnemy,6),(Enemy,8)],       1850, 647),
    # Волна 13: TimeBender — замедляет башни
    ([(TimeBender,2),(ArmoredEnemy,8),(BreakerEnemy,8),(MirrorShield,4)],                  2000, 700),
    # Волна 14: смешанная угроза
    ([(TimeBender,2),(ShadowStepper,5),(VoltCrawler,10),(NormalBoss,2),(HiddenEnemy,8)],   2150, 752),
    # Волна 15: IronMaiden впервые — медленно, но страшно
    ([(IronMaiden,2),(ArmoredEnemy,10),(Necromancer,1),(BreakerEnemy,10)],                 2300, 805),
    # Волна 16: SlowBoss + поддержка
    ([(SlowBoss,1),(TimeBender,2),(VoltCrawler,8),(ShadowStepper,4)],                     2450, 857),
    # Волна 17: HiddenBoss + мерцающая свита
    ([(HiddenBoss,1),(ShadowStepper,6),(MirrorShield,5),(VoltCrawler,10)],                2600, 909),
    # Волна 18: тяжёлая броня + TimeBender мешает
    ([(IronMaiden,3),(TimeBender,3),(ArmoredEnemy,12),(BreakerEnemy,10)],                 2750, 962),
    # Волна 19: предфинал — всё вместе
    ([(IronMaiden,2),(SlowBoss,1),(Necromancer,2),(ShadowStepper,6),
      (TimeBender,2),(VoltCrawler,8),(MirrorShield,4)],                                   2900,1014),
    # Волна 20: финал — полный хаос
    ([(IronMaiden,4),(TimeBender,4),(ShadowStepper,8),(MirrorShield,6),
      (VoltCrawler,12),(SlowBoss,2),(NormalBoss,4),(ArmoredEnemy,15),
      (BreakerEnemy,15),(HiddenBoss,1),(Necromancer,2)],                                  5000,   0),
]

# ── WaveManager ────────────────────────────────────────────────────────────────
class WaveManager:
    def __init__(self, wave_data=None):
        self.wave=0; self.state="prep"; self.prep_timer=5.0
        self.spawn_queue=[]; self.spawn_timer=0.0; self.spawn_interval=0.9
        self._bonus_paid=False; self._lmoney_paid=False; self._gd_spawned=False
        self.wave_elapsed=0.0  # seconds since current wave started
        self.extra_queue=[]; self.extra_timer=0.0  # parallel next-wave spawn on skip
        self._wave_data = wave_data if wave_data is not None else WAVE_DATA

    def _build_queue(self, wn):
        if wn<1 or wn>MAX_WAVES or self._wave_data[wn] is None: return []
        groups,_,_=self._wave_data[wn]
        q=[]
        for EClass,count in groups:
            for _ in range(count): q.append(EClass(wn))
        random.shuffle(q); return q

    def update(self, dt, enemies):
        # Tick parallel extra spawn queue (from skip)
        if self.extra_queue:
            self.extra_timer -= dt
            if self.extra_timer <= 0:
                self.extra_timer = self.spawn_interval
                enemies.append(self.extra_queue.pop(0))
            # When extra queue finishes, promote to normal wave state
            if not self.extra_queue:
                # merge: current spawn_queue stays, state becomes spawning for the new wave
                self.spawn_queue = []
                self.state = "waiting"

        if self.state=="prep":
            self.prep_timer-=dt
            if self.prep_timer<=0: self._start_wave()
        elif self.state=="spawning":
            self.wave_elapsed+=dt
            self.spawn_timer-=dt
            if self.spawn_timer<=0 and self.spawn_queue:
                self.spawn_timer=self.spawn_interval
                enemies.append(self.spawn_queue.pop(0))
            if not self.spawn_queue: self.state="waiting"
        elif self.state=="waiting":
            self.wave_elapsed+=dt
            if self.wave==20 and not self._gd_spawned:
                if len(enemies)==0: enemies.append(GraveDigger()); self._gd_spawned=True
            else:
                if len(enemies)==0: self.state="between"; self.prep_timer=5.0
        elif self.state=="between":
            self.prep_timer-=dt
            if self.prep_timer<=0:
                if self.wave<MAX_WAVES: self._start_wave()
                else: self.state="done"

    def _start_wave(self):
        self.wave+=1; self.state="spawning"
        self.spawn_queue=self._build_queue(self.wave)
        self.spawn_timer=0; self._bonus_paid=False; self._lmoney_paid=False; self._gd_spawned=False
        self.wave_elapsed=0.0

    def skip_wave(self):
        """Start spawning the next wave in parallel while current enemies keep going."""
        if self.wave >= MAX_WAVES: return
        next_wave = self.wave + 1
        if next_wave > MAX_WAVES or self._wave_data[next_wave] is None: return
        self.wave += 1
        self.extra_queue = self._build_queue(self.wave)
        self.extra_timer = 0.0
        self._bonus_paid = False; self._lmoney_paid = False
        self.wave_elapsed = 0.0

    def time_left(self):
        if self.state in ("prep","between"): return max(0,self.prep_timer)
        return None
    def wave_lmoney(self):
        if 1<=self.wave<=MAX_WAVES: return self._wave_data[self.wave][1]
        return 0
    def wave_bmoney(self):
        if 1<=self.wave<=MAX_WAVES: return self._wave_data[self.wave][2]
        return 0

# ── Ability ────────────────────────────────────────────────────────────────────
class ShadowStepAbility:
    """Teleport to the highest-HP enemy in range, deal heavy strike,
    and mark it: vulnerable (double damage) for 3 seconds."""
    name="Shadow Step"; cooldown=12.0; dmg_base=80
    def __init__(self, owner): self.owner=owner; self.cd_left=0.0
    @property
    def damage(self): return self.dmg_base + self.owner._shadow_bonus
    def update(self, dt):
        if self.cd_left>0: self.cd_left-=dt
    def ready(self): return self.cd_left<=0
    def activate(self, enemies, effects):
        if not self.ready(): return
        self.cd_left = self.cooldown
        ox, oy = self.owner.px, self.owner.py
        r = self.owner.range_tiles * TILE
        hd = getattr(self.owner, 'hidden_detection', False)
        candidates = [
            e for e in enemies
            if e.alive and dist((e.x,e.y),(ox,oy)) <= r
            and not (e.IS_HIDDEN and not hd)
        ]
        if not candidates:
            return
        # pick highest HP target
        target = max(candidates, key=lambda e: e.hp)
        # deal damage
        target.take_damage(self.damage)
        # mark vulnerable: double incoming damage for 3s
        target._shadow_marked = 3.0
        effects.append(ShadowStepEffect(ox, oy, target.x, target.y))

# ── Unit base ──────────────────────────────────────────────────────────────────
class Unit:
    hidden_detection=False
    def __init__(self, px, py):
        self.px=float(px); self.py=float(py)
        self.level=0; self.ability=None; self.cd_left=0.0
        self._total_spent=self.PLACE_COST  # track all money invested
    def update(self, dt, enemies, effects, money):
        if self.cd_left>0: self.cd_left-=dt
        if self.ability: self.ability.update(dt)
        self._try_attack(enemies, effects)
    def _try_attack(self, enemies, effects): pass
    def draw(self, surf): pass
    def draw_range(self, surf):
        r=int(self.range_tiles*TILE)
        s=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
        own_col = getattr(self,'COLOR',(200,220,255))
        pygame.draw.circle(s,(*own_col[:3],10),(r+2,r+2),r)
        pygame.draw.circle(s,(255,255,255,50),(r+2,r+2),r,2)
        pygame.draw.circle(s,(*own_col[:3],80),(r+2,r+2),r,1)
        surf.blit(s,(int(self.px)-r-2,int(self.py)-r-2))
    def get_info(self): return {}
    def get_next_info(self): return None
    def upgrade_cost(self): return None
    def upgrade(self): pass
    def _get_rightmost(self, enemies, count=1):
        r=self.range_tiles*TILE; targets=[]
        for e in enemies:
            if not e.alive: continue
            if e.IS_HIDDEN and not self.hidden_detection: continue
            if dist((e.x,e.y),(self.px,self.py))<=r: targets.append(e)
        targets.sort(key=lambda e:-e.x); return targets[:count]

# ── Assassin ───────────────────────────────────────────────────────────────────
ASSASSIN_LEVELS=[(3,0.608,4,None),(5,0.508,4,450),(5,0.508,4,550),(15,0.358,4,1500),(27,0.358,5,2500)]

class Assassin(Unit):
    PLACE_COST=300; COLOR=C_ASSASSIN; NAME="Assassin"; _shadow_bonus=0
    def __init__(self, px, py):
        super().__init__(px, py)
        # ── animation state ──────────────────────────────────────────────────
        self._atk_t     = 0.0   # counts up from 0 after each attack; drives strike anim
        self._atk_dur   = 0.22  # full duration of a single strike animation (s)
        self._atk_angle = 0.0   # angle toward last target (degrees, 0 = right)
        self._alt_hand  = False # alternate L / R dagger each strike
        self._idle_t    = 0.0   # idle breathing timer
        self._apply_level()
    def _apply_level(self):
        d,fr,r,_=ASSASSIN_LEVELS[self.level]
        self.damage=d; self.firerate=fr; self.range_tiles=r
        self.hidden_detection=(self.level>=2)
        if self.level>=2 and self.ability is None: self.ability=ShadowStepAbility(self)
        b=0
        if self.level>=3: b+=30
        if self.level>=4: b+=25
        self._shadow_bonus=b
    def upgrade_cost(self):
        if self.level>=len(ASSASSIN_LEVELS)-1: return None
        return ASSASSIN_LEVELS[self.level+1][3]
    def upgrade(self):
        if self.level<len(ASSASSIN_LEVELS)-1:
            cost=ASSASSIN_LEVELS[self.level+1][3] or 0
            self.level+=1; self._apply_level(); self._total_spent+=cost
    def update(self, dt, enemies, effects, money):
        # advance animation timers
        self._idle_t += dt
        if self._atk_t > 0:
            self._atk_t = max(0.0, self._atk_t - dt)
        # base class: cooldown + ability + attack
        if self.cd_left > 0:
            self.cd_left -= dt
        if self.ability:
            self.ability.update(dt)
        self._try_attack(enemies, effects)
    def _try_attack(self, enemies, effects):
        if self.cd_left>0: return
        t=self._get_rightmost(enemies,1)
        if t:
            self.cd_left=self.firerate
            t[0].take_damage(self.damage)
            self._atk_angle = math.degrees(math.atan2(t[0].y-self.py, t[0].x-self.px))
            self._atk_t     = self._atk_dur   # restart strike animation
            self._alt_hand  = not self._alt_hand
            effects.append(SwordEffect(self.px, self.py, self._atk_angle))
    def draw(self, surf):
        cx, cy = int(self.px), int(self.py)

        # ── Animation parameters ─────────────────────────────────────────────
        # atk_prog: 0.0 = idle, 1.0 = just struck, fades back to 0
        atk_prog = self._atk_t / self._atk_dur if self._atk_dur > 0 else 0.0
        # strike arc: peaks at prog=1.0 (just fired), fades to 0
        strike    = atk_prog                           # 1→0 over atk_dur
        # recoil: body lurches toward target then snaps back
        lurch     = int(strike * 5)
        rad       = math.radians(self._atk_angle)
        lurch_dx  = int(math.cos(rad) * lurch)
        lurch_dy  = int(math.sin(rad) * lurch)
        # idle breathing bob
        idle_bob  = int(math.sin(self._idle_t * 2.2) * 1.5)

        # offset the whole body during strike
        bx = cx + lurch_dx
        by = cy + lurch_dy + idle_bob

        # ── Outer aura (pulses on attack) ────────────────────────────────────
        aura_r = int(52 + strike * 18)
        aura_a = int(28 + strike * 60)
        aura = pygame.Surface((aura_r*2+4, aura_r*2+4), pygame.SRCALPHA)
        pygame.draw.circle(aura, (*self.COLOR, aura_a), (aura_r+2, aura_r+2), aura_r)
        surf.blit(aura, (bx - aura_r - 2, by - aura_r - 2))

        # ── Ground shadow ────────────────────────────────────────────────────
        pygame.draw.ellipse(surf, (20, 10, 35), (bx - 18, by + 14, 36, 10))

        # ── Helper: draw one dagger from base_pt toward angle, with animation ──
        def draw_dagger(base_x, base_y, angle_deg, extend=0.0, trail=False):
            """Draw a dagger.
               extend=0  → resting position (handle down, blade diagonal)
               extend=1  → full strike (blade thrust toward angle_deg)
            """
            ang = math.radians(angle_deg)
            # blade direction unit vector
            bvx = math.cos(ang)
            bvy = math.sin(ang)
            # perpendicular (for crossguard)
            pvx = -bvy
            pvy =  bvx

            # resting: dagger held diagonally; on strike: extended toward target
            rest_len   = 18
            strike_len = 26
            blade_len  = rest_len + int((strike_len - rest_len) * extend)

            tip_x = base_x + int(bvx * blade_len)
            tip_y = base_y + int(bvy * blade_len)

            # ── motion trail (ghosted blade) ──────────────────────────────────
            if trail and extend > 0.15:
                trail_a = int(extend * 80)
                trail_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                trail_tip_x = base_x + int(bvx * (blade_len + 10))
                trail_tip_y = base_y + int(bvy * (blade_len + 10))
                pygame.draw.line(trail_s, (200, 160, 255, trail_a),
                                 (base_x, base_y), (trail_tip_x, trail_tip_y), 3)
                surf.blit(trail_s, (0, 0))

            # ── blade ─────────────────────────────────────────────────────────
            pygame.draw.line(surf, (200, 215, 235),
                             (base_x, base_y), (tip_x, tip_y), 3)
            # edge glint
            glint_a = int(160 + extend * 95)
            glint_col = (glint_a, glint_a, 255)
            pygame.draw.line(surf, glint_col,
                             (base_x + int(pvx), base_y + int(pvy)),
                             (tip_x  + int(pvx), tip_y  + int(pvy)), 1)

            # ── tip flash on peak strike ──────────────────────────────────────
            if extend > 0.6:
                flash_a = int((extend - 0.6) / 0.4 * 200)
                flash_s = pygame.Surface((30, 30), pygame.SRCALPHA)
                pygame.draw.circle(flash_s, (220, 180, 255, flash_a), (15, 15), int(4 + extend*4))
                surf.blit(flash_s, (tip_x - 15, tip_y - 15))

            # ── crossguard ────────────────────────────────────────────────────
            guard_x = base_x + int(bvx * (blade_len * 0.35))
            guard_y = base_y + int(bvy * (blade_len * 0.35))
            g_len = 5
            pygame.draw.line(surf, (140, 90, 200),
                             (int(guard_x - pvx*g_len), int(guard_y - pvy*g_len)),
                             (int(guard_x + pvx*g_len), int(guard_y + pvy*g_len)), 3)

            # ── handle ────────────────────────────────────────────────────────
            handle_x = base_x - int(bvx * 8)
            handle_y = base_y - int(bvy * 8)
            pygame.draw.line(surf, (80, 50, 120),
                             (base_x, base_y), (handle_x, handle_y), 4)

        # ── Compute per-hand angles and extend amounts ────────────────────────
        # Left hand rests at ~315° (upper-left diagonal), right at ~45° (upper-right)
        # On strike: the active hand thrusts toward the target angle
        left_rest_ang  = -135.0   # upper-left
        right_rest_ang =  -45.0   # upper-right (raised ready position)

        if self._alt_hand:          # RIGHT hand struck last
            left_ang    = left_rest_ang
            left_ext    = 0.0
            right_ang   = self._atk_angle
            right_ext   = strike
        else:                       # LEFT hand struck last
            left_ang    = self._atk_angle
            left_ext    = strike
            right_ang   = right_rest_ang
            right_ext   = 0.0

        # ── Draw daggers BEHIND body first (the one that went forward) ────────
        # left dagger base position
        ldx = bx - 14
        ldy = by + 2
        rdx = bx + 14
        rdy = by

        # draw the non-striking dagger first (behind body)
        if self._alt_hand:
            draw_dagger(ldx, ldy, left_ang, left_ext, trail=False)
        else:
            draw_dagger(rdx, rdy, right_ang, right_ext, trail=False)

        # ── Cloak / body ─────────────────────────────────────────────────────
        # body sways slightly toward target during strike
        cloak_sway = int(lurch_dx * 0.3)
        cloak_pts = [
            (bx + cloak_sway, by - 28),
            (bx + 22,         by - 8),
            (bx + 18,         by + 18),
            (bx,              by + 22),
            (bx - 18,         by + 18),
            (bx - 22,         by - 8),
        ]
        pygame.draw.polygon(surf, (22, 12, 40), cloak_pts)
        pygame.draw.polygon(surf, (50, 25, 80), cloak_pts, 2)

        # ── Hood ─────────────────────────────────────────────────────────────
        pygame.draw.circle(surf, (30, 15, 55), (bx, by - 14), 16)
        pygame.draw.circle(surf, (55, 28, 88), (bx, by - 14), 16, 2)

        # ── Face mask ────────────────────────────────────────────────────────
        pygame.draw.ellipse(surf, (12, 6, 22), (bx - 8, by - 22, 16, 12))

        # ── Eyes (flash white on strike peak) ────────────────────────────────
        eye_col = (200, 80, 255) if not self.hidden_detection else (80, 255, 160)
        if strike > 0.7:
            eye_col = (255, 255, 255)
        pygame.draw.circle(surf, eye_col,        (bx - 5, by - 16), 3)
        pygame.draw.circle(surf, eye_col,        (bx + 5, by - 16), 3)
        pygame.draw.circle(surf, (255, 255, 255),(bx - 5, by - 16), 1)
        pygame.draw.circle(surf, (255, 255, 255),(bx + 5, by - 16), 1)

        # ── Chest gem (glows on attack) ───────────────────────────────────────
        gem_col = self.COLOR
        if strike > 0.4:
            gem_col = (255, 200, 255)
        pygame.draw.circle(surf, gem_col,          (bx, by - 2), 5)
        pygame.draw.circle(surf, (240, 200, 255),  (bx, by - 2), 2)

        # ── Draw the striking dagger IN FRONT of the body ─────────────────────
        if self._alt_hand:
            draw_dagger(rdx, rdy, right_ang, right_ext, trail=(right_ext > 0.1))
        else:
            draw_dagger(ldx, ldy, left_ang, left_ext,  trail=(left_ext  > 0.1))

        # ── Hidden-detection icon ─────────────────────────────────────────────
        if self.hidden_detection:
            pygame.draw.circle(surf, (60, 220, 100), (bx + 22, by - 26), 6)
            pygame.draw.circle(surf, (10, 10, 10),   (bx + 22, by - 26), 2)

        # ── Level pips ───────────────────────────────────────────────────────
        for i in range(self.level):
            pygame.draw.circle(surf, C_GOLD, (cx - 10 + i * 7, cy + 28), 3)
    def get_info(self):
        return {"Damage":self.damage,"Range":self.range_tiles,
                "Firerate":f"{self.firerate:.3f}"}
    def get_next_info(self):
        nl=self.level+1
        if nl>=len(ASSASSIN_LEVELS): return None
        d,fr,r,_=ASSASSIN_LEVELS[nl]
        hd="YES" if nl>=2 else "no"
        return {"Damage":d,"Range":r,"Firerate":f"{fr:.3f}"}

# ── Accelerator ────────────────────────────────────────────────────────────────
ACCEL_LEVELS=[(12,0.208,7,None,False),(15,0.1808,7,2000,False),(20,0.1808,7,3500,False),
              (30,0.1608,7,6000,True),(33,0.158,7,8250,True),(38,0.108,8,15000,True)]

class Accelerator(Unit):
    PLACE_COST=4500; COLOR=C_ACCEL; NAME="Accelerator"; hidden_detection=True
    def __init__(self, px, py):
        super().__init__(px,py); self._laser_targets=[]; self._laser_t=0.0; self._apply_level()
    def _apply_level(self):
        d,fr,r,_,dual=ACCEL_LEVELS[self.level]
        self.damage=d; self.firerate=fr; self.range_tiles=r; self.dual=dual
    def upgrade_cost(self):
        if self.level>=len(ACCEL_LEVELS)-1: return None
        return ACCEL_LEVELS[self.level+1][3]
    def upgrade(self):
        if self.level<len(ACCEL_LEVELS)-1:
            cost=ACCEL_LEVELS[self.level+1][3] or 0
            self.level+=1; self._apply_level(); self._total_spent+=cost
    def update(self, dt, enemies, effects, money):
        self._laser_t+=dt
        if self.cd_left>0: self.cd_left-=dt
        targets=self._get_rightmost(enemies,2 if self.dual else 1)
        self._laser_targets=targets
        if self.cd_left<=0 and targets:
            self.cd_left=self.firerate
            for t in targets: t.take_damage(self.damage)
    def draw(self, surf):
        cx,cy=int(self.px),int(self.py)
        s=pygame.Surface((180,180),pygame.SRCALPHA)
        pygame.draw.circle(s,(*C_ACCEL,35),(45,45),42); surf.blit(s,(cx-45,cy-45))
        pygame.draw.ellipse(surf,(30,15,60),(cx-20,cy+11,40,13))
        spin=self._laser_t*180
        for i in range(4):
            a=math.radians(spin+i*90)
            pygame.draw.circle(surf,(160,100,255),(int(cx+math.cos(a)*18),int(cy+math.sin(a)*18)),4)
        pygame.draw.circle(surf,(40,20,80),(cx,cy),36)
        pygame.draw.circle(surf,C_ACCEL,(cx,cy),26)
        pygame.draw.circle(surf,(200,170,255),(cx-8,cy-8),10)
        pulse=int(abs(math.sin(self._laser_t*8))*4)+3
        pygame.draw.circle(surf,(230,210,255),(cx,cy),pulse)
        for i in range(self.level):
            pygame.draw.circle(surf,C_GOLD,(cx-14+i*7,cy+24),3)
        for target in self._laser_targets:
            if not target.alive: continue
            tx,ty=int(target.x),int(target.y); tv=self._laser_t
            s2=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
            flicker=int(abs(math.sin(tv*22))*3)
            for width,color,alpha in [(20+flicker,(120,40,255),18),(13,(160,80,255),35),
                                       (8,(200,130,255),70),(4,(230,190,255),140),(2,(255,240,255),220)]:
                pygame.draw.line(s2,(*color,alpha),(cx,cy),(tx,ty),width)
            bl=dist((cx,cy),(tx,ty))
            if bl>1:
                for i in range(6):
                    frac=(i/5+tv*2.5)%1.0
                    sx2=int(cx+(tx-cx)*frac); sy2=int(cy+(ty-cy)*frac)
                    px2=-(ty-cy)/bl; py2=(tx-cx)/bl
                    offset=math.sin(tv*30+i*1.4)*(3+flicker)
                    pygame.draw.circle(s2,(200,150,255,160),
                                       (sx2+int(px2*offset),sy2+int(py2*offset)),random.randint(2,4))
            surf.blit(s2,(0,0))
            fs=pygame.Surface((80,80),pygame.SRCALPHA)
            fr2=int(abs(math.sin(tv*18))*8)+6
            pygame.draw.circle(fs,(220,180,255,100),(20,20),fr2+4)
            pygame.draw.circle(fs,(255,240,255,180),(20,20),fr2)
            surf.blit(fs,(tx-20,ty-20))
    def get_info(self):
        return {"Damage":self.damage,"Range":self.range_tiles,
                "Firerate":f"{self.firerate:.4f}","Dual":"YES" if self.dual else "no"}
    def get_next_info(self):
        nl=self.level+1
        if nl>=len(ACCEL_LEVELS): return None
        d,fr,r,_,dual=ACCEL_LEVELS[nl]
        return {"Damage":d,"Range":r,"Firerate":f"{fr:.4f}","Dual":"YES" if dual else "no"}

# ── Clown ──────────────────────────────────────────────────────────────────────
C_CLOWN = (220, 60, 60)   # C_RED alias with explicit name for clarity

# level: (damage, firerate, range_tiles, upgrade_cost)
CLOWN_LEVELS = [
    {"dmg": 8,  "fr": 1.6, "rng": 3.5, "cost": None},   # 0 base  (dmg 5→8, fr 1.8→1.6, rng 2.5→3.5)
    {"dmg": 14, "fr": 1.4, "rng": 4.0, "cost": 400},    # 1        (dmg 8→14, rng 2.8→4.0)
    {"dmg": 22, "fr": 1.2, "rng": 4.5, "cost": 850},    # 2        (dmg 12→22, rng 3.0→4.5)
    {"dmg": 38, "fr": 1.0, "rng": 5.0, "cost": 1800},   # 3        (dmg 20→38, rng 3.5→5.0)
    {"dmg": 65, "fr": 0.75,"rng": 5.8, "cost": 4500},   # 4        (dmg 35→65, rng 4.0→5.8)
    {"dmg": 110,"fr": 0.45,"rng": 7.0, "cost": 12000},  # 5 max    (dmg 65→110, fr 0.6→0.45, rng 5.0→7.0)
]

CLOWN_MAX_PLACED = 5   # placement limit

class Clown(Unit):
    PLACE_COST    = 750
    COLOR         = C_CLOWN
    NAME          = "Clown"
    _PLACE_LIMIT  = 5   # max 5 Clowns per map
    hidden_detection = False   # overridden at Lv3+

    # ── Global confusion cooldown (shared across ALL Clown instances) ──────────
    _CONFUSE_CD       = 0.0    # seconds remaining until next confusion allowed
    _CONFUSE_INTERVAL = 5.0    # cooldown duration in seconds

    # ── slow config per level (fraction removed from speed) ───────────────────
    # Base 15% slow from Lv0; aura grows stronger at higher levels
    _SLOW_CFG = [
        0.15,   # Lv0 – 15% slow
        0.20,   # Lv1 – 20% slow
        0.25,   # Lv2 – 25% slow
        0.30,   # Lv3 – 30% slow
        0.35,   # Lv4 – 35% slow
        0.45,   # Lv5 – 45% slow
    ]

    def __init__(self, px, py):
        super().__init__(px, py)
        self._anim_t      = 0.0
        self._projectiles = []      # active ClownProjectile list
        self._prev_alive  = set()   # for Lv5 death detection
        self._apply_level()

    def _apply_level(self):
        lv = self.level
        cfg = CLOWN_LEVELS[lv]
        self.damage      = cfg["dmg"]
        self.firerate    = cfg["fr"]
        self.range_tiles = cfg["rng"]   # already in tiles, same unit as Assassin/Accel
        self.hidden_detection = (lv >= 3)

    # ── upgrade ───────────────────────────────────────────────────────────────
    def upgrade_cost(self):
        nl = self.level + 1
        if nl >= len(CLOWN_LEVELS): return None
        return CLOWN_LEVELS[nl]["cost"]

    def upgrade(self):
        nl = self.level + 1
        if nl < len(CLOWN_LEVELS):
            cost = CLOWN_LEVELS[nl]["cost"] or 0
            self.level = nl
            self._apply_level()
            self._total_spent += cost

    # ── helpers ───────────────────────────────────────────────────────────────
    def _enemies_in_range(self, enemies):
        r = self.range_tiles * TILE
        out = []
        for e in enemies:
            if not e.alive: continue
            if e.IS_HIDDEN and not self.hidden_detection: continue
            if dist((e.x, e.y), (self.px, self.py)) <= r:
                out.append(e)
        return out

    # ── update ────────────────────────────────────────────────────────────────
    def update(self, dt, enemies, effects, money):
        self._anim_t += dt
        if self.cd_left > 0: self.cd_left -= dt

        in_range = self._enemies_in_range(enemies)

        # ── Slow aura — apply each frame (all levels, 15% base) ───────────────
        slow_amount = self._SLOW_CFG[self.level]
        for e in in_range:
            e._slow_factor = min(e._slow_factor, 1.0 - slow_amount)

        # ── Lv4+: confusion debuff (global 5s cooldown across all Clowns) ────────
        # Cooldown is ticked centrally in Game.update — not here, to avoid
        # multiple Clown instances decrementing it several times per frame.

        in_range_set = set(id(e) for e in in_range)
        if self.level >= 4 and in_range and Clown._CONFUSE_CD <= 0:
            # Apply confusion and start global cooldown
            Clown._CONFUSE_CD = Clown._CONFUSE_INTERVAL
            for e in enemies:
                if not e.alive: continue
                e._laugh_debuff = (id(e) in in_range_set)
        elif Clown._CONFUSE_CD > 0:
            # During cooldown: keep debuff on enemies already confused, don't add new
            pass
        else:
            # No active confusion: clear debuff
            for e in enemies:
                if not e.alive: continue
                e._laugh_debuff = False

        # ── Projectile attack ─────────────────────────────────────────────────
        if self.cd_left <= 0 and in_range:
            self.cd_left = self.firerate
            t = max(in_range, key=lambda e: e.x)
            proj = ClownProjectile(self.px, self.py, t, self.damage, self.range_tiles * TILE)
            self._projectiles.append(proj)

        # ── Update projectiles ────────────────────────────────────────────────
        self._projectiles = [p for p in self._projectiles if p.update(dt)]

        # ── Lv3+: pushback flag is set by projectile hit; processed centrally
        #    in Game.update once per frame to avoid multi-Clown stacking.

        # ── Lv5: confetti explosion on enemy death inside aura ────────────────
        if self.level >= 5:
            alive_now = set(id(e) for e in enemies if e.alive)
            for e in enemies:
                if not e.alive and id(e) in self._prev_alive:
                    ex, ey = e.x, e.y
                    if dist((ex, ey), (self.px, self.py)) <= self.range_tiles * TILE:
                        effects.append(ConfettiExplosionEffect(ex, ey))
            self._prev_alive = alive_now

    # ── draw ──────────────────────────────────────────────────────────────────
    def draw(self, surf):
        cx, cy = int(self.px), int(self.py)
        t = self._anim_t

        # ── Projectiles ───────────────────────────────────────────────────────
        for p in self._projectiles:
            p.draw(surf)

        # ── Body shadow ───────────────────────────────────────────────────────
        pygame.draw.ellipse(surf, (20, 10, 10), (cx - 22, cy + 20, 44, 14))

        # ── Body (big round clown torso) ───────────────────────────────────────
        body_col = C_RED if self.level < 3 else (200, 30, 30)
        pygame.draw.circle(surf, (60, 20, 20),   (cx, cy), 36)        # dark base
        pygame.draw.circle(surf, body_col,        (cx, cy), 30)        # body
        # white polka-dots
        for i in range(4):
            a = math.radians(i * 90 + t * 30)
            dx2, dy2 = int(math.cos(a) * 14), int(math.sin(a) * 14)
            pygame.draw.circle(surf, C_WHITE, (cx + dx2, cy + dy2), 4)

        # ── Clown hat (triangle) ───────────────────────────────────────────────
        hat_col = (255, 200, 50) if self.level >= 2 else (220, 180, 40)
        hat_pts = [
            (cx, cy - 52),
            (cx - 18, cy - 28),
            (cx + 18, cy - 28),
        ]
        pygame.draw.polygon(surf, hat_col, hat_pts)
        pygame.draw.polygon(surf, C_WHITE, hat_pts, 2)
        pygame.draw.circle(surf, C_RED, (cx, cy - 52), 5)  # tip pom-pom

        # ── Face ──────────────────────────────────────────────────────────────
        # eyes
        pygame.draw.circle(surf, C_WHITE, (cx - 9, cy - 8), 6)
        pygame.draw.circle(surf, C_WHITE, (cx + 9, cy - 8), 6)
        pygame.draw.circle(surf, C_BG,    (cx - 9, cy - 8), 3)
        pygame.draw.circle(surf, C_BG,    (cx + 9, cy - 8), 3)
        # red nose
        nose_bob = int(math.sin(t * 4) * 2)
        pygame.draw.circle(surf, C_RED, (cx, cy + nose_bob), 6)
        # smile
        smile_pts = [(cx - 10 + i * 4, cy + 10 + int(math.sin(i * 0.5) * 4)) for i in range(6)]
        if len(smile_pts) >= 2:
            pygame.draw.lines(surf, C_WHITE, False, smile_pts, 2)

        # ── Hidden-detection indicator (green dot at Lv3+) ────────────────────
        if self.hidden_detection:
            pygame.draw.circle(surf, (100, 255, 100), (cx + 26, cy - 30), 7)

        # ── Level pip dots ────────────────────────────────────────────────────
        for i in range(self.level):
            pygame.draw.circle(surf, C_GOLD, (cx - 10 + i * 5, cy + 28), 3)

    # ── draw_range override: show aura ring clearly when selected ─────────────
    def draw_range(self, surf):
        r = int(self.range_tiles * TILE)
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*C_CLOWN, 28), (r, r), r)
        pygame.draw.circle(s, (*C_CLOWN, 90), (r, r), r, 3)
        surf.blit(s, (int(self.px) - r, int(self.py) - r))

    # ── info panels ───────────────────────────────────────────────────────────
    def get_info(self):
        slow_pct = int(self._SLOW_CFG[self.level] * 100)
        info = {
            "Damage":   self.damage,
            "Range":    self.range_tiles,
            "Firerate": f"{self.firerate:.2f}",
            "Slow":     f"{slow_pct}%",
        }
        if self.level >= 4:
            info["Confuse"] = f"CD {Clown._CONFUSE_CD:.1f}s" if Clown._CONFUSE_CD > 0 else "READY"
        return info

    def get_next_info(self):
        nl = self.level + 1
        if nl >= len(CLOWN_LEVELS): return None
        cfg = CLOWN_LEVELS[nl]
        slow_pct = int(self._SLOW_CFG[nl] * 100)
        return {
            "Damage":   cfg["dmg"],
            "Range":    cfg["rng"],
            "Firerate": f"{cfg['fr']:.2f}",
            "Slow":     f"{slow_pct}%",
        }


# ── Archer ─────────────────────────────────────────────────────────────────────
# Arrow types
ARROW_NORMAL = "normal"
ARROW_ICE    = "ice"
ARROW_FLAME  = "flame"

C_ARCHER = (139, 90, 43)  # brown

# level: (damage, firerate, range_tiles, pierce, upgrade_cost, hidden_detection)
ARCHER_LEVELS = [
    {"dmg": 5,  "fr": 0.580, "rng": 6.0, "pierce": 2, "cost": None,  "hd": False},  # 0
    {"dmg": 6,  "fr": 0.530, "rng": 6.0, "pierce": 3, "cost": 350,   "hd": False},  # 1
    {"dmg": 7,  "fr": 0.500, "rng": 6.5, "pierce": 3, "cost": 600,   "hd": False},  # 2  ice arrow unlocked
    {"dmg": 10, "fr": 0.480, "rng": 6.5, "pierce": 4, "cost": 800,   "hd": False},  # 3  flame arrow unlocked
    {"dmg": 12, "fr": 0.450, "rng": 7.0, "pierce": 5, "cost": 1300,  "hd": True},   # 4
    {"dmg": 15, "fr": 0.420, "rng": 7.5, "pierce": 7, "cost": 1700,  "hd": True},   # 5
]

ARCHER_PLACE_COST = 400
ARCHER_MAX_PLACED = 5


class ArrowProjectile:
    """Arrow shot by the Archer tower. Can pierce multiple enemies."""
    _SPD = 600  # px/s

    def __init__(self, ox, oy, target, damage, pierce, arrow_type, hidden_detection=False):
        self.x = float(ox); self.y = float(oy)
        self.alive = True
        self._damage = damage
        self._pierce_left = pierce
        self._arrow_type = arrow_type
        self._hidden_detection = hidden_detection
        self._hit_ids = set()

        dx = target.x - ox; dy = target.y - oy
        d  = math.hypot(dx, dy) or 1
        self.vx = dx / d * self._SPD
        self.vy = dy / d * self._SPD
        self._angle = math.degrees(math.atan2(dy, dx))
        self._dist_traveled = 0.0
        self._max_dist = 7.0 * TILE  # disappear after ~7 tiles

    def update(self, dt, enemies):
        if not self.alive: return False
        self.x += self.vx * dt
        self.y += self.vy * dt
        self._dist_traveled += self._SPD * dt

        for e in enemies:
            if not e.alive: continue
            if e.IS_HIDDEN and not self._hidden_detection: continue
            if id(e) in self._hit_ids: continue
            if math.hypot(self.x - e.x, self.y - e.y) < e.radius + 10:
                self._hit_ids.add(id(e))
                e.take_damage(self._damage)
                # Apply arrow type effects
                if self._arrow_type == ARROW_FLAME:
                    e._fire_timer = getattr(e, '_fire_timer', 0.0)
                    e._fire_timer = 3.0   # 3 seconds burn
                    e._fire_dmg_tick = 0.0
                elif self._arrow_type == ARROW_ICE:
                    if not getattr(e, 'SLOW_RESISTANCE', False):
                        e._slow_factor = min(e._slow_factor, 0.55)  # slow to 55%
                        e._ice_timer = 0.6  # 0.6 seconds
                self._pierce_left -= 1
                if self._pierce_left <= 0:
                    self.alive = False
                    return False

        if self._dist_traveled > self._max_dist:
            self.alive = False
        return self.alive

    def draw(self, surf):
        if not self.alive: return
        # Arrow body
        if self._arrow_type == ARROW_FLAME:
            col = (255, 120, 30)
            tip_col = (255, 60, 0)
        elif self._arrow_type == ARROW_ICE:
            col = (100, 200, 255)
            tip_col = (180, 240, 255)
        else:
            col = (200, 160, 80)
            tip_col = (220, 190, 100)

        rad = math.radians(self._angle)
        ex = self.x + math.cos(rad) * 18
        ey = self.y + math.sin(rad) * 18
        sx = self.x - math.cos(rad) * 14
        sy = self.y - math.sin(rad) * 14

        pygame.draw.line(surf, col, (int(sx), int(sy)), (int(ex), int(ey)), 3)
        # Arrowhead
        pygame.draw.circle(surf, tip_col, (int(ex), int(ey)), 4)
        # Flame trail
        if self._arrow_type == ARROW_FLAME:
            s2 = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.circle(s2, (255, 100, 20, 80), (30, 30), 10)
            surf.blit(s2, (int(sx) - 30, int(sy) - 30))


class Archer(Unit):
    PLACE_COST    = ARCHER_PLACE_COST
    COLOR         = C_ARCHER
    NAME          = "Archer"
    _PLACE_LIMIT  = ARCHER_MAX_PLACED
    ON_ROAD       = True   # flag: can be placed on road

    def __init__(self, px, py):
        super().__init__(px, py)
        self._anim_t     = 0.0
        self._projectiles = []
        self._arrow_type  = ARROW_NORMAL   # current arrow selection
        self._apply_level()

    def _apply_level(self):
        cfg = ARCHER_LEVELS[self.level]
        self.damage       = cfg["dmg"]
        self.firerate     = cfg["fr"]
        self.range_tiles  = cfg["rng"]
        self._pierce      = cfg["pierce"]
        self.hidden_detection = cfg["hd"]

    # Available arrow types at current level
    def _available_arrows(self):
        types = [ARROW_NORMAL]
        if self.level >= 2: types.append(ARROW_ICE)
        if self.level >= 3: types.append(ARROW_FLAME)
        return types

    def cycle_arrow(self):
        """Switch to next available arrow type."""
        avail = self._available_arrows()
        if self._arrow_type not in avail:
            self._arrow_type = ARROW_NORMAL
            return
        idx = avail.index(self._arrow_type)
        self._arrow_type = avail[(idx + 1) % len(avail)]

    def upgrade_cost(self):
        if self.level >= len(ARCHER_LEVELS) - 1: return None
        return ARCHER_LEVELS[self.level + 1]["cost"]

    def upgrade(self):
        nl = self.level + 1
        if nl < len(ARCHER_LEVELS):
            cost = ARCHER_LEVELS[nl]["cost"] or 0
            self.level = nl
            self._apply_level()
            self._total_spent += cost
            # Ensure arrow type is still valid
            if self._arrow_type not in self._available_arrows():
                self._arrow_type = ARROW_NORMAL

    def update(self, dt, enemies, effects, money):
        self._anim_t += dt
        if self.cd_left > 0: self.cd_left -= dt

        # Update fire/ice timers on enemies (archer is the one applying them)
        for e in enemies:
            if not e.alive: continue
            # Flame burn DoT
            ft = getattr(e, '_fire_timer', 0.0)
            if ft > 0:
                e._fire_timer = max(0.0, ft - dt)
                e._fire_dmg_tick = getattr(e, '_fire_dmg_tick', 0.0) + dt
                if e._fire_dmg_tick >= 0.5:
                    e.take_damage(2)
                    e._fire_dmg_tick = 0.0
            # Ice slow re-application (keep slow while timer active)
            it = getattr(e, '_ice_timer', 0.0)
            if it > 0:
                e._ice_timer = max(0.0, it - dt)
                e._slow_factor = min(e._slow_factor, 0.55)

        # Attack
        if self.cd_left <= 0:
            target = self._get_rightmost(enemies, 1)
            if target:
                self.cd_left = self.firerate
                proj = ArrowProjectile(
                    self.px, self.py, target[0],
                    self.damage, self._pierce,
                    self._arrow_type, self.hidden_detection
                )
                self._projectiles.append(proj)

        # Update projectiles
        self._projectiles = [p for p in self._projectiles if p.update(dt, enemies)]

    def draw(self, surf):
        cx, cy = int(self.px), int(self.py)
        t = self._anim_t

        # Draw projectiles
        for p in self._projectiles:
            p.draw(surf)

        # Shadow
        pygame.draw.ellipse(surf, (30, 20, 10), (cx - 20, cy + 18, 40, 12))

        # Body base (dark brown)
        pygame.draw.circle(surf, (80, 50, 20), (cx, cy), 36)
        # Main circle (brown)
        pygame.draw.circle(surf, C_ARCHER, (cx, cy), 28)
        # Highlight
        pygame.draw.circle(surf, (180, 130, 70), (cx - 9, cy - 9), 9)

        # Draw a bow on the circle
        # Bow arc (left side)
        bow_col = (100, 65, 25)
        bow_rect = pygame.Rect(cx - 18, cy - 22, 14, 44)
        pygame.draw.arc(surf, bow_col, bow_rect, math.radians(270), math.radians(90), 4)
        # Bow string
        pygame.draw.line(surf, (220, 200, 160), (cx - 11, cy - 22), (cx - 11, cy + 22), 1)
        # Arrow on bow (nocked)
        arr_col = (200, 160, 80) if self._arrow_type == ARROW_NORMAL else \
                  (100, 200, 255) if self._arrow_type == ARROW_ICE else (255, 120, 30)
        pygame.draw.line(surf, arr_col, (cx - 11, cy), (cx + 18, cy), 2)
        pygame.draw.circle(surf, arr_col, (cx + 18, cy), 3)

        # Arrow type indicator dot (top right)
        if self._arrow_type == ARROW_ICE:
            pygame.draw.circle(surf, (100, 200, 255), (cx + 24, cy - 26), 7)
            pygame.draw.circle(surf, (200, 240, 255), (cx + 24, cy - 26), 7, 2)
        elif self._arrow_type == ARROW_FLAME:
            pygame.draw.circle(surf, (255, 100, 20), (cx + 24, cy - 26), 7)
            pygame.draw.circle(surf, (255, 200, 50), (cx + 24, cy - 26), 7, 2)

        # Hidden detection indicator
        if self.hidden_detection:
            pygame.draw.circle(surf, (100, 255, 100), (cx + 26, cy - 30), 7)

        # Level pips
        for i in range(self.level):
            pygame.draw.circle(surf, C_GOLD, (cx - 10 + i * 5, cy + 28), 3)

        # Border ring
        pygame.draw.circle(surf, (180, 120, 60), (cx, cy), 28, 2)

    def get_info(self):
        arrow_label = {"normal": "Normal", "ice": "Ice", "flame": "Flame"}
        return {
            "Damage":   self.damage,
            "Range":    self.range_tiles,
            "Firerate": f"{self.firerate:.3f}",
            "Pierce":   self._pierce,
            "Arrow":    arrow_label.get(self._arrow_type, self._arrow_type),
        }

    def get_next_info(self):
        nl = self.level + 1
        if nl >= len(ARCHER_LEVELS): return None
        cfg = ARCHER_LEVELS[nl]
        return {
            "Damage":   cfg["dmg"],
            "Range":    cfg["rng"],
            "Firerate": f"{cfg['fr']:.3f}",
            "Pierce":   cfg["pierce"],
            "Arrow":    "—",
        }


# ── Zigres ─────────────────────────────────────────────────────────────────────
C_ZIGRES = (80, 200, 255)   # electric blue

# (damage, firerate, range_tiles, sentinel_hp, sentinel_dmg, upgrade_cost)
ZIGRES_LEVELS = [
    (15,  1.4, 5,   70,   8, None),   # 0
    (18,  1.3, 6,  100,  15, 2250),   # 1
    (26,  1.1, 7,  200,  15, 3000),   # 2  hidden detection
    (20,  0.8, 8,  600,  23, 6000),   # 3  resonance
    (50,  0.9, 9, 1000,  40, 12000),  # 4  sentinel thorns
    (55,  0.7, 10,2000,  60, 24000),  # 5  death explosion
    (70,  0.5, 9, 8000, 100, 50000),  # 6  COLOSSUS GUARDIAN + rubber duck throw
]


class ZigresResonanceEffect:
    """AoE flash when beam + sentinel hit same target (resonance)."""
    def __init__(self, ox, oy):
        self.x = ox; self.y = oy
        self.t = 0.0; self.life = 0.45

    def update(self, dt):
        self.t += dt
        return self.t < self.life

    def draw(self, surf):
        progress = self.t / self.life
        alpha = int(220 * (1 - progress))
        r = int(60 + progress * 80)
        s = pygame.Surface((r*2+8, r*2+8), pygame.SRCALPHA)
        pygame.draw.circle(s, (80, 220, 255, max(0, alpha//2)), (r+4, r+4), r)
        pygame.draw.circle(s, (200, 240, 255, max(0, alpha)),   (r+4, r+4), r, 3)
        surf.blit(s, (int(self.x)-r-4, int(self.y)-r-4))


class SentinelDeathEffect:
    """Explosion when a Lv5 sentinel dies."""
    def __init__(self, ox, oy):
        self.x = ox; self.y = oy
        self.t = 0.0; self.life = 0.7

    def update(self, dt):
        self.t += dt
        return self.t < self.life

    def draw(self, surf):
        progress = self.t / self.life
        alpha = int(255 * (1 - progress))
        r = int(20 + progress * 100)
        s = pygame.Surface((r*2+8, r*2+8), pygame.SRCALPHA)
        pygame.draw.circle(s, (100, 200, 255, max(0, alpha//2)), (r+4, r+4), r)
        pygame.draw.circle(s, (220, 255, 255, max(0, alpha)),    (r+4, r+4), r, 4)
        surf.blit(s, (int(self.x)-r-4, int(self.y)-r-4))
        # inner white flash
        inner = int(r * 0.4)
        pygame.draw.circle(surf, (220, 240, 255, max(0, alpha)),
                           (int(self.x), int(self.y)), max(1, inner))


class RubberDuckEffect:
    """A giant rubber duck flung by the Colossus Guardian every 5 seconds.
    Flies straight at the target like a heat-seeking missile of absurdity."""

    def __init__(self, ox, oy, targets):
        self.x = float(ox); self.y = float(oy)
        self.alive = True
        self.t = 0.0
        self.life = 3.0
        self._enemies_ref = targets
        # pick the furthest (rightmost) live target
        live = [e for e in targets if e.alive]
        self._target = max(live, key=lambda e: e.x) if live else None
        self.vx = 0.0; self.vy = 0.0
        self._hit_ids = set()
        self._speed = 520

    def update(self, dt):
        if not self.alive: return False
        self.t += dt

        if self._target and not self._target.alive:
            # retarget to nearest alive enemy
            live = [e for e in self._enemies_ref if e.alive and id(e) not in self._hit_ids]
            self._target = max(live, key=lambda e: e.x) if live else None

        if self._target:
            dx = self._target.x - self.x
            dy = self._target.y - self.y
            d = math.hypot(dx, dy) or 1
            # homing: steer toward target
            tx = dx / d * self._speed; ty = dy / d * self._speed
            steer = min(1.0, dt * 8)
            self.vx = self.vx + (tx - self.vx) * steer
            self.vy = self.vy + (ty - self.vy) * steer

        self.x += self.vx * dt
        self.y += self.vy * dt

        # hit enemies within radius
        for e in self._enemies_ref:
            if not e.alive or id(e) in self._hit_ids: continue
            if math.hypot(e.x - self.x, e.y - self.y) < 44:
                self._hit_ids.add(id(e))
                e.take_damage(500)
                try_stun(e, 3.0)
                e._laugh_debuff = True
                # after main hit, keep flying through crowd
                self._target = None
                live = [e2 for e2 in self._enemies_ref if e2.alive and id(e2) not in self._hit_ids]
                if live:
                    self._target = max(live, key=lambda e2: e2.x)

        if self.t >= self.life or (not self._target and len(self._hit_ids) > 0
                                   and not any(e.alive and id(e) not in self._hit_ids
                                               for e in self._enemies_ref)):
            self.alive = False
        return self.alive

    def draw(self, surf):
        if not self.alive: return
        cx, cy = int(self.x), int(self.y)
        progress = self.t / self.life
        r = 30  # big duck

        angle = math.atan2(self.vy, self.vx)  # direction of flight

        s = pygame.Surface((r*4+8, r*4+8), pygame.SRCALPHA)
        sc = r*2 + 4

        # body
        pygame.draw.ellipse(s, (255, 220, 0, 240), (sc-r, sc-int(r*0.75), r*2, int(r*1.5)))
        pygame.draw.ellipse(s, (220, 180, 0, 160), (sc-r, sc-int(r*0.75), r*2, int(r*1.5)), 3)
        # head
        pygame.draw.circle(s, (255, 235, 40, 240), (sc, sc - int(r*0.85)), int(r*0.65))
        # beak
        beak_pts = [
            (sc + int(r*0.5),     sc - int(r*0.85) - 3),
            (sc + int(r*0.5)+12,  sc - int(r*0.85)),
            (sc + int(r*0.5),     sc - int(r*0.85) + 5),
        ]
        pygame.draw.polygon(s, (255, 130, 10, 240), beak_pts)
        # eye
        pygame.draw.circle(s, (20, 20, 20, 240), (sc + int(r*0.25), sc - int(r*1.05)), 4)
        pygame.draw.circle(s, (255, 255, 255, 240), (sc + int(r*0.25) - 1, sc - int(r*1.05) - 1), 2)

        # rotate surface to face flight direction
        rot_deg = -math.degrees(angle)
        rotated = pygame.transform.rotate(s, rot_deg)
        rr = rotated.get_rect(center=(cx, cy))
        surf.blit(rotated, rr.topleft)

        # yellow motion trail
        alpha_trail = max(0, int(200 * (1 - progress)))
        for i in range(1, 5):
            tx = cx - int(self.vx * 0.014 * i)
            ty = cy - int(self.vy * 0.014 * i)
            ts = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            a = max(0, alpha_trail - i * 40)
            pygame.draw.ellipse(ts, (255, 220, 0, a), (0, 0, r*2, r*2))
            surf.blit(ts, (tx - r, ty - r))

        # SQUEAK label on first hit
        if len(self._hit_ids) > 0 and progress < 0.7:
            alpha = int(255 * (1 - progress * 1.4))
            squeak_surf = font_md.render("SQUEAK!", True, (255, 220, 0))
            squeak_surf.set_alpha(max(0, alpha))
            surf.blit(squeak_surf, (cx - squeak_surf.get_width()//2, cy - r - 28))





class PulseEffect:
    """Expanding ring visual when PulseSentinel fires its AoE pulse."""
    def __init__(self, x, y, radius):
        self.x = x; self.y = y; self.max_r = radius
        self.t = 0.0; self.life = 0.5
    def update(self, dt):
        self.t += dt
        return self.t < self.life
    def draw(self, surf):
        p = self.t / self.life
        r = int(p * self.max_r)
        alpha = int(200 * (1 - p))
        s = pygame.Surface((r*2+8, r*2+8), pygame.SRCALPHA)
        pygame.draw.circle(s, (80, 220, 255, alpha//2), (r+4, r+4), r)
        pygame.draw.circle(s, (180, 240, 255, alpha),   (r+4, r+4), r, 3)
        surf.blit(s, (int(self.x)-r-4, int(self.y)-r-4))


class ChainLightningEffect:
    """Zig-zag lightning bolt between two points."""
    def __init__(self, x1, y1, x2, y2):
        self.x1 = x1; self.y1 = y1; self.x2 = x2; self.y2 = y2
        self.t = 0.0; self.life = 0.25
        self._pts = self._gen()
    def _gen(self):
        pts = [(self.x1, self.y1)]
        segs = 6
        for i in range(1, segs):
            frac = i / segs
            mx = self.x1 + (self.x2 - self.x1) * frac
            my = self.y1 + (self.y2 - self.y1) * frac
            mx += random.randint(-12, 12)
            my += random.randint(-12, 12)
            pts.append((mx, my))
        pts.append((self.x2, self.y2))
        return pts
    def update(self, dt):
        self.t += dt
        if self.t > self.life * 0.4:
            self._pts = self._gen()
        return self.t < self.life
    def draw(self, surf):
        alpha = int(255 * (1 - self.t / self.life))
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for i in range(len(self._pts) - 1):
            pygame.draw.line(s, (120, 220, 255, alpha), self._pts[i], self._pts[i+1], 2)
            pygame.draw.line(s, (220, 250, 255, alpha//2), self._pts[i], self._pts[i+1], 4)
        surf.blit(s, (0, 0))


class PulseSentinel:
    """Floats above the path near Zigres. Every 3s fires an AoE electric pulse
    that slows and damages all enemies within 100px. Does NOT block enemies physically.
    Unlocked at Zigres Lv3."""
    RADIUS = 14
    PULSE_INTERVAL = 3.0
    PULSE_RADIUS = 100

    def __init__(self, x, y, hp, damage, owner=None, level=0):
        self.x = float(x); self.y = float(PATH_Y - 42)
        self.hp = hp; self.maxhp = hp
        self.damage = damage
        self.owner = owner
        self.level = level
        self.alive = True
        self._pulse_cd = self.PULSE_INTERVAL
        self._anim_t = 0.0
        self._orbit = 0.0
        self._pulse_flash = 0.0
        self._arrived = False
        self.WALK_SPEED = 140
        self._collided_enemies = set()
        self._beam_target = None
        self._last_hit_enemy = None
        self.hidden_detection = True
        self.thorns = False
        self.death_explode = False

    def _target_x(self):
        if self.owner is None:
            return SCREEN_W * 0.65
        pulse_sents = [s for s in self.owner._sentinels if isinstance(s, PulseSentinel) and s.alive]
        idx = next((i for i, s in enumerate(pulse_sents) if s is self), 0)
        return min(SCREEN_W - 80, self.owner.px + TILE * (2.5 + idx * 2.5))

    def update(self, dt, enemies, effects):
        if not self.alive: return
        self._anim_t += dt
        self._orbit  += dt * 130
        self._pulse_flash = max(0.0, self._pulse_flash - dt)
        tx = self._target_x()
        if abs(self.x - tx) > 4:
            self.x += (-1 if self.x > tx else 1) * self.WALK_SPEED * dt
        else:
            self._arrived = True
        self.y = PATH_Y - 42 + math.sin(self._anim_t * 2.2) * 5
        self._pulse_cd -= dt
        if self._pulse_cd <= 0 and self._arrived:
            self._pulse_cd = self.PULSE_INTERVAL
            self._pulse_flash = 0.4
            if effects is not None:
                effects.append(PulseEffect(self.x, self.y, self.PULSE_RADIUS))
            for e in enemies:
                if not e.alive: continue
                if math.hypot(e.x - self.x, e.y - self.y) < self.PULSE_RADIUS:
                    e.take_damage(self.damage)
                    e._slow_factor = min(e._slow_factor, 0.55)
                    self._last_hit_enemy = e

    def take_damage(self, dmg, attacker=None, effects=None):
        self.hp -= dmg
        if self.hp <= 0:
            self.alive = False
        return None

    def draw(self, surf, hovered=False):
        if not self.alive: return
        cx = int(self.x); cy = int(self.y)
        t = self._anim_t
        ring_s = pygame.Surface((self.PULSE_RADIUS*2+4, self.PULSE_RADIUS*2+4), pygame.SRCALPHA)
        pygame.draw.circle(ring_s, (80, 200, 255, 18),
                           (self.PULSE_RADIUS+2, self.PULSE_RADIUS+2), self.PULSE_RADIUS, 2)
        surf.blit(ring_s, (cx - self.PULSE_RADIUS - 2, cy - self.PULSE_RADIUS - 2))
        if self._pulse_flash > 0:
            gp = self._pulse_flash / 0.4
            gs = pygame.Surface((80, 80), pygame.SRCALPHA)
            pygame.draw.circle(gs, (100, 230, 255, int(180*gp)), (40, 40), int(20+gp*20))
            surf.blit(gs, (cx-40, cy-40))
        pygame.draw.ellipse(surf, (15, 20, 35), (cx-10, PATH_Y+PATH_H-6, 20, 6))
        for i in range(3):
            a = math.radians(self._orbit + i * 120)
            rx = cx + int(math.cos(a) * 14)
            ry = cy + int(math.sin(a) * 6)
            pygame.draw.circle(surf, (80, 200, 255), (rx, ry), 4)
            pygame.draw.circle(surf, (200, 240, 255), (rx, ry), 2)
        pygame.draw.circle(surf, (20, 40, 80),   (cx, cy), 14)
        pygame.draw.circle(surf, (40, 120, 200), (cx, cy), 10)
        pygame.draw.circle(surf, (120, 210, 255),(cx-3, cy-3), 5)
        pygame.draw.circle(surf, (180, 230, 255),(cx, cy), 14, 2)
        for i in range(4):
            a = math.radians(t * 200 + i * 90)
            sx2 = cx + int(math.cos(a) * 16)
            sy2 = cy + int(math.sin(a) * 16)
            pygame.draw.line(surf, (100, 220, 255), (cx, cy), (sx2, sy2), 1)
        bw = 36; bar_y = cy - 24
        pygame.draw.rect(surf, (20, 10, 10), (cx-bw//2, bar_y, bw, 5), border_radius=2)
        fill = max(0, int(bw * self.hp / self.maxhp))
        if fill:
            pygame.draw.rect(surf, (80, 200, 255), (cx-bw//2, bar_y, fill, 5), border_radius=2)
        pygame.draw.rect(surf, (80, 200, 255), (cx-bw//2, bar_y, bw, 5), 1, border_radius=2)
        if hovered:
            txt(surf, "Pulse Sentinel", (cx, cy-30), (80, 200, 255), font_sm, center=True)
            txt(surf, f"HP {int(self.hp)}/{int(self.maxhp)}", (cx, cy-46), C_WHITE, font_sm, center=True)


class ChainSentinel:
    """Stands on the road. On attack chains lightning to up to 3 enemies.
    Each hop deals 60% of previous. Unlocked at Zigres Lv5."""
    RADIUS = 16
    WALK_SPEED = 150
    CHAIN_RANGE = 130
    MAX_CHAINS = 3

    def __init__(self, x, y, hp, damage, owner=None, level=0):
        self.x = float(x); self.y = float(PATH_Y)
        self.hp = hp; self.maxhp = hp
        self.damage = damage
        self.owner = owner
        self.level = level
        self.alive = True
        self.firerate = 1.2
        self.cd_left = 0.0
        self._anim_t = 0.0
        self._arrived = False
        self._beam_target = None
        self._last_hit_enemy = None
        self._attack_anim = 0.0
        self._walk_phase = 0.0
        self._collided_enemies = set()
        self.hidden_detection = True
        self.thorns = False
        self.death_explode = False

    def _target_x(self):
        if self.owner is None:
            return SCREEN_W * 0.55
        chain_sents = [s for s in self.owner._sentinels if isinstance(s, ChainSentinel) and s.alive]
        idx = next((i for i, s in enumerate(chain_sents) if s is self), 0)
        return min(SCREEN_W - 60, self.owner.px + TILE * (4.0 + idx * 2.5))

    def update(self, dt, enemies, effects):
        if not self.alive: return
        self._anim_t += dt
        self._attack_anim = max(0.0, self._attack_anim - dt * 3.0)
        tx = self._target_x()
        if abs(self.x - tx) > 4:
            self.x += (-1 if self.x > tx else 1) * self.WALK_SPEED * dt
            if abs(self.x - tx) < self.WALK_SPEED * dt:
                self.x = tx; self._arrived = True
            self._walk_phase += dt * 10.0
        else:
            self._arrived = True
        if self.cd_left > 0: self.cd_left -= dt
        if self._arrived and self.cd_left <= 0:
            candidates = [e for e in enemies if e.alive and
                          (self.hidden_detection or not e.IS_HIDDEN) and
                          abs(e.x - self.x) < 3 * TILE]
            if candidates:
                candidates.sort(key=lambda e: e.x)
                first = candidates[0]
                self.cd_left = self.firerate
                self._attack_anim = 1.0
                self._beam_target = first
                self._last_hit_enemy = first
                hit = {id(first)}; cur = first
                chain_targets = [first]
                for _ in range(self.MAX_CHAINS - 1):
                    nexts = [e for e in enemies if e.alive and id(e) not in hit
                             and math.hypot(e.x - cur.x, e.y - cur.y) < self.CHAIN_RANGE]
                    if not nexts: break
                    nxt = min(nexts, key=lambda e: math.hypot(e.x - cur.x, e.y - cur.y))
                    hit.add(id(nxt)); chain_targets.append(nxt); cur = nxt
                for i, tgt in enumerate(chain_targets):
                    dmg = int(self.damage * (0.6 ** i))
                    tgt.take_damage(max(1, dmg))
                    if effects is not None and i > 0:
                        prev = chain_targets[i-1]
                        effects.append(ChainLightningEffect(
                            int(prev.x), int(prev.y), int(tgt.x), int(tgt.y)))

    def take_damage(self, dmg, attacker=None, effects=None):
        self.hp -= dmg
        if self.hp <= 0:
            self.alive = False
        return None

    def draw(self, surf, hovered=False):
        if not self.alive: return
        cx, cy = int(self.x), int(self.y)
        t = self._anim_t
        R = self.RADIUS
        sw = self._attack_anim
        if not self._arrived:
            cy += int(math.sin(self._walk_phase) * 3)
        pygame.draw.ellipse(surf, (15, 20, 35), (cx-R, cy+R-4, R*2, 8))
        if self._beam_target and self._beam_target.alive and sw > 0.3:
            bs = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(bs, (100, 220, 255, int(180*sw)),
                             (cx, cy), (int(self._beam_target.x), int(self._beam_target.y)), 2)
            surf.blit(bs, (0, 0))
        acc_col = (80, 255, 120)
        pygame.draw.circle(surf, (20, 60, 30),   (cx, cy), R)
        pygame.draw.circle(surf, (40, 140, 60),  (cx, cy-4), R-5)
        pygame.draw.circle(surf, acc_col,        (cx, cy), R, 2)
        bolt_pts = [(cx+3, cy-8), (cx-2, cy-1), (cx+2, cy-1), (cx-3, cy+8)]
        pygame.draw.lines(surf, (180, 255, 100), False, bolt_pts, 2)
        for i in range(2):
            a = math.radians(t * 280 + i * 180)
            sx2 = cx + int(math.cos(a) * (R + 6))
            sy2 = cy + int(math.sin(a) * (R + 6))
            pygame.draw.circle(surf, (120, 255, 150), (sx2, sy2), 3)
        if sw > 0.5:
            fs = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.circle(fs, (80, 255, 120, int(160*sw)), (30, 30), int(10+sw*14))
            surf.blit(fs, (cx-30, cy-30))
        bw = 36; bar_y = cy - R - 14
        pygame.draw.rect(surf, (20, 10, 10), (cx-bw//2, bar_y, bw, 5), border_radius=2)
        fill = max(0, int(bw * self.hp / self.maxhp))
        if fill:
            pygame.draw.rect(surf, (80, 255, 120), (cx-bw//2, bar_y, fill, 5), border_radius=2)
        pygame.draw.rect(surf, acc_col, (cx-bw//2, bar_y, bw, 5), 1, border_radius=2)
        if hovered:
            txt(surf, "Chain Sentinel", (cx, cy-R-22), acc_col, font_sm, center=True)
            txt(surf, f"HP {int(self.hp)}/{int(self.maxhp)}", (cx, cy-R-38), C_WHITE, font_sm, center=True)


class StaticSentinel:
    """A sentinel unit that walks in from the right and guards near its owner Zigres."""
    RADIUS = 18
    WALK_SPEED = 150  # px/s toward target position

    def __init__(self, x, y, hp, damage, thorns=False, death_explode=False, hidden_detection=False, owner=None, level=0):
        self.x = float(x); self.y = float(PATH_Y)
        self.hp = hp; self.maxhp = hp
        self.damage = damage
        self.thorns = thorns
        self.death_explode = death_explode
        self.hidden_detection = hidden_detection
        self.owner = owner        # Zigres tower reference
        self.level = level        # mirrors owner Zigres level for visuals
        # radius grows with level: 18 at lv0, up to 28 at lv5; Lv6 = COLOSSUS
        self.RADIUS = 58 if level >= 6 else (18 + level * 2)
        self.WALK_SPEED = 38 if level >= 6 else 150  # colossus lumbers slowly
        # Armor: 10% at Lv2-4, 15% at Lv5, 10% at Lv6
        if level == 5:
            self.armor = 0.15
        elif level in (2, 3, 4, 6):
            self.armor = 0.10
        else:
            self.armor = 0.0
        self.alive = True
        self.cd_left = 0.0
        self.firerate = 1.0
        self._anim_t = 0.0
        self._last_hit_enemy = None
        self._beam_target = None
        self._arrived = False     # True once sentinel reached its guard position
        self._collided_enemies = set()  # enemies already hit by collision (one-shot damage)
        self._attack_anim = 0.0   # 0..1 attack swing timer
        self._walk_phase = 0.0    # bob phase while walking

    def _target_x(self):
        """X position this sentinel should guard (near owner, spaced from siblings)."""
        if self.owner is None:
            return SCREEN_W * 0.7
        siblings = [s for s in self.owner._sentinels if s.alive and s is not self]
        # stand to the right of owner, spaced by 2 tiles per slot index
        idx = 0
        for i, s in enumerate(self.owner._sentinels):
            if s is self:
                idx = i
                break
        return min(SCREEN_W - 60, self.owner.px + TILE * (3.0 + idx * 2.5))

    def update(self, dt, enemies, effects):
        if not self.alive: return
        self._anim_t += dt

        # Walk toward guard position if not arrived
        target_x = self._target_x()
        if abs(self.x - target_x) > 4:
            direction = -1 if self.x > target_x else 1
            self.x += direction * self.WALK_SPEED * dt
            # snap when close
            if abs(self.x - target_x) < self.WALK_SPEED * dt:
                self.x = target_x
                self._arrived = True
        else:
            self._arrived = True

        # Collision damage: one-shot when enemy first touches sentinel
        # sentinel loses enemy's current hp, enemy loses sentinel's current hp
        still_touching = set()
        for e in enemies:
            if not e.alive: continue
            if abs(e.x - self.x) < self.RADIUS + e.radius:
                still_touching.add(id(e))
                if id(e) not in self._collided_enemies:
                    self._collided_enemies.add(id(e))
                    sentinel_dmg = e.hp          # страж теряет столько, сколько хп у врага
                    enemy_dmg    = self.hp        # враг теряет столько, сколько хп у стража
                    e.take_damage(enemy_dmg)
                    self.hp -= sentinel_dmg
                    if self.hp <= 0:
                        self.alive = False
                        if self.death_explode and effects is not None:
                            effects.append(SentinelDeathEffect(self.x, self.y))
                        return
        # clear ids of enemies that are no longer touching (so re-entry counts again)
        self._collided_enemies &= still_touching

        if self.cd_left > 0: self.cd_left -= dt

        # Attack nearest enemy within 2 tiles once arrived
        best = None; best_d = 999999
        for e in enemies:
            if not e.alive: continue
            if e.IS_HIDDEN and not self.hidden_detection: continue
            d = abs(e.x - self.x)
            if d < 2 * TILE and d < best_d:
                best_d = d; best = e

        self._beam_target = best
        if best and self.cd_left <= 0 and self._arrived:
            self.cd_left = self.firerate
            best.take_damage(self.damage)
            self._last_hit_enemy = best
            best._slow_factor = min(best._slow_factor, 0.9)
            if self.thorns:
                try_stun(best, 0.2)
            self._attack_anim = 1.0  # trigger swing animation

        # decay attack animation
        if self._attack_anim > 0:
            self._attack_anim = max(0.0, self._attack_anim - dt * 4.0)

        # walk bob
        if not self._arrived:
            self._walk_phase += dt * 10.0

    def take_damage(self, dmg, attacker=None, effects=None):
        self.hp -= dmg * (1.0 - self.armor)
        if self.thorns and attacker:
            attacker.take_damage(5)
        if self.hp <= 0:
            self.alive = False
            if self.death_explode and effects is not None:
                effects.append(SentinelDeathEffect(self.x, self.y))
                return "explode"
        return None

    def draw(self, surf, hovered=False):
        if not self.alive: return
        cx, cy = int(self.x), int(self.y)
        t = self._anim_t
        lv = self.level   # 0-5

        # ── per-level palette ──────────────────────────────────────────────────
        # cloak, plate, accent, crest, glow
        PALETTES = [
            ((30,  50, 100), (60, 100, 180), (80,  200, 255), (80,  200, 255), (80,  200, 255)),  # 0 blue
            ((35,  60,  80), (50, 120, 100), (80,  220, 180), (80,  220, 180), (80,  220, 180)),  # 1 teal
            ((60,  40,  80), (100, 60, 160), (180, 100, 255), (180, 100, 255), (180, 100, 255)),  # 2 purple
            ((70,  50,  20), (140, 100, 30), (255, 200,  50), (255, 200,  50), (255, 180,  40)),  # 3 gold
            ((80,  20,  20), (160,  40, 40), (255,  80,  60), (255, 200,  60), (255,  80,  60)),  # 4 red/fire
            ((20,  20,  20), ( 40,  40, 40), (200, 220, 255), (200, 220, 255), (200, 200, 255)),  # 5 dark steel
            ((10,  40,  10), ( 30, 100, 30), (80,  255, 100), (255, 255, 100), (80,  255, 100)),  # 6 colossus emerald
        ]
        cloak_col, plate_col, accent_col, crest_col, glow_col = PALETTES[min(lv, 6)]
        plate_hi = tuple(min(255, c + 60) for c in plate_col)
        R = self.RADIUS   # grows with level

        # walking bob
        walk_bob = int(math.sin(self._walk_phase) * 3) if not self._arrived else 0
        cy += walk_bob

        # attack animation
        sw = self._attack_anim
        sword_len = 24 + lv * 3
        swing_angle = math.radians(-120 + sw * 100)
        grip_x = cx + 13 + lv; grip_y = cy - 4
        gx = grip_x + int(math.cos(swing_angle) * 8)
        gy = grip_y + int(math.sin(swing_angle) * 8)
        sx_tip = grip_x + int(math.cos(swing_angle) * (sword_len + 8))
        sy_tip = grip_y + int(math.sin(swing_angle) * (sword_len + 8))

        # attack beam flash
        if self._beam_target and self._beam_target.alive and sw > 0.5:
            ex, ey = int(self._beam_target.x), int(self._beam_target.y)
            bsurf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(bsurf, (*accent_col, int(200 * sw)), (cx, cy), (ex, ey), 2)
            surf.blit(bsurf, (0, 0))

        # shadow (bigger at higher levels)
        pygame.draw.ellipse(surf, (15, 20, 35),
                            (cx - R, cy + R - 4, R * 2, 10 + lv))

        # ── Lv4+ fire aura behind body ────────────────────────────────────────
        if lv >= 4:
            for i in range(6):
                a = math.radians(i * 60 + t * 90)
                fr = 8 + int(abs(math.sin(t * 5 + i)) * 6)
                fx = cx + int(math.cos(a) * (R - 4))
                fy = cy + int(math.sin(a) * (R - 4))
                fs = pygame.Surface((fr * 2 + 4, fr * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(fs, (255, 100, 20, 80), (fr + 2, fr + 2), fr)
                surf.blit(fs, (fx - fr - 2, fy - fr - 2))

        # ── Lv5 dark energy rings ─────────────────────────────────────────────
        if lv >= 5:
            for i in range(2):
                ring_r = R + 8 + i * 6 + int(abs(math.sin(t * 3 + i)) * 4)
                rs = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(rs, (200, 220, 255, 40 - i * 10),
                                   (ring_r + 2, ring_r + 2), ring_r, 2)
                surf.blit(rs, (cx - ring_r - 2, cy - ring_r - 2))

        # thorns spikes (behind body, gold at lv4, fiery at lv4+)
        if self.thorns:
            spike_col = (255, 80, 30) if lv >= 4 else (255, 210, 60)
            tip_col   = (255, 160, 80) if lv >= 4 else (255, 240, 120)
            for i in range(6 + lv):
                a = math.radians(i * (360 / (6 + lv)) + t * 30)
                tx2 = cx + int(math.cos(a) * (R + 7))
                ty2 = cy + int(math.sin(a) * (R + 7))
                pygame.draw.line(surf, spike_col, (cx, cy), (tx2, ty2), 2)
                pygame.draw.circle(surf, tip_col, (tx2, ty2), 2)

        # cloak / base (scaled)
        pygame.draw.circle(surf, cloak_col, (cx, cy + 4), R - 2)
        pygame.draw.ellipse(surf, cloak_col, (cx - R, cy - 4, R * 2, R + 12))

        # torso plate
        pygame.draw.ellipse(surf, plate_col,
                            (cx - int(R * 0.55), cy - int(R * 0.55),
                             int(R * 1.1), int(R * 1.0)))
        pygame.draw.ellipse(surf, plate_hi,
                            (cx - int(R * 0.3), cy - int(R * 0.45),
                             int(R * 0.5), int(R * 0.35)))

        # ── Lv3+ extra decorative runes on chest ──────────────────────────────
        if lv >= 3:
            for i in range(lv - 1):
                a = math.radians(i * (360 / max(1, lv - 1)) + t * 20)
                rx = cx + int(math.cos(a) * int(R * 0.4))
                ry = cy + int(math.sin(a) * int(R * 0.4))
                pygame.draw.circle(surf, accent_col, (rx, ry), 3)

        # shoulders (bigger with level)
        sho_r = 7 + lv
        pygame.draw.circle(surf, tuple(max(0,c-20) for c in plate_col), (cx - R + 4, cy - 6), sho_r)
        pygame.draw.circle(surf, tuple(max(0,c-20) for c in plate_col), (cx + R - 4, cy - 6), sho_r)
        pygame.draw.circle(surf, plate_hi, (cx - R + 4, cy - 8), sho_r // 2 + 1)
        pygame.draw.circle(surf, plate_hi, (cx + R - 4, cy - 8), sho_r // 2 + 1)

        # shield (left, grows and changes with level)
        sh_w = 12 + lv * 2; sh_h = 24 + lv * 2
        sh_x = cx - R - 4
        sh_pts = [
            (sh_x,        cy - sh_h // 2),
            (sh_x + sh_w, cy - sh_h // 2),
            (sh_x + sh_w, cy + sh_h // 4),
            (sh_x + sh_w // 2, cy + sh_h // 2),
            (sh_x,        cy + sh_h // 4),
        ]
        sh_col = tuple(max(0, c - 30) for c in plate_col)
        pygame.draw.polygon(surf, sh_col, sh_pts)
        pygame.draw.polygon(surf, accent_col, sh_pts, 2)
        mid_x = sh_x + sh_w // 2
        pygame.draw.line(surf, accent_col, (mid_x, cy - sh_h // 2), (mid_x, cy + sh_h // 2), 1)
        pygame.draw.line(surf, accent_col, (sh_x, cy), (sh_x + sh_w, cy), 1)
        # Lv2+ glowing shield gem
        if lv >= 2:
            pygame.draw.circle(surf, accent_col, (mid_x, cy), 4)
            pygame.draw.circle(surf, (255, 255, 255), (mid_x, cy), 2)

        # helmet (taller/more ornate with level)
        helm_r = 11 + lv
        pygame.draw.circle(surf, plate_col, (cx, cy - R + 4), helm_r)
        # visor slit
        visor_col = accent_col
        pygame.draw.rect(surf, visor_col,
                         (cx - helm_r + 2, cy - R + 1, (helm_r - 2) * 2, 4 + lv // 2),
                         border_radius=2)
        pygame.draw.rect(surf, tuple(min(255, c + 60) for c in accent_col),
                         (cx - helm_r + 2, cy - R + 1, (helm_r - 2) * 2, 4 + lv // 2),
                         1, border_radius=2)
        # crest — changes by level
        if lv <= 1:
            # simple spike
            pygame.draw.line(surf, crest_col, (cx, cy - R - 8), (cx, cy - R + 4), 3)
            pygame.draw.circle(surf, crest_col, (cx, cy - R - 9), 3)
        elif lv == 2:
            # double spike
            for ox in (-4, 4):
                pygame.draw.line(surf, crest_col, (cx + ox, cy - R - 8), (cx + ox, cy - R + 4), 2)
            pygame.draw.line(surf, crest_col, (cx, cy - R - 12), (cx, cy - R + 4), 3)
        elif lv == 3:
            # triple crown-like
            for ox in (-6, 0, 6):
                h = 14 if ox == 0 else 10
                pygame.draw.line(surf, crest_col, (cx + ox, cy - R - h), (cx + ox, cy - R + 2), 3)
                pygame.draw.circle(surf, crest_col, (cx + ox, cy - R - h), 3)
        elif lv == 4:
            # fire crest
            for ox in (-5, 0, 5):
                h = 16 if ox == 0 else 11
                pygame.draw.line(surf, (255, 180, 40), (cx + ox, cy - R - h), (cx + ox, cy - R + 2), 3)
                pygame.draw.circle(surf, (255, 230, 100), (cx + ox, cy - R - h), 3)
        else:
            # lv5: dark star crown
            for i in range(5):
                a = math.radians(-90 + i * 72)
                px2 = cx + int(math.cos(a) * 10)
                py2 = (cy - R - 8) + int(math.sin(a) * 10)
                pygame.draw.line(surf, crest_col, (cx, cy - R), (px2, py2), 2)
                pygame.draw.circle(surf, crest_col, (px2, py2), 3)
        if lv >= 6:
            # lv6 COLOSSUS: massive pulsing halo + rubber duck badge
            halo_r = R + 18 + int(abs(math.sin(t * 2)) * 6)
            hs = pygame.Surface((halo_r*2+8, halo_r*2+8), pygame.SRCALPHA)
            pulse_a = int(60 + abs(math.sin(t * 3)) * 60)
            pygame.draw.circle(hs, (80, 255, 100, pulse_a), (halo_r+4, halo_r+4), halo_r, 5)
            surf.blit(hs, (cx - halo_r - 4, cy - halo_r - 4))
            # tiny duck icon on shield
            duck_x = int(cx - R - 4 + (12 + lv*2)//2)
            pygame.draw.circle(surf, (255, 220, 0), (duck_x, cy), 5)
            pygame.draw.circle(surf, (255, 200, 0), (duck_x + 4, cy - 4), 3)
            pygame.draw.line(surf, (255, 140, 20), (duck_x + 6, cy - 4), (duck_x + 10, cy - 3), 2)

        # ── sword ─────────────────────────────────────────────────────────────
        blade_col = (200, 230, 255) if sw < 0.1 else (255, 255, 180)
        # Lv3+ golden blade, Lv4+ fiery, Lv5 dark
        if lv >= 5:   blade_col = (180, 200, 255) if sw < 0.1 else (220, 240, 255)
        elif lv >= 4: blade_col = (255, 160,  60) if sw < 0.1 else (255, 220, 100)
        elif lv >= 3: blade_col = (255, 210,  80) if sw < 0.1 else (255, 240, 140)
        blade_w = 3 + lv // 2

        # grip
        pygame.draw.line(surf, (100, 70, 40),
                         (grip_x, grip_y),
                         (grip_x + int(math.cos(swing_angle - math.pi) * 10),
                          grip_y + int(math.sin(swing_angle - math.pi) * 10)), 3)
        # guard
        perp = swing_angle + math.pi / 2
        guard_len = 7 + lv
        pygame.draw.line(surf, accent_col,
                         (gx + int(math.cos(perp) * guard_len), gy + int(math.sin(perp) * guard_len)),
                         (gx - int(math.cos(perp) * guard_len), gy - int(math.sin(perp) * guard_len)), 2)
        # blade
        pygame.draw.line(surf, blade_col, (gx, gy), (sx_tip, sy_tip), blade_w)
        pygame.draw.circle(surf, (240, 250, 255), (sx_tip, sy_tip), 2)

        # swing trail
        if sw > 0.2:
            trail_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            for ti in range(5 + lv):
                trail_sw = sw - ti * 0.10
                if trail_sw <= 0: break
                ta = math.radians(-120 + trail_sw * 100)
                ttx = grip_x + int(math.cos(ta) * (sword_len + 8))
                tty = grip_y + int(math.sin(ta) * (sword_len + 8))
                talpha = max(0, int(140 * (sw - ti * 0.12)))
                pygame.draw.line(trail_surf, (*accent_col, talpha),
                                 (grip_x, grip_y), (ttx, tty), max(1, blade_w - ti // 2))
            surf.blit(trail_surf, (0, 0))

        # electric glow ring
        glow_alpha = int(40 + abs(math.sin(t * 4)) * 30)
        gs_size = (R + 10) * 2 + 4
        gs = pygame.Surface((gs_size, gs_size), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*glow_col, glow_alpha),
                           (gs_size // 2, gs_size // 2), R + 8)
        surf.blit(gs, (cx - gs_size // 2, cy - gs_size // 2))

        # HP bar
        bw = 44 + lv * 4 if not hovered else 70 + lv * 4
        bh = 6 if not hovered else 10
        bar_y = cy - R - 16
        pygame.draw.rect(surf, (30, 15, 15), (cx - bw//2, bar_y, bw, bh), border_radius=2)
        fill = max(0, int(bw * self.hp / self.maxhp))
        if fill:
            col = accent_col if self.hp / self.maxhp > 0.5 else (255, 100, 60)
            pygame.draw.rect(surf, col, (cx - bw//2, bar_y, fill, bh), border_radius=2)
        pygame.draw.rect(surf, accent_col, (cx - bw//2, bar_y, bw, bh), 1, border_radius=2)

        if hovered:
            txt(surf, f"Sentinel Lv{lv}",
                (cx, cy - R - 32), accent_col, font_sm, center=True)
            txt(surf, f"HP {int(self.hp)}/{int(self.maxhp)}",
                (cx, cy - R - 54), C_WHITE, font_sm, center=True)
            if self.armor > 0:
                armor_col = (255, 200, 50) if self.armor >= 0.15 else (180, 200, 220)
                txt(surf, f"Armor {int(self.armor*100)}%",
                    (cx, cy - R - 76), armor_col, font_sm, center=True)


class Zigres(Unit):
    PLACE_COST = 3000
    COLOR = C_ZIGRES
    NAME = "Zigres"
    _PLACE_LIMIT = 4

    def __init__(self, px, py):
        super().__init__(px, py)
        self._sentinels = []
        self._anim_t = 0.0
        self._beam_targets = []
        self._beam_last_target = None   # persists during flash animation
        self._spawn_timer = 0.0   # 0 = spawn immediately on first update
        self._SPAWN_INTERVAL = 25.0
        self._beam_flash = 0.0    # attack flash animation timer
        self._duck_timer = 0.0    # Lv6: rubber duck throw cooldown
        self._DUCK_INTERVAL = 7.0
        self._apply_level()

    def _apply_level(self):
        cfg = ZIGRES_LEVELS[self.level]
        self.damage, self.firerate, self.range_tiles = cfg[0], cfg[1], cfg[2]
        self._sent_hp   = cfg[3]
        self._sent_dmg  = cfg[4]
        self.hidden_detection = (self.level >= 2)
        self._resonance   = (self.level >= 3)
        self._thorns      = (self.level >= 4)
        self._death_explode = (self.level >= 5)
        self._colossus    = (self.level >= 6)   # Lv6: giant sentinel + duck throw
        if self.level <= 2:
            self._SPAWN_INTERVAL = 30.0
        elif self.level <= 4:
            self._SPAWN_INTERVAL = 45.0
        elif self.level == 5:
            self._SPAWN_INTERVAL = 50.0
        else:  # level 6
            self._SPAWN_INTERVAL = 75.0
        # update existing sentinels' stats and visuals
        for s in self._sentinels:
            s.damage  = self._sent_dmg
            s.thorns  = self._thorns
            s.death_explode = self._death_explode
            s.hidden_detection = self.hidden_detection
            # update armor based on new level
            if self.level == 5:
                s.armor = 0.15
            elif self.level in (2, 3, 4, 6):
                s.armor = 0.10
            else:
                s.armor = 0.0

    def upgrade_cost(self):
        if self.level >= len(ZIGRES_LEVELS) - 1: return None
        return ZIGRES_LEVELS[self.level + 1][5]

    def upgrade(self):
        if self.level < len(ZIGRES_LEVELS) - 1:
            cost = ZIGRES_LEVELS[self.level + 1][5] or 0
            self.level += 1
            self._apply_level()
            self._total_spent += cost

    def _spawn_sentinel(self):
        """Spawn a sentinel that walks in from the right side (opposite to enemies)."""
        s = StaticSentinel(
            SCREEN_W + 40, PATH_Y,
            self._sent_hp, self._sent_dmg,
            thorns=self._thorns,
            death_explode=self._death_explode,
            hidden_detection=self.hidden_detection,
            owner=self,
            level=self.level,
        )
        self._sentinels.append(s)

    def update(self, dt, enemies, effects, money):
        self._anim_t += dt
        if self.cd_left > 0: self.cd_left -= dt
        if self._beam_flash > 0: self._beam_flash -= dt

        # Sentinel spawn timer — unlimited sentinels, one every 25s
        self._spawn_timer -= dt
        if self._spawn_timer <= 0:
            self._spawn_sentinel()
            self._spawn_timer = self._SPAWN_INTERVAL

        # Lv6: Rubber Duck throw every 5 seconds — the Colossus Guardian hurls a giant duck
        if self._colossus:
            self._duck_timer -= dt
            if self._duck_timer <= 0:
                self._duck_timer = self._DUCK_INTERVAL
                live_enemies = [e for e in enemies if e.alive]
                if live_enemies:
                    # sentinel closest to path throws the duck (or tower itself)
                    throw_x = self._sentinels[0].x if self._sentinels else self.px
                    throw_y = PATH_Y - 10
                    effects.append(RubberDuckEffect(throw_x, throw_y, enemies))

        # Remove dead sentinels (trigger death explosion first)
        for s in self._sentinels:
            if not s.alive and s.death_explode:
                effects.append(SentinelDeathEffect(s.x, s.y))
                for e in enemies:
                    if e.alive and dist((e.x, e.y), (s.x, s.y)) < 100:
                        e.take_damage(200)
                        try_stun(e, 2.0)
        self._sentinels = [s for s in self._sentinels if s.alive]



        # Update sentinels; track who they hit
        sentinel_hit_ids = set()
        for s in self._sentinels:
            s.update(dt, enemies, effects)
            if s._last_hit_enemy and s._last_hit_enemy.alive:
                sentinel_hit_ids.add(id(s._last_hit_enemy))

        # Tower beam attack
        self._beam_targets = []
        if self.cd_left <= 0:
            targets = self._get_rightmost(enemies, 1)
            if targets:
                tgt = targets[0]
                self.cd_left = self.firerate
                tgt.take_damage(self.damage)
                self._beam_targets = [tgt]
                self._beam_last_target = tgt
                self._beam_flash = 0.35  # longer flash so animation is visible

                # Resonance: same enemy hit by both beam and sentinel → AoE flash
                if self._resonance and id(tgt) in sentinel_hit_ids:
                    effects.append(ZigresResonanceEffect(tgt.x, tgt.y))
                    for e in enemies:
                        if e.alive and dist((e.x, e.y), (tgt.x, tgt.y)) < 80:
                            e._slow_factor = min(e._slow_factor, 0.9)

    def draw(self, surf):
        cx, cy = int(self.px), int(self.py)
        t = self._anim_t
        mx, my = pygame.mouse.get_pos()

        # draw sentinels first (behind tower)
        for s in self._sentinels:
            hovered = dist((s.x, s.y), (mx, my)) < s.RADIUS + 8
            s.draw(surf, hovered=hovered)

        # energy beam from tower to each sentinel
        for s in self._sentinels:
            if not s.alive: continue
            alpha = int(100 + abs(math.sin(t * 5)) * 80)
            beam_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(beam_s, (180, 100, 255, alpha),
                             (cx, cy), (int(s.x), int(s.y)), 2)
            surf.blit(beam_s, (0, 0))

        # beam to current target — with flash animation
        flash_tgt = self._beam_last_target if self._beam_flash > 0 else None
        if flash_tgt and flash_tgt.alive:
            beam_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            flash_ratio = self._beam_flash / 0.35
            beam_alpha = int(200 * flash_ratio)
            beam_w = max(2, int(5 * flash_ratio))
            ex2, ey2 = int(flash_tgt.x), int(flash_tgt.y)
            pygame.draw.line(beam_s, (255, 180, 255, beam_alpha), (cx, cy), (ex2, ey2), beam_w)
            steps = 8
            pts = [(cx, cy)]
            for k in range(1, steps):
                frac = k / steps
                mx2 = cx + (ex2 - cx) * frac
                my2 = cy + (ey2 - cy) * frac
                perp_x = -(ey2 - cy); perp_y = (ex2 - cx)
                plen = math.hypot(perp_x, perp_y) or 1
                off = (random.random() - 0.5) * 28 * flash_ratio
                pts.append((int(mx2 + perp_x / plen * off),
                            int(my2 + perp_y / plen * off)))
            pts.append((ex2, ey2))
            pygame.draw.lines(beam_s, (255, 200, 255, int(200 * flash_ratio)), False, pts, 2)
            impact_r = int(18 * flash_ratio)
            if impact_r > 0:
                pygame.draw.circle(beam_s, (255, 200, 255, int(180 * flash_ratio)), (ex2, ey2), impact_r)
            surf.blit(beam_s, (0, 0))

        # ── LUNTIK TOWER DRAWING ───────────────────────────────────────────────
        bob = int(math.sin(t * 2.5) * 3)   # gentle breathing bob
        by = cy + bob                        # body Y with bob

        # Luntik colours
        C_LUNT_BODY   = (180, 100, 220)   # main purple
        C_LUNT_BELLY  = (230, 180, 255)   # light belly
        C_LUNT_EAR    = (200, 120, 240)   # ear purple
        C_LUNT_INNER  = (255, 180, 220)   # inner ear pink
        C_LUNT_DARK   = (120,  50, 160)   # outline/dark
        C_LUNT_EYE    = (30,   20,  50)   # eye
        C_LUNT_NOSE   = (255, 160, 180)   # nose
        C_LUNT_CHEEK  = (255, 180, 200)   # cheek blush

        # ── glow aura (pulsing purple) ─────────────────────────────────────────
        pulse = int(abs(math.sin(t * 3)) * 8)
        flash_boost = 12 if self._beam_flash > 0 else 0
        glow_r = 46 + pulse + flash_boost
        gs = pygame.Surface((glow_r*2+4, glow_r*2+4), pygame.SRCALPHA)
        glow_a = 80 if self._beam_flash > 0 else 35
        pygame.draw.circle(gs, (200, 120, 255, glow_a), (glow_r+2, glow_r+2), glow_r)
        surf.blit(gs, (cx - glow_r - 2, by - glow_r - 2))

        # ── EARS (drawn behind body) ───────────────────────────────────────────
        ear_wobble = int(math.sin(t * 3.5) * 4)
        # left ear — big rounded ear
        le_cx = cx - 20; le_ty = by - 54 + ear_wobble
        pygame.draw.ellipse(surf, C_LUNT_DARK,
                            (le_cx - 14, le_ty - 2, 26, 38))
        pygame.draw.ellipse(surf, C_LUNT_EAR,
                            (le_cx - 12, le_ty, 22, 34))
        pygame.draw.ellipse(surf, C_LUNT_INNER,
                            (le_cx - 7,  le_ty + 5, 12, 20))
        # right ear
        re_cx = cx + 20; re_ty = by - 52 - ear_wobble
        pygame.draw.ellipse(surf, C_LUNT_DARK,
                            (re_cx - 12, re_ty - 2, 26, 38))
        pygame.draw.ellipse(surf, C_LUNT_EAR,
                            (re_cx - 10, re_ty, 22, 34))
        pygame.draw.ellipse(surf, C_LUNT_INNER,
                            (re_cx - 5,  re_ty + 5, 12, 20))

        # ── rotating magic orbs around body ───────────────────────────────────
        orb_col = (220, 160, 255) if self._beam_flash == 0 else (255, 220, 255)
        for i in range(3 + self.level):
            a = math.radians(t * 100 + i * (360 / (3 + self.level)))
            ox2 = cx + int(math.cos(a) * 28)
            oy2 = by + int(math.sin(a) * 14)
            pygame.draw.circle(surf, orb_col, (ox2, oy2), 4)
            pygame.draw.circle(surf, (255, 255, 255), (ox2, oy2), 2)

        # ── BODY ──────────────────────────────────────────────────────────────
        # main round body
        pygame.draw.circle(surf, C_LUNT_DARK, (cx, by + 2), 33)   # shadow outline
        pygame.draw.circle(surf, C_LUNT_BODY, (cx, by),     31)
        # belly (lighter oval)
        pygame.draw.ellipse(surf, C_LUNT_BELLY,
                            (cx - 14, by - 10, 28, 26))

        # ── FACE ──────────────────────────────────────────────────────────────
        # head is the upper part of the body circle, draw face features
        face_y = by - 8  # face centre

        # eyes — big cute round eyes
        eye_blink = abs(math.sin(t * 0.8)) > 0.92  # occasional blink
        eye_h = 2 if eye_blink else 6
        # left eye
        pygame.draw.ellipse(surf, C_LUNT_EYE,  (cx - 14, face_y - eye_h//2, 10, eye_h + 2))
        if not eye_blink:
            pygame.draw.circle(surf, (255, 255, 255), (cx - 11, face_y - 2), 2)  # shine
        # right eye
        pygame.draw.ellipse(surf, C_LUNT_EYE,  (cx + 4,  face_y - eye_h//2, 10, eye_h + 2))
        if not eye_blink:
            pygame.draw.circle(surf, (255, 255, 255), (cx + 7,  face_y - 2), 2)

        # nose — small pink dot
        pygame.draw.circle(surf, C_LUNT_NOSE, (cx, face_y + 5), 4)
        pygame.draw.circle(surf, (255, 220, 230), (cx - 1, face_y + 4), 2)

        # mouth — little smile curve
        smile_pts = [(cx - 7, face_y + 10),
                     (cx,     face_y + 14),
                     (cx + 7, face_y + 10)]
        pygame.draw.lines(surf, C_LUNT_DARK, False, smile_pts, 2)

        # cheek blush circles
        blush_a = 120
        bs = pygame.Surface((18, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(bs, (*C_LUNT_CHEEK, blush_a), (0, 0, 18, 10))
        surf.blit(bs, (cx - 22, face_y + 6))
        surf.blit(bs, (cx + 4,  face_y + 6))

        # ── antennae / magic feelers ───────────────────────────────────────────
        ant_wobble = math.sin(t * 4) * 6
        # left antennae
        pygame.draw.line(surf, C_LUNT_DARK,
                         (cx - 8, by - 29),
                         (cx - 18 + int(ant_wobble), by - 48), 2)
        pygame.draw.circle(surf, (255, 200, 80),
                           (cx - 18 + int(ant_wobble), by - 48), 4)
        # right antennae
        pygame.draw.line(surf, C_LUNT_DARK,
                         (cx + 8, by - 29),
                         (cx + 18 - int(ant_wobble), by - 48), 2)
        pygame.draw.circle(surf, (255, 200, 80),
                           (cx + 18 - int(ant_wobble), by - 48), 4)

        # ── hidden detection indicator ─────────────────────────────────────────
        if self.hidden_detection:
            pygame.draw.circle(surf, (100, 255, 100), (cx + 30, by - 30), 7)
            pygame.draw.circle(surf, (200, 255, 200), (cx + 30, by - 30), 4)

        # ── level pips ────────────────────────────────────────────────────────
        for i in range(self.level):
            pip_col = (255, 220, 80) if i < 5 else (255, 100, 200)
            pygame.draw.circle(surf, pip_col,
                               (cx - 10 + i * 7, by + 32), 3)

        # ── spawn timer arc ────────────────────────────────────────────────────
        timer_ratio = max(0, 1.0 - self._spawn_timer / self._SPAWN_INTERVAL)
        if timer_ratio < 1.0:
            arc_rect = pygame.Rect(cx - 36, by - 36, 72, 72)
            try:
                pygame.draw.arc(surf, (200, 120, 255), arc_rect,
                                math.pi / 2,
                                math.pi / 2 + math.tau * timer_ratio, 3)
            except Exception:
                pass

    def draw_range(self, surf):
        r = int(self.range_tiles * TILE)
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*C_ZIGRES, 20), (r, r), r)
        pygame.draw.circle(s, (*C_ZIGRES, 70), (r, r), r, 2)
        surf.blit(s, (int(self.px)-r, int(self.py)-r))
        # also show sentinel attack rings
        for snt in self._sentinels:
            if snt.alive:
                sr = int(2 * TILE)
                ss = pygame.Surface((sr*2, sr*2), pygame.SRCALPHA)
                pygame.draw.circle(ss, (80, 200, 255, 15), (sr, sr), sr)
                pygame.draw.circle(ss, (80, 200, 255, 50), (sr, sr), sr, 1)
                surf.blit(ss, (int(snt.x)-sr, int(snt.y)-sr))

    def get_info(self):
        cd = max(0, self._spawn_timer)
        info = {
            "Damage":    self.damage,
            "Range":     self.range_tiles,
            "Firerate":  f"{self.firerate:.1f}",
            "Sentinels": f"{len(self._sentinels)}  (next {cd:.0f}s)",
        }
        if self._colossus:
            duck_cd = max(0.0, self._duck_timer)
            info["Duck"] = f"next {duck_cd:.0f}s"
        return info

    def get_next_info(self):
        nl = self.level + 1
        if nl >= len(ZIGRES_LEVELS): return None
        cfg = ZIGRES_LEVELS[nl]
        info = {
            "Damage":    cfg[0],
            "Range":     cfg[2],
            "Firerate":  f"{cfg[1]:.1f}",
            "Sentinels": f"HP {cfg[3]}",
        }
        if nl >= 6:
            info["Duck"] = "every 5s!"
        return info


# ── Gunner ─────────────────────────────────────────────────────────────────────
# Простая пушечная башня — доступна только через Shop за монеты
C_GUNNER = (220, 140, 40)   # оранжево-золотой

GUNNER_LEVELS = [
    {"dmg": 14, "fr": 0.92,  "rng": 5.5, "cost": None},   # 0 base  (нерф: 18→14, fr 0.85→0.92)
    {"dmg": 20, "fr": 0.82,  "rng": 6.0, "cost": 500},    # 1       (нерф: 26→20)
    {"dmg": 30, "fr": 0.70,  "rng": 6.5, "cost": 1100},   # 2       (нерф: 38→30)
    {"dmg": 44, "fr": 0.60,  "rng": 7.0, "cost": 2500},   # 3       (нерф: 55→44)
    {"dmg": 62, "fr": 0.46,  "rng": 7.5, "cost": 5000},   # 4  max  (нерф: 80→62)
]

GUNNER_SHOP_PRICE = 600   # цена покупки в Shop за shop_coins

class Gunner(Unit):
    PLACE_COST = 600
    COLOR = C_GUNNER
    NAME = "Gunner"
    hidden_detection = False

    def __init__(self, px, py):
        super().__init__(px, py)
        self._barrel_angle = 0.0
        self._fire_t = 0.0
        self._anim_t = 0.0
        self._muzzle_flash = 0.0
        self._apply_level()

    def _apply_level(self):
        cfg = GUNNER_LEVELS[self.level]
        self.damage = cfg["dmg"]
        self.firerate = cfg["fr"]
        self.range_tiles = cfg["rng"]

    def upgrade_cost(self):
        nl = self.level + 1
        if nl >= len(GUNNER_LEVELS): return None
        return GUNNER_LEVELS[nl]["cost"]

    def upgrade(self):
        nl = self.level + 1
        if nl < len(GUNNER_LEVELS):
            cost = GUNNER_LEVELS[nl]["cost"] or 0
            self.level = nl
            self._apply_level()
            self._total_spent += cost

    def update(self, dt, enemies, effects, money):
        self._anim_t += dt
        self._muzzle_flash = max(0.0, self._muzzle_flash - dt)
        if self.cd_left > 0: self.cd_left -= dt
        self._try_attack(enemies, effects)

    def _try_attack(self, enemies, effects):
        if self.cd_left > 0: return
        t = self._get_rightmost(enemies, 1)
        if t:
            self.cd_left = self.firerate
            t[0].take_damage(self.damage)
            dx = t[0].x - self.px; dy = t[0].y - self.py
            self._barrel_angle = math.degrees(math.atan2(dy, dx))
            self._muzzle_flash = 0.18
            # bullet trail effect
            effects.append(GunnerBulletEffect(self.px, self.py, t[0].x, t[0].y))

    def draw(self, surf):
        cx, cy = int(self.px), int(self.py)
        t = self._anim_t

        # shadow
        pygame.draw.ellipse(surf, (20, 12, 5), (cx - 24, cy + 20, 48, 14))

        # base platform
        pygame.draw.ellipse(surf, (60, 40, 15), (cx - 26, cy + 10, 52, 18))
        pygame.draw.ellipse(surf, (90, 65, 25), (cx - 24, cy + 10, 48, 14))

        # rotating turret base
        pygame.draw.circle(surf, (50, 35, 12), (cx, cy), 28)
        pygame.draw.circle(surf, (110, 80, 30), (cx, cy), 24)
        # rivets
        for i in range(6):
            a = math.radians(i * 60 + t * 20)
            rx = cx + int(math.cos(a) * 20)
            ry = cy + int(math.sin(a) * 20)
            pygame.draw.circle(surf, (160, 120, 50), (rx, ry), 3)
            pygame.draw.circle(surf, (200, 170, 80), (rx, ry), 1)

        # barrel (rotates toward last target)
        ang_r = math.radians(self._barrel_angle)
        barrel_len = 28
        barrel_end_x = cx + int(math.cos(ang_r) * barrel_len)
        barrel_end_y = cy + int(math.sin(ang_r) * barrel_len)
        perp_x = -math.sin(ang_r) * 5
        perp_y =  math.cos(ang_r) * 5
        pts = [
            (cx + int(perp_x * 1.6), cy + int(perp_y * 1.6)),
            (cx - int(perp_x * 1.6), cy - int(perp_y * 1.6)),
            (barrel_end_x - int(perp_x), barrel_end_y - int(perp_y)),
            (barrel_end_x + int(perp_x), barrel_end_y + int(perp_y)),
        ]
        pygame.draw.polygon(surf, (70, 50, 18), pts)
        pygame.draw.polygon(surf, (140, 105, 45), pts, 2)
        # barrel ring
        mid_x = cx + int(math.cos(ang_r) * 14)
        mid_y = cy + int(math.sin(ang_r) * 14)
        pygame.draw.circle(surf, (160, 120, 50), (mid_x, mid_y), 6)
        pygame.draw.circle(surf, (200, 160, 70), (mid_x, mid_y), 4)

        # muzzle flash
        if self._muzzle_flash > 0:
            frac = self._muzzle_flash / 0.18
            fs = pygame.Surface((50, 50), pygame.SRCALPHA)
            pygame.draw.circle(fs, (255, 220, 80, int(200 * frac)), (25, 25), int(10 * frac + 4))
            pygame.draw.circle(fs, (255, 255, 180, int(255 * frac)), (25, 25), int(5 * frac + 2))
            surf.blit(fs, (barrel_end_x - 25, barrel_end_y - 25))

        # turret top dome
        pygame.draw.circle(surf, (90, 65, 25), (cx, cy), 14)
        pygame.draw.circle(surf, (200, 160, 70), (cx - 4, cy - 4), 6)

        # level pips
        for i in range(self.level):
            pygame.draw.circle(surf, C_GOLD, (cx - 8 + i * 7, cy + 30), 3)

    def get_info(self):
        return {"Damage": self.damage, "Range": self.range_tiles,
                "Firerate": f"{self.firerate:.2f}"}

    def get_next_info(self):
        nl = self.level + 1
        if nl >= len(GUNNER_LEVELS): return None
        cfg = GUNNER_LEVELS[nl]
        return {"Damage": cfg["dmg"], "Range": cfg["rng"],
                "Firerate": f"{cfg['fr']:.2f}"}


class GunnerBulletEffect:
    """Short tracer line from tower to target."""
    def __init__(self, ox, oy, tx, ty):
        self.ox = ox; self.oy = oy; self.tx = tx; self.ty = ty
        self.life = 0.08; self.t = 0.0

    def update(self, dt):
        self.t += dt
        return self.t < self.life

    def draw(self, surf):
        frac = 1.0 - self.t / self.life
        a = int(200 * frac)
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        pygame.draw.line(s, (255, 220, 80, a), (int(self.ox), int(self.oy)),
                         (int(self.tx), int(self.ty)), 3)
        pygame.draw.line(s, (255, 255, 200, min(255, a + 55)), (int(self.ox), int(self.oy)),
                         (int(self.tx), int(self.ty)), 1)
        surf.blit(s, (0, 0))


# ── UI ─────────────────────────────────────────────────────────────────────────
class UI:
    SLOT_TYPES=[Assassin,Accelerator,Clown,Archer,Zigres]
    def __init__(self):
        self.slots=self._build_slots(); self.selected_slot=None
        self.drag_unit=None; self.open_unit=None; self.msg=""; self.msg_timer=0.0
    def _build_slots(self):
        slots=[]; gap=(SCREEN_W-5*SLOT_W)//6
        for i in range(5): slots.append(pygame.Rect(gap+i*(SLOT_W+gap),SLOT_AREA_Y+10,SLOT_W,SLOT_H))
        return slots
    def show_msg(self,text,dur=2.0): self.msg=text; self.msg_timer=dur
    def update(self,dt):
        if self.msg_timer>0: self.msg_timer-=dt

    def handle_click(self,pos,units,money,effects,enemies):
        for u in units:
            btn=getattr(u,'_ability_btn_rect',None)
            if btn and btn.collidepoint(pos):
                if u.ability and u.ability.ready(): u.ability.activate(enemies,effects)
                return 0
        if self.open_unit:
            menu,btns=self._menu_rects(self.open_unit)
            if btns.get("close") and btns["close"].collidepoint(pos): self.open_unit=None; return 0
            if btns.get("sell") and btns["sell"].collidepoint(pos):
                refund=self.sell_unit(self.open_unit,units)
                self.show_msg(f"+{refund} Sold!",2.0); return refund
            if btns.get("upgrade") and btns["upgrade"].collidepoint(pos):
                cost=self.open_unit.upgrade_cost()
                if cost and money>=cost: self.open_unit.upgrade(); return -cost
                self.show_msg("Not enough money!" if cost else "Max level!"); return 0
            if btns.get("ability") and btns["ability"].collidepoint(pos):
                if self.open_unit.ability and self.open_unit.ability.ready():
                    self.open_unit.ability.activate(enemies,effects)
                return 0
            if btns.get("archer_arrow") and btns["archer_arrow"].collidepoint(pos):
                if isinstance(self.open_unit, Archer):
                    self.open_unit.cycle_arrow()
                return 0
            if not menu.collidepoint(pos): self.open_unit=None
            return 0

        # If a tower is already selected (click-to-place mode), second click places it
        if self.selected_slot is not None and self.drag_unit is not None:
            mx,my=pos
            if any(slot.collidepoint(pos) for slot in self.slots):
                # clicked on a slot panel area — cancel or reselect
                for i,slot in enumerate(self.slots):
                    if slot.collidepoint(pos):
                        if i == self.selected_slot:
                            # cancel selection
                            self.drag_unit=None; self.selected_slot=None; return 0
                        else:
                            # switch to different slot
                            UType2=self.SLOT_TYPES[i]
                            if UType2 is None: self.show_msg("Coming soon!"); self.drag_unit=None; self.selected_slot=None; return 0
                            if money<UType2.PLACE_COST: self.show_msg("Not enough money!"); self.drag_unit=None; self.selected_slot=None; return 0
                            self.selected_slot=i; self.drag_unit=UType2(*pos); return 0
            # Place the tower
            UType_check=self.SLOT_TYPES[self.selected_slot]
            on_road_ok = getattr(UType_check, 'ON_ROAD', False)
            road_blocked = (abs(my-PATH_Y)<PATH_H+5) and not on_road_ok
            if road_blocked or my>SLOT_AREA_Y-10 or any(dist((u.px,u.py),pos)<36 for u in units):
                self.show_msg("Can't place here!"); self.drag_unit=None; self.selected_slot=None; return 0
            UType=self.SLOT_TYPES[self.selected_slot]
            # Check placement limit
            limit = getattr(UType, '_PLACE_LIMIT', None)
            if limit and sum(1 for u2 in units if isinstance(u2, UType)) >= limit:
                self.show_msg(f"Max {limit} {UType.NAME}s allowed!"); self.drag_unit=None; self.selected_slot=None; return 0
            u=UType(mx,my); units.append(u)
            self.drag_unit=None; self.selected_slot=None; return -UType.PLACE_COST

        for u in units:
            if dist((u.px,u.py),pos)<28: self.open_unit=u; return 0
        for i,slot in enumerate(self.slots):
            if slot.collidepoint(pos):
                UType=self.SLOT_TYPES[i]
                if UType is None: self.show_msg("Coming soon!"); return 0
                if UType is Clown and not is_clown_unlocked():
                    self.show_msg("Clown locked! Beat the Key Hunt first."); return 0
                if money<UType.PLACE_COST: self.show_msg("Not enough money!"); return 0
                self.selected_slot=i; self.drag_unit=UType(*pos); return 0
        return 0

    def handle_release(self,pos,units,money):
        # Placement is now done via second click, not on mouse release
        return 0

    def select_slot_by_key(self, slot_idx, mouse_pos, units, money):
        """Select a tower slot by keyboard hotkey (1-5)."""
        if slot_idx >= len(self.SLOT_TYPES): return 0
        UType = self.SLOT_TYPES[slot_idx]
        # Cancel if same slot pressed again
        if self.selected_slot == slot_idx and self.drag_unit is not None:
            self.drag_unit = None; self.selected_slot = None; return 0
        if UType is None: self.show_msg("Coming soon!"); return 0
        if UType is Clown and not is_clown_unlocked():
            self.show_msg("Clown locked! Beat the Key Hunt first."); return 0
        if money < UType.PLACE_COST: self.show_msg("Not enough money!"); return 0
        self.open_unit = None
        self.selected_slot = slot_idx
        self.drag_unit = UType(*mouse_pos)
        return 0

    def sell_unit(self, unit, units):
        """Remove unit, return 30% of total spent."""
        refund = max(1, int(getattr(unit, '_total_spent', unit.PLACE_COST) * 0.30))
        if unit in units: units.remove(unit)
        if self.open_unit is unit: self.open_unit = None
        return refund

    def _menu_rects(self,unit):
        # Fixed panel on the RIGHT side, between top bar and slot panel
        mw, mh = 368, 533
        mx = SCREEN_W - mw - 12
        my = 80
        menu=pygame.Rect(mx,my,mw,mh); btns={}
        btns["close"]=pygame.Rect(mx+mw-43,my+12,32,32)
        btns["sell"]=pygame.Rect(mx+14,my+mh-69,mw//2-20,55)
        btns["upgrade"]=pygame.Rect(mx+mw//2+6,my+mh-69,mw//2-20,55)
        if unit.ability and unit.level>=2:
            btns["ability"]=pygame.Rect(mx+14,my+mh-138,mw-28,52)
        if isinstance(unit, Archer) and unit.level >= 2:
            btns["archer_arrow"]=pygame.Rect(mx+14,my+mh-138,mw-28,52)
        return menu,btns

    def draw(self,surf,units,money,wave_mgr,player_hp,player_maxhp,enemies,boss_enemy=None):
        wave=wave_mgr.wave
        # ── TOP BAR gradient ────────────────────────────────────────────────────
        draw_rect_gradient(surf,(22,26,44),(14,18,32),(0,0,SCREEN_W,72),alpha=248)
        pygame.draw.line(surf,(80,90,140),(0,72),(SCREEN_W,72),1)
        pygame.draw.line(surf,(40,50,90),(0,73),(SCREEN_W,73),2)

        # Wave indicator + progress dots
        wave_col = C_CYAN if wave < MAX_WAVES else C_GOLD
        txt(surf,"WAVE",(26,10),(80,90,130),pygame.font.SysFont("consolas",18,bold=True))
        txt(surf,f"{wave}/{MAX_WAVES}",(26,30),wave_col,pygame.font.SysFont("consolas",24,bold=True))
        for wi in range(MAX_WAVES):
            dc = C_CYAN if wi < wave else (38,48,68)
            pygame.draw.circle(surf,dc,(122+wi*8,52),3)

        tl=wave_mgr.time_left()
        if tl is not None:
            t_col=(255,200,50) if tl>2 else (255,100,50)
            txt(surf,f"[T] {tl:.1f}s",(26,56),(90,100,130),font_sm)

        # Money display
        money_str = str(money)
        money_surf = font_lg.render(money_str, True, C_GOLD)
        total_w = (ICO_COIN.get_width() + 8 if ICO_COIN else 0) + money_surf.get_width()
        mx_off = SCREEN_W // 2 - total_w // 2
        if ICO_COIN:
            surf.blit(ICO_COIN, (mx_off, 12))
            mx_off += ICO_COIN.get_width() + 8
        else:
            txt(surf, "[C]", (mx_off, 28), C_GOLD, font_lg)
            mx_off += 36
        surf.blit(money_surf, (mx_off, 28))

        # HP bar (right side) — gradient fill
        bx=SCREEN_W-403; bw2=317; bh2=28
        ratio=max(0,player_hp/max(1,player_maxhp))
        pygame.draw.rect(surf,(8,4,4),(bx-2,18,bw2+4,bh2+4),border_radius=8)
        pygame.draw.rect(surf,(20,10,10),(bx,20,bw2,bh2),border_radius=7)
        if ratio>0:
            hc1=(60,220,90) if ratio>0.5 else (220,60,60)
            hc2=(40,160,65) if ratio>0.5 else (160,40,40)
            draw_rect_gradient(surf,hc1,hc2,(bx,20,int(bw2*ratio),bh2),alpha=255,brad=7)
            draw_rect_alpha(surf,(255,255,255),(bx,20,int(bw2*ratio),bh2//3),28,brad=7)
        pygame.draw.rect(surf,(60,70,110),(bx,20,bw2,bh2),2,border_radius=7)
        txt(surf,f"HP  {player_hp}/{player_maxhp}",(bx+bw2//2,34),C_WHITE,font_sm,center=True)

        # ── BOSS BAR ────────────────────────────────────────────────────────────
        if boss_enemy and boss_enemy.alive:
            ratio = max(0.0, boss_enemy.hp / boss_enemy.maxhp)
            bbw = SCREEN_W - 160; bbh = 22
            bbx = (SCREEN_W - bbw) // 2; bby = 36

            # outer glow shadow
            glow_surf = pygame.Surface((bbw + 24, bbh + 24), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (180, 30, 30, 60),
                             (0, 0, bbw + 24, bbh + 24), border_radius=12)
            surf.blit(glow_surf, (bbx - 12, bby - 12))

            # background track
            pygame.draw.rect(surf, (10, 8, 8),
                             (bbx - 3, bby - 3, bbw + 6, bbh + 6), border_radius=10)
            pygame.draw.rect(surf, (35, 12, 12),
                             (bbx, bby, bbw, bbh), border_radius=8)

            # gradient health fill
            g_val = int(30 + ratio * 40)
            bc1 = (180 + int((1-ratio)*50), g_val, 10)
            bc2 = (int(bc1[0]*0.7), int(bc1[1]*0.7), 5)
            fill_w = max(0, int(bbw * ratio))
            if fill_w > 0:
                draw_rect_gradient(surf, bc1, bc2, (bbx, bby, fill_w, bbh), alpha=255, brad=8)
                hi_r = pygame.Rect(bbx+4, bby+2, max(0, fill_w-8), 4)
                if hi_r.width > 0:
                    hs = pygame.Surface((hi_r.width, hi_r.height), pygame.SRCALPHA)
                    hs.fill((255,255,255,60)); surf.blit(hs, hi_r.topleft)

            for seg in range(1, 10):
                sx = bbx + int(bbw * seg / 10)
                pygame.draw.line(surf, (0,0,0), (sx, bby), (sx, bby+bbh), 2)
            pygame.draw.rect(surf, (200,60,60), (bbx, bby, bbw, bbh), 2, border_radius=8)
            boss_label = getattr(boss_enemy, "DISPLAY_NAME", "BOSS")
            txt(surf, f"[!] {boss_label.upper()}", (bbx+6, bby+bbh//2), (255,130,130), font_sm)
            hp_str = f"{int(boss_enemy.hp):,} / {int(boss_enemy.maxhp):,}"
            hp_w = font_sm.size(hp_str)[0]
            txt(surf, hp_str, (bbx+bbw-hp_w-6, bby+bbh//2), (255,200,200), font_sm)

        # ── SLOT PANEL gradient ──────────────────────────────────────────────────
        draw_rect_gradient(surf,(20,22,38),(14,16,28),(0,SLOT_AREA_Y,SCREEN_W,SCREEN_H-SLOT_AREA_Y),alpha=248)
        pygame.draw.line(surf,(80,90,140),(0,SLOT_AREA_Y),(SCREEN_W,SLOT_AREA_Y),1)
        pygame.draw.line(surf,(40,50,80),(0,SLOT_AREA_Y+1),(SCREEN_W,SLOT_AREA_Y+1),2)
        # slot panel money
        if ICO_COIN:
            surf.blit(ICO_COIN, (14, SLOT_AREA_Y - 38))
            txt(surf, f" {money}", (50, SLOT_AREA_Y - 34), C_GOLD, font_md)
        else:
            txt(surf, f"[C] {money}", (14, SLOT_AREA_Y - 34), C_GOLD, font_md)
        _lo = Lobby.__new__(Lobby)
        mx2h,my2h=pygame.mouse.get_pos()
        for i,slot in enumerate(self.slots):
            UType=self.SLOT_TYPES[i]; sel=(i==self.selected_slot)
            hov_slot=slot.collidepoint(mx2h,my2h) and not sel
            if sel:
                draw_rect_gradient(surf,(50,70,140),(30,45,95),slot,alpha=240,brad=10)
                draw_rect_alpha(surf,C_CYAN,(slot.x,slot.y,slot.w,3),80,brad=10)
                pygame.draw.rect(surf,C_CYAN,slot,2,border_radius=10)
            elif hov_slot:
                draw_rect_gradient(surf,(35,40,65),(22,26,48),slot,alpha=228,brad=10)
                pygame.draw.rect(surf,(80,90,140),slot,2,border_radius=10)
            else:
                draw_rect_gradient(surf,(28,32,52),(18,20,38),slot,alpha=218,brad=10)
                pygame.draw.rect(surf,C_BORDER,slot,1,border_radius=10)
            if UType:
                cx2=slot.centerx; cy2=slot.centery-16
                _lo._draw_tower_icon(surf, UType, cx2, cy2, size=22)
                nc=UType.COLOR if sel else (200,210,230)
                txt(surf,UType.NAME,(slot.centerx,slot.bottom-24),nc,font_sm,center=True)
                if ICO_COIN:
                    coin_slot=pygame.transform.smoothscale(ICO_COIN,(18,18))
                    cost_str=f"${UType.PLACE_COST}"
                    cost_w3=font_sm.size(cost_str)[0]
                    cost_x=slot.centerx-(20+4+cost_w3)//2
                    surf.blit(coin_slot,(cost_x,slot.bottom-22))
                    cc=C_GOLD if money>=UType.PLACE_COST else (160,70,70)
                    txt(surf,cost_str,(cost_x+22,slot.bottom-16),cc,font_sm)
                else:
                    cc=C_GOLD if money>=UType.PLACE_COST else (160,70,70)
                    txt(surf,f"${UType.PLACE_COST}",(slot.centerx,slot.bottom-8),cc,font_sm,center=True)
                badge_rect=pygame.Rect(slot.x+6,slot.y+6,23,20)
                draw_rect_alpha(surf,(0,0,0),(*badge_rect.topleft,badge_rect.w,badge_rect.h),180,brad=7)
                bc2=(60,100,180) if sel else (60,55,100)
                pygame.draw.rect(surf,bc2,badge_rect,1,border_radius=7)
                txt(surf,str(i+1),badge_rect.center,(220,230,255) if sel else (140,130,180),font_sm,center=True)
                # Lock overlay for Clown if not unlocked
                if UType is Clown and not is_clown_unlocked():
                    draw_rect_alpha(surf,(0,0,0),(slot.x,slot.y,slot.w,slot.h),160,brad=10)
                    lf = pygame.font.SysFont("consolas", 22, bold=True)
                    txt(surf,"[L]",(slot.centerx,slot.centery-6),(180,80,255),lf,center=True)
                    lf2 = pygame.font.SysFont("consolas", 9, bold=True)
                    txt(surf,"KEY HUNT",(slot.centerx,slot.bottom-10),(180,80,255),lf2,center=True)
            else:
                txt(surf,"???",(slot.centerx,slot.centery),(80,80,120),font_lg,center=True)
                badge_rect=pygame.Rect(slot.x+6,slot.y+6,23,20)
                draw_rect_alpha(surf,(0,0,0),(*badge_rect.topleft,badge_rect.w,badge_rect.h),120,brad=8)
                pygame.draw.rect(surf,(60,55,80),badge_rect,2,border_radius=8)
                txt(surf,str(i+1),badge_rect.center,(100,90,130),font_sm,center=True)

        mx2,my2=pygame.mouse.get_pos()
        for u in units:
            if dist((u.px,u.py),(mx2,my2))<43 and self.open_unit!=u: u.draw_range(surf)

        if self.open_unit:
            u=self.open_unit; u.draw_range(surf)
            menu,btns=self._menu_rects(u)
            mx0,my0=menu.x,menu.y; mw,mh=menu.w,menu.h

            # ── Drop shadow ──────────────────────────────────────────────
            draw_rect_alpha(surf,(0,0,0),(mx0+6,my0+8,mw,mh),80,brad=16)

            # ── Glassmorphism panel background ───────────────────────────
            draw_rect_alpha(surf,(12,16,30),(mx0,my0,mw,mh),245,brad=16)
            # subtle inner glow along top edge
            draw_rect_alpha(surf,(80,60,160),(mx0,my0,mw,2),60,brad=16)

            # ── Gradient header strip ────────────────────────────────────
            header_h=60
            for row in range(header_h):
                t=row/header_h
                r2=int(28+t*8); g2=int(14+t*6); b2=int(60+t*20)
                pygame.draw.line(surf,(r2,g2,b2),(mx0,my0+row),(mx0+mw,my0+row))
            # round the corners of the header by re-clipping panel edges
            pygame.draw.rect(surf,(12,16,30),(mx0,my0+header_h-1,mw,3))  # smooth join
            # header bottom separator glow
            for i in range(3):
                alpha_sep=80-i*25
                draw_rect_alpha(surf,u.COLOR,(mx0,my0+header_h+i,mw,1),alpha_sep)

            # ── Tower icon badge ─────────────────────────────────────────
            icon_cx=mx0+40; icon_cy=my0+header_h//2
            draw_rect_alpha(surf,(0,0,0),(icon_cx-20,icon_cy-20,40,40),80,brad=20)
            pygame.draw.circle(surf,(30,20,60),(icon_cx,icon_cy),20)
            for ring_r,ring_a in [(23,60),(26,30),(29,12)]:
                draw_rect_alpha(surf,u.COLOR,(icon_cx-ring_r,icon_cy-ring_r,ring_r*2,ring_r*2),ring_a,brad=ring_r)
            pygame.draw.circle(surf,u.COLOR,(icon_cx,icon_cy),16)
            pygame.draw.circle(surf,(255,255,255),(icon_cx,icon_cy),16,2)

            # ── Tower name ───────────────────────────────────────────────
            name_f=pygame.font.SysFont("consolas",24,bold=True)
            name_surf=name_f.render(u.NAME,True,C_WHITE)
            surf.blit(name_surf,(mx0+72,my0+7))

            # ── Level bar (modern segmented) ─────────────────────────────
            max_lv=getattr(u,'_max_level',None) or (len(ASSASSIN_LEVELS)-1 if isinstance(u,Assassin) else len(ACCEL_LEVELS)-1 if isinstance(u,Accelerator) else len(ARCHER_LEVELS)-1 if isinstance(u,Archer) else len(CLOWN_LEVELS)-1)
            lv_label_f=pygame.font.SysFont("consolas",19)
            lv_surf=lv_label_f.render(f"LVL {u.level}/{max_lv}",True,(180,160,255))
            surf.blit(lv_surf,(mx0+72,my0+36))
            seg_w=16; seg_gap=4; seg_h=7
            seg_x=mx0+72+lv_surf.get_width()+10; seg_y=my0+39
            for i in range(max_lv):
                filled=i<u.level
                seg_col=u.COLOR if filled else (35,35,55)
                pygame.draw.rect(surf,seg_col,(seg_x+i*(seg_w+seg_gap),seg_y,seg_w,seg_h),border_radius=3)
                if filled:
                    draw_rect_alpha(surf,(255,255,255),(seg_x+i*(seg_w+seg_gap),seg_y,seg_w,4),60,brad=3)
                pygame.draw.rect(surf,(60,50,90) if not filled else (200,200,255),
                                 (seg_x+i*(seg_w+seg_gap),seg_y,seg_w,seg_h),1,border_radius=3)

            # ── Close button ─────────────────────────────────────────────
            cx2,cy2=btns["close"].center
            draw_rect_alpha(surf,(100,20,20),(*btns["close"].topleft,btns["close"].w,btns["close"].h),200,brad=12)
            pygame.draw.rect(surf,(200,60,60),btns["close"],2,border_radius=12)
            txt(surf,"✕",(cx2,cy2),(255,140,140),font_sm,center=True)

            # ── Panel border ─────────────────────────────────────────────
            pygame.draw.rect(surf,(60,45,110),menu,2,border_radius=16)

            # ── Stats section ────────────────────────────────────────────
            cur=u.get_info(); nxt=u.get_next_info()
            stat_y=my0+header_h+14

            stat_label_text={"Damage":"Damage","Range":"Range","Firerate":"Firerate","Dual":"Dual Shot","HidDet":"Detection","Stun":"Stun","Pierce":"Pierce","Arrow":"Arrow"}
            stat_colors={"Damage":(255,120,100),"Range":(100,200,255),"Firerate":(255,220,80),
                         "Dual":(160,120,255),"HidDet":(80,255,180),"Stun":(120,200,255),
                         "Pierce":(200,180,100),"Arrow":(160,230,120)}

            lbl_f  = pygame.font.SysFont("consolas", 19, bold=True)
            val_f  = pygame.font.SysFont("consolas", 19)
            arr_f  = pygame.font.SysFont("consolas", 20, bold=True)
            row_h  = 33   # enough room for 19px font + padding

            # column positions (within the 512px wide panel)
            COL_ICON  = mx0 + 19
            COL_LABEL = mx0 + 36
            COL_CUR   = mx0 + mw - 151
            COL_ARROW = mx0 + mw - 108
            COL_NXT   = mx0 + mw - 10

            for idx,(k,v) in enumerate(cur.items()):
                ry = stat_y + idx * row_h
                pill_col = (22,28,48) if idx%2==0 else (18,22,40)
                draw_rect_alpha(surf, pill_col, (mx0+6, ry, mw-12, row_h-4), 220, brad=8)

                # Draw image icon if available, else fall back to emoji text
                ico = STAT_ICONS_IMG.get(k)
                if ico:
                    surf.blit(ico, (COL_ICON - ico.get_width()//2, ry + (row_h-4)//2 - ico.get_height()//2))
                label = stat_label_text.get(k, k)
                lcol  = stat_colors.get(k, (160,170,210))
                lbl_surf = lbl_f.render(label, True, lcol)
                surf.blit(lbl_surf, (COL_LABEL, ry+10))

                if nxt and k in nxt:
                    nv = nxt[k]
                    try:
                        cvf=float(v); nvf=float(nv)
                        better=(nvf>cvf) if k!="Firerate" else (nvf<cvf)
                        same=(cvf==nvf)
                        if same:     arrow="—"; acol=(70,75,100)
                        elif better: arrow="▲"; acol=(60,220,110)
                        else:        arrow="▼"; acol=(220,70,70)
                    except:
                        same=(v==nv)
                        arrow="—" if same else "▲"; acol=(70,75,100) if same else (60,220,110)

                    cv_surf = val_f.render(str(v),  True, (190,195,220))
                    nv_surf = val_f.render(str(nv),  True, (80,230,120))
                    surf.blit(cv_surf, (COL_CUR - cv_surf.get_width(), ry+10))
                    # Arrow: use image if available, else text glyph
                    if ICO_ARROW and arrow in ("▲","▼"):
                        ar_ico = ICO_ARROW
                        # tint by flipping/rotating not possible easily; just blit tinted via surface
                        tinted = ar_ico.copy()
                        tinted.fill((*acol, 200), special_flags=pygame.BLEND_RGBA_MULT)
                        if arrow == "▼":
                            tinted = pygame.transform.flip(tinted, False, True)
                        surf.blit(tinted, (COL_ARROW - tinted.get_width()//2, ry + (row_h-4)//2 - tinted.get_height()//2))
                    else:
                        ar_surf = arr_f.render(arrow, True, acol)
                        surf.blit(ar_surf, (COL_ARROW - ar_surf.get_width()//2, ry+9))
                    surf.blit(nv_surf, (COL_NXT - nv_surf.get_width(), ry+10))
                else:
                    cv_surf = val_f.render(str(v), True, (200,205,230))
                    surf.blit(cv_surf, (COL_NXT - cv_surf.get_width(), ry+10))

            # ── Divider before buttons ────────────────────────────────────
            _has_extra_btn = (u.ability and u.level>=2) or (isinstance(u, Archer) and u.level>=2)
            div_y=my0+mh-(96+20+(_has_extra_btn*(72+16))+28)
            for i,dcol in enumerate([(60,45,110),(40,30,80),(20,15,40)]):
                pygame.draw.line(surf,dcol,(mx0+20,div_y+i),(mx0+mw-20,div_y+i),2)

            # ── Archer arrow-type switch button ──────────────────────────
            if isinstance(u, Archer) and u.level >= 2:
                ab_rect = btns["archer_arrow"]
                avail = u._available_arrows()
                arrow_names = {"normal": "Normal Arrow", "ice": "Ice Arrow", "flame": "Flame Arrow"}
                arrow_cols  = {"normal": (200,160,80), "ice": (100,200,255), "flame": (255,120,30)}
                cur_col = arrow_cols.get(u._arrow_type, C_WHITE)
                draw_rect_alpha(surf,(20,40,60),(*ab_rect.topleft,ab_rect.w,ab_rect.h),230,brad=10)
                pygame.draw.rect(surf,cur_col,ab_rect,2,border_radius=10)
                draw_rect_alpha(surf,(255,255,255),(*ab_rect.topleft,ab_rect.w,2),30,brad=10)
                alabel = f">> {arrow_names.get(u._arrow_type,'Normal Arrow')}  [click to switch]"
                txt(surf,alabel,ab_rect.center,cur_col,font_sm,center=True)
                # Small dots for available types
                dot_x = ab_rect.centerx - (len(avail)-1)*18
                for ai, atype in enumerate(avail):
                    dc = arrow_cols.get(atype, C_WHITE)
                    filled = (atype == u._arrow_type)
                    pygame.draw.circle(surf, dc, (dot_x + ai*36, ab_rect.bottom-12), 6, 0 if filled else 2)

            # ── Ability button ───────────────────────────────────────────
            if u.ability and u.level>=2:
                ab=u.ability; ready=ab.ready()
                ab_rect=btns["ability"]
                if ready:
                    draw_rect_alpha(surf,(0,90,110),(*ab_rect.topleft,ab_rect.w,ab_rect.h),230,brad=10)
                    pygame.draw.rect(surf,C_CYAN,ab_rect,2,border_radius=10)
                    # shimmer line
                    draw_rect_alpha(surf,(255,255,255),(*ab_rect.topleft,ab_rect.w,2),40,brad=10)
                    alabel=f"* {ab.name}  [F]"
                    txt(surf,alabel,ab_rect.center,C_CYAN,font_md,center=True)
                else:
                    draw_rect_alpha(surf,(20,24,40),(*ab_rect.topleft,ab_rect.w,ab_rect.h),210,brad=10)
                    pygame.draw.rect(surf,(45,55,75),ab_rect,2,border_radius=10)
                    # cooldown progress bar
                    r3=1-(ab.cd_left/ab.cooldown)
                    bar_w=ab_rect.w-20
                    pygame.draw.rect(surf,(30,35,55),(ab_rect.x+10,ab_rect.centery+6,bar_w,4),border_radius=2)
                    pygame.draw.rect(surf,(60,180,200),(ab_rect.x+10,ab_rect.centery+6,int(bar_w*r3),4),border_radius=2)
                    txt(surf,f"CD {ab.cd_left:.1f}s",ab_rect.center,(70,80,105),font_sm,center=True)

            # ── Sell button ──────────────────────────────────────────────
            sell_rect=btns["sell"]
            refund_val=max(1,int(getattr(u,'_total_spent',u.PLACE_COST)*0.30))
            mx_h,my_h=pygame.mouse.get_pos()
            hov_sell=sell_rect.collidepoint(mx_h,my_h)
            if hov_sell:
                draw_rect_alpha(surf,(180,40,40),(*sell_rect.topleft,sell_rect.w,sell_rect.h),240,brad=10)
                pygame.draw.rect(surf,(255,80,80),sell_rect,2,border_radius=10)
            else:
                draw_rect_alpha(surf,(90,20,20),(*sell_rect.topleft,sell_rect.w,sell_rect.h),220,brad=10)
                pygame.draw.rect(surf,(160,45,45),sell_rect,2,border_radius=10)
            draw_rect_alpha(surf,(255,255,255),(*sell_rect.topleft,sell_rect.w,2),20,brad=10)
            sell_f=pygame.font.SysFont("consolas",18,bold=True)
            txt(surf,"[X] SELL",(sell_rect.centerx,sell_rect.y+10),(255,120,120),sell_f,center=True)
            # Refund amount with coin icon
            if ICO_COIN:
                coin_sm = pygame.transform.smoothscale(ICO_COIN, (20, 20))
                coin_x = sell_rect.centerx - sell_f.size(f"+${refund_val}")[0]//2 - 14
                surf.blit(coin_sm, (coin_x, sell_rect.y+26))
                txt(surf,f"+${refund_val}",(coin_x+22, sell_rect.y+28),(255,200,80),sell_f)
            else:
                txt(surf,f"+${refund_val}",(sell_rect.centerx,sell_rect.y+28),(255,200,80),sell_f,center=True)

            # ── Upgrade button ───────────────────────────────────────────
            cost=u.upgrade_cost()
            up_rect=btns["upgrade"]
            if cost:
                afford=money>=cost
                if afford:
                    # glowing green button
                    for glow_i in range(3):
                        draw_rect_alpha(surf,(40,200,80),
                                        (up_rect.x-glow_i,up_rect.y-glow_i,
                                         up_rect.w+glow_i*2,up_rect.h+glow_i*2),
                                        25-glow_i*8,brad=11+glow_i)
                    draw_rect_alpha(surf,(15,80,30),(*up_rect.topleft,up_rect.w,up_rect.h),240,brad=10)
                    pygame.draw.rect(surf,(55,210,85),up_rect,2,border_radius=10)
                    draw_rect_alpha(surf,(255,255,255),(*up_rect.topleft,up_rect.w,3),30,brad=10)
                    upg_f=pygame.font.SysFont("consolas",18,bold=True)
                    txt(surf,"[E] UPGRADE",(up_rect.centerx,up_rect.y+10),(100,255,130),upg_f,center=True)
                    if ICO_COIN:
                        coin_sm2 = pygame.transform.smoothscale(ICO_COIN, (20, 20))
                        cost_w = upg_f.size(f"${cost}")[0]
                        cx3 = up_rect.centerx - (cost_w + 30)//2
                        surf.blit(coin_sm2, (cx3, up_rect.y+26))
                        txt(surf,f"${cost}",(cx3+20, up_rect.y+28),(180,255,200),upg_f)
                    else:
                        txt(surf,f"${cost}",(up_rect.centerx,up_rect.y+28),(180,255,200),upg_f,center=True)
                else:
                    draw_rect_alpha(surf,(45,18,18),(*up_rect.topleft,up_rect.w,up_rect.h),210,brad=10)
                    pygame.draw.rect(surf,(110,35,35),up_rect,2,border_radius=10)
                    upg_f=pygame.font.SysFont("consolas",18,bold=True)
                    txt(surf,"[E] UPGRADE",(up_rect.centerx,up_rect.y+10),(160,65,65),upg_f,center=True)
                    if ICO_COIN:
                        coin_sm3 = pygame.transform.smoothscale(ICO_COIN, (20, 20))
                        cost_w2 = upg_f.size(f"${cost}")[0]
                        cx4 = up_rect.centerx - (cost_w2 + 30)//2
                        coin_sm3.set_alpha(120)
                        surf.blit(coin_sm3, (cx4, up_rect.y+26))
                        txt(surf,f"${cost}",(cx4+20, up_rect.y+28),(120,50,50),upg_f)
                    else:
                        txt(surf,f"${cost}",(up_rect.centerx,up_rect.y+28),(120,50,50),upg_f,center=True)
            else:
                draw_rect_alpha(surf,(30,26,50),(*up_rect.topleft,up_rect.w,up_rect.h),220,brad=10)
                pygame.draw.rect(surf,(100,85,140),up_rect,2,border_radius=10)
                draw_rect_alpha(surf,C_GOLD,(*up_rect.topleft,up_rect.w,2),50,brad=10)
                txt(surf,"★ MAX LEVEL",up_rect.center,(220,190,80),font_md,center=True)

        if self.drag_unit:
            mx2,my2=pygame.mouse.get_pos()
            self.drag_unit.px=mx2; self.drag_unit.py=my2
            self.drag_unit.draw_range(surf); self.drag_unit.draw(surf)
            # hint text
            _on_road_ok = getattr(self.drag_unit, 'ON_ROAD', False)
            _road_bad = (abs(my2-PATH_Y)<PATH_H+5) and not _on_road_ok
            hint_col=(200,80,80) if (_road_bad or my2>SLOT_AREA_Y-10) else C_CYAN
            txt(surf,"Click to place  |  Click slot to cancel",(SCREEN_W//2,SLOT_AREA_Y-70),hint_col,font_sm,center=True)

        for idx,u in enumerate([u for u in units if u.ability and u.level>=2]):
            ab=u.ability; bw3,bh3=200,56; bx3=SCREEN_W-bw3-16; by3=SLOT_AREA_Y-16-(idx+1)*(bh3+8)
            ready=ab.ready()
            pygame.draw.rect(surf,(30,70,80) if ready else (30,30,40),(bx3,by3,bw3,bh3),border_radius=6)
            pygame.draw.rect(surf,C_CYAN if ready else C_BORDER,(bx3,by3,bw3,bh3),2,border_radius=6)
            pygame.draw.circle(surf,u.COLOR,(bx3+28,by3+bh3//2),18)
            pygame.draw.circle(surf,C_WHITE,(bx3+28,by3+bh3//2),18,2)
            txt(surf,ab.name if ready else f"CD {ab.cd_left:.1f}s",
                (bx3+52,by3+6),C_WHITE if ready else (100,100,120),font_sm)
            if not ready:
                r3=1-(ab.cd_left/ab.cooldown)
                pygame.draw.rect(surf,(40,40,60),(bx3+52,by3+30,bw3-60,10),border_radius=4)
                pygame.draw.rect(surf,C_CYAN,(bx3+52,by3+30,int((bw3-60)*r3),10),border_radius=4)
            else:
                txt(surf,"CLICK TO USE",(bx3+52,by3+32),C_CYAN,font_sm)
            u._ability_btn_rect=pygame.Rect(bx3,by3,bw3,bh3)

        if self.msg_timer>0:
            alpha=min(255,int(self.msg_timer*255))
            s2=font_lg.render(self.msg,True,C_ORANGE); s2.set_alpha(alpha)
            surf.blit(s2,s2.get_rect(center=(SCREEN_W//2,SCREEN_H//2-60)))

        for e in enemies:
            if e.alive and dist((e.x,e.y),(mx2,my2))<e.radius+5:
                e.draw(surf,hovered=True,detected=True)



# ── Difficulty Settings ────────────────────────────────────────────────────────
DIFFICULTIES = {
    "Easy": {
        "hp_mult": 1.5,
        "money_mult": 1.5,
        "enemy_hp_mult": 0.7,
        "enemy_speed_mult": 0.85,
        "start_money": 800,
        "color": (60, 200, 80),
        "desc": ["Enemies are weaker", "More starting money", "Extra HP"],
        "img_label": "Tower Battles",
    },
    "Hard": {
        "hp_mult": 1.2,
        "money_mult": 1.2,
        "enemy_hp_mult": 0.85,
        "enemy_speed_mult": 0.9,
        "start_money": 650,
        "color": (255, 200, 50),
        "desc": ["Enemies slightly weaker", "More money & HP", "Balanced challenge"],
        "img_label": "TDS Classic",
    },
    "Hell": {
        "hp_mult": 0.7,
        "money_mult": 0.9,
        "enemy_hp_mult": 1.1,
        "enemy_speed_mult": 1.0,
        "start_money": 700,
        "color": (220, 60, 60),
        "desc": ["HP scales with waves", "Scarce resources", "Survive if you can"],
        "img_label": "Zombie Attack",
    },
}

# ── TDS-style game cover art (drawn procedurally) ──────────────────────────────
def draw_easy_cover(surf, rect):
    """Sunny green grassland map with winding path"""
    x, y, w, h = rect
    pygame.draw.rect(surf, (34, 85, 34), rect, border_radius=10)
    rng = random.Random(11)
    for _ in range(40):
        gx = x + rng.randint(4, w-4); gy = y + rng.randint(4, h-4)
        pygame.draw.circle(surf, (40, 95, 40), (gx, gy), rng.randint(2,5))
    path_pts = []
    segs = 12
    for i in range(segs+1):
        px3 = x + int(i * w / segs)
        py3 = y + h//2 + int(math.sin(i / segs * math.pi * 2) * h // 5)
        path_pts.append((px3, py3))
    pw = 16
    for i in range(len(path_pts)-1):
        pygame.draw.line(surf, (110, 95, 65), path_pts[i], path_pts[i+1], pw+4)
    for i in range(len(path_pts)-1):
        pygame.draw.line(surf, (130, 110, 75), path_pts[i], path_pts[i+1], pw)
    for tx, ty, tr in [(x+18, y+22, 9), (x+w-22, y+18, 8), (x+22, y+h-22, 9),
                        (x+w-18, y+h-18, 8), (x+w//2-40, y+12, 7)]:
        pygame.draw.circle(surf, (20,50,20), (tx, ty+3), tr)
        pygame.draw.circle(surf, (35,100,35), (tx, ty), tr)
        pygame.draw.circle(surf, (60,140,60), (tx-2, ty-2), tr//2)
    for i, (px3, py3) in enumerate(path_pts[2::4]):
        side = -1 if i%2==0 else 1
        tx2 = px3; ty2 = py3 + side*(pw//2+14)
        if y+8 < ty2 < y+h-8:
            pygame.draw.rect(surf, (50,35,15), (tx2-5, ty2-4, 10, 14), border_radius=2)
            pygame.draw.circle(surf, (60,190,70), (tx2, ty2-6), 9)
            pygame.draw.circle(surf, (150,255,150), (tx2-2, ty2-9), 3)
    for ep in path_pts[3:9:2]:
        pygame.draw.circle(surf, (180,45,45), ep, 7)
        pygame.draw.circle(surf, (240,100,100), (ep[0]-2, ep[1]-2), 3)
    pygame.draw.rect(surf, (60,200,80), rect, 2, border_radius=10)

def draw_hard_cover(surf, rect):
    """Night city map with zigzag path and golden towers"""
    x, y, w, h = rect
    pygame.draw.rect(surf, (14, 18, 30), rect, border_radius=10)
    rng = random.Random(99)
    for _ in range(30):
        sx2 = x + rng.randint(5, w-5); sy2 = y + rng.randint(5, h//2)
        pygame.draw.circle(surf, (200,200,255), (sx2,sy2), 1)
    # Zigzag path (like classic TDS maps)
    path_pts2 = [
        (x, y+h//2),
        (x+w//4, y+h//2),
        (x+w//4, y+h//4),
        (x+w//2, y+h//4),
        (x+w//2, y+3*h//4),
        (x+3*w//4, y+3*h//4),
        (x+3*w//4, y+h//2),
        (x+w, y+h//2),
    ]
    pw2 = 14
    for i in range(len(path_pts2)-1):
        pygame.draw.line(surf, (45,50,65), path_pts2[i], path_pts2[i+1], pw2+4)
    for i in range(len(path_pts2)-1):
        pygame.draw.line(surf, (55,60,75), path_pts2[i], path_pts2[i+1], pw2)
    # Buildings in background
    for bx3, by3, bw3, bh3 in [(x+5,y+h-40,18,35),(x+w-28,y+h-50,20,45),(x+w//2+30,y+h-45,16,40)]:
        pygame.draw.rect(surf,(22,28,45),(bx3,by3,bw3,bh3))
        pygame.draw.rect(surf,(30,38,60),(bx3,by3,bw3,bh3),1)
        for wrow in range(by3+4,by3+bh3-4,8):
            for wcol in range(bx3+3,bx3+bw3-3,6):
                col3=(220,200,100) if rng.random()>0.4 else (40,40,60)
                pygame.draw.rect(surf,col3,(wcol,wrow,4,4))
    # Golden towers
    for tx, ty in [(x+w//4+14, y+h//4-22), (x+w//2+14, y+3*h//4-20), (x+3*w//4+14, y+h//2-22)]:
        if y+4 < ty < y+h-4:
            pygame.draw.rect(surf,(60,45,10),(tx-6,ty-4,12,20),border_radius=2)
            pygame.draw.circle(surf,(160,130,20),(tx,ty-7),10)
            pygame.draw.circle(surf,(255,210,60),(tx,ty-7),10,2)
            pygame.draw.line(surf,(255,200,40),(tx,ty-17),(tx,ty-24),2)
    # Laser effect
    pygame.draw.line(surf,(130,60,255),(x+w//4+14,y+h//4-7),(x+w//2-4,y+h//4-7),2)
    # Enemies on path
    for ep2 in [path_pts2[2], path_pts2[4], path_pts2[6]]:
        pygame.draw.circle(surf,(160,50,50),ep2,8)
        pygame.draw.circle(surf,(220,90,90),(ep2[0]-2,ep2[1]-3),3)
    pygame.draw.rect(surf, (255,200,50), rect, 2, border_radius=10)

def draw_hell_cover(surf, rect):
    """Volcanic hellscape with lava rivers and cracked earth"""
    x, y, w, h = rect
    pygame.draw.rect(surf, (22, 8, 8), rect, border_radius=10)
    # Cracked lava ground texture
    rng2 = random.Random(77)
    for _ in range(18):
        cx4 = x + rng2.randint(10, w-10); cy4 = y + rng2.randint(10, h-10)
        for _ in range(5):
            nx2 = cx4 + rng2.randint(-18, 18); ny2 = cy4 + rng2.randint(-10, 10)
            pygame.draw.line(surf, (100,30,0), (cx4,cy4), (nx2,ny2), 1)
            cx4, cy4 = nx2, ny2
    # Lava glow pools
    for lx, ly, lr in [(x+30, y+h-25, 18), (x+w-35, y+20, 14), (x+w//2+10, y+h-30, 12)]:
        s4 = pygame.Surface((lr*2+10, lr*2+10), pygame.SRCALPHA)
        pygame.draw.circle(s4, (200,80,0,60), (lr+5,lr+5), lr+4)
        surf.blit(s4, (lx-lr-5, ly-lr-5))
        pygame.draw.circle(surf, (160,50,0), (lx,ly), lr)
        pygame.draw.circle(surf, (220,100,20), (lx,ly), lr//2)
    # Winding lava path
    path_pts3 = []
    segs3 = 10
    for i in range(segs3+1):
        px4 = x + int(i * w / segs3)
        py4 = y + h//2 + int(math.sin(i / segs3 * math.pi * 1.5) * h // 4)
        path_pts3.append((px4, py4))
    for i in range(len(path_pts3)-1):
        pygame.draw.line(surf, (70,20,10), path_pts3[i], path_pts3[i+1], 20)
    for i in range(len(path_pts3)-1):
        pygame.draw.line(surf, (90,30,15), path_pts3[i], path_pts3[i+1], 16)
    # Lava glow on path edges
    for i in range(len(path_pts3)-1):
        pygame.draw.line(surf, (140,40,0), path_pts3[i], path_pts3[i+1], 1)
    # Dark ruined towers
    for tx, ty in [(x+w//4-5, y+h//2-32), (x+3*w//4+5, y+h//2-30)]:
        pygame.draw.rect(surf, (30,10,5), (tx-6,ty-4,12,22), border_radius=2)
        pygame.draw.circle(surf, (100,15,15), (tx,ty-8), 10)
        pygame.draw.circle(surf, (180,40,40), (tx,ty-8), 10, 2)
        # flames
        pygame.draw.circle(surf, (255,80,0), (tx, ty-18), 4)
        pygame.draw.circle(surf, (255,180,0), (tx, ty-20), 2)
    # Many zombie enemies
    for ep3, er3 in [(path_pts3[2],10),(path_pts3[4],12),(path_pts3[6],9),(path_pts3[8],11)]:
        pygame.draw.circle(surf,(120,25,25),ep3,er3)
        pygame.draw.circle(surf,(180,70,50),(ep3[0]-2,ep3[1]-3),er3//3)
    # Skull
    skull_x2, skull_y2 = x+w-20, y+14
    pygame.draw.circle(surf,(160,0,0),(skull_x2,skull_y2),8)
    pygame.draw.circle(surf,(22,8,8),(skull_x2-3,skull_y2-1),2)
    pygame.draw.circle(surf,(22,8,8),(skull_x2+3,skull_y2-1),2)
    pygame.draw.rect(surf,(22,8,8),(skull_x2-4,skull_y2+3,9,4))
    pygame.draw.rect(surf, (220,60,60), rect, 2, border_radius=10)

COVER_DRAW_FUNCS = {"Easy": draw_easy_cover, "Hard": draw_hard_cover, "Hell": draw_hell_cover}


# ── In-Game Clown Key Widget ───────────────────────────────────────────────────
# Keys appear during normal gameplay. Players click them to collect.
# Positions are fixed per difficulty per session.

class InGameKeyManager:
    """
    Manages Clown Key Fragments that appear during normal gameplay.
    Each key is a clickable object rendered on the map (away from the path).
    Collected keys are saved persistently via collect_clown_key().
    """
    # Allowed zones for key placement (away from the path zone 490-530 and HUD)
    _SAFE_ZONES = [
        (80, 80, SCREEN_W - 320, 420),       # above path
        (80, 560, SCREEN_W - 320, SCREEN_H - 180),  # below path
    ]

    def __init__(self, source):
        self.source = source   # "Easy" / "Hard" / "Hell" / "Sandbox"
        cap = CLOWN_KEY_SOURCES.get(source, 0)
        ck, _ = get_clown_keys()
        already = ck.get(source, 0)
        self.remaining = cap - already   # how many more can be collected here
        self._keys = self._place_keys() if self.remaining > 0 else []
        self._collected_this_session = 0
        self._popfx = []   # pop particle effects

    def _place_keys(self):
        keys = []
        for i in range(self.remaining):
            zone = self._SAFE_ZONES[i % len(self._SAFE_ZONES)]
            for _ in range(200):
                x = random.randint(zone[0], zone[0] + zone[2])
                y = random.randint(zone[1], zone[1] + zone[3])
                if all(math.hypot(x - k["x"], y - k["y"]) > 110 for k in keys):
                    break
            keys.append({
                "x": float(x), "y": float(y),
                "alive": True,
                "bob_phase": random.uniform(0, math.tau),
                "spin": random.uniform(-1.5, 1.5),
                "angle": random.uniform(0, math.tau),
                "color": (255, 215, 40),
                "pulse": 0.0,
            })
        return keys

    def handle_click(self, pos):
        """Call from game's mouse click handler. Returns True if key was collected."""
        if not self._keys:
            return False
        mx, my = pos
        for k in self._keys:
            if not k["alive"]:
                continue
            if math.hypot(mx - k["x"], my - k["y"]) <= 24:
                k["alive"] = False
                k["pulse"] = 1.0
                self._collected_this_session += 1
                collect_clown_key(self.source)
                self._spawn_fx(k["x"], k["y"])
                return True
        return False

    def _spawn_fx(self, x, y):
        for _ in range(16):
            self._popfx.append({
                "x": x, "y": y,
                "vx": random.uniform(-180, 180),
                "vy": random.uniform(-240, 60),
                "life": random.uniform(0.4, 0.8),
                "t": 0.0,
                "size": random.randint(3, 7),
            })

    def update(self, dt):
        for k in self._keys:
            k["angle"] += k["spin"] * dt
        live = []
        for p in self._popfx:
            p["t"] += dt; p["x"] += p["vx"]*dt; p["y"] += p["vy"]*dt
            p["vy"] += 300*dt
            if p["t"] < p["life"]: live.append(p)
        self._popfx = live

    def draw(self, surf, anim_t):
        for k in self._keys:
            if not k["alive"]: continue
            bob = math.sin(anim_t * 2.8 + k["bob_phase"]) * 5
            cx, cy = int(k["x"]), int(k["y"] + bob)
            ang = k["angle"]
            col = k["color"]

            # Glow halo
            gs = pygame.Surface((72, 72), pygame.SRCALPHA)
            pulse_a = int(abs(math.sin(anim_t * 3.0 + k["bob_phase"])) * 45 + 20)
            pygame.draw.circle(gs, (255, 215, 40, pulse_a), (36, 36), 34)
            surf.blit(gs, (cx - 36, cy - 36))

            # Rotate helper
            def rv(px, py):
                c2, s2 = math.cos(ang), math.sin(ang)
                return (int(cx + c2*px - s2*py), int(cy + s2*px + c2*py))

            # Key bow (ring)
            pygame.draw.circle(surf, col, (cx, cy - 4), 13)
            pygame.draw.circle(surf, (30, 20, 0), (cx, cy - 4), 13, 2)
            pygame.draw.circle(surf, (255, 240, 140), (cx - 3, cy - 7), 4)  # shine
            # hole in bow
            pygame.draw.circle(surf, (20, 18, 12), (cx, cy - 4), 5)

            # Shank
            p1 = rv(0, 9); p2 = rv(0, 28)
            pygame.draw.line(surf, col, p1, p2, 5)
            pygame.draw.line(surf, (30, 20, 0), p1, p2, 1)
            # Teeth
            pygame.draw.line(surf, col, rv(5, 20), rv(9, 20), 4)
            pygame.draw.line(surf, col, rv(5, 26), rv(9, 26), 4)

        # Pop particles
        for p in self._popfx:
            frac = 1.0 - p["t"]/p["life"]
            a = int(220 * frac)
            ps = pygame.Surface((p["size"]*2, p["size"]*2), pygame.SRCALPHA)
            pygame.draw.circle(ps, (255, 215, 40, a), (p["size"], p["size"]), p["size"])
            surf.blit(ps, (int(p["x"]) - p["size"], int(p["y"]) - p["size"]))

    def draw_hud(self, surf, anim_t):
        """Draw the key counter badge (top-right area)."""
        _, total = get_clown_keys()
        if is_clown_unlocked():
            return  # already unlocked, no need
        cap = CLOWN_KEY_SOURCES.get(self.source, 0)
        ck, _ = get_clown_keys()
        src_got = ck.get(self.source, 0)
        src_cap = cap

        bx, by = SCREEN_W - 310, 6
        bw, bh = 182, 34
        draw_rect_alpha(surf, (10, 8, 20), (bx, by, bw, bh), 200, brad=10)
        pygame.draw.rect(surf, (200, 170, 30), (bx, by, bw, bh), 1, border_radius=10)

        # Key icon
        kf = pygame.font.SysFont("consolas", 13, bold=True)
        txt(surf, f"Keys: {total}/{CLOWN_KEYS_TOTAL}",
            (bx + bw//2, by + bh//2), (255, 215, 40), kf, center=True)

    def all_collected(self):
        return all(not k["alive"] for k in self._keys) if self._keys else True


# ── Clown Boss Arena ───────────────────────────────────────────────────────────
class ClownBossArena:
    """
    Clown Boss Arena — переработанный бой.

    Новые механики:
      - 4 живых + 5 сердечек игрока
      - Щит (фаза 2+): нельзя бить босса пока щит активен — надо кликнуть 3 щита вокруг
      - Телепортация (фаза 2+): босс внезапно мигает в другую точку
      - Призыв миньонов (фаза 2+): маленькие кружки летят к курсору
      - Предупреждения AoE: красные зоны на земле — надо уйти за ~1 сек
      - Орбитальные снаряды (фаза 3): 6 снарядов вращаются вокруг босса
      - Дэш: пробел — короткий рывок в направлении мыши, 2-сек кулдаун
      - Паттерны атак меняются на каждой фазе
    """

    BOSS_MAX_HP   = 2400
    PLAYER_LIVES  = 5
    BOSS_RADIUS   = 52
    DMG_PER_CLICK = 45

    PATROL_PTS = [
        (300, 250), (960, 180), (1620, 250),
        (1700, 540), (1620, 840), (960, 900),
        (300, 840), (200, 540),
    ]
    PROJ_COLORS = [(220,60,60),(255,200,50),(60,220,220),(180,80,255),(255,140,40),(255,80,180)]

    def __init__(self, screen):
        self.screen = screen
        self.clock  = pygame.time.Clock()
        # Кэшируем полноэкранные SRCALPHA-поверхности — не создаём каждый кадр
        self._flash_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self._rage_surf  = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self._dash_surf  = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        # Кэш фона арены — пересчитывается только при изменении фазы
        self._arena_bg_cache = None
        self._arena_bg_phase = -1
        self._reset()

    # ─────────────────────────────────────────────────────────────────────────
    def _reset(self):
        self.anim_t   = 0.0
        self.state    = "playing"
        self.boss_hp  = self.BOSS_MAX_HP
        self.lives    = self.PLAYER_LIVES
        self._hit_flash   = 0.0
        self._life_flash  = 0.0
        self._particles   = []
        self._projectiles = []   # стандартные снаряды
        self._minions     = []   # миньоны (фаза 2+)
        self._aoe_warnings = []  # предупреждающие зоны {x,y,r,t,max_t}
        self._orbitals    = []   # орбитальные снаряды (фаза 3)

        # Щит
        self._shield_active      = False
        self._shield_shards      = []   # 3 кружка-щита, каждый dict {angle, alive}
        self._shield_cd          = 0.0  # до следующего появления щита
        self._shield_broken_once = False  # после первого разрушения щит не возрождается

        # Телепорт
        self._tele_cd    = 0.0
        self._tele_flash = 0.0   # белая вспышка при телепорте
        self._p1_inside_boss_t = 0.0  # фаза 1: время нахождения курсора внутри босса

        # Движение босса
        self._patrol_idx = 0
        tx, ty = self.PATROL_PTS[0]
        self._boss_x = float(tx)
        self._boss_y = float(ty)

        # Атака
        self._atk_cd = 0.0
        self._atk_pattern = 0   # чередование паттернов

        # Фаза
        self._phase = 1
        self._phase_announced = 0

        # Дэш игрока
        self._dash_cd   = 0.0
        self._dash_vx   = 0.0
        self._dash_vy   = 0.0
        self._dash_t    = 0.0   # оставшееся время дэша
        self._cursor_x  = float(SCREEN_W // 2)
        self._cursor_y  = float(SCREEN_H // 2)

        # Конец боя
        self._end_t = 0.0

        # ── НОВЫЕ СПОСОБНОСТИ ────────────────────────────────────────────────
        # Зеркальный снаряд (фаза 1+): снаряды отражаются от стен
        self._mirror_cd = 0.0

        # Карточный бросок (фаза 1+): веер «карт»-снарядов
        self._card_cd = 0.0

        # Лазерный луч (фаза 2+)
        self._laser_active = False
        self._laser_angle  = 0.0
        self._laser_t      = 0.0     # время активности луча
        self._laser_cd     = 0.0
        self._laser_warn_t = 0.0     # предупреждение перед лазером
        self._laser_warn_angle = 0.0

        # Бомбы-клоуны (фаза 2+)
        self._bombs        = []      # [{x,y,vx,vy,t,alive}]
        self._bomb_cd      = 0.0

        # Гравитационный притяг (фаза 3)
        self._gravity_active = False
        self._gravity_t    = 0.0
        self._gravity_cd   = 0.0

        # Финальный взрыв (фаза 3, 1 раз)
        self._nova_fired   = False
        self._nova_t       = 0.0    # анимация вспышки
        self._nova_warn_t  = 0.0    # предупреждение

    # ── хелперы фаз ──────────────────────────────────────────────────────────
    @property
    def _hp_frac(self):
        return max(0.0, self.boss_hp / self.BOSS_MAX_HP)

    def _get_phase(self):
        if self._hp_frac > 0.55: return 1
        if self._hp_frac > 0.22: return 2
        return 3

    def _boss_speed(self):
        return {1: 145, 2: 220, 3: 320}[self._get_phase()]

    def _atk_interval(self):
        return {1: 2.2, 2: 1.4, 3: 0.9}[self._get_phase()]

    # ── частицы ──────────────────────────────────────────────────────────────
    def _spawn_particles(self, x, y, color, n=20, big=False):
        for _ in range(n):
            spd = random.uniform(200, 440) if big else random.uniform(90, 280)
            self._particles.append({
                "x": float(x), "y": float(y),
                "vx": random.uniform(-spd, spd),
                "vy": random.uniform(-spd*1.2, spd*0.3),
                "color": color,
                "life": random.uniform(0.4, 0.9),
                "t": 0.0,
                "size": random.randint(5, 14) if big else random.randint(3, 7),
            })

    def _update_particles(self, dt):
        live = []
        for p in self._particles:
            p["t"] += dt; p["x"] += p["vx"]*dt; p["y"] += p["vy"]*dt
            p["vy"] += 380*dt
            if p["t"] < p["life"]: live.append(p)
        self._particles = live

    def _draw_particles(self, surf):
        for p in self._particles:
            frac = 1.0 - p["t"]/p["life"]
            a = int(255*frac); sz = p["size"]
            # Рисуем через set_alpha вместо создания SRCALPHA Surface каждый кадр
            ps = pygame.Surface((sz*2, sz*2), pygame.SRCALPHA)
            pygame.draw.circle(ps, (*p["color"][:3], a), (sz, sz), sz)
            surf.blit(ps, (int(p["x"])-sz, int(p["y"])-sz))

    # ── снаряды ──────────────────────────────────────────────────────────────
    def _fire_volley(self, tx, ty, pattern=0):
        bx, by = self._boss_x, self._boss_y
        base = math.atan2(ty - by, tx - bx)
        ph = self._get_phase()

        if pattern == 0:
            # Стандартный веер
            n = {1:4, 2:7, 3:10}[ph]
            spread = math.pi / 4
            for i in range(n):
                a = base - spread/2 + spread * i / max(1, n-1)
                spd = random.uniform(280, 380)
                self._add_proj(bx, by, a, spd)

        elif pattern == 1:
            # Круговой залп
            n = {1:8, 2:12, 3:16}[ph]
            for i in range(n):
                a = math.pi*2 * i / n
                self._add_proj(bx, by, a, 260)

        elif pattern == 2:
            # Тройной поток по курсору
            for off in (-0.18, 0, 0.18):
                a = base + off
                for k in range(3):
                    spd = 260 + k*60
                    self._add_proj(bx + math.cos(a)*20*k, by + math.sin(a)*20*k, a, spd)

        elif pattern == 3:
            # Спираль (фаза 3)
            n = 24
            for i in range(n):
                a = base + math.pi*2 * i / n + self.anim_t*2
                spd = 180 + i*8
                self._add_proj(bx, by, a, spd)

    def _add_proj(self, bx, by, angle, spd, r=10, homing=False):
        self._projectiles.append({
            "x": bx + math.cos(angle)*64,
            "y": by + math.sin(angle)*64,
            "vx": math.cos(angle)*spd,
            "vy": math.sin(angle)*spd,
            "color": random.choice(self.PROJ_COLORS),
            "r": r, "alive": True, "t": 0.0,
            "homing": homing,
            "bounces": 0,   # количество отражений от стен
        })

    # ── Зеркальный снаряд: отражается от стен ────────────────────────────────
    def _fire_mirror_volley(self, cx, cy):
        """Пускает снаряды которые отражаются от краёв экрана (до 2 раз)."""
        bx, by = self._boss_x, self._boss_y
        ph = self._get_phase()
        n = {1: 5, 2: 8, 3: 12}[ph]
        for i in range(n):
            a = math.pi * 2 * i / n
            spd = random.uniform(220, 320)
            p = {
                "x": bx + math.cos(a)*64, "y": by + math.sin(a)*64,
                "vx": math.cos(a)*spd, "vy": math.sin(a)*spd,
                "color": (100, 220, 255),
                "r": 9, "alive": True, "t": 0.0,
                "homing": False, "bounces": 2,   # ← будет отражаться 2 раза
            }
            self._projectiles.append(p)

    # ── Карточный бросок ─────────────────────────────────────────────────────
    def _fire_card_throw(self, cx, cy):
        """Веер «карт»-снарядов (вытянутых ромбов) к курсору."""
        bx, by = self._boss_x, self._boss_y
        ph = self._get_phase()
        base = math.atan2(cy - by, cx - bx)
        n = {1: 7, 2: 11, 3: 15}[ph]
        spread = math.pi / 3
        for i in range(n):
            a = base - spread/2 + spread * i / max(1, n-1)
            spd = random.uniform(300, 420)
            self._projectiles.append({
                "x": bx + math.cos(a)*60, "y": by + math.sin(a)*60,
                "vx": math.cos(a)*spd, "vy": math.sin(a)*spd,
                "color": (255, 215, 50),
                "r": 8, "alive": True, "t": 0.0,
                "homing": False, "bounces": 0, "card": True,
            })

    # ── Лазерный луч ─────────────────────────────────────────────────────────
    def _update_laser(self, dt, cx, cy):
        if self._laser_warn_t > 0:
            self._laser_warn_t -= dt
            if self._laser_warn_t <= 0:
                self._laser_active = True
                self._laser_t = 2.0   # луч активен 2 сек
        if self._laser_active:
            self._laser_t -= dt
            self._laser_angle += (1.8 if self._get_phase() == 3 else 1.2) * dt
            # проверяем попадание по игроку
            lx = self._boss_x + math.cos(self._laser_angle) * 2000
            ly = self._boss_y + math.sin(self._laser_angle) * 2000
            # точка ближайшая к курсору на луче
            dx = lx - self._boss_x; dy = ly - self._boss_y
            dl = math.hypot(dx, dy) or 1
            t_proj = ((cx - self._boss_x)*dx + (cy - self._boss_y)*dy) / (dl*dl)
            t_proj = max(0.0, min(1.0, t_proj))
            closest_x = self._boss_x + t_proj*dx
            closest_y = self._boss_y + t_proj*dy
            if math.hypot(cx - closest_x, cy - closest_y) < 18:
                self._take_damage(cx, cy)
            if self._laser_t <= 0:
                self._laser_active = False
                self._laser_cd = {2: 9.0, 3: 6.0}.get(self._get_phase(), 9.0)

    def _draw_laser(self, surf):
        # Предупреждение
        if self._laser_warn_t > 0 and not self._laser_active:
            frac = 1.0 - self._laser_warn_t / 1.5
            alpha = int(80 + 100*abs(math.sin(frac*math.pi*6)))
            end_x = self._boss_x + math.cos(self._laser_warn_angle)*2000
            end_y = self._boss_y + math.sin(self._laser_warn_angle)*2000
            warn_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(warn_s, (255,80,20,alpha),
                             (int(self._boss_x), int(self._boss_y)),
                             (int(end_x), int(end_y)), 8)
            surf.blit(warn_s, (0,0))
        # Луч
        if self._laser_active:
            end_x = self._boss_x + math.cos(self._laser_angle)*2000
            end_y = self._boss_y + math.sin(self._laser_angle)*2000
            ls = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(ls, (255,60,60,160),
                             (int(self._boss_x), int(self._boss_y)),
                             (int(end_x), int(end_y)), 22)
            pygame.draw.line(ls, (255,220,220,220),
                             (int(self._boss_x), int(self._boss_y)),
                             (int(end_x), int(end_y)), 6)
            surf.blit(ls, (0,0))

    # ── Бомбы-клоуны ─────────────────────────────────────────────────────────
    def _spawn_bombs(self, cx, cy):
        ph = self._get_phase()
        n = {2: 3, 3: 5}[ph]
        for i in range(n):
            a = math.pi*2*i/n + random.uniform(0, 0.4)
            r = random.uniform(180, 300)
            spd = random.uniform(160, 240)
            dx = cx - (self._boss_x + math.cos(a)*r)
            dy = cy - (self._boss_y + math.sin(a)*r)
            dl = math.hypot(dx, dy) or 1
            self._bombs.append({
                "x": self._boss_x + math.cos(a)*r,
                "y": self._boss_y + math.sin(a)*r,
                "vx": dx/dl*spd, "vy": dy/dl*spd,
                "alive": True, "t": 0.0,
            })

    def _update_bombs(self, dt, cx, cy):
        live = []
        for b in self._bombs:
            if not b["alive"]: continue
            b["t"] += dt
            b["x"] += b["vx"]*dt; b["y"] += b["vy"]*dt
            if b["x"] < -80 or b["x"] > SCREEN_W+80 or b["y"] < -80 or b["y"] > SCREEN_H+80:
                continue
            if math.hypot(b["x"]-cx, b["y"]-cy) < 24:
                b["alive"] = False
                self._take_damage(cx, cy)
                self._spawn_particles(int(b["x"]), int(b["y"]), (255,160,30), n=20, big=True)
                continue
            live.append(b)
        self._bombs = live

    def _draw_bombs(self, surf):
        for b in self._bombs:
            bx, by = int(b["x"]), int(b["y"])
            pulse = 14 + int(math.sin(b["t"]*12)*4)
            pygame.draw.circle(surf, (255, 140, 20), (bx, by), pulse)
            pygame.draw.circle(surf, (255, 255, 80), (bx, by), pulse, 3)
            # мини-клоунская шляпа
            hat_pts = [(bx-8, by-pulse), (bx+8, by-pulse),
                       (bx+5, by-pulse-14), (bx-5, by-pulse-14)]
            pygame.draw.polygon(surf, (20,20,20), hat_pts)
            pygame.draw.polygon(surf, (255,80,80), hat_pts, 2)
            # таймер (через 5 сек взрываются сами)
            if b["t"] > 3.5:
                fuse_alpha = int(200 + 55*math.sin(b["t"]*20))
                fs = pygame.Surface((30,14), pygame.SRCALPHA)
                ff = pygame.font.SysFont("consolas", 10, bold=True)
                ft = ff.render("BOOM!", True, (255,50,50,fuse_alpha))
                surf.blit(ft, (bx-ft.get_width()//2, by-pulse-22))

    # ── Гравитационный притяг (фаза 3) ───────────────────────────────────────
    def _update_gravity(self, dt, cx, cy):
        if not self._gravity_active:
            return cx, cy
        self._gravity_t -= dt
        dx = self._boss_x - cx; dy = self._boss_y - cy
        d = math.hypot(dx, dy) or 1
        pull = 380 * dt   # пикселей/сек тяги
        new_cx = cx + dx/d * pull
        new_cy = cy + dy/d * pull
        if self._gravity_t <= 0:
            self._gravity_active = False
            self._gravity_cd = 10.0
        return new_cx, new_cy

    def _draw_gravity(self, surf):
        if not self._gravity_active:
            return
        frac = self._gravity_t / 3.0
        for ring_r in range(80, 320, 60):
            alpha = int(60 * frac)
            gs = pygame.Surface((ring_r*2+4, ring_r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(gs, (180, 80, 255, alpha),
                               (ring_r+2, ring_r+2), ring_r, 4)
            surf.blit(gs, (int(self._boss_x)-ring_r-2, int(self._boss_y)-ring_r-2))

    # ── Финальный взрыв (фаза 3, однократно) ─────────────────────────────────
    def _trigger_nova(self):
        self._nova_warn_t = 2.0
        self._nova_t = 0.0

    def _update_nova(self, dt, cx, cy):
        if self._nova_warn_t > 0:
            self._nova_warn_t -= dt
            if self._nova_warn_t <= 0:
                # Взрыв: урон если далеко от центра (<200px — безопасная зона)
                d = math.hypot(cx - self._boss_x, cy - self._boss_y)
                if d > 200:
                    self._take_damage(cx, cy)
                self._nova_t = 0.5
                self._spawn_particles(int(self._boss_x), int(self._boss_y),
                                      (255, 200, 50), n=80, big=True)
                # Взрывная волна снарядов
                for i in range(20):
                    a = math.pi*2*i/20
                    self._projectiles.append({
                        "x": self._boss_x + math.cos(a)*80,
                        "y": self._boss_y + math.sin(a)*80,
                        "vx": math.cos(a)*300, "vy": math.sin(a)*300,
                        "color": (255, 220, 50),
                        "r": 11, "alive": True, "t": 0.0,
                        "homing": False, "bounces": 1,
                    })
        if self._nova_t > 0:
            self._nova_t -= dt

    def _draw_nova_warning(self, surf):
        if self._nova_warn_t <= 0 and self._nova_t <= 0:
            return
        if self._nova_warn_t > 0:
            frac = 1.0 - self._nova_warn_t / 2.0
            alpha = int(60 + 80*abs(math.sin(frac*math.pi*8)))
            # безопасная зона
            safe_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.circle(safe_s, (80, 255, 120, alpha//2),
                               (int(self._boss_x), int(self._boss_y)), 200)
            pygame.draw.circle(safe_s, (255, 80, 20, alpha),
                               (int(self._boss_x), int(self._boss_y)), 200, 4)
            surf.blit(safe_s, (0,0))
            nf = pygame.font.SysFont("consolas", 20, bold=True)
            wt = nf.render("⚠ NOVA — GET CLOSE!", True, (255, 240, 80))
            wt.set_alpha(alpha+80)
            surf.blit(wt, (SCREEN_W//2 - wt.get_width()//2, SCREEN_H//2 - 60))
        elif self._nova_t > 0:
            frac = self._nova_t / 0.5
            ns = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ns.fill((255, 200, 50, int(180*frac)))
            surf.blit(ns, (0,0))

    def _update_projectiles(self, dt, cx, cy):
        live = []
        for p in self._projectiles:
            if not p["alive"]: continue
            if p["homing"]:
                # слабое наведение
                dx = cx - p["x"]; dy = cy - p["y"]
                d = math.hypot(dx, dy) or 1
                spd = math.hypot(p["vx"], p["vy"])
                p["vx"] += dx/d * spd * 1.2 * dt
                p["vy"] += dy/d * spd * 1.2 * dt
                # нормализуем скорость
                s = math.hypot(p["vx"], p["vy"]) or 1
                p["vx"] = p["vx"]/s * spd
                p["vy"] = p["vy"]/s * spd
            p["x"] += p["vx"]*dt; p["y"] += p["vy"]*dt; p["t"] += dt
            # Отражение от стен
            bounces = p.get("bounces", 0)
            if bounces > 0:
                if p["x"] < p["r"] or p["x"] > SCREEN_W - p["r"]:
                    p["vx"] = -p["vx"]; p["bounces"] -= 1
                    p["x"] = max(p["r"], min(SCREEN_W - p["r"], p["x"]))
                if p["y"] < p["r"] or p["y"] > SCREEN_H - p["r"]:
                    p["vy"] = -p["vy"]; p["bounces"] -= 1
                    p["y"] = max(p["r"], min(SCREEN_H - p["r"], p["y"]))
            if p.get("bounces", 0) == 0 and (p["x"] < -60 or p["x"] > SCREEN_W+60 or p["y"] < -60 or p["y"] > SCREEN_H+60):
                continue
            if math.hypot(p["x"] - cx, p["y"] - cy) < p["r"] + 16:
                p["alive"] = False
                self._take_damage(cx, cy)
                continue
            live.append(p)
        self._projectiles = live

    def _draw_projectiles(self, surf):
        # Кэш glow-поверхностей по радиусу (r -> Surface)
        if not hasattr(self, "_proj_glow_cache"):
            self._proj_glow_cache = {}
        for p in self._projectiles:
            cx, cy = int(p["x"]), int(p["y"]); r = p["r"]
            # Glow-кружок (переиспользуем если радиус тот же)
            if r not in self._proj_glow_cache:
                ts = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
                pygame.draw.circle(ts, (255, 255, 255, 55), (r*2, r*2), r*2)
                self._proj_glow_cache[r] = ts
            ts = self._proj_glow_cache[r]
            surf.blit(ts, (cx-r*2, cy-r*2))
            pygame.draw.circle(surf, p["color"], (cx, cy), r)
            pygame.draw.circle(surf, (255,255,255), (cx, cy), r, 2)
            ang = p["t"]*8
            sx = cx + int(math.cos(ang)*(r-3)); sy = cy + int(math.sin(ang)*(r-3))
            pygame.draw.circle(surf, (255,255,255), (sx, sy), 2)

    # ── миньоны ──────────────────────────────────────────────────────────────
    def _spawn_minions(self, cx, cy, n=4):
        for i in range(n):
            a = math.pi*2 * i / n + random.uniform(0, 0.5)
            r = random.uniform(200, 350)
            self._minions.append({
                "x": self._boss_x + math.cos(a)*r,
                "y": self._boss_y + math.sin(a)*r,
                "vx": 0.0, "vy": 0.0,
                "alive": True, "t": 0.0,
                "hp": 1,
            })

    def _update_minions(self, dt, cx, cy):
        live = []
        for m in self._minions:
            if not m["alive"]: continue
            m["t"] += dt
            # движутся к курсору
            dx = cx - m["x"]; dy = cy - m["y"]
            d = math.hypot(dx, dy) or 1
            spd = 200
            m["vx"] += dx/d * spd * dt * 3
            m["vy"] += dy/d * spd * dt * 3
            s = math.hypot(m["vx"], m["vy"]) or 1
            m["vx"] = m["vx"]/s * spd
            m["vy"] = m["vy"]/s * spd
            m["x"] += m["vx"]*dt; m["y"] += m["vy"]*dt
            if m["x"] < -80 or m["x"] > SCREEN_W+80 or m["y"] < -80 or m["y"] > SCREEN_H+80:
                continue
            if math.hypot(m["x"] - cx, m["y"] - cy) < 20:
                m["alive"] = False
                self._take_damage(cx, cy)
                self._spawn_particles(int(m["x"]), int(m["y"]), (255,80,80), n=8)
                continue
            live.append(m)
        self._minions = live

    def _draw_minions(self, surf):
        if not hasattr(self, "_minion_glow_cache"):
            self._minion_glow_cache = {}
        for m in self._minions:
            mx, my = int(m["x"]), int(m["y"])
            pulse = 10 + int(math.sin(m["t"]*8)*3)
            sz = pulse*2
            if sz not in self._minion_glow_cache:
                gs = pygame.Surface((sz*2, sz*2), pygame.SRCALPHA)
                pygame.draw.circle(gs, (255,80,200,50), (sz, sz), sz)
                self._minion_glow_cache[sz] = gs
            gs = self._minion_glow_cache[sz]
            surf.blit(gs, (mx-sz, my-sz))
            pygame.draw.circle(surf, (255,80,200), (mx, my), pulse)
            pygame.draw.circle(surf, (255,255,255), (mx, my), pulse, 2)

    # ── AoE предупреждения ───────────────────────────────────────────────────
    def _spawn_aoe(self, x, y, r, delay=1.0):
        self._aoe_warnings.append({"x": x, "y": y, "r": r, "t": 0.0, "max_t": delay, "fired": False})

    def _update_aoe(self, dt, cx, cy):
        live = []
        for a in self._aoe_warnings:
            a["t"] += dt
            if not a["fired"] and a["t"] >= a["max_t"]:
                a["fired"] = True
                # взрыв
                self._spawn_particles(int(a["x"]), int(a["y"]), (255,140,30), n=25, big=True)
                if math.hypot(cx - a["x"], cy - a["y"]) < a["r"] - 10:
                    self._take_damage(cx, cy)
            if a["t"] < a["max_t"] + 0.18:
                live.append(a)
        self._aoe_warnings = live

    def _draw_aoe(self, surf):
        if not hasattr(self, "_aoe_surf_cache"):
            self._aoe_surf_cache = {}
        for a in self._aoe_warnings:
            if a["fired"]: continue
            frac = a["t"] / a["max_t"]
            r = int(a["r"])
            alpha = int(80 + 100 * abs(math.sin(frac * math.pi * 5)))
            # Кольцо предупреждения
            key = r
            if key not in self._aoe_surf_cache:
                sz = r*2+4
                self._aoe_surf_cache[key] = pygame.Surface((sz, sz), pygame.SRCALPHA)
            gs = self._aoe_surf_cache[key]
            gs.fill((0,0,0,0))
            pygame.draw.circle(gs, (255, 80, 20, alpha//2), (r+2, r+2), r)
            pygame.draw.circle(gs, (255, 80, 20, alpha), (r+2, r+2), r, 3)
            surf.blit(gs, (int(a["x"])-r-2, int(a["y"])-r-2))
            # заполнение по времени
            fill_r = int(r * frac)
            if fill_r > 0:
                fkey = fill_r
                if fkey not in self._aoe_surf_cache:
                    sz2 = fill_r*2
                    self._aoe_surf_cache[fkey] = pygame.Surface((sz2, sz2), pygame.SRCALPHA)
                fs = self._aoe_surf_cache[fkey]
                fs.fill((0,0,0,0))
                pygame.draw.circle(fs, (255,120,20, 35), (fill_r, fill_r), fill_r)
                surf.blit(fs, (int(a["x"])-fill_r, int(a["y"])-fill_r))

    # ── орбитальные снаряды (фаза 3) ─────────────────────────────────────────
    def _init_orbitals(self):
        n = 4  # было 6 — меньше орбиталей, можно найти окно
        self._orbitals = [{"angle": math.pi*2*i/n, "r": 75, "spd": 2.0} for i in range(n)]  # радиус 75 вместо 110, скорость 2.0 вместо 2.8

    def _update_orbitals(self, dt, cx, cy):
        for o in self._orbitals:
            o["angle"] += o["spd"] * dt
            ox = self._boss_x + math.cos(o["angle"]) * o["r"]
            oy = self._boss_y + math.sin(o["angle"]) * o["r"]
            if math.hypot(ox - cx, oy - cy) < 14:
                self._take_damage(cx, cy)
                o["angle"] += math.pi   # отпрыгнуть назад

    def _draw_orbitals(self, surf):
        for o in self._orbitals:
            ox = int(self._boss_x + math.cos(o["angle"]) * o["r"])
            oy = int(self._boss_y + math.sin(o["angle"]) * o["r"])
            gs = pygame.Surface((36, 36), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255,200,50,80), (18,18), 18)
            surf.blit(gs, (ox-18, oy-18))
            pygame.draw.circle(surf, (255,200,50), (ox,oy), 11)
            pygame.draw.circle(surf, (255,255,255), (ox,oy), 11, 2)
            # искра
            sx = ox + int(math.cos(o["angle"]+math.pi/2)*7)
            sy = oy + int(math.sin(o["angle"]+math.pi/2)*7)
            pygame.draw.circle(surf, (255,255,180), (sx,sy), 3)

    # ── щит ──────────────────────────────────────────────────────────────────
    def _activate_shield(self):
        self._shield_active = True
        n = 3
        self._shield_shards = [{"angle": math.pi*2*i/n, "alive": True} for i in range(n)]

    def _draw_shield(self, surf):
        if not self._shield_active: return
        bx, by = int(self._boss_x), int(self._boss_y)
        # полупрозрачный купол — используем кэшированную поверхность
        if not hasattr(self, "_shield_dome_surf"):
            self._shield_dome_surf = pygame.Surface((260, 260), pygame.SRCALPHA)
        gs = self._shield_dome_surf
        gs.fill((0,0,0,0))
        a = int(40 + 20*abs(math.sin(self.anim_t*4)))
        pygame.draw.circle(gs, (80,180,255,a), (130,130), 130)
        pygame.draw.circle(gs, (80,180,255,160), (130,130), 130, 3)
        surf.blit(gs, (bx-130, by-130))
        # осколки щита
        for sh in self._shield_shards:
            if not sh["alive"]: continue
            sh["angle"] += 1.8 * (1/60)
            sx = bx + int(math.cos(sh["angle"]) * 105)
            sy = by + int(math.sin(sh["angle"]) * 105)
            pygame.draw.circle(surf, (140, 220, 255), (sx, sy), 16)
            pygame.draw.circle(surf, (255,255,255), (sx, sy), 16, 2)
            pygame.draw.line(surf, (255,255,120), (sx-5,sy-8),(sx,sy), 2)
            pygame.draw.line(surf, (255,255,120), (sx,sy),(sx+5,sy+8), 2)

    def _update_shield(self, dt):
        if not self._shield_active: return
        # обновляем углы осколков
        for sh in self._shield_shards:
            if sh["alive"]:
                sh["angle"] += 1.8 * dt
        # если все осколки уничтожены — щит снят навсегда
        if all(not sh["alive"] for sh in self._shield_shards):
            self._shield_active      = False
            self._shield_broken_once = True   # больше не появится
            self._shield_cd = 999999.0        # не триггерим повторно
            self._spawn_particles(int(self._boss_x), int(self._boss_y), (80,200,255), n=30, big=True)

    def _try_click_shield(self, mx, my):
        """Клик попал в осколок щита? Возвращает True если попал."""
        bx, by = self._boss_x, self._boss_y
        for sh in self._shield_shards:
            if not sh["alive"]: continue
            sx = bx + math.cos(sh["angle"]) * 105
            sy = by + math.sin(sh["angle"]) * 105
            if math.hypot(mx - sx, my - sy) < 20:
                sh["alive"] = False
                self._spawn_particles(int(sx), int(sy), (140,220,255), n=14)
                return True
        return False

    # ── телепорт ─────────────────────────────────────────────────────────────
    def _do_teleport(self):
        pts = [p for p in self.PATROL_PTS
               if math.hypot(p[0]-self._boss_x, p[1]-self._boss_y) > 300]
        if not pts:
            pts = self.PATROL_PTS
        tx, ty = random.choice(pts)
        self._spawn_particles(int(self._boss_x), int(self._boss_y), (200,80,255), n=30, big=True)
        self._boss_x, self._boss_y = float(tx), float(ty)
        self._tele_flash = 0.22
        self._spawn_particles(int(tx), int(ty), (255,200,80), n=30, big=True)

    # ── урон игроку ──────────────────────────────────────────────────────────
    def _take_damage(self, cx, cy):
        self.lives -= 1
        self._life_flash = 0.45
        self._spawn_particles(int(cx), int(cy), (220,60,60), n=14)
        if self.lives <= 0:
            self.state = "lose"

    # ── движение босса ───────────────────────────────────────────────────────
    def _update_boss(self, dt):
        spd = self._boss_speed()
        tx, ty = self.PATROL_PTS[self._patrol_idx]
        dx = tx - self._boss_x; dy = ty - self._boss_y
        d = math.hypot(dx, dy)
        if d < 14:
            self._patrol_idx = (self._patrol_idx + 1) % len(self.PATROL_PTS)
        else:
            self._boss_x += dx/d * spd * dt
            self._boss_y += dy/d * spd * dt
        if self._hit_flash > 0:
            self._hit_flash = max(0.0, self._hit_flash - dt)

    # ── фоновый рисунок арены ────────────────────────────────────────────────
    def _draw_arena(self, surf):
        # Статичный фон (полигоны + spot) — кэшируется, рисуется один раз
        if self._arena_bg_cache is None:
            bg = pygame.Surface((SCREEN_W, SCREEN_H))
            draw_rect_gradient(bg, (8, 5, 18), (16, 10, 30), (0, 0, SCREEN_W, SCREEN_H), alpha=255)
            cx2, cy2 = SCREEN_W//2, SCREEN_H//2
            for i in range(12):
                a1 = math.radians(i*30)
                a2 = math.radians(i*30 + 15)
                col = (35, 10, 10) if i % 2 == 0 else (10, 8, 30)
                pts = [
                    (cx2, cy2),
                    (int(cx2 + math.cos(a1)*1400), int(cy2 + math.sin(a1)*1400)),
                    (int(cx2 + math.cos(a2)*1400), int(cy2 + math.sin(a2)*1400)),
                ]
                pygame.draw.polygon(bg, col, pts)
            # Arena ring drawn dynamically in _draw_arena_ring() below
            spot_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            for r2 in range(500, 0, -20):
                a2 = max(0, int(8 * (1 - r2/500)))
                pygame.draw.circle(spot_surf, (255, 240, 200, a2), (cx2, -80), r2 + 580)
            bg.blit(spot_surf, (0, 0))
            self._arena_bg_cache = bg
        surf.blit(self._arena_bg_cache, (0, 0))

        # Анимированное кольцо арены (пульсирует, руны, краснеет когда босс внутри)
        self._draw_arena_ring(surf)

        # Анимированные огни вверху (лёгкие — только 20 кружков)
        for i in range(20):
            lx = int(SCREEN_W * i / 19)
            ly = 30 + int(math.sin(self.anim_t*1.5 + i*0.7)*8)
            pygame.draw.line(surf, (80, 70, 60), (lx, 0), (lx, ly+10), 1)
            col_b = self.PROJ_COLORS[i % len(self.PROJ_COLORS)]
            pygame.draw.circle(surf, col_b, (lx, ly), 7)
            pygame.draw.circle(surf, (255,255,255), (lx-2, ly-2), 2)

    # ── анимированное кольцо арены ───────────────────────────────────────────
    def _draw_arena_ring(self, surf):
        """
        Кольцо арены — не просто декор.
        • Пульсирует фиолетовым в норме
        • Краснеет + усиливает пульсацию если БОСС ВНУТРИ кольца (R=520)
          → игрок видит: «босс в центре — опаснее!»
        • По кольцу вращаются 8 рун (★) — маркеры арены
        """
        RING_R = 520
        cx2, cy2 = SCREEN_W // 2, SCREEN_H // 2

        boss_inside = math.hypot(self._boss_x - cx2, self._boss_y - cy2) < RING_R

        # Пульсация: медленная в норме, быстрая и крупная когда босс внутри
        pulse_speed = 4.0 if boss_inside else 2.0
        pulse_amp   = 8   if boss_inside else 3
        pulse = math.sin(self.anim_t * pulse_speed) * pulse_amp

        # Цвет кольца
        if boss_inside:
            phase = self._get_phase()
            if phase == 3:
                ring_col  = (255, 60, 60)
                glow_col  = (220, 40, 40)
            elif phase == 2:
                ring_col  = (255, 120, 40)
                glow_col  = (200, 80, 20)
            else:
                ring_col  = (255, 80, 80)
                glow_col  = (180, 40, 40)
        else:
            ring_col = (80, 50, 120)
            glow_col = (60, 30, 100)

        # Внешнее свечение (3 полупрозрачных кольца)
        ring_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for width, alpha in [(18, 18), (10, 35), (5, 70)]:
            r_draw = int(RING_R + pulse)
            pygame.draw.circle(ring_surf, (*glow_col, alpha), (cx2, cy2), r_draw, width)
        surf.blit(ring_surf, (0, 0))

        # Основное кольцо
        pygame.draw.circle(surf, ring_col, (cx2, cy2), int(RING_R + pulse), 3)
        pygame.draw.circle(surf, (min(255, ring_col[0]+60), min(255, ring_col[1]+40), min(255, ring_col[2]+60)),
                           (cx2, cy2), int(RING_R + pulse), 1)

        # 8 вращающихся рун-маркеров по кольцу
        n_runes = 8
        rune_chars = ["★", "◆", "★", "◆", "★", "◆", "★", "◆"]
        rune_font = pygame.font.SysFont("segoe ui symbol", 13, bold=True)
        spin = self.anim_t * (0.6 if boss_inside else 0.25)
        for i in range(n_runes):
            a = math.pi * 2 * i / n_runes + spin
            rx = cx2 + int(math.cos(a) * (RING_R + pulse))
            ry = cy2 + int(math.sin(a) * (RING_R + pulse))
            rune_col = (255, 100, 100) if boss_inside else (140, 90, 200)
            rune_surf2 = rune_font.render(rune_chars[i], True, rune_col)
            rw2, rh2 = rune_surf2.get_size()
            surf.blit(rune_surf2, (rx - rw2 // 2, ry - rh2 // 2))

        # Предупреждающий текст если босс внутри
        if boss_inside:
            warn_alpha = int(180 + math.sin(self.anim_t * 6) * 75)
            warn_alpha = max(0, min(255, warn_alpha))
            wf = pygame.font.SysFont("consolas", 14, bold=True)
            warn_surf = wf.render("⚠ BOSS IN ARENA CENTER", True, (255, 120, 80))
            warn_surf.set_alpha(warn_alpha)
            surf.blit(warn_surf, (cx2 - warn_surf.get_width() // 2, cy2 + RING_R + 14))

    # ── спрайт босса ─────────────────────────────────────────────────────────
    def _draw_boss_sprite(self, surf):
        bx, by = int(self._boss_x), int(self._boss_y)
        r = self.BOSS_RADIUS
        phase = self._get_phase()
        hp_frac = self._hp_frac

        if self._hit_flash > 0:
            body = (255, 80, 80)
        elif phase == 3:
            body = (220, 30, 100)
        elif phase == 2:
            body = (200, 80, 200)
        else:
            body = (180, 50, 220)

        shad = pygame.Surface((r*3, r), pygame.SRCALPHA)
        pygame.draw.ellipse(shad, (0, 0, 0, 60), (0, 0, r*3, r))
        surf.blit(shad, (bx - r*3//2, by + r - 4))

        draw_glow_circle(surf, body, (bx, by), r + 30, intensity=50)

        pygame.draw.circle(surf, body, (bx, by), r)
        pygame.draw.circle(surf, (255, 255, 255), (bx, by), r, 3)

        collar_r = r + 10
        for i in range(8):
            a = math.radians(i*45 + self.anim_t*60)
            cx3 = bx + int(math.cos(a)*collar_r)
            cy3 = by + int(math.sin(a)*collar_r)
            pygame.draw.circle(surf, (255, 80, 80) if i%2==0 else (255,255,50), (cx3, cy3), 8)

        hat_w = r + 18; hat_h = r + 24
        hat_pts = [
            (bx - r - 4, by - r + 4), (bx + r + 4, by - r + 4),
            (bx + hat_w//2, by - r - hat_h), (bx - hat_w//2, by - r - hat_h),
        ]
        pygame.draw.polygon(surf, (20, 20, 20), hat_pts)
        pygame.draw.polygon(surf, (255, 80, 80), hat_pts, 3)
        band_y = by - r - hat_h//3
        pygame.draw.line(surf, (255, 200, 50), (bx - hat_w//2, band_y), (bx + hat_w//2, band_y), 4)
        pygame.draw.circle(surf, (255, 255, 50), (bx, by - r - hat_h), 10)

        eye_col = (255, 30, 30) if phase >= 2 else (40, 20, 20)
        pygame.draw.ellipse(surf, (255,255,255), (bx-20, by-18, 20, 16))
        pygame.draw.ellipse(surf, (255,255,255), (bx+ 2, by-18, 20, 16))
        mx2, my2 = int(self._cursor_x), int(self._cursor_y)
        ang_e = math.atan2(my2-by, mx2-bx)
        for ex, ey in [(bx-10, by-10), (bx+12, by-10)]:
            px3 = ex + int(math.cos(ang_e)*4)
            py3 = ey + int(math.sin(ang_e)*4)
            pygame.draw.circle(surf, eye_col, (px3, py3), 6)

        if phase == 3:
            ang_m = self.anim_t * 3
            mouth_pts = [
                (bx - 20, by + 14 + int(math.sin(ang_m)*4)),
                (bx,      by + 28),
                (bx + 20, by + 14 + int(math.sin(ang_m+1)*4)),
            ]
            pygame.draw.polygon(surf, (20, 5, 5), mouth_pts)
            pygame.draw.lines(surf, (255, 50, 50), False, mouth_pts, 3)
        else:
            pygame.draw.arc(surf, (255, 50, 50) if phase==2 else (50, 200, 50),
                            (bx-18, by+8, 36, 20), math.pi, 0, 3)

        pygame.draw.circle(surf, (255, 50, 50), (bx, by+6), 8)
        pygame.draw.circle(surf, (255,180,180), (bx-2, by+4), 3)

        # HP бар
        bar_w, bar_h = 160, 14
        bx4, by4 = bx - bar_w//2, by - r - 40
        pygame.draw.rect(surf, (40,10,10), (bx4, by4, bar_w, bar_h), border_radius=7)
        fill = max(0, int(bar_w * hp_frac))
        fc = (int(220*(1-hp_frac)+50*hp_frac), int(50*(1-hp_frac)+200*hp_frac), 50)
        if fill > 0:
            pygame.draw.rect(surf, fc, (bx4, by4, fill, bar_h), border_radius=7)
        pygame.draw.rect(surf, (200,200,200), (bx4, by4, bar_w, bar_h), 2, border_radius=7)
        hpf = pygame.font.SysFont("consolas", 10, bold=True)
        txt(surf, f"{max(0,self.boss_hp)}/{self.BOSS_MAX_HP}", (bx, by4+bar_h//2),
            (255,255,255), hpf, center=True)

    # ── HUD ──────────────────────────────────────────────────────────────────
    def _draw_hud(self, surf, font_med, font_lg, dash_cd):
        phase = self._get_phase()
        phase_names = {1: "PHASE 1 — The Jester", 2: "PHASE 2 — The Madman", 3: "PHASE 3 — FINAL STAND"}
        phase_cols  = {1: (180, 80, 255), 2: (255, 120, 50), 3: (255, 40, 40)}
        pf = pygame.font.SysFont("consolas", 18, bold=True)
        txt(surf, phase_names[phase], (SCREEN_W//2, 14), phase_cols[phase], pf, center=True)

        # Жизни
        for i in range(self.PLAYER_LIVES):
            col = (255, 80, 80) if i < self.lives else (60, 30, 30)
            pygame.draw.circle(surf, col, (36 + i*32, 36), 11)
            pygame.draw.circle(surf, (255,255,255) if i < self.lives else (80,40,40),
                               (36 + i*32, 36), 11, 2)
        lbl = pygame.font.SysFont("consolas", 12)
        txt(surf, "LIVES", (36 + (self.PLAYER_LIVES//2)*32, 56), (150,120,150), lbl, center=True)

        # Дэш кулдаун (правый нижний угол)
        df = pygame.font.SysFont("consolas", 15, bold=True)
        dash_ready = dash_cd <= 0
        dcol = (100,255,180) if dash_ready else (120,120,140)
        dlbl = "DASH [SPACE]  READY" if dash_ready else f"DASH [SPACE]  {dash_cd:.1f}s"
        txt(surf, dlbl, (SCREEN_W - 16, SCREEN_H - 36), dcol, df, right=True)

        # Щит подсказка
        if self._shield_active:
            sf = pygame.font.SysFont("consolas", 16, bold=True)
            alive_n = sum(1 for s in self._shield_shards if s["alive"])
            txt(surf, f"SHIELD ACTIVE — click the orbs! ({alive_n} left)",
                (SCREEN_W//2, SCREEN_H - 52), (100,200,255), sf, center=True)
        elif self._gravity_active:
            sf = pygame.font.SysFont("consolas", 16, bold=True)
            txt(surf, f"⚠ GRAVITATIONAL PULL — DASH to escape! ({self._gravity_t:.1f}s)",
                (SCREEN_W//2, SCREEN_H - 52), (200, 80, 255), sf, center=True)
        elif self._laser_active:
            sf = pygame.font.SysFont("consolas", 16, bold=True)
            txt(surf, f"⚠ LASER BEAM — dodge the line! ({self._laser_t:.1f}s)",
                (SCREEN_W//2, SCREEN_H - 52), (255, 80, 80), sf, center=True)
        else:
            hint = pygame.font.SysFont("consolas", 13)
            txt(surf, "CLICK THE BOSS — dodge projectiles — SPACE to dash",
                (SCREEN_W//2, SCREEN_H - 22), (80, 90, 120), hint, center=True)

    # ── главный цикл ─────────────────────────────────────────────────────────
    def run(self):
        font_huge = pygame.font.SysFont("consolas", 72, bold=True)
        font_big  = pygame.font.SysFont("consolas", 42, bold=True)
        font_med  = pygame.font.SysFont("consolas", 26, bold=True)
        font_sm   = pygame.font.SysFont("consolas", 18)
        back_btn  = pygame.Rect(24, 24, 130, 44)

        # Скрываем курсор — рисуем свой
        pygame.mouse.set_visible(False)
        self._cursor_x, self._cursor_y = pygame.mouse.get_pos()

        # Орбитали появятся в фазе 3
        _orbitals_inited = False
        _minion_cd = 7.0
        _aoe_cd    = 5.0

        try:
            while True:
                dt = min(self.clock.tick(FPS)/1000.0, 0.05)
                self.anim_t += dt
                raw_mx, raw_my = pygame.mouse.get_pos()

                # Дэш: плавно двигаем "курсор" если дэш активен
                if self._dash_t > 0:
                    self._dash_t = max(0.0, self._dash_t - dt)
                    self._cursor_x += self._dash_vx * dt
                    self._cursor_y += self._dash_vy * dt
                    self._cursor_x = max(0, min(SCREEN_W, self._cursor_x))
                    self._cursor_y = max(0, min(SCREEN_H, self._cursor_y))
                else:
                    self._cursor_x = float(raw_mx)
                    self._cursor_y = float(raw_my)
                cx, cy = self._cursor_x, self._cursor_y

                if self._dash_cd > 0:
                    self._dash_cd = max(0.0, self._dash_cd - dt)

                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        pygame.mouse.set_visible(True)
                        pygame.quit(); sys.exit()
                    if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                        pygame.mouse.set_visible(True)
                        return False
                    if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
                        if self._dash_cd <= 0 and self.state == "playing":
                            # Дэш в направлении от босса к курсору (убегаем от босса).
                            # Если курсор почти на боссе — дэш вниз как запасной вариант.
                            dx = cx - self._boss_x; dy = cy - self._boss_y
                            d = math.hypot(dx, dy)
                            if d < 20:
                                dx, dy, d = 0.0, 1.0, 1.0
                            spd = 900
                            self._dash_vx = dx/d * spd
                            self._dash_vy = dy/d * spd
                            self._dash_t  = 0.18
                            self._dash_cd = 2.0
                            self._spawn_particles(int(cx), int(cy), (100,200,255), n=10)

                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        if self.state in ("win", "lose"):
                            pygame.mouse.set_visible(True)
                            return self.state == "win"
                        if back_btn.collidepoint(ev.pos):
                            pygame.mouse.set_visible(True)
                            return False

                        if self.state == "playing":
                            if self._shield_active:
                                # сначала пытаемся разбить осколок щита
                                if not self._try_click_shield(cx, cy):
                                    pass  # мимо щита — босса не бьём
                            else:
                                if math.hypot(cx - self._boss_x, cy - self._boss_y) <= self.BOSS_RADIUS + 10:
                                    self.boss_hp -= self.DMG_PER_CLICK
                                    self._hit_flash = 0.14
                                    self._spawn_particles(int(self._boss_x), int(self._boss_y),
                                                          (255, 100, 80), n=10)
                                    if self.boss_hp <= 0:
                                        self.boss_hp = 0
                                        self.state = "win"
                                        self._spawn_particles(int(self._boss_x), int(self._boss_y),
                                                              (255, 220, 50), n=60, big=True)

                # ── Update ────────────────────────────────────────────────
                if self.state == "playing":
                    prev_phase = self._phase
                    self._phase = self._get_phase()

                    # Переход фазы
                    if self._phase > self._phase_announced:
                        self._phase_announced = self._phase
                        self._spawn_particles(int(self._boss_x), int(self._boss_y),
                                             (255, 80, 200), n=50, big=True)
                        self._projectiles = []
                        self._minions = []
                        # Фикс: не сбрасываем КД дэша при смене фазы.
                        # Если КД уже истёк — ставим минимальный штраф 1 сек,
                        # чтобы смена фазы не давала мгновенный бесплатный дэш.
                        if self._dash_cd <= 0:
                            self._dash_cd = 1.0
                        if self._phase == 3 and not _orbitals_inited:
                            self._init_orbitals()
                            _orbitals_inited = True

                    self._update_boss(dt)
                    self._update_shield(dt)

                    # Щит кулдаун (только если ещё ни разу не сломан)
                    if self._phase >= 2 and not self._shield_active and not self._shield_broken_once:
                        self._shield_cd -= dt
                        if self._shield_cd <= 0:
                            self._activate_shield()

                    # Телепорт
                    if self._phase >= 2:
                        self._tele_cd -= dt
                        if self._tele_cd <= 0:
                            self._do_teleport()
                            self._tele_cd = {2: 8.0, 3: 5.0}[self._phase]

                    # Фаза 1: телепорт если игрок сидит внутри босса > 2 сек
                    if self._phase == 1:
                        if math.hypot(cx - self._boss_x, cy - self._boss_y) <= self.BOSS_RADIUS + 10:
                            self._p1_inside_boss_t += dt
                            if self._p1_inside_boss_t >= 2.0:
                                self._do_teleport()
                                self._p1_inside_boss_t = 0.0
                        else:
                            self._p1_inside_boss_t = 0.0

                    if self._tele_flash > 0:
                        self._tele_flash = max(0.0, self._tele_flash - dt)

                    # Атаки
                    self._atk_cd -= dt
                    if self._atk_cd <= 0:
                        self._atk_cd = self._atk_interval()
                        pattern = self._atk_pattern
                        if self._phase == 1:
                            pattern = self._atk_pattern % 2
                        elif self._phase == 2:
                            pattern = self._atk_pattern % 3
                        else:
                            pattern = self._atk_pattern % 4
                        self._atk_pattern += 1
                        self._fire_volley(cx, cy, pattern)

                    # ── НОВЫЕ СПОСОБНОСТИ ────────────────────────────────
                    # Зеркальный снаряд (все фазы)
                    self._mirror_cd -= dt
                    if self._mirror_cd <= 0:
                        self._mirror_cd = {1: 7.0, 2: 5.0, 3: 3.5}[self._phase]
                        self._fire_mirror_volley(cx, cy)

                    # Карточный бросок (все фазы)
                    self._card_cd -= dt
                    if self._card_cd <= 0:
                        self._card_cd = {1: 9.0, 2: 6.0, 3: 4.0}[self._phase]
                        self._fire_card_throw(cx, cy)

                    # Лазерный луч (фаза 2+)
                    if self._phase >= 2:
                        if self._laser_cd > 0:
                            self._laser_cd -= dt
                        elif not self._laser_active and self._laser_warn_t <= 0:
                            # начинаем предупреждение
                            self._laser_warn_t = 1.5
                            self._laser_warn_angle = math.atan2(cy - self._boss_y, cx - self._boss_x)
                            self._laser_angle = self._laser_warn_angle
                        self._update_laser(dt, cx, cy)

                    # Бомбы-клоуны (фаза 2+)
                    if self._phase >= 2:
                        self._bomb_cd -= dt
                        if self._bomb_cd <= 0:
                            self._bomb_cd = {2: 8.0, 3: 5.5}[self._phase]
                            self._spawn_bombs(cx, cy)
                        self._update_bombs(dt, cx, cy)

                    # Гравитационный притяг (фаза 3)
                    if self._phase == 3:
                        if self._gravity_cd > 0:
                            self._gravity_cd -= dt
                        elif not self._gravity_active:
                            self._gravity_active = True
                            self._gravity_t = 3.0
                        new_cx, new_cy = self._update_gravity(dt, cx, cy)
                        if self._gravity_active:
                            self._cursor_x = new_cx
                            self._cursor_y = new_cy
                            cx, cy = new_cx, new_cy

                    # Финальный взрыв (фаза 3, при 15% HP)
                    if self._phase == 3 and not self._nova_fired and self._hp_frac <= 0.15:
                        self._nova_fired = True
                        self._trigger_nova()
                    self._update_nova(dt, cx, cy)

                    # Миньоны
                    if self._phase >= 2:
                        _minion_cd -= dt
                        if _minion_cd <= 0:
                            _minion_cd = {2: 6.0, 3: 4.0}[self._phase]
                            self._spawn_minions(cx, cy, n={2:3,3:5}[self._phase])

                    # AoE
                    _aoe_cd -= dt
                    if _aoe_cd <= 0:
                        _aoe_cd = {1: 6.0, 2: 4.5, 3: 3.0}[self._phase]
                        # 2-3 зоны вокруг курсора
                        for _ in range(1 + self._phase):
                            ax = cx + random.uniform(-200, 200)
                            ay = cy + random.uniform(-200, 200)
                            ax = max(80, min(SCREEN_W-80, ax))
                            ay = max(80, min(SCREEN_H-80, ay))
                            self._spawn_aoe(ax, ay, r={1:90,2:110,3:130}[self._phase],
                                           delay={1:1.2,2:1.0,3:0.8}[self._phase])

                    # Орбитали (фаза 3)
                    if self._phase == 3 and self._orbitals:
                        self._update_orbitals(dt, cx, cy)

                    self._update_projectiles(dt, cx, cy)
                    self._update_minions(dt, cx, cy)
                    self._update_aoe(dt, cx, cy)

                self._update_particles(dt)

                # ── Draw ──────────────────────────────────────────────────
                surf = self.screen
                self._draw_arena(surf)

                # Вспышка при попадании
                if self._life_flash > 0:
                    frac = self._life_flash / 0.45
                    self._flash_surf.fill((220, 30, 30, int(130*frac)))
                    surf.blit(self._flash_surf, (0,0))
                    self._life_flash = max(0.0, self._life_flash - dt)

                # Вспышка телепорта
                if self._tele_flash > 0:
                    frac = self._tele_flash / 0.22
                    self._flash_surf.fill((200, 150, 255, int(100*frac)))
                    surf.blit(self._flash_surf, (0,0))

                # Ярость фаза 3
                if self._get_phase() == 3 and self.state == "playing":
                    a_r = int(abs(math.sin(self.anim_t*7))*22)
                    self._rage_surf.fill((200, 20, 20, a_r))
                    surf.blit(self._rage_surf, (0,0))

                self._draw_aoe(surf)
                self._draw_particles(surf)

                if self.state == "playing":
                    self._draw_gravity(surf)
                    self._draw_laser(surf)
                    self._draw_nova_warning(surf)
                    self._draw_projectiles(surf)
                    self._draw_bombs(surf)
                    self._draw_minions(surf)
                    if self._orbitals: self._draw_orbitals(surf)
                    self._draw_shield(surf)
                    self._draw_boss_sprite(surf)
                    self._draw_hud(surf, font_med, font_big, self._dash_cd)

                    # Курсор
                    mcx, mcy = int(self._cursor_x), int(self._cursor_y)
                    cr = 16
                    dash_ready = self._dash_cd <= 0
                    ccol = (100,255,180) if dash_ready else (255,255,255)
                    pygame.draw.line(surf, ccol, (mcx-cr,mcy), (mcx+cr,mcy), 2)
                    pygame.draw.line(surf, ccol, (mcx,mcy-cr), (mcx,mcy+cr), 2)
                    pygame.draw.circle(surf, ccol, (mcx,mcy), 5, 1)
                    # Дэш-след
                    if self._dash_t > 0:
                        self._dash_surf.fill((0,0,0,0))
                        pygame.draw.circle(self._dash_surf, (100,200,255,80), (mcx,mcy), 22)
                        surf.blit(self._dash_surf, (0,0))

                    # Back button
                    draw_rect_alpha(surf, (40,40,70), back_btn, 200, brad=8)
                    pygame.draw.rect(surf, C_BORDER, back_btn, 1, border_radius=8)
                    txt(surf, "<- BACK", back_btn.center, C_WHITE, font_sm, center=True)

                elif self.state == "win":
                    for _ in range(25):
                        pygame.draw.circle(surf, random.choice(self.PROJ_COLORS),
                            (random.randint(0,SCREEN_W), random.randint(0,SCREEN_H)),
                            random.randint(5,16))
                    gs2 = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                    pygame.draw.ellipse(gs2, (50,220,80,40), (SCREEN_W//2-500,SCREEN_H//2-220,1000,440))
                    surf.blit(gs2, (0,0))
                    txt(surf, "BOSS DEFEATED!", (SCREEN_W//2, SCREEN_H//2-130), C_GREEN, font_huge, center=True)
                    txt(surf, "CLOWN TOWER UNLOCKED!", (SCREEN_W//2, SCREEN_H//2-45), C_GOLD, font_big, center=True)
                    txt(surf, "The Clown is now available in your Loadout.",
                        (SCREEN_W//2, SCREEN_H//2+30), C_WHITE, font_med, center=True)
                    txt(surf, "Click anywhere to return.", (SCREEN_W//2, SCREEN_H//2+110), (120,130,160), font_sm, center=True)

                elif self.state == "lose":
                    gs3 = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                    pygame.draw.ellipse(gs3, (220,50,50,35), (SCREEN_W//2-450,SCREEN_H//2-200,900,400))
                    surf.blit(gs3, (0,0))
                    txt(surf, "YOU WERE CLOWNED!", (SCREEN_W//2, SCREEN_H//2-120), C_RED, font_huge, center=True)
                    txt(surf, "Clown remains locked. Try again!",
                        (SCREEN_W//2, SCREEN_H//2+40), (180,80,80), font_med, center=True)
                    txt(surf, "Click anywhere to return.", (SCREEN_W//2, SCREEN_H//2+110), (120,130,160), font_sm, center=True)

                pygame.display.flip()

        finally:
            pygame.mouse.set_visible(True)



# ── Lobby ──────────────────────────────────────────────────────────────────────
class Lobby:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.state = "main"          # "main" | "difficulty" | "loadout" | "changelog" | "sandbox"
        self.selected_difficulty = None
        self.anim_t = 0.0
        self._changelog_scroll = 0   # pixel scroll offset for changelog
        self._changelog_open_idx = None  # index of expanded entry (None = all collapsed)
        self._sandbox_cfg = {        # sandbox configuration
            "map": "Easy",
            "enemies": [],           # list of enemy class names to spawn
            "loadout": [None]*5,
        }

        # Loadout: which towers are in each of the 5 slots
        # All available tower types
        self.all_towers = [Assassin, Accelerator, Clown, Archer, Zigres, Gunner]
        _saved_ld = load_loadout()
        self.loadout = _saved_ld if _saved_ld is not None else list(UI.SLOT_TYPES)

        # For drag in loadout screen
        self.drag_tower = None
        self.drag_from_slot = None

        self._build_rects()

    def _build_rects(self):
        cx = SCREEN_W // 2
        # Main buttons
        self.btn_play = pygame.Rect(cx-187, 490, 374, 94)
        self.btn_loadout = pygame.Rect(cx-187, 600, 374, 69)
        self.btn_sandbox = pygame.Rect(cx-187, 685, 374, 56)
        self.btn_shop = pygame.Rect(cx-187, 757, 374, 52)
        self.btn_minigame = pygame.Rect(cx-187, 825, 374, 44)
        self.btn_quit = pygame.Rect(cx-130, 883, 259, 44)
        self.btn_changelog = pygame.Rect(cx-130, 940, 259, 38)

        # Difficulty cards
        card_w, card_h = 317, 403
        gap = 43
        total = 3*(card_w+gap)-gap
        start_x = (SCREEN_W - total)//2
        self.diff_cards = {}
        for i, name in enumerate(["Easy","Hard","Hell"]):
            rx = start_x + i*(card_w+gap)
            ry = (SCREEN_H - card_h) // 2 - 30
            self.diff_cards[name] = pygame.Rect(rx, ry, card_w, card_h)
        self.btn_diff_back = pygame.Rect(29, 29, 158, 52)
        self.btn_diff_start = pygame.Rect(SCREEN_W//2-202, SCREEN_H-108, 403, 75)

        # Loadout screen
        self._build_loadout_rects()

    def _build_loadout_rects(self):
        # LEFT PANEL — tower list (scrollable column)
        self._lo_list_x = 52
        self._lo_list_y = 120
        self._lo_list_item_h = 96
        self._lo_list_item_w = 340
        self._lo_list_gap = 10
        self._lo_list_scroll = 0  # pixel scroll offset

        # RIGHT PANEL — tower detail/preview panel
        self._lo_detail_x = 430
        self._lo_detail_y = 100
        self._lo_detail_w = SCREEN_W - 430 - 52
        self._lo_detail_h = SCREEN_H - 260

        # BOTTOM BAR — 5 deck slots
        deck_y = SCREEN_H - 148
        deck_h = 130
        sw = 186
        sg = 14
        total_s = 5 * sw + 4 * sg
        ssx = (SCREEN_W - total_s) // 2
        self.loadout_slot_rects = []
        for i in range(5):
            self.loadout_slot_rects.append(pygame.Rect(ssx + i * (sw + sg), deck_y, sw, deck_h))

        # Selected tower in list (for detail panel)
        if not hasattr(self, '_lo_selected_tower'):
            self._lo_selected_tower = self.all_towers[0] if self.all_towers else None

        self.btn_lo_back = pygame.Rect(29, 29, 140, 46)
        self.btn_lo_save = pygame.Rect(SCREEN_W - 240, SCREEN_H - 68, 210, 50)
        # "Add to loadout" button inside detail panel
        self._lo_btn_add = pygame.Rect(
            self._lo_detail_x, SCREEN_H - 210, self._lo_detail_w, 54)

        # palette_rects kept for click compat — map to list items
        self.palette_rects = []
        for i in range(len(self.all_towers)):
            self.palette_rects.append(pygame.Rect(
                self._lo_list_x,
                self._lo_list_y + i * (self._lo_list_item_h + self._lo_list_gap) - self._lo_list_scroll,
                self._lo_list_item_w,
                self._lo_list_item_h,
            ))

    def _draw_bg(self):
        surf = self.screen
        # Deep space gradient background
        draw_rect_gradient(surf, (8,10,22), (14,18,32), (0,0,SCREEN_W,SCREEN_H), alpha=255)
        # Static twinkling stars
        rng_s = random.Random(1337)
        for _ in range(220):
            sx = rng_s.randint(0, SCREEN_W); sy = rng_s.randint(0, SCREEN_H)
            br = rng_s.randint(80, 220)
            twinkle = int(abs(math.sin(self.anim_t * rng_s.uniform(0.5, 2.0) + sx * 0.01)) * 70)
            col_s = min(255, br + twinkle)
            pygame.draw.circle(surf, (col_s, col_s, min(255, col_s+30)), (sx, sy), 1)
        # Moving subtle grid
        for x in range(0, SCREEN_W+80, 80):
            ox = (x + int(self.anim_t*12)) % (SCREEN_W+80)
            gs = pygame.Surface((1, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(gs, (255,255,255,7), (0,0), (0,SCREEN_H))
            surf.blit(gs, (ox, 0))
        for y in range(0, SCREEN_H+80, 80):
            oy = (y + int(self.anim_t*6)) % (SCREEN_H+80)
            gs = pygame.Surface((SCREEN_W, 1), pygame.SRCALPHA)
            pygame.draw.line(gs, (255,255,255,7), (0,0), (SCREEN_W,0))
            surf.blit(gs, (0, oy))
        # Floating colour orbs
        orb_cols = [(80,100,255),(60,200,180),(180,80,255),(80,160,255),(120,255,160),(200,120,255)]
        for i in range(6):
            ang = self.anim_t * 0.28 + i * math.pi / 3
            ox2 = SCREEN_W//2 + int(math.cos(ang) * (200 + i*55))
            oy2 = SCREEN_H//2 + int(math.sin(ang * 0.7) * 110)
            draw_glow_circle(surf, orb_cols[i], (ox2, oy2), 20+i*2, 32)
        # Central vignette glow
        sv = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for r in range(700, 0, -70):
            a = max(0, int(26*(1-r/700)))
            pygame.draw.circle(sv, (50,80,200,a), (SCREEN_W//2, SCREEN_H//2), r)
        surf.blit(sv, (0, 0))

    def _draw_button(self, rect, label, color, text_color=C_WHITE, font=font_lg,
                     hover=False, border=None, alpha=200):
        mx, my = pygame.mouse.get_pos()
        is_hov = rect.collidepoint(mx, my)
        col = tuple(min(255, c+30) for c in color) if is_hov else color
        draw_rect_alpha(self.screen, col, rect, 220, brad=10)
        bc = border or tuple(min(255, c+80) for c in color)
        pygame.draw.rect(self.screen, bc, rect, 2, border_radius=10)
        txt(self.screen, label, rect.center, text_color, font, center=True)

    def _draw_tower_icon(self, surf, TType, cx, cy, size=28):
        """Draw a scaled mini-version of the tower exactly as it looks in-game."""
        if TType is None:
            txt(surf, "?", (cx, cy), (80, 80, 120), font_lg, center=True)
            return

        # scale factor relative to the in-game draw size (~28-36px radius)
        sc = size / 32.0
        def r(v): return max(1, int(v * sc))
        def p(ox, oy): return (cx + int(ox * sc), cy + int(oy * sc))

        if TType is Assassin:
            # ground shadow
            pygame.draw.ellipse(surf, (20, 10, 35),
                                (cx - r(18), cy + r(14), r(36), r(10)))
            # cloak body
            cloak_pts_i = [
                p(0,   -28), p(22,  -8), p(18, 18),
                p(0,    22), p(-18, 18), p(-22, -8),
            ]
            pygame.draw.polygon(surf, (22, 12, 40), cloak_pts_i)
            pygame.draw.polygon(surf, (55, 28, 85), cloak_pts_i, max(1, r(2)))
            # hood
            pygame.draw.circle(surf, (30, 15, 55), p(0, -14), r(16))
            pygame.draw.circle(surf, (60, 30, 90),  p(0, -14), r(16), max(1, r(2)))
            # face shadow / mask
            pygame.draw.ellipse(surf, (12, 6, 22),
                                (cx - r(8), cy - r(22), r(16), r(12)))
            # glowing eyes
            pygame.draw.circle(surf, (200, 80, 255), p(-5, -16), r(3))
            pygame.draw.circle(surf, (200, 80, 255), p( 5, -16), r(3))
            pygame.draw.circle(surf, (255,255,255),  p(-5, -16), r(1))
            pygame.draw.circle(surf, (255,255,255),  p( 5, -16), r(1))
            # left dagger blade
            pygame.draw.line(surf, (210,220,240), p(-18,-2),  p(-30,-18), max(1,r(3)))
            pygame.draw.line(surf, (255,255,255), p(-19,-3),  p(-28,-16), max(1,r(1)))
            pygame.draw.line(surf, (140,90,200),  p(-15, 0),  p(-22, -4), max(1,r(3)))
            # right dagger blade
            pygame.draw.line(surf, (210,220,240), p(16,  0),  p(30, -18), max(1,r(3)))
            pygame.draw.line(surf, (255,255,255), p(17, -1),  p(28, -16), max(1,r(1)))
            pygame.draw.line(surf, (140,90,200),  p(13,  2),  p(20,  -2), max(1,r(3)))
            # chest gem
            pygame.draw.circle(surf, C_ASSASSIN,    p(0, -2), r(5))
            pygame.draw.circle(surf, (240,200,255), p(0, -2), r(2))

        elif TType is Accelerator:
            pygame.draw.ellipse(surf, (30, 15, 60),
                                (cx - r(20), cy + r(11), r(40), r(13)))
            pygame.draw.circle(surf, (40, 20, 80),  (cx, cy), r(36))
            pygame.draw.circle(surf, C_ACCEL,        (cx, cy), r(26))
            pygame.draw.circle(surf, (200, 170, 255), p(-8, -8), r(10))
            pygame.draw.circle(surf, (230, 210, 255), (cx, cy), r(5))
            for i in range(4):
                a = math.radians(i * 90)
                pygame.draw.circle(surf, (160, 100, 255),
                                   (cx + int(math.cos(a) * r(18)),
                                    cy + int(math.sin(a) * r(18))), r(4))

        elif TType is Clown:
            pygame.draw.ellipse(surf, (20, 10, 10),
                                (cx - r(22), cy + r(20), r(44), r(14)))
            pygame.draw.circle(surf, (60, 20, 20),  (cx, cy), r(36))
            pygame.draw.circle(surf, C_RED,          (cx, cy), r(30))
            # polka dots
            for i in range(4):
                a = math.radians(i * 90)
                pygame.draw.circle(surf, C_WHITE,
                                   (cx + int(math.cos(a) * r(14)),
                                    cy + int(math.sin(a) * r(14))), r(4))
            # hat
            hat_pts = [p(0, -52), p(-18, -28), p(18, -28)]
            pygame.draw.polygon(surf, (255, 200, 50), hat_pts)
            pygame.draw.polygon(surf, C_WHITE, hat_pts, max(1, r(2)))
            pygame.draw.circle(surf, C_RED, p(0, -52), r(5))
            # eyes
            pygame.draw.circle(surf, C_WHITE, p(-9, -8), r(6))
            pygame.draw.circle(surf, C_WHITE, p(9, -8),  r(6))
            pygame.draw.circle(surf, C_BG,    p(-9, -8), r(3))
            pygame.draw.circle(surf, C_BG,    p(9, -8),  r(3))
            # nose
            pygame.draw.circle(surf, C_RED, p(0, 0), r(6))

        elif TType is Archer:
            pygame.draw.ellipse(surf, (30, 20, 10),
                                (cx - r(20), cy + r(18), r(40), r(12)))
            pygame.draw.circle(surf, (80, 50, 20),    (cx, cy), r(36))
            pygame.draw.circle(surf, (140, 90, 40),   (cx, cy), r(28))
            pygame.draw.circle(surf, (180, 130, 70),  p(-9, -9), r(9))
            # bow arc
            bow_rect = pygame.Rect(cx - r(18), cy - r(22), r(14), r(44))
            pygame.draw.arc(surf, (100, 65, 25), bow_rect,
                            math.radians(270), math.radians(90), max(1, r(4)))
            pygame.draw.line(surf, (220, 200, 160), p(-11, -22), p(-11, 22), 1)
            pygame.draw.line(surf, (200, 160, 80),  p(-11, 0),   p(18, 0),   max(1, r(2)))
            pygame.draw.circle(surf, (180, 120, 60), (cx, cy), r(28), max(1, r(2)))

        elif TType is Zigres:
            # ── Mini Luntik (Zigres) icon ──────────────────────────────────
            C_LB = (180, 100, 220); C_LBEL = (230, 180, 255)
            C_LE = (200, 120, 240); C_LI = (255, 180, 220)
            C_LD = (120,  50, 160); C_LEY = (30,  20,  50)
            C_LN = (255, 160, 180); C_LCH = (255, 180, 200)
            # glow aura
            gs2 = pygame.Surface((r(100), r(100)), pygame.SRCALPHA)
            pygame.draw.circle(gs2, (200, 100, 255, 40), (r(50), r(50)), r(44))
            surf.blit(gs2, (cx - r(50), cy - r(50)))
            # ears (behind body)
            pygame.draw.ellipse(surf, C_LD,  (cx - r(30), cy - r(52), r(22), r(34)))
            pygame.draw.ellipse(surf, C_LE,  (cx - r(28), cy - r(50), r(18), r(30)))
            pygame.draw.ellipse(surf, C_LI,  (cx - r(24), cy - r(45), r(10), r(18)))
            pygame.draw.ellipse(surf, C_LD,  (cx + r(10), cy - r(50), r(22), r(34)))
            pygame.draw.ellipse(surf, C_LE,  (cx + r(12), cy - r(48), r(18), r(30)))
            pygame.draw.ellipse(surf, C_LI,  (cx + r(16), cy - r(43), r(10), r(18)))
            # orbiting magic dots
            for i in range(3):
                oa = math.radians(i * 120)
                ox3 = cx + int(math.cos(oa) * r(26))
                oy3 = cy + int(math.sin(oa) * r(13))
                pygame.draw.circle(surf, (220, 160, 255), (ox3, oy3), max(1, r(4)))
                pygame.draw.circle(surf, (255, 255, 255), (ox3, oy3), max(1, r(2)))
            # body
            pygame.draw.circle(surf, C_LD, (cx, cy + r(2)), r(31))
            pygame.draw.circle(surf, C_LB, (cx, cy),        r(29))
            pygame.draw.ellipse(surf, C_LBEL, (cx - r(12), cy - r(9), r(24), r(22)))
            # face
            fy = cy - r(7)
            pygame.draw.ellipse(surf, C_LEY, (cx - r(13), fy - r(5), r(9),  r(7)))
            pygame.draw.circle(surf, (255,255,255), (cx - r(10), fy - r(3)), max(1, r(2)))
            pygame.draw.ellipse(surf, C_LEY, (cx + r(4),  fy - r(5), r(9),  r(7)))
            pygame.draw.circle(surf, (255,255,255), (cx + r(7),  fy - r(3)), max(1, r(2)))
            pygame.draw.circle(surf, C_LN, (cx, fy + r(4)), max(1, r(4)))
            # tiny smile
            spts = [(cx - r(6), fy + r(9)), (cx, fy + r(13)), (cx + r(6), fy + r(9))]
            if len(spts) >= 2:
                pygame.draw.lines(surf, C_LD, False, spts, max(1, r(2)))
            # cheek blush
            bs2 = pygame.Surface((r(16), r(9)), pygame.SRCALPHA)
            pygame.draw.ellipse(bs2, (*C_LCH, 110), (0, 0, r(16), r(9)))
            surf.blit(bs2, (cx - r(20), fy + r(5)))
            surf.blit(bs2, (cx + r(5),  fy + r(5)))
            # antennae
            pygame.draw.line(surf, C_LD, p(-7, -27), p(-16, -46), max(1, r(2)))
            pygame.draw.circle(surf, (255, 200, 80), p(-16, -46), max(1, r(4)))
            pygame.draw.line(surf, C_LD, p(7, -27), p(16, -46), max(1, r(2)))
            pygame.draw.circle(surf, (255, 200, 80), p(16, -46), max(1, r(4)))

        elif TType is Gunner:
            # base platform
            pygame.draw.ellipse(surf, (60, 40, 15),
                                (cx - r(22), cy + r(12), r(44), r(14)))
            pygame.draw.circle(surf, (110, 80, 30), (cx, cy), r(28))
            pygame.draw.circle(surf, (160, 120, 50), (cx, cy), r(20))
            pygame.draw.circle(surf, (200, 160, 70), p(-4, -4), r(8))
            # barrel pointing right
            bpts = [p(-4, -5), p(-4, 5), p(24, 3), p(24, -3)]
            pygame.draw.polygon(surf, (80, 55, 18), bpts)
            pygame.draw.polygon(surf, (150, 110, 45), bpts, max(1, r(2)))
            pygame.draw.circle(surf, (160, 120, 50), p(10, 0), r(6))

        else:
            # fallback generic
            pygame.draw.circle(surf, (70, 40, 100), (cx, cy), r(36))
            pygame.draw.circle(surf, TType.COLOR,   (cx, cy), r(28))
            pygame.draw.circle(surf, C_WHITE,        (cx, cy), r(28), 2)

    # ── MAIN LOBBY SCREEN ──────────────────────────────────────────────────────
    def _draw_main(self):
        self._draw_bg()
        surf = self.screen
        t = self.anim_t

        # ── Animated title glow ──────────────────────────────────────────────
        pulse_glow = int(abs(math.sin(t * 1.2)) * 30)
        for gr in range(120, 0, -20):
            ga = max(0, int((18 + pulse_glow//2) * (1 - gr/120)))
            gs_e = pygame.Surface((SCREEN_W, gr*2), pygame.SRCALPHA)
            pygame.draw.ellipse(gs_e, (60, 160, 255, ga), (SCREEN_W//2-500, 0, 1000, gr*2))
            surf.blit(gs_e, (0, 155 - gr))

        # Title shadow + title
        title_font = pygame.font.SysFont("consolas", 82, bold=True)
        sub_font   = pygame.font.SysFont("consolas", 46, bold=True)
        sh_s = title_font.render("TOWER DEFENSE", True, (15,50,110))
        sh_s.set_alpha(110)
        surf.blit(sh_s, sh_s.get_rect(center=(SCREEN_W//2+3, 193)))
        txt(surf, "TOWER DEFENSE", (SCREEN_W//2, 190), C_CYAN, title_font, center=True)

        # Glowing separator line
        line_w, line_y = 620, 248
        for li in range(4):
            la = 65 - li*16
            ls = pygame.Surface((line_w, 2), pygame.SRCALPHA)
            pygame.draw.rect(ls, (80,200,255,la), (0,0,line_w,2))
            surf.blit(ls, (SCREEN_W//2 - line_w//2, line_y+li))

        txt(surf, "SIMULATOR", (SCREEN_W//2, 278), C_GOLD, sub_font, center=True)

        # Version badge
        vr = pygame.Rect(SCREEN_W//2-38, 322, 76, 24)
        draw_rect_alpha(surf, (30,70,30), vr, 200, brad=8)
        pygame.draw.rect(surf, (60,180,80), vr, 1, border_radius=8)
        txt(surf, "v2.0", vr.center, (100,255,140),
            pygame.font.SysFont("consolas",14), center=True)

        # ── Decorative tower icons with orbiting dots ────────────────────────
        for tx2, ty2, col2, phase in [
            (240, 212, C_ASSASSIN, 0.0),
            (SCREEN_W-240, 212, C_ACCEL, 1.0),
            (168, 418, (80,200,80), 2.0),
            (SCREEN_W-168, 418, (255,140,40), 3.0)
        ]:
            pulse2 = abs(math.sin(t*1.8 + phase)) * 10
            draw_glow_circle(surf, col2, (tx2, ty2), int(50+pulse2), 45)
            # shadow ellipse
            se = pygame.Surface((110,32), pygame.SRCALPHA)
            pygame.draw.ellipse(se, (0,0,0,55), (0,0,110,32))
            surf.blit(se, (tx2-55, ty2+33))
            # body gradient
            draw_rect_gradient(surf,
                tuple(min(255,c+70) for c in col2), col2,
                (tx2-30, ty2-30, 60, 60), alpha=255, brad=30)
            pygame.draw.circle(surf, C_WHITE, (tx2, ty2), 32, 3)
            pygame.draw.circle(surf, (255,255,255), (tx2-10, ty2-10), 8)
            # orbiting dots
            for oi in range(3):
                oa = math.radians(t*95 + oi*120 + phase*65)
                ox3 = tx2 + int(math.cos(oa)*50)
                oy3 = ty2 + int(math.sin(oa)*50)
                pygame.draw.circle(surf, col2, (ox3, oy3), 5)
                pygame.draw.circle(surf, C_WHITE, (ox3, oy3), 2)

        # ── Fancy gradient buttons ───────────────────────────────────────────
        mx2, my2 = pygame.mouse.get_pos()

        def fancy_btn(rect, label, c_top, c_bot, tc=C_WHITE, fnt=font_xl, gc=None):
            hov = rect.collidepoint(mx2, my2)
            t2 = tuple(min(255,c+28) for c in c_top) if hov else c_top
            b2 = tuple(min(255,c+28) for c in c_bot) if hov else c_bot
            if hov and gc:
                draw_glow_circle(surf, gc, rect.center, rect.h, 18)
            draw_rect_gradient(surf, t2, b2, rect, alpha=232, brad=12)
            draw_rect_alpha(surf,(255,255,255),(rect.x,rect.y,rect.w,rect.h//3),16,brad=12)
            brd = gc or tuple(min(255,c+100) for c in c_top)
            pygame.draw.rect(surf, brd, rect, 2, border_radius=12)
            txt(surf, label, rect.center, tc, fnt, center=True)

        fancy_btn(self.btn_play,      "▶  PLAY",
                  (20,70,165),(14,45,110), C_WHITE, font_xl, (60,140,255))
        fancy_btn(self.btn_loadout,   "⚙  LOADOUT",
                  (42,42,98),(26,26,65),  C_CYAN,  font_lg, (80,80,200))
        fancy_btn(self.btn_sandbox,   "🧪 SANDBOX",
                  (14,65,44),(9,40,28),   (80,255,160), font_lg, (40,180,100))
        fancy_btn(self.btn_shop,      "[S] SHOP",
                  (50,38,10),(32,22,5),   C_GOLD, font_lg, (200,160,40))
        # Key Hunt button — show key progress or boss fight availability
        _clown_locked = not is_clown_unlocked()
        _keys_now = total_clown_keys()
        if not _clown_locked:
            mg_label = "🗝️ KEY HUNT  ✔ Clown Unlocked"
            mg_col   = (80,200,80)
            mg_bg1, mg_bg2, mg_bdr = (20,60,20),(12,36,12),(60,180,60)
        elif _keys_now >= CLOWN_KEYS_TOTAL:
            mg_label = f"🗝️ BOSS FIGHT READY! ({_keys_now}/{CLOWN_KEYS_TOTAL} keys)"
            mg_col   = (255,200,50)
            mg_bg1, mg_bg2, mg_bdr = (60,45,5),(38,28,3),(220,160,30)
        else:
            mg_label = f"🗝️ Keys: {_keys_now}/{CLOWN_KEYS_TOTAL}  — Play to find more!"
            mg_col   = (180,80,255)
            mg_bg1, mg_bg2, mg_bdr = (55,20,80),(32,10,50),(140,60,200)
        fancy_btn(self.btn_minigame, mg_label,
                  mg_bg1, mg_bg2, mg_col, font_sm, mg_bdr)
        fancy_btn(self.btn_quit,      "✕  QUIT",
                  (72,20,20),(46,12,12),  (255,120,120), font_md, (180,50,50))
        fancy_btn(self.btn_changelog, "📋 CHANGELOG",
                  (14,45,55),(9,28,35),   (100,210,220), font_sm)

        # bottom hint
        txt(surf,
            "Keys:  [1-5] select tower  |  [E] upgrade  |  [X] sell  |  [F] ability  |  [ESC] pause",
            (SCREEN_W//2, SCREEN_H-28), (50,60,80), font_sm, center=True)

        # ── Shop coin counter (top-right corner) ──────────────────────────────
        coins = get_shop_coins()
        coin_badge_w = 160
        coin_badge_h = 40
        coin_badge_x = SCREEN_W - coin_badge_w - 18
        coin_badge_y = 18
        # panel
        draw_rect_alpha(surf, (30,24,8), (coin_badge_x, coin_badge_y, coin_badge_w, coin_badge_h), 210, brad=10)
        pygame.draw.rect(surf, C_GOLD, (coin_badge_x, coin_badge_y, coin_badge_w, coin_badge_h), 2, border_radius=10)
        # animated coin icon
        pulse_c = abs(math.sin(t * 2.0))
        cr = int(13 + pulse_c*2)
        coin_cx3 = coin_badge_x + 22
        coin_cy3 = coin_badge_y + coin_badge_h//2
        pygame.draw.circle(surf, (180,140,0), (coin_cx3, coin_cy3), cr)
        pygame.draw.circle(surf, (255,215,0), (coin_cx3, coin_cy3), cr, 2)
        pygame.draw.circle(surf, (255,240,120), (coin_cx3-3, coin_cy3-3), cr//3)
        coin_num_f = pygame.font.SysFont("consolas", 18, bold=True)
        txt(surf, f"{coins}", (coin_cx3+cr+8, coin_cy3), C_GOLD, coin_num_f)
        coin_lbl_f = pygame.font.SysFont("consolas", 10)
        txt(surf, "shop coins", (coin_badge_x + coin_badge_w//2 + 10, coin_cy3+11), (180,150,60), coin_lbl_f, center=True)

    # ── CHANGELOG SCREEN ───────────────────────────────────────────────────────
    def _draw_changelog(self):
        self._draw_bg()
        surf = self.screen

        hdr_font = pygame.font.SysFont("consolas", 40, bold=True)
        txt(surf, "CHANGELOG", (SCREEN_W//2, 52), C_CYAN, hdr_font, center=True)
        txt(surf, "Click an entry to expand", (SCREEN_W//2, 98), (90,100,130), font_sm, center=True)

        self._draw_button(self.btn_diff_back, "<- BACK", (40,40,70), C_WHITE, font_md)

        CONTENT_X = SCREEN_W//2 - 480
        CONTENT_W = 960
        CONTENT_Y = 128
        CONTENT_H = SCREEN_H - 148

        ROW_H     = 52   # collapsed row height
        ROW_GAP   = 8
        ENTRY_H   = 22
        EXPAND_PAD_TOP = 14
        EXPAND_PAD_BOT = 14

        # Measure total height for scroll
        total_h = 0
        for i, blk in enumerate(CHANGELOG):
            total_h += ROW_H + ROW_GAP
            if self._changelog_open_idx == i:
                total_h += EXPAND_PAD_TOP + len(blk["entries"]) * ENTRY_H + EXPAND_PAD_BOT

        max_scroll = max(0, total_h - CONTENT_H + 20)
        self._changelog_scroll = max(0, min(self._changelog_scroll, max_scroll))

        clip_rect = pygame.Rect(CONTENT_X, CONTENT_Y, CONTENT_W, CONTENT_H)
        old_clip  = surf.get_clip()
        surf.set_clip(clip_rect)

        oy = CONTENT_Y - self._changelog_scroll
        mx, my = pygame.mouse.get_pos()

        # Store rects for click detection
        self._changelog_row_rects = []

        ver_font   = pygame.font.SysFont("consolas", 20, bold=True)
        title_font2 = pygame.font.SysFont("consolas", 16, bold=True)
        date_font  = pygame.font.SysFont("consolas", 13)
        tag_font   = pygame.font.SysFont("consolas", 11, bold=True)

        for i, blk in enumerate(CHANGELOG):
            is_open   = (self._changelog_open_idx == i)
            row_rect  = pygame.Rect(CONTENT_X, oy, CONTENT_W, ROW_H)
            hovered   = row_rect.collidepoint(mx, my)
            self._changelog_row_rects.append(pygame.Rect(CONTENT_X, oy, CONTENT_W, ROW_H))

            # expanded block height
            expand_h = EXPAND_PAD_TOP + len(blk["entries"]) * ENTRY_H + EXPAND_PAD_BOT if is_open else 0
            full_rect = pygame.Rect(CONTENT_X, oy, CONTENT_W, ROW_H + expand_h)

            # background
            bg_col   = (30, 45, 75) if is_open else ((28, 38, 62) if hovered else (22, 30, 50))
            brd_col  = C_CYAN if is_open else (C_BORDER if not hovered else (100, 120, 180))
            draw_rect_alpha(surf, bg_col, (full_rect.x, full_rect.y, full_rect.w, full_rect.h), 230, brad=10)
            pygame.draw.rect(surf, brd_col, (full_rect.x, full_rect.y, full_rect.w, full_rect.h), 1, border_radius=10)

            # chevron
            chev = "▾" if is_open else "▸"
            chev_font = pygame.font.SysFont("consolas", 20, bold=True)
            txt(surf, chev, (CONTENT_X + 20, oy + ROW_H//2),
                C_CYAN if is_open else (100, 120, 160), chev_font, center=False)

            # version badge
            badge_col = (60, 180, 60) if blk["date"] == "26 Apr 2026" else (60, 100, 180)
            badge_rect = pygame.Rect(CONTENT_X + 42, oy + ROW_H//2 - 12, 130, 24)
            draw_rect_alpha(surf, badge_col, badge_rect, 80, brad=5)
            pygame.draw.rect(surf, badge_col, badge_rect, 1, border_radius=5)
            txt(surf, blk["version"], (badge_rect.centerx, badge_rect.centery),
                C_WHITE, ver_font, center=True)

            # title
            txt(surf, blk["title"], (CONTENT_X + 188, oy + ROW_H//2 - 9),
                C_WHITE if is_open else (180, 190, 210), title_font2)

            # date (right side)
            dw = date_font.size(blk["date"])[0]
            txt(surf, blk["date"], (CONTENT_X + CONTENT_W - dw - 18, oy + ROW_H//2 - 7),
                (100, 110, 140) if not is_open else (140, 160, 200), date_font)

            # count badge on collapsed
            if not is_open:
                count_str = f"{len(blk['entries'])} changes"
                cw = date_font.size(count_str)[0]
                txt(surf, count_str, (CONTENT_X + CONTENT_W - dw - cw - 36, oy + ROW_H//2 - 7),
                    (70, 80, 110), date_font)

            oy += ROW_H

            # expanded entries
            if is_open:
                ey = oy + EXPAND_PAD_TOP
                tag_w = 60
                # thin separator
                pygame.draw.line(surf, (50, 70, 110),
                                 (CONTENT_X + 20, oy), (CONTENT_X + CONTENT_W - 20, oy), 1)
                for tag, col, entry_text in blk["entries"]:
                    if ey > CONTENT_Y + CONTENT_H + 10:
                        break
                    draw_rect_alpha(surf, col, (CONTENT_X + 24, ey, tag_w, 18), 55, brad=4)
                    pygame.draw.rect(surf, col, (CONTENT_X + 24, ey, tag_w, 18), 1, border_radius=4)
                    txt(surf, tag, (CONTENT_X + 24 + tag_w//2, ey + 9), col, tag_font, center=True)
                    txt(surf, entry_text, (CONTENT_X + 24 + tag_w + 10, ey + 3),
                        (190, 200, 220), font_sm)
                    ey += ENTRY_H
                oy = ey + EXPAND_PAD_BOT

            oy += ROW_GAP

        surf.set_clip(old_clip)

        # Scrollbar
        if max_scroll > 0:
            sb_x = CONTENT_X + CONTENT_W + 8
            sb_h = CONTENT_H; sb_y = CONTENT_Y
            draw_rect_alpha(surf, (30,35,50), (sb_x, sb_y, 8, sb_h), 180, brad=4)
            thumb_h = max(30, int(sb_h * CONTENT_H / (total_h + 1)))
            thumb_y = sb_y + int((sb_h - thumb_h) * self._changelog_scroll / max(1, max_scroll))
            draw_rect_alpha(surf, (80,100,160), (sb_x, thumb_y, 8, thumb_h), 220, brad=4)
            txt(surf, "▲▼ scroll", (SCREEN_W//2, SCREEN_H - 16), (60,70,95), font_sm, center=True)

    # ── DIFFICULTY SELECTION ───────────────────────────────────────────────────
    def _draw_difficulty(self):
        self._draw_bg()
        surf = self.screen
        txt(surf, "SELECT DIFFICULTY", (SCREEN_W//2,58), C_WHITE,
            pygame.font.SysFont("consolas",43,bold=True), center=True)
        txt(surf, "Choose your challenge", (SCREEN_W//2,107), (100,110,140), font_sm, center=True)

        mx, my = pygame.mouse.get_pos()
        for name, rect in self.diff_cards.items():
            info = DIFFICULTIES[name]
            col = info["color"]
            is_hov = rect.collidepoint(mx,my)
            is_sel = (self.selected_difficulty == name)

            # card shadow
            draw_rect_alpha(surf, (0,0,0), (rect.x+6,rect.y+8,rect.w,rect.h), 75, brad=16)

            # card gradient background
            if is_sel:
                bg1 = tuple(min(255,c//2+22) for c in col)
                bg2 = tuple(min(255,c//4+12) for c in col)
            elif is_hov:
                bg1, bg2 = (36,44,68),(24,30,48)
            else:
                bg1, bg2 = (26,32,50),(16,20,36)
            draw_rect_gradient(surf, bg1, bg2, rect, alpha=242, brad=14)

            # top shine
            draw_rect_alpha(surf,(255,255,255),(rect.x+4,rect.y+2,rect.w-8,8),16,brad=12)

            border_col = col if (is_hov or is_sel) else C_BORDER
            bw = 3 if is_sel else (2 if is_hov else 1)
            pygame.draw.rect(surf, border_col, rect, bw, border_radius=14)

            # glow if selected
            if is_sel:
                draw_glow_circle(surf, col, rect.center, rect.h//2, 22)

            # cover art
            cover_rect = (rect.x+12, rect.y+12, rect.w-23, 158)
            COVER_DRAW_FUNCS[name](surf, cover_rect)

            # difficulty name
            name_font = pygame.font.SysFont("consolas", 16, bold=True)
            txt(surf, name.upper(), (rect.centerx, rect.y+183), col, name_font, center=True)

            # stars
            star_count = ["Easy","Hard","Hell"].index(name)+1
            star_x = rect.centerx - (star_count*26)//2 + 13
            for si in range(star_count):
                pygame.draw.polygon(surf, C_GOLD,
                    [(star_x+si*26 + 9*math.cos(math.radians(-90+i*72)),
                      rect.y+213 + 9*math.sin(math.radians(-90+i*72))) for i in range(5)])

            # desc
            for di, line in enumerate(info["desc"]):
                txt(surf, "• "+line, (rect.x+13, rect.y+239+di*22), (160,170,200), font_sm)

            # stats preview
            iy2 = rect.y+rect.h-58
            pygame.draw.line(surf, (50,60,80), (rect.x+10, iy2), (rect.right-10, iy2))
            txt(surf, f"Enemy HP: x{info['enemy_hp_mult']:.1f}", (rect.x+16, iy2+7), (140,150,180), font_sm)
            txt(surf, f"Start $: {info['start_money']}", (rect.x+16, iy2+25), (140,150,180), font_sm)

        # Back / Start
        self._draw_button(self.btn_diff_back, "<- BACK", (40,40,70), C_WHITE, font_md)
        if self.selected_difficulty:
            dc = DIFFICULTIES[self.selected_difficulty]["color"]
            self._draw_button(self.btn_diff_start,
                f"START  [{self.selected_difficulty.upper()}]", dc, C_BLACK, font_xl)
        else:
            draw_rect_alpha(surf, (30,35,50), self.btn_diff_start, 140, brad=10)
            pygame.draw.rect(surf, (50,55,70), self.btn_diff_start, 2, border_radius=10)
            txt(surf, "<- Select a difficulty", self.btn_diff_start.center, (80,90,110), font_lg, center=True)

    # ── LOADOUT SCREEN ─────────────────────────────────────────────────────────
    def _draw_loadout(self):
        self._draw_bg()
        surf = self.screen
        mx, my = pygame.mouse.get_pos()

        # ─── helpers ───────────────────────────────────────────────────────────
        def panel(r, bg=(18, 22, 38), alpha=240, brad=14):
            draw_rect_alpha(surf, bg, r, alpha, brad=brad)
            pygame.draw.rect(surf, (40, 50, 78), r, 1, border_radius=brad)

        def glabel(text, x, y, col=(70, 85, 125), fsize=11, bold=False):
            f = pygame.font.SysFont("consolas", fsize, bold=bold)
            txt(surf, text, (x, y), col, f)

        def gcenter(text, cx, y, col=C_WHITE, fsize=14, bold=False):
            f = pygame.font.SysFont("consolas", fsize, bold=bold)
            txt(surf, text, (cx, y), col, f, center=True)

        # ─── rebuild list rects (scroll-aware) ────────────────────────────────
        self.palette_rects = []
        for i in range(len(self.all_towers)):
            ry = (self._lo_list_y + i * (self._lo_list_item_h + self._lo_list_gap)
                  - self._lo_list_scroll)
            self.palette_rects.append(pygame.Rect(
                self._lo_list_x, ry, self._lo_list_item_w, self._lo_list_item_h))

        # ─── tower data tables ─────────────────────────────────────────────────
        tower_tags = {
            Assassin:    ["MELEE", "HD DETECT", "ABILITY"],
            Accelerator: ["LONG RANGE", "HD DETECT", "LASER"],
            Clown:       ["AoE AURA", "SLOW", "DEBUFF"],
            Archer:      ["ON-ROAD", "PIERCE", "ELEMENTS"],
            Zigres:      ["SUMMONS", "AoE", "COLOSSUS"],
            Gunner:      ["RANGED", "SHOP", "TURRET"],
        }
        tower_stats = {
            Assassin:    [("DMG", "HIGH"), ("SPD", "FAST"), ("RNG", "MELEE")],
            Accelerator: [("DMG", "MED"),  ("SPD", "SLOW"), ("RNG", "MAX")],
            Clown:       [("DMG", "MED"),  ("SPD", "MED"),  ("RNG", "WIDE")],
            Archer:      [("DMG", "MED"),  ("SPD", "FAST"), ("RNG", "LONG")],
            Zigres:      [("DMG", "HIGH"), ("SPD", "SLOW"), ("RNG", "MED")],
            Gunner:      [("DMG", "HIGH"), ("SPD", "MED"),  ("RNG", "LONG")],
        }
        tower_abilities = {
            Assassin:    ["Lv2: Shadow Step  (F key)", "Lv2: Detects Hidden"],
            Accelerator: ["Lv3: Dual-Target Lock", "Always Detects Hidden"],
            Clown:       ["Lv2: Slow Aura", "Lv4: Laugh Debuff", "Lv5: Confetti Burst"],
            Archer:      ["Lv2: Ice Arrow", "Lv3: Flame Arrow", "Lv4: Detects Hidden"],
            Zigres:      ["Lv3: Resonance AoE", "Lv4: Sentinel Thorns",
                          "Lv6: COLOSSUS Form"],
            Gunner:      ["Rotating turret barrel", "Lv3: Extended range",
                          "Shop exclusive — buy with coins"],
        }

        # ─── BACKGROUND PANELS ─────────────────────────────────────────────────
        # Left panel background
        lp = pygame.Rect(self._lo_list_x - 14, 96,
                         self._lo_list_item_w + 28,
                         SCREEN_H - 96 - 168)
        panel(lp, (14, 18, 30), 200, 16)

        # Right detail panel
        dp = pygame.Rect(self._lo_detail_x - 14, 96,
                         self._lo_detail_w + 28,
                         self._lo_detail_h + 14)
        panel(dp, (14, 18, 30), 200, 16)

        # Bottom deck bar
        deck_bg = pygame.Rect(40, SCREEN_H - 168, SCREEN_W - 80, 158)
        panel(deck_bg, (10, 13, 24), 235, 18)
        pygame.draw.rect(surf, (30, 38, 65), deck_bg, 1, border_radius=18)

        # ─── HEADER ────────────────────────────────────────────────────────────
        hf = pygame.font.SysFont("consolas", 36, bold=True)
        txt(surf, "LOADOUT", (SCREEN_W // 2, 34), C_WHITE, hf, center=True)
        pygame.draw.line(surf, (35, 45, 75),
                         (48, 60), (SCREEN_W - 48, 60), 1)

        # column labels
        glabel("TOWERS", self._lo_list_x, 76, (100, 120, 170), 11, bold=True)
        glabel("TOWER DETAILS",
               self._lo_detail_x, 76, (100, 120, 170), 11, bold=True)
        filled = sum(1 for t in self.loadout if t is not None)
        glabel(f"DECK  {filled}/5",
               deck_bg.x + 24, SCREEN_H - 160, (100, 120, 170), 11, bold=True)

        # ─── LEFT: tower list ──────────────────────────────────────────────────
        clip = pygame.Rect(self._lo_list_x - 14, 96,
                           self._lo_list_item_w + 28,
                           SCREEN_H - 96 - 168)
        old_clip = surf.get_clip()
        surf.set_clip(clip)

        for i, TType in enumerate(self.all_towers):
            r = self.palette_rects[i]
            if r.bottom < clip.top or r.top > clip.bottom:
                continue
            is_sel = (TType is self._lo_selected_tower)
            is_hov = r.collidepoint(mx, my)
            in_deck = TType in self.loadout

            # card bg
            if is_sel:
                bg_col = tuple(min(255, int(c * 0.25 + 18)) for c in TType.COLOR)
                draw_rect_alpha(surf, bg_col, r, 245, brad=12)
                pygame.draw.rect(surf, TType.COLOR, r, 2, border_radius=12)
            elif is_hov:
                draw_rect_alpha(surf, (30, 36, 60), r, 240, brad=12)
                pygame.draw.rect(surf, (60, 75, 120), r, 1, border_radius=12)
            else:
                draw_rect_alpha(surf, (20, 25, 42), r, 220, brad=12)
                pygame.draw.rect(surf, (32, 40, 65), r, 1, border_radius=12)

            # mini icon on left
            icon_x = r.x + 44
            icon_y = r.centery
            self._draw_tower_icon(surf, TType, icon_x, icon_y, 30)

            # name
            nf = pygame.font.SysFont("consolas", 17, bold=True)
            ncol = TType.COLOR if is_sel else C_WHITE
            txt(surf, TType.NAME, (r.x + 84, r.y + 18), ncol, nf)

            # cost row
            cf = pygame.font.SysFont("consolas", 12)
            cost_str = f"${TType.PLACE_COST}"
            if ICO_COIN:
                ci = pygame.transform.smoothscale(ICO_COIN, (16, 16))
                surf.blit(ci, (r.x + 84, r.y + 42))
                txt(surf, cost_str, (r.x + 104, r.y + 44), C_GOLD, cf)
            else:
                txt(surf, cost_str, (r.x + 84, r.y + 44), C_GOLD, cf)

            # tags
            tf_s = pygame.font.SysFont("consolas", 10, bold=True)
            tx = r.x + 84
            ty = r.y + 62
            for tag in tower_tags.get(TType, [])[:3]:
                tw_px = tf_s.size(tag)[0] + 10
                tag_r = pygame.Rect(tx, ty, tw_px, 17)
                tag_col = tuple(min(255, int(c * 0.45 + 10)) for c in TType.COLOR)
                draw_rect_alpha(surf, tag_col, tag_r, 200, brad=4)
                txt(surf, tag, (tx + 5, ty + 3), TType.COLOR, tf_s)
                tx += tw_px + 6

            # IN DECK badge on right
            if in_deck:
                bd_r = pygame.Rect(r.right - 72, r.y + 10, 64, 22)
                draw_rect_alpha(surf, (20, 100, 50), bd_r, 210, brad=5)
                bf = pygame.font.SysFont("consolas", 10, bold=True)
                txt(surf, "IN DECK", (bd_r.centerx, bd_r.centery),
                    (80, 230, 130), bf, center=True)

            # SHOP badge for shop-exclusive towers
            if TType is Gunner:
                purchased_towers = load_save().get("purchased_towers", [])
                is_bought = Gunner.__name__ in purchased_towers
                sh_r = pygame.Rect(r.right - 76, r.y + 36, 68, 20)
                if is_bought:
                    draw_rect_alpha(surf, (30, 70, 20), sh_r, 200, brad=4)
                    sf2 = pygame.font.SysFont("consolas", 9, bold=True)
                    txt(surf, "UNLOCKED", (sh_r.centerx, sh_r.centery),
                        (80, 230, 80), sf2, center=True)
                else:
                    draw_rect_alpha(surf, (70, 55, 10), sh_r, 200, brad=4)
                    pygame.draw.rect(surf, C_GOLD, sh_r, 1, border_radius=4)
                    sf2 = pygame.font.SysFont("consolas", 9, bold=True)
                    txt(surf, f"[S] {GUNNER_SHOP_PRICE}c", (sh_r.centerx, sh_r.centery),
                        C_GOLD, sf2, center=True)

            # MINI-GAME lock badge for Clown
            if TType is Clown:
                clown_owned = is_clown_unlocked()
                cl_r = pygame.Rect(r.right - 82, r.y + 36, 74, 20)
                if clown_owned:
                    draw_rect_alpha(surf, (30, 70, 20), cl_r, 200, brad=4)
                    sf3 = pygame.font.SysFont("consolas", 9, bold=True)
                    txt(surf, "UNLOCKED", (cl_r.centerx, cl_r.centery),
                        (80, 230, 80), sf3, center=True)
                else:
                    draw_rect_alpha(surf, (60, 20, 80), cl_r, 200, brad=4)
                    pygame.draw.rect(surf, (180, 80, 255), cl_r, 1, border_radius=4)
                    sf3 = pygame.font.SysFont("consolas", 9, bold=True)
                    txt(surf, "[L] KEY HUNT", (cl_r.centerx, cl_r.centery),
                        (180, 80, 255), sf3, center=True)

            # selected indicator bar on left edge
            if is_sel:
                sel_r = pygame.Rect(r.x, r.y + 8, 3, r.h - 16)
                pygame.draw.rect(surf, TType.COLOR, sel_r, border_radius=2)

        surf.set_clip(old_clip)

        # ─── RIGHT: detail panel ───────────────────────────────────────────────
        T = self._lo_selected_tower
        if T:
            dx = self._lo_detail_x
            dw = self._lo_detail_w
            dy = self._lo_detail_y

            # large tower icon
            big_icon_y = dy + 90
            self._draw_tower_icon(surf, T, dx + dw // 2, big_icon_y, 72)

            # name + cost
            nf2 = pygame.font.SysFont("consolas", 26, bold=True)
            txt(surf, T.NAME, (dx + dw // 2, dy + 162), T.COLOR, nf2, center=True)
            cf2 = pygame.font.SysFont("consolas", 14)
            if ICO_COIN:
                ci2 = pygame.transform.smoothscale(ICO_COIN, (20, 20))
                coin_tx = dx + dw // 2 - 40
                surf.blit(ci2, (coin_tx, dy + 186))
                txt(surf, f"${T.PLACE_COST}", (coin_tx + 24, dy + 188), C_GOLD, cf2)
            else:
                txt(surf, f"${T.PLACE_COST}", (dx + dw // 2, dy + 188), C_GOLD, cf2, center=True)

            # tags row centered
            tags = tower_tags.get(T, [])
            tf2 = pygame.font.SysFont("consolas", 11, bold=True)
            tag_total = sum(tf2.size(tg)[0] + 14 for tg in tags) + max(0, len(tags)-1)*8
            tx2 = dx + dw // 2 - tag_total // 2
            for tg in tags:
                tw2 = tf2.size(tg)[0] + 14
                tgr = pygame.Rect(tx2, dy + 210, tw2, 20)
                tg_bg = tuple(min(255, int(c * 0.4 + 8)) for c in T.COLOR)
                draw_rect_alpha(surf, tg_bg, tgr, 210, brad=4)
                txt(surf, tg, (tx2 + 7, dy + 212), T.COLOR, tf2)
                tx2 += tw2 + 8

            # divider
            pygame.draw.line(surf, (30, 38, 62),
                             (dx + 12, dy + 242), (dx + dw - 12, dy + 242))

            # stat bars
            stat_labels = {"NONE": 0, "LOW": 1, "MED": 2, "FAST": 2,
                           "HIGH": 3, "LONG": 3, "WIDE": 3, "MAX": 4}
            stats = tower_stats.get(T, [])
            sf = pygame.font.SysFont("consolas", 12)
            for si, (sname, sval) in enumerate(stats):
                sy = dy + 256 + si * 38
                txt(surf, sname, (dx + 16, sy), (90, 110, 160), sf)
                bar_x = dx + 70
                bar_w = dw - 90
                bar_h = 10
                bar_bg = pygame.Rect(bar_x, sy + 1, bar_w, bar_h)
                draw_rect_alpha(surf, (25, 32, 52), bar_bg, 240, brad=5)
                filled_frac = stat_labels.get(sval, 2) / 4
                fill_w = max(6, int(bar_w * filled_frac))
                fill_col = T.COLOR
                bar_fill = pygame.Rect(bar_x, sy + 1, fill_w, bar_h)
                draw_rect_alpha(surf, fill_col, bar_fill, 230, brad=5)
                txt(surf, sval, (dx + dw - 6, sy), (100, 120, 170), sf, right=True)

            # divider 2
            pygame.draw.line(surf, (30, 38, 62),
                             (dx + 12, dy + 375), (dx + dw - 12, dy + 375))

            # abilities / perks list
            glabel("ABILITIES", dx + 16, dy + 384, (80, 100, 155), 10, bold=True)
            af = pygame.font.SysFont("consolas", 12)
            for ai, ab in enumerate(tower_abilities.get(T, [])):
                ay = dy + 400 + ai * 24
                if ay + 16 < self._lo_detail_y + self._lo_detail_h - 20:
                    dot_col = tuple(min(255, c + 20) for c in T.COLOR)
                    pygame.draw.circle(surf, dot_col, (dx + 20, ay + 7), 3)
                    txt(surf, ab, (dx + 30, ay), (160, 175, 210), af)

            # ── ADD/REMOVE button ──
            ab_r = self._lo_btn_add
            in_deck_now = T in self.loadout
            deck_full = all(t is not None for t in self.loadout)
            if in_deck_now:
                btn_bg = (80, 22, 22)
                btn_brd = (200, 50, 50)
                btn_lbl = "✕  REMOVE FROM DECK"
                btn_col = (220, 80, 80)
            elif deck_full:
                btn_bg = (28, 32, 50)
                btn_brd = (50, 60, 85)
                btn_lbl = "DECK FULL  (remove a slot first)"
                btn_col = (60, 70, 100)
            else:
                btn_bg = (18, 75, 38)
                btn_brd = (50, 200, 100)
                btn_lbl = "+  ADD TO DECK"
                btn_col = (80, 220, 130)
            btn_hov = ab_r.collidepoint(mx, my)
            bg2 = tuple(min(255, c + 15) for c in btn_bg) if btn_hov else btn_bg
            draw_rect_alpha(surf, bg2, ab_r, 240, brad=10)
            pygame.draw.rect(surf, btn_brd, ab_r, 2, border_radius=10)
            bf2 = pygame.font.SysFont("consolas", 16, bold=True)
            txt(surf, btn_lbl, ab_r.center, btn_col, bf2, center=True)

        # ─── BOTTOM: deck slots ────────────────────────────────────────────────
        for i, r3 in enumerate(self.loadout_slot_rects):
            T3 = self.loadout[i]
            is_hov3 = r3.collidepoint(mx, my)

            if T3:
                bg3 = tuple(min(255, int(c * 0.22 + 14)) for c in T3.COLOR)
                brd3 = T3.COLOR
                brd_w = 2
            else:
                bg3 = (18, 22, 38)
                brd3 = (50, 60, 90) if is_hov3 else (32, 40, 62)
                brd_w = 1

            draw_rect_alpha(surf, bg3, r3, 240, brad=12)
            pygame.draw.rect(surf, brd3, r3, brd_w, border_radius=12)

            # slot number badge top-left
            nb_r = pygame.Rect(r3.x + 6, r3.y + 6, 22, 18)
            nb_col = tuple(min(255, int(c * 0.5)) for c in brd3) if T3 else (30, 38, 62)
            draw_rect_alpha(surf, nb_col, nb_r, 200, brad=4)
            nf3 = pygame.font.SysFont("consolas", 11, bold=True)
            txt(surf, str(i + 1), nb_r.center, C_WHITE, nf3, center=True)

            if T3:
                self._draw_tower_icon(surf, T3, r3.centerx, r3.centery - 16, 26)
                nf4 = pygame.font.SysFont("consolas", 12, bold=True)
                txt(surf, T3.NAME, (r3.centerx, r3.bottom - 36), C_WHITE, nf4, center=True)
                cf4 = pygame.font.SysFont("consolas", 11)
                txt(surf, f"${T3.PLACE_COST}", (r3.centerx, r3.bottom - 20), C_GOLD, cf4, center=True)
                if is_hov3:
                    ov3 = pygame.Surface((r3.w, r3.h), pygame.SRCALPHA)
                    pygame.draw.rect(ov3, (180, 30, 30, 70), (0, 0, r3.w, r3.h), border_radius=12)
                    surf.blit(ov3, r3.topleft)
                    rf3 = pygame.font.SysFont("consolas", 11, bold=True)
                    txt(surf, "CLICK TO REMOVE", (r3.centerx, r3.y + 14),
                        (240, 80, 80), rf3, center=True)
            else:
                ef = pygame.font.SysFont("consolas", 26, bold=True)
                txt(surf, "+", (r3.centerx, r3.centery - 8), (40, 52, 85), ef, center=True)
                ef2 = pygame.font.SysFont("consolas", 10)
                txt(surf, "EMPTY", (r3.centerx, r3.bottom - 22), (45, 58, 88), ef2, center=True)

        # ─── NAV BUTTONS ──────────────────────────────────────────────────────
        self._draw_button(self.btn_lo_back, "← BACK",
                          (22, 28, 48), C_WHITE, font_md, border=(55, 68, 105))
        sv2 = self.btn_lo_save
        sv2_hov = sv2.collidepoint(mx, my)
        sv2_bg = (20, 115, 58) if sv2_hov else (16, 90, 45)
        draw_rect_alpha(surf, sv2_bg, sv2, 245, brad=10)
        pygame.draw.rect(surf, (55, 220, 105), sv2, 2, border_radius=10)
        sf3 = pygame.font.SysFont("consolas", 15, bold=True)
        txt(surf, "SAVE LOADOUT", sv2.center, (90, 240, 140), sf3, center=True)


    # ── SANDBOX SCREEN ─────────────────────────────────────────────────────────
    def _build_sandbox_rects(self):
        """Build all UI rects for the sandbox config screen."""
        # Map selection buttons (3 maps)
        self._sb_map_rects = {}
        maps = ["Easy", "Hard", "Hell"]
        mw, mh = 200, 52
        total_mw = len(maps) * (mw + 16) - 16
        mx0 = SCREEN_W//2 - total_mw//2
        for i, name in enumerate(maps):
            self._sb_map_rects[name] = pygame.Rect(mx0 + i*(mw+16), 108, mw, mh)

        # Enemy toggle buttons (all enemy types)
        ENEMY_LIST = [
            (Enemy,            "Normal",      (160, 50,  50)),
            (TankEnemy,        "Tank",        (100, 60,  20)),
            (ScoutEnemy,       "Scout",       (40,  140, 180)),
            (HiddenEnemy,      "Hidden",      (100, 200, 100)),
            (BreakerEnemy,     "Breaker",     (140, 100, 20)),
            (ArmoredEnemy,     "Armored",     (80,  90,  110)),
            (NormalBoss,       "Boss",        (180, 140, 20)),
            (SlowBoss,         "SlowBoss",    (200, 140, 30)),
            (HiddenBoss,       "HiddenBoss",  (80,  160, 80)),
            (Necromancer,      "Necromancer", (100, 0,   160)),
            (GraveDigger,      "GraveDigger", (30,  100, 30)),
            # ── Sandbox-exclusive ──────────────────────────
            (GlassEnemy,       "Glass",       (160, 220, 255)),
            (SteelGolem,       "SteelGolem",  (120, 140, 160)),
            (RegeneratorEnemy, "Regen",       (40,  200, 90)),
            (PhantomBoss,      "Phantom",     (160, 60,  220)),
            (SwarmBoss,        "SwarmQueen",  (220, 120, 30)),
            (AbyssLord,        "AbyssLord",   (80,  0,   160)),
            # ── Weak starters ──────────────────────────────
            (BlobEnemy,        "Blob",        (40,  200, 80)),
            (PaperEnemy,       "Paper",       (220, 215, 170)),
            (ZombieEnemy,      "Zombie",      (90,  160, 50)),
            (BabyDragonEnemy,  "BabyDragon",  (220, 90,  30)),
            # ── Mid-game ────────────────────────────────────
            (MirrorShield,     "MirrorShield",(180, 200, 220)),
            (ShadowStepper,    "ShadowStep",  (130, 60,  220)),
            (VoltCrawler,      "VoltCrawler", (60,  200, 255)),
            (IronMaiden,       "IronMaiden",  (160, 155, 145)),
            (TimeBender,       "TimeBender",  (240, 200, 50)),
            # ── Demonic (Hell) ──────────────────────────────
            (HellHound,        "HellHound",   (220, 60,  15)),
            (AbyssalSpawn,     "AbyssSpawn",  (200, 30,  30)),
            (InfernoWyrm,      "InfernoWyrm", (255, 100, 0 )),
            (AshWraith,        "AshWraith",   (160, 145, 130)),
            (SoulReaper,       "SoulReaper",  (180, 0,   80)),
            (DemonKnight,      "DemonKnight", (100, 20,  180)),
            (CursedWitch,      "CursedWitch", (180, 0,   220)),
            (BrimstoneGolem,   "BrimGolem",   (200, 70,  0 )),
            (DoomBringer,      "DoomBringer", (180, 10,  30)),
            (HellGateKeeper,   "HellKeeper",  (220, 20,  50)),
        ]
        self._sb_enemy_list = ENEMY_LIST
        ew, eh = 190, 44   # компактные чипы (было 220x68)
        eg = 8
        cols = 7           # 7 колонок вместо 5
        total_ew = cols * (ew + eg) - eg
        ex0 = SCREEN_W//2 - total_ew//2
        self._sb_enemy_rects = []
        for i, (ecls, ename, ecol) in enumerate(ENEMY_LIST):
            col_i = i % cols
            row_i = i // cols
            self._sb_enemy_rects.append(
                pygame.Rect(ex0 + col_i*(ew+eg), 210 + row_i*(eh+7), ew, eh)
            )

        # How many rows of enemies
        n_rows = (len(ENEMY_LIST) + cols - 1) // cols
        enemy_grid_bottom = 210 + n_rows * (eh + 10) + 18

        # Tower (unit) selection
        tw, th = 200, 58
        tg = 18
        total_tw = len(self.all_towers) * (tw + tg) - tg
        tx0 = SCREEN_W//2 - total_tw//2
        self._sb_tower_rects = []
        for i in range(len(self.all_towers)):
            self._sb_tower_rects.append(pygame.Rect(tx0 + i*(tw+tg), enemy_grid_bottom + 32, tw, th))

        # Loadout slots (5)
        slw, slh = 150, 52
        slg = 14
        total_slw = 5*(slw+slg)-slg
        slx0 = SCREEN_W//2 - total_slw//2
        slots_y = enemy_grid_bottom + 32 + th + 18
        self._sb_slot_rects = [pygame.Rect(slx0+i*(slw+slg), slots_y, slw, slh) for i in range(5)]

        # Count spinners (enemy count per type) - parallel to enemy_rects
        self._sb_count_rects_minus = []
        self._sb_count_rects_plus  = []
        for r2 in self._sb_enemy_rects:
            # Place [-] [count] [+] at right side of compact chip
            self._sb_count_rects_minus.append(pygame.Rect(r2.right - 58, r2.centery - 9, 18, 18))
            self._sb_count_rects_plus.append( pygame.Rect(r2.right - 22, r2.centery - 9, 18, 18))

        # Enemy counts dict
        if not hasattr(self, '_sb_enemy_counts'):
            self._sb_enemy_counts = {ecls: 0 for ecls, _, _ in ENEMY_LIST}

        # Sandbox loadout
        if not hasattr(self, '_sb_loadout'):
            self._sb_loadout = [None]*5

        # Difficulty mode buttons
        dw2, dh2 = 170, 46
        dg2 = 14
        modes = ["Easy", "Hard", "Hell"]
        total_dw2 = len(modes)*(dw2+dg2)-dg2
        dx0 = SCREEN_W//2 - total_dw2//2
        diff_y = slots_y + slh + 20
        self._sb_diff_rects = {}
        for i, name in enumerate(modes):
            self._sb_diff_rects[name] = pygame.Rect(dx0+i*(dw2+dg2), diff_y, dw2, dh2)
        if not hasattr(self, '_sb_selected_diff'):
            self._sb_selected_diff = None

        # Buttons
        self._sb_btn_back   = pygame.Rect(28, 28, 144, 46)
        start_y = diff_y + dh2 + 18
        self._sb_btn_start_sandbox = pygame.Rect(SCREEN_W//2-200, start_y, 400, 62)

    def _draw_sandbox(self):
        self._draw_bg()
        surf = self.screen
        mx, my = pygame.mouse.get_pos()

        # Make sure rects are built
        if not hasattr(self, '_sb_map_rects'):
            self._build_sandbox_rects()

        # ── Header ──
        hf = pygame.font.SysFont("consolas", 38, bold=True)
        txt(surf, "🧪 SANDBOX MODE", (SCREEN_W//2, 46), (80,255,160), hf, center=True)
        txt(surf, "Infinite money  •  Custom enemies & loadout  •  No waves",
            (SCREEN_W//2, 84), (80,110,90), font_sm, center=True)

        # ── Section: Map ──
        txt(surf, "MAP", (SCREEN_W//2, 96), (120,130,160), font_sm, center=True)
        for name, r in self._sb_map_rects.items():
            sel = (self._sandbox_cfg["map"] == name)
            col = DIFFICULTIES[name]["color"]
            bg = (30,50,30) if sel else (22,28,40)
            draw_rect_alpha(surf, bg, r, 230, brad=8)
            pygame.draw.rect(surf, col if sel else C_BORDER, r, 2 if sel else 1, border_radius=8)
            txt(surf, name, r.center, col if sel else (140,150,170),
                pygame.font.SysFont("consolas",16,bold=True), center=True)

        # ── Section: Enemies ──
        ey_label_y = self._sb_enemy_rects[0].y - 22
        txt(surf, "ENEMIES  (click to toggle, +/- to set count)", (SCREEN_W//2, ey_label_y),
            (120,130,160), font_sm, center=True)

        name_f2   = pygame.font.SysFont("consolas", 13, bold=True)
        hp_f      = pygame.font.SysFont("consolas", 11)
        spin_f    = pygame.font.SysFont("consolas", 13, bold=True)
        ICON_R    = 13   # меньший радиус для компактного чипа

        for i, (ecls, ename, ecol) in enumerate(self._sb_enemy_list):
            r = self._sb_enemy_rects[i]
            count  = self._sb_enemy_counts.get(ecls, 0)
            active = count > 0
            draw_rect_alpha(surf, ecol, r, 55 if active else 18, brad=8)
            pygame.draw.rect(surf, ecol if active else C_BORDER, r,
                             2 if active else 1, border_radius=8)

            # ── Иконка врага (слева, маленькая) ──
            icon_cx = r.x + ICON_R + 6
            icon_cy = r.centery
            icon_surf = pygame.Surface((ICON_R*4, ICON_R*4), pygame.SRCALPHA)
            try:
                dummy = ecls.__new__(ecls)
                dummy.x    = float(ICON_R * 2)
                dummy.y    = float(ICON_R * 2)
                dummy.radius = ICON_R
                dummy._bob  = 0.0
                dummy._stun_timer  = 0.0
                dummy._slow_factor = 1.0
                dummy._fire_timer  = 0.0
                dummy._ice_timer   = 0.0
                dummy._rot         = 0.0
                dummy._pulse       = 0.0
                dummy._phase_timer = 4.0
                dummy._phased      = False
                dummy.IS_HIDDEN    = getattr(ecls, 'IS_HIDDEN', False)
                dummy.alive        = True
                dummy._draw_hp_bar   = lambda *a, **kw: None
                dummy._hover_label   = lambda *a, **kw: None
                dummy._draw_status_effects = lambda *a, **kw: None
                dummy.draw(icon_surf, hovered=False, detected=True)
            except Exception:
                pygame.draw.circle(icon_surf, ecol, (ICON_R*2, ICON_R*2), ICON_R)
            surf.blit(icon_surf, (icon_cx - ICON_R*2, icon_cy - ICON_R*2))

            # ── Имя + HP в одну-две строки ──
            tx = icon_cx + ICON_R + 6
            base_hp = ecls.BASE_HP
            # Область для текста: от tx до спиннеров (r.right - 68)
            txt(surf, ename, (tx, r.centery - 9),
                ecol if active else (180, 190, 210), name_f2)
            txt(surf, f"HP: {base_hp}", (tx, r.centery + 4),
                (120, 130, 155), hp_f)

            # ── Компактный спиннер справа ──
            rm = self._sb_count_rects_minus[i]
            rp = self._sb_count_rects_plus[i]
            draw_rect_alpha(surf, (60, 15, 15), rm, 210, brad=4)
            draw_rect_alpha(surf, (15, 60, 15), rp, 210, brad=4)
            pygame.draw.rect(surf, (180, 50, 50),  rm, 1, border_radius=4)
            pygame.draw.rect(surf, (50, 180, 50),  rp, 1, border_radius=4)
            txt(surf, "-", rm.center, (240, 80,  80),  spin_f, center=True)
            txt(surf, "+", rp.center, (80,  240, 80),  spin_f, center=True)
            cnt_cx = rm.right + (rp.x - rm.right) // 2
            txt(surf, str(count), (cnt_cx, rm.centery),
                (220, 220, 220), spin_f, center=True)

        # ── Section: Towers (loadout) ──
        tow_label_y = self._sb_tower_rects[0].y - 20
        txt(surf, "LOADOUT  (click to add/remove)", (SCREEN_W//2, tow_label_y),
            (120,130,160), font_sm, center=True)

        for i, TType in enumerate(self.all_towers):
            r = self._sb_tower_rects[i]
            in_loadout = TType in self._sb_loadout
            hov = r.collidepoint(mx, my)
            bg = (30,50,80) if in_loadout else (22,28,40)
            draw_rect_alpha(surf, bg, r, 220, brad=8)
            pygame.draw.rect(surf, (C_CYAN if in_loadout else C_BORDER), r, 2 if in_loadout else 1, border_radius=8)
            self._draw_tower_icon(surf, TType, r.x+28, r.centery, 22)
            txt(surf, TType.NAME, (r.x+52, r.centery-8), TType.COLOR,
                pygame.font.SysFont("consolas",13,bold=True))
            txt(surf, f"${TType.PLACE_COST}", (r.x+52, r.centery+6), C_GOLD, font_sm)

        # Slots display
        slot_label_y = self._sb_slot_rects[0].y - 18
        txt(surf, "Active slots:", (SCREEN_W//2, slot_label_y), (100,110,140), font_sm, center=True)
        for i, r in enumerate(self._sb_slot_rects):
            TType = self._sb_loadout[i]
            draw_rect_alpha(surf, (28,35,50), r, 210, brad=6)
            pygame.draw.rect(surf, C_BORDER, r, 1, border_radius=6)
            txt(surf, f"#{i+1}", (r.x+4, r.y+3), (50,60,80), font_sm)
            if TType:
                self._draw_tower_icon(surf, TType, r.x+20, r.centery, 18)
                txt(surf, TType.NAME, (r.x+36, r.centery-5), TType.COLOR,
                    pygame.font.SysFont("consolas",12,bold=True))
            else:
                txt(surf, "—", r.center, (50,60,80), font_sm, center=True)

        # ── Section: Difficulty mode (for money rewards) ──
        diff_lbl_y = self._sb_diff_rects["Easy"].y - 20
        txt(surf, "MONEY REWARDS  (optional — leave unselected for infinite money only)",
            (SCREEN_W//2, diff_lbl_y), (120,130,160), font_sm, center=True)
        for name, r in self._sb_diff_rects.items():
            sel = (self._sb_selected_diff == name)
            col = DIFFICULTIES[name]["color"]
            bg2 = (30,50,30) if sel else (22,28,40)
            draw_rect_alpha(surf, bg2, r, 220, brad=8)
            pygame.draw.rect(surf, col if sel else C_BORDER, r, 2 if sel else 1, border_radius=8)
            label_d = f"{'✔ ' if sel else ''}{name}"
            txt(surf, label_d, r.center, col if sel else (140,150,170),
                pygame.font.SysFont("consolas",15,bold=True), center=True)

        # ── Start button ──
        any_enemy = any(v > 0 for v in self._sb_enemy_counts.values())
        start_col = (20,110,60) if any_enemy else (30,40,40)
        start_tcol = (80,255,160) if any_enemy else (60,70,70)
        self._draw_button(self._sb_btn_start_sandbox,
                          "▶  START SANDBOX" if any_enemy else "Select at least 1 enemy",
                          start_col, start_tcol, font_lg)

        # Back
        self._draw_button(self._sb_btn_back, "<- BACK", (40,40,70), C_WHITE, font_md)

    # ── SHOP SCREEN ────────────────────────────────────────────────────────────
    def _build_shop_items(self):
        """Returns list of (tower_class, shop_price, label, desc) for shop items."""
        return [
            (Gunner, GUNNER_SHOP_PRICE,
             "Gunner Tower",
             "Rotating turret. High damage, good range.\nSimple but effective against all enemies."),
        ]

    def _shop_handle_buy(self, idx):
        items = self._build_shop_items()
        if idx >= len(items): return
        tower_cls, price, label, _ = items[idx]
        data = load_save()
        purchased = data.get("purchased_towers", [])
        cls_name = tower_cls.__name__
        # Block if already owned
        if cls_name in purchased:
            self._shop_msg = f"{label} already owned!"
            self._shop_msg_t = 2.0
            return
        if data["shop_coins"] < price:
            self._shop_msg = "Not enough coins!"
            self._shop_msg_t = 2.0
            return
        # Deduct coins and save
        data["shop_coins"] -= price
        purchased.append(cls_name)
        data["purchased_towers"] = purchased
        save_data(data)
        self._shop_msg = f"Purchased {label}!"
        self._shop_msg_t = 2.5

    def _draw_shop(self):
        self._draw_bg()
        surf = self.screen
        t = self.anim_t

        if not hasattr(self, '_shop_msg'):
            self._shop_msg = ""
            self._shop_msg_t = 0.0
        if self._shop_msg_t > 0:
            self._shop_msg_t -= 1/FPS

        coins = get_shop_coins()

        # ── Header ──
        hf = pygame.font.SysFont("consolas", 48, bold=True)
        txt(surf, "[S] SHOP", (SCREEN_W//2, 52), C_GOLD, hf, center=True)
        pygame.draw.line(surf, (80, 60, 20), (200, 88), (SCREEN_W-200, 88), 1)

        # ── Coin display bar ──
        coin_bar_w = 280; coin_bar_h = 52
        coin_bar_x = SCREEN_W//2 - coin_bar_w//2
        coin_bar_y = 102
        draw_rect_alpha(surf, (50, 38, 10), (coin_bar_x, coin_bar_y, coin_bar_w, coin_bar_h), 230, brad=14)
        pygame.draw.rect(surf, C_GOLD, (coin_bar_x, coin_bar_y, coin_bar_w, coin_bar_h), 2, border_radius=14)
        # animated coin
        pulse_c = abs(math.sin(t * 2.5))
        cr2 = int(17 + pulse_c * 3)
        ccx = coin_bar_x + 30
        ccy = coin_bar_y + coin_bar_h // 2
        pygame.draw.circle(surf, (180, 140, 0), (ccx, ccy), cr2)
        pygame.draw.circle(surf, (255, 215, 0), (ccx, ccy), cr2, 3)
        pygame.draw.circle(surf, (255, 240, 120), (ccx - 4, ccy - 4), cr2 // 3)
        cf_big = pygame.font.SysFont("consolas", 26, bold=True)
        txt(surf, f"{coins}  coins", (ccx + cr2 + 10, ccy), C_GOLD, cf_big)

        # ── Info text ──
        info_f = pygame.font.SysFont("consolas", 14)
        txt(surf, "Earn coins by completing waves. More coins on higher difficulties.",
            (SCREEN_W//2, 176), (130, 110, 60), info_f, center=True)

        # ── Shop items ──
        items = self._build_shop_items()
        item_w = 580; item_h = 180
        self._shop_item_rects = []
        mx, my = pygame.mouse.get_pos()

        purchased_data = load_save().get("purchased_towers", [])

        for idx, (tower_cls, price, label, desc) in enumerate(items):
            ix = SCREEN_W//2 - item_w//2
            iy = 220 + idx * (item_h + 24)
            r = pygame.Rect(ix, iy, item_w, item_h)
            self._shop_item_rects.append(r)

            already_owned = tower_cls.__name__ in purchased_data
            can_afford = (coins >= price) and not already_owned
            hov = r.collidepoint(mx, my)

            # card bg
            if already_owned:
                bg_c = (14, 40, 22)
                brd_c = (40, 160, 70)
            elif hov and can_afford:
                bg_c = (50, 38, 10)
                brd_c = C_GOLD
            else:
                bg_c = (22, 18, 8)
                brd_c = (80, 65, 30) if can_afford else (50, 45, 40)

            draw_rect_alpha(surf, bg_c, r, 230, brad=14)
            pygame.draw.rect(surf, brd_c, r, 2, border_radius=14)

            # tower icon
            icon_cx = ix + 80; icon_cy = iy + item_h // 2
            self._draw_tower_icon(surf, tower_cls, icon_cx, icon_cy, 52)

            # name
            nf = pygame.font.SysFont("consolas", 24, bold=True)
            name_col = (80, 230, 120) if already_owned else (tower_cls.COLOR if can_afford else (120, 110, 90))
            txt(surf, label, (ix + 160, iy + 28), name_col, nf)

            # description
            df = pygame.font.SysFont("consolas", 13)
            for li, line in enumerate(desc.split("\n")):
                txt(surf, line, (ix + 160, iy + 62 + li * 20), (160, 145, 110), df)

            # price / owned badge
            if already_owned:
                badge_f = pygame.font.SysFont("consolas", 16, bold=True)
                txt(surf, "✔  OWNED", (ix + 160, iy + 118), (80, 230, 120), badge_f)
            else:
                pf = pygame.font.SysFont("consolas", 18, bold=True)
                p_col = C_GOLD if can_afford else (100, 85, 50)
                # coin mini icon
                pygame.draw.circle(surf, (180,140,0), (ix+163, iy+125), 11)
                pygame.draw.circle(surf, (255,215,0), (ix+163, iy+125), 11, 2)
                txt(surf, f"{price}  coins", (ix + 180, iy + 117), p_col, pf)
                if not can_afford:
                    nef = pygame.font.SysFont("consolas", 11)
                    txt(surf, f"Need {price - coins} more", (ix + 180, iy + 140), (160, 80, 60), nef)

            # hover buy button
            if hov and can_afford and not already_owned:
                btn_r = pygame.Rect(ix + item_w - 148, iy + item_h - 52, 132, 38)
                draw_rect_alpha(surf, (80, 60, 10), btn_r, 230, brad=8)
                pygame.draw.rect(surf, C_GOLD, btn_r, 2, border_radius=8)
                bf = pygame.font.SysFont("consolas", 16, bold=True)
                txt(surf, "BUY", btn_r.center, C_GOLD, bf, center=True)

        # ── Message ──
        if self._shop_msg and self._shop_msg_t > 0:
            alpha = min(255, int(self._shop_msg_t * 180))
            mf = pygame.font.SysFont("consolas", 22, bold=True)
            ms = mf.render(self._shop_msg, True, C_GOLD)
            ms.set_alpha(alpha)
            surf.blit(ms, ms.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 60)))

        # ── Back button ──
        self._shop_btn_back = pygame.Rect(29, 29, 140, 46)
        self._draw_button(self._shop_btn_back, "<- BACK", (40,40,70), C_WHITE, font_md)

    # ── EVENT HANDLING ─────────────────────────────────────────────────────────
    def handle_event(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            if self.state != "main":
                self.state = "main"
            # ESC on main screen does nothing (no quit)

        if ev.type != pygame.MOUSEBUTTONDOWN or ev.button != 1:
            return None
        pos = ev.pos

        if self.state == "main":
            if self.btn_play.collidepoint(pos):
                self.state = "difficulty"
            elif self.btn_loadout.collidepoint(pos):
                self.state = "loadout"
            elif self.btn_sandbox.collidepoint(pos):
                self.state = "sandbox"
                self._build_sandbox_rects()
            elif self.btn_shop.collidepoint(pos):
                self.state = "shop"
            elif self.btn_minigame.collidepoint(pos):
                # Only launch boss fight when all 12 keys collected
                arena = ClownBossArena(self.screen)
                won = arena.run()
                if won:
                    unlock_clown()
            elif self.btn_changelog.collidepoint(pos):
                self.state = "changelog"
                self._changelog_scroll = 0
                self._changelog_open_idx = None
            elif self.btn_quit.collidepoint(pos):
                return "quit"

        elif self.state == "difficulty":
            if self.btn_diff_back.collidepoint(pos):
                self.state = "main"
            for name, rect in self.diff_cards.items():
                if rect.collidepoint(pos):
                    self.selected_difficulty = name
            if self.selected_difficulty and self.btn_diff_start.collidepoint(pos):
                return "start"

        elif self.state == "loadout":
            if self.btn_lo_back.collidepoint(pos):
                self.state = "main"
            elif self.btn_lo_save.collidepoint(pos):
                self.state = "main"
            else:
                # Click on tower list row → select for detail panel
                for i, r in enumerate(self.palette_rects):
                    if r.collidepoint(pos):
                        self._lo_selected_tower = self.all_towers[i]
                        break

                # Click ADD/REMOVE button in detail panel
                if hasattr(self, '_lo_btn_add') and self._lo_btn_add.collidepoint(pos):
                    T = self._lo_selected_tower
                    if T is not None:
                        # Block locked towers
                        if T is Clown and not is_clown_unlocked():
                            pass  # silently block — badge makes it obvious
                        elif T is Gunner and Gunner.__name__ not in load_save().get("purchased_towers", []):
                            pass
                        elif T in self.loadout:
                            for si in range(5):
                                if self.loadout[si] is T:
                                    self.loadout[si] = None
                                    break
                        else:
                            for si in range(5):
                                if self.loadout[si] is None:
                                    self.loadout[si] = T
                                    break

                # Click on deck slot → clear it
                for i, r in enumerate(self.loadout_slot_rects):
                    if r.collidepoint(pos) and self.loadout[i] is not None:
                        self.loadout[i] = None

        elif self.state == "changelog":
            if self.btn_diff_back.collidepoint(pos):
                self.state = "main"
            else:
                for i, r in enumerate(getattr(self, '_changelog_row_rects', [])):
                    if r.collidepoint(pos):
                        if self._changelog_open_idx == i:
                            self._changelog_open_idx = None
                        else:
                            self._changelog_open_idx = i
                        break

        elif self.state == "shop":
            if hasattr(self, '_shop_btn_back') and self._shop_btn_back.collidepoint(pos):
                self.state = "main"
            elif hasattr(self, '_shop_item_rects'):
                for idx, r in enumerate(self._shop_item_rects):
                    if r.collidepoint(pos):
                        self._shop_handle_buy(idx)
                        break

        elif self.state == "sandbox":
            if not hasattr(self, '_sb_map_rects'):
                self._build_sandbox_rects()
            if self._sb_btn_back.collidepoint(pos):
                self.state = "main"
                return None
            # Map selection
            for name, r in self._sb_map_rects.items():
                if r.collidepoint(pos):
                    self._sandbox_cfg["map"] = name
            # Enemy toggle / count
            for i, (ecls, _, _) in enumerate(self._sb_enemy_list):
                r = self._sb_enemy_rects[i]
                rm = self._sb_count_rects_minus[i]
                rp = self._sb_count_rects_plus[i]
                if rp.collidepoint(pos):
                    self._sb_enemy_counts[ecls] = min(50, self._sb_enemy_counts.get(ecls,0)+1)
                elif rm.collidepoint(pos):
                    self._sb_enemy_counts[ecls] = max(0, self._sb_enemy_counts.get(ecls,0)-1)
                elif r.collidepoint(pos):
                    cur = self._sb_enemy_counts.get(ecls,0)
                    self._sb_enemy_counts[ecls] = 0 if cur>0 else 5
            # Tower loadout toggle
            for i, TType in enumerate(self.all_towers):
                r = self._sb_tower_rects[i]
                if r.collidepoint(pos):
                    if TType in self._sb_loadout:
                        idx2 = self._sb_loadout.index(TType)
                        self._sb_loadout[idx2] = None
                    else:
                        for si in range(5):
                            if self._sb_loadout[si] is None:
                                self._sb_loadout[si] = TType
                                break
            # Difficulty reward mode
            for name, r in self._sb_diff_rects.items():
                if r.collidepoint(pos):
                    self._sb_selected_diff = None if self._sb_selected_diff==name else name
            # Start sandbox
            any_enemy = any(v>0 for v in self._sb_enemy_counts.values())
            if any_enemy and self._sb_btn_start_sandbox.collidepoint(pos):
                return "start_sandbox"
        return None

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS)/1000.0, 0.05)
            self.anim_t += dt

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                # Mouse wheel scroll for changelog
                if ev.type == pygame.MOUSEWHEEL and self.state == "changelog":
                    self._changelog_scroll -= ev.y * 28
                # Mouse wheel for sandbox enemy counts
                if ev.type == pygame.MOUSEWHEEL and self.state == "sandbox":
                    if hasattr(self, '_sb_enemy_rects'):
                        mx2, my2 = pygame.mouse.get_pos()
                        for i, (ecls, _, _) in enumerate(self._sb_enemy_list):
                            if self._sb_enemy_rects[i].collidepoint(mx2, my2):
                                self._sb_enemy_counts[ecls] = max(0, min(50,
                                    self._sb_enemy_counts.get(ecls,0)+ev.y))
                result = self.handle_event(ev)
                if result == "quit":
                    pygame.quit(); sys.exit()
                if result == "start":
                    save_loadout(self.loadout)
                    return self.selected_difficulty, list(self.loadout)
                if result == "start_sandbox":
                    return "sandbox", {
                        "map":      self._sandbox_cfg["map"],
                        "enemies":  dict(self._sb_enemy_counts),
                        "loadout":  list(self._sb_loadout),
                        "diff_rewards": self._sb_selected_diff,
                    }

            if self.state == "main":
                self._draw_main()
            elif self.state == "difficulty":
                self._draw_difficulty()
            elif self.state == "loadout":
                self._draw_loadout()
            elif self.state == "changelog":
                self._draw_changelog()
            elif self.state == "sandbox":
                self._draw_sandbox()
            elif self.state == "shop":
                self._draw_shop()

            pygame.display.flip()


# ── Game with difficulty applied ───────────────────────────────────────────────
class Game:
    def __init__(self, difficulty="Hard", loadout=None, screen_override=None):
        if screen_override is not None:
            self.screen = screen_override
        else:
            self.screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
        pygame.display.set_caption("Tower Defense"); self.clock=pygame.time.Clock(); self.running=True

        diff = DIFFICULTIES.get(difficulty, DIFFICULTIES["Hard"])
        self.player_hp=int(100*diff["hp_mult"]); self.player_maxhp=self.player_hp
        self.money=diff["start_money"]
        self._enemy_hp_mult=diff["enemy_hp_mult"]
        self._enemy_speed_mult=diff["enemy_speed_mult"]
        self._difficulty_name=difficulty

        self.enemies=[]; self.units=[]; self.effects=[]
        _wdata = {"Easy": WAVE_DATA_EASY, "Hard": WAVE_DATA, "Hell": WAVE_DATA_HELL}.get(difficulty, WAVE_DATA)
        self.wave_mgr=WaveManager(wave_data=_wdata); self.ui=UI()
        if loadout:
            self.ui.SLOT_TYPES = loadout

        self.game_over=False; self.win=False; self._win_coins_earned=0
        self._defeat_this_frame=False; self._boss_enemy=None
        self.speed_x2=False  # 2x speed toggle
        self.anim_t=0.0      # for win/lose screen animations

        # Clown Key fragments appear during gameplay if Clown not yet unlocked
        if not is_clown_unlocked():
            self._key_mgr = InGameKeyManager(difficulty)
        else:
            self._key_mgr = None

        # Patch enemy stats with difficulty multipliers
        self._patch_enemies()
        # Dev console (F3 to open)
        self.dev_console = DevConsole()

    def _get_hell_hp_mult(self):
        """Return a progressive HP multiplier for Hell mode based on current wave.
        Early waves are much easier; difficulty ramps up toward the end."""
        wave = self.wave_mgr.wave if hasattr(self, 'wave_mgr') else 1
        if wave <= 3:
            return 0.55   # Волны 1-3:  очень лёгкие
        elif wave <= 6:
            return 0.70   # Волны 4-6:  лёгкие
        elif wave <= 10:
            return 0.85   # Волны 7-10: средние
        elif wave <= 14:
            return 1.0    # Волны 11-14: полная сложность
        else:
            return 1.1    # Волны 15-20: оригинальный Hell

    def _patch_enemies(self):
        """Apply difficulty multipliers to all enemy classes."""
        self._orig_enemy_inits = {}
        m_hp = self._enemy_hp_mult
        m_spd = self._enemy_speed_mult
        is_hell = self._difficulty_name == "Hell"
        game_ref = self  # ссылка на игру для динамического мультиплаера
        classes = [Enemy, TankEnemy, ScoutEnemy, NormalBoss, HiddenEnemy,
                   BreakerEnemy, ArmoredEnemy, SlowBoss, HiddenBoss, Necromancer, GraveDigger,
                   MirrorShield, ShadowStepper, VoltCrawler, IronMaiden, TimeBender,
                   GlassEnemy, SteelGolem, RegeneratorEnemy, PhantomBoss,
                   SwarmBoss, AbyssLord, BlobEnemy, PaperEnemy, ZombieEnemy, BabyDragonEnemy]
        for cls in classes:
            orig = cls.__init__
            self._orig_enemy_inits[cls] = orig
            def patched(self_e, *args, _orig=orig, _mhp=m_hp, _mspd=m_spd,
                        _is_hell=is_hell, _game=game_ref, **kw):
                _orig(self_e, *args, **kw)
                # В Hell режиме HP мультиплаер зависит от текущей волны
                actual_mhp = _game._get_hell_hp_mult() if _is_hell else _mhp
                self_e.hp = self_e.hp * actual_mhp
                self_e.maxhp = self_e.maxhp * actual_mhp
                self_e.speed = self_e.speed * _mspd
            cls.__init__ = patched

    def _restore_enemies(self):
        for cls, orig in self._orig_enemy_inits.items():
            cls.__init__ = orig

    def draw_map(self):
        surf=self.screen
        if self._difficulty_name == "Easy":
            self._draw_map_easy(surf)
        elif self._difficulty_name == "Hard":
            self._draw_map_hard(surf)
        else:
            self._draw_map_hell(surf)
        # difficulty badge
        dcol = DIFFICULTIES[self._difficulty_name]["color"]
        pygame.draw.rect(surf, (20,24,36), (SCREEN_W-100,0,100,28))
        pygame.draw.rect(surf, dcol, (SCREEN_W-100,0,100,28), 2)
        txt(surf, self._difficulty_name.upper(), (SCREEN_W-50,14), dcol, font_md, center=True)

    def _draw_path_line(self, surf, col_dark, col_mid, pw=PATH_H*2):
        """Draw the standard straight path"""
        pygame.draw.rect(surf, col_dark, (0, PATH_Y-PATH_H, SCREEN_W, PATH_H*2))
        pygame.draw.line(surf, (max(0,col_mid[0]-30),max(0,col_mid[1]-30),max(0,col_mid[2]-30)),
                         (0,PATH_Y-PATH_H),(SCREEN_W,PATH_Y-PATH_H),2)
        pygame.draw.line(surf, (max(0,col_mid[0]-30),max(0,col_mid[1]-30),max(0,col_mid[2]-30)),
                         (0,PATH_Y+PATH_H),(SCREEN_W,PATH_Y+PATH_H),2)
        pygame.draw.rect(surf,(60,20,20),(0,PATH_Y-PATH_H,12,PATH_H*2))
        txt(surf,"S",(6,PATH_Y-5),C_RED,font_sm,center=True)
        pygame.draw.rect(surf,(20,60,20),(SCREEN_W-12,PATH_Y-PATH_H,12,PATH_H*2))
        txt(surf,"E",(SCREEN_W-6,PATH_Y-5),C_GREEN,font_sm,center=True)

    def _draw_map_easy(self, surf):
        """Sunny green grassland map — full screen version"""
        surf.fill((34, 85, 34))
        rng = random.Random(42)
        # Dense grass texture
        for _ in range(600):
            gx=rng.randint(0,SCREEN_W); gy=rng.randint(72,SLOT_AREA_Y-5)
            if abs(gy-PATH_Y)>PATH_H+8:
                pygame.draw.circle(surf,(rng.randint(30,55),rng.randint(90,115),rng.randint(30,55)),(gx,gy),rng.randint(1,3))
        # Scattered wildflowers
        rng2 = random.Random(7)
        flower_cols = [(220,80,80),(220,200,60),(180,80,220),(80,200,220),(255,160,50)]
        for _ in range(80):
            fx=rng2.randint(0,SCREEN_W); fy=rng2.randint(80,SLOT_AREA_Y-20)
            if abs(fy-PATH_Y)>PATH_H+22:
                fc=rng2.choice(flower_cols)
                pygame.draw.circle(surf,fc,(fx,fy),3)
                pygame.draw.circle(surf,(255,240,180),(fx,fy),1)
        # Trees — large, detailed
        trees = [(80,260,22),(200,210,18),(420,190,24),(660,240,20),(900,200,22),
                 (1100,230,18),(1300,200,20),(1500,250,22),(1700,210,18),(1860,240,20),
                 (80,760,20),(250,800,17),(500,780,22),(720,770,19),(960,790,21),
                 (1180,760,18),(1400,790,23),(1620,770,20),(1800,800,17),(1920,760,19)]
        for tx,ty,tr in trees:
            # shadow
            pygame.draw.ellipse(surf,(20,60,20),(tx-tr,ty+tr-4,tr*2,int(tr*0.6)))
            # trunk
            pygame.draw.rect(surf,(80,50,20),(tx-4,ty,8,tr//2+4))
            # foliage layers
            pygame.draw.circle(surf,(20,70,20),(tx,ty),tr+4)
            pygame.draw.circle(surf,(35,105,35),(tx,ty),tr)
            pygame.draw.circle(surf,(55,140,55),(tx-tr//3,ty-tr//3),tr//2)
            pygame.draw.circle(surf,(80,170,60),(tx-tr//4,ty-tr//2),tr//4)
        # Bushes along path edges
        for bx in range(0,SCREEN_W,140):
            for by_off,bcol in [(-PATH_H-16,(25,95,25)),( PATH_H+16,(25,85,20))]:
                by=PATH_Y+by_off
                if 80<by<SLOT_AREA_Y-10:
                    pygame.draw.circle(surf,(15,55,15),(bx,by+4),10)
                    pygame.draw.circle(surf,bcol,(bx,by),10)
                    pygame.draw.circle(surf,(60,140,50),(bx-3,by-3),5)
        # Dirt road — wide, textured
        pygame.draw.rect(surf,(100,80,50),(0,PATH_Y-PATH_H,SCREEN_W,PATH_H*2))
        pygame.draw.rect(surf,(115,93,62),(0,PATH_Y-PATH_H,SCREEN_W,PATH_H*2),2)
        # Tire tracks
        for x in range(0,SCREEN_W,4):
            if rng.random()<0.12:
                pygame.draw.circle(surf,(90,70,42),(x,PATH_Y-PATH_H//3),1)
                pygame.draw.circle(surf,(90,70,42),(x,PATH_Y+PATH_H//3),1)
        # Dashed center line
        for x in range(0,SCREEN_W,44):
            pygame.draw.rect(surf,(140,118,80),(x,PATH_Y-1,22,3))
        # Edge glow
        pygame.draw.line(surf,(150,125,75),(0,PATH_Y-PATH_H),(SCREEN_W,PATH_Y-PATH_H),2)
        pygame.draw.line(surf,(150,125,75),(0,PATH_Y+PATH_H),(SCREEN_W,PATH_Y+PATH_H),2)
        # Start / End markers
        pygame.draw.rect(surf,(70,20,20),(0,PATH_Y-PATH_H,14,PATH_H*2),border_radius=3)
        txt(surf,"S",(7,PATH_Y),C_RED,font_sm,center=True)
        pygame.draw.rect(surf,(20,70,20),(SCREEN_W-14,PATH_Y-PATH_H,14,PATH_H*2),border_radius=3)
        txt(surf,"E",(SCREEN_W-7,PATH_Y),C_GREEN,font_sm,center=True)

    def _draw_map_hard(self, surf):
        """Night city map — full screen version"""
        surf.fill((12, 16, 28))
        rng = random.Random(99)
        # Stars
        for _ in range(160):
            sx=rng.randint(0,SCREEN_W); sy=rng.randint(72,PATH_Y-PATH_H-10)
            c=rng.randint(140,255)
            pygame.draw.circle(surf,(c,c,min(255,c+30)),(sx,sy),1)
        # Moon glow
        mg=pygame.Surface((200,200),pygame.SRCALPHA)
        pygame.draw.circle(mg,(200,210,255,25),(100,100),100)
        pygame.draw.circle(mg,(220,225,255,40),(100,100),60)
        pygame.draw.circle(mg,(240,240,255,60),(100,100),30)
        surf.blit(mg,(SCREEN_W-180,40))
        pygame.draw.circle(surf,(240,240,255),(SCREEN_W-80,90),18)
        # Buildings ABOVE path
        rng2=random.Random(55)
        for i in range(22):
            bx=rng2.randint(0,SCREEN_W-80); bh2=rng2.randint(50,160)
            by=PATH_Y-PATH_H-bh2; bw=rng2.randint(35,90)
            if by>72:
                pygame.draw.rect(surf,(16,22,38),(bx,by,bw,bh2))
                pygame.draw.rect(surf,(24,32,52),(bx,by,bw,bh2),1)
                for wr in range(by+6,by+bh2-6,14):
                    for wc in range(bx+5,bx+bw-5,10):
                        wc2=(220,195,90) if rng2.random()>0.4 else (28,32,52)
                        pygame.draw.rect(surf,wc2,(wc,wr,7,8))
                # Antenna
                if rng2.random()>0.5:
                    pygame.draw.line(surf,(60,70,100),(bx+bw//2,by),(bx+bw//2,by-20),1)
                    pygame.draw.circle(surf,(255,60,60),(bx+bw//2,by-20),2)
        # Buildings BELOW path
        rng3=random.Random(77)
        for i in range(14):
            bx=rng3.randint(0,SCREEN_W-60); bh2=rng3.randint(40,120)
            by=PATH_Y+PATH_H; bw=rng3.randint(30,75)
            if by+bh2<SLOT_AREA_Y-5:
                pygame.draw.rect(surf,(16,22,38),(bx,by,bw,bh2))
                pygame.draw.rect(surf,(24,32,52),(bx,by,bw,bh2),1)
                for wr in range(by+6,by+bh2-6,14):
                    for wc in range(bx+5,bx+bw-5,10):
                        wc2=(220,195,90) if rng3.random()>0.4 else (28,32,52)
                        pygame.draw.rect(surf,wc2,(wc,wr,7,8))
        # Neon signs
        for nx2,ny2,nc in [(200,PATH_Y-PATH_H-20,(255,30,100)),(600,PATH_Y-PATH_H-30,(30,200,255)),
                           (1000,PATH_Y-PATH_H-25,(180,30,255)),(1400,PATH_Y-PATH_H-18,(255,180,30)),
                           (1700,PATH_Y-PATH_H-28,(30,255,140))]:
            ngs=pygame.Surface((80,16),pygame.SRCALPHA)
            pygame.draw.rect(ngs,(*nc,60),(0,0,80,16),border_radius=4)
            surf.blit(ngs,(nx2-40,ny2-8))
            pygame.draw.rect(surf,nc,(nx2-38,ny2-6,76,12),1,border_radius=3)
        # Road surface
        pygame.draw.rect(surf,(42,48,62),(0,PATH_Y-PATH_H,SCREEN_W,PATH_H*2))
        pygame.draw.line(surf,(32,38,52),(0,PATH_Y-PATH_H),(SCREEN_W,PATH_Y-PATH_H),2)
        pygame.draw.line(surf,(32,38,52),(0,PATH_Y+PATH_H),(SCREEN_W,PATH_Y+PATH_H),2)
        # Road shine
        rs=pygame.Surface((SCREEN_W,4),pygame.SRCALPHA)
        pygame.draw.rect(rs,(255,255,255,15),(0,0,SCREEN_W,4))
        surf.blit(rs,(0,PATH_Y-PATH_H+2))
        # Dashed center line
        for x in range(0,SCREEN_W,56):
            pygame.draw.rect(surf,(75,82,100),(x,PATH_Y-2,28,5),border_radius=2)
        # Street lamps
        for lx in range(100,SCREEN_W-50,190):
            # Pole
            pygame.draw.line(surf,(60,65,90),(lx,PATH_Y-PATH_H),(lx,PATH_Y-PATH_H-40),2)
            pygame.draw.line(surf,(60,65,90),(lx,PATH_Y-PATH_H-40),(lx+20,PATH_Y-PATH_H-40),2)
            # Glow halo
            gs2=pygame.Surface((80,80),pygame.SRCALPHA)
            pygame.draw.circle(gs2,(255,220,100,50),(20,20),20)
            surf.blit(gs2,(lx+20-20,PATH_Y-PATH_H-60))
            pygame.draw.circle(surf,(255,230,130),(lx+20,PATH_Y-PATH_H-40),4)
        # Headlight streaks from "cars"
        for cx3 in range(180,SCREEN_W,350):
            hs=pygame.Surface((120,4),pygame.SRCALPHA)
            pygame.draw.rect(hs,(255,240,200,60),(0,0,120,4))
            surf.blit(hs,(cx3,PATH_Y-10))
        # Start / End
        pygame.draw.rect(surf,(60,20,20),(0,PATH_Y-PATH_H,14,PATH_H*2),border_radius=3)
        txt(surf,"S",(7,PATH_Y),C_RED,font_sm,center=True)
        pygame.draw.rect(surf,(20,60,20),(SCREEN_W-14,PATH_Y-PATH_H,14,PATH_H*2),border_radius=3)
        txt(surf,"E",(SCREEN_W-7,PATH_Y),C_GREEN,font_sm,center=True)

    def _draw_map_hell(self, surf):
        """Volcanic hellscape — full screen version"""
        surf.fill((20, 6, 6))
        rng = random.Random(42)
        # Ambient lava glow across whole screen
        gl=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        pygame.draw.ellipse(gl,(160,40,0,35),(0,PATH_Y-120,SCREEN_W,240))
        surf.blit(gl,(0,0))
        # Cracked ground texture — both zones
        for _ in range(120):
            cx2=rng.randint(0,SCREEN_W); cy2=rng.randint(72,SLOT_AREA_Y-5)
            if abs(cy2-PATH_Y)>PATH_H+12:
                cx3,cy3=cx2,cy2
                for _ in range(5):
                    nx2=cx3+rng.randint(-30,30); ny2=cy3+rng.randint(-15,15)
                    pygame.draw.line(surf,(70,18,0),(cx3,cy3),(nx2,ny2),1)
                    cx3,cy3=nx2,ny2
        # Large lava pools scattered
        for lx2,ly2,lr2 in [(120,200,30),(480,170,22),(820,220,28),(250,750,26),(680,780,32),
                             (1050,200,20),(1350,190,25),(1600,750,24),(1800,200,18),(1700,800,22),
                             (950,780,20),(1200,200,18)]:
            sg2=pygame.Surface((lr2*2+20,lr2*2+20),pygame.SRCALPHA)
            pygame.draw.circle(sg2,(220,80,0,55),(lr2+10,lr2+10),lr2+9)
            surf.blit(sg2,(lx2-lr2-10,ly2-lr2-10))
            pygame.draw.circle(surf,(130,35,0),(lx2,ly2),lr2)
            pygame.draw.circle(surf,(190,70,5),(lx2,ly2),lr2*2//3)
            pygame.draw.circle(surf,(240,120,10),(lx2,ly2),lr2//3)
            # Lava bubbles
            for bi in range(3):
                ba=math.radians(bi*120)
                bx2=int(lx2+math.cos(ba)*lr2*0.6); by2=int(ly2+math.sin(ba)*lr2*0.6)
                pygame.draw.circle(surf,(255,150,20),(bx2,by2),3)
        # Volcanic rocks
        for rx2,ry2,rr2 in [(180,300,18),(420,160,14),(750,360,20),(960,300,16),
                             (1200,280,15),(1450,180,12),(1650,340,17),(1850,280,14),
                             (300,700,16),(600,720,14),(1100,700,18),(1400,740,12)]:
            pygame.draw.circle(surf,(45,18,8),(rx2,ry2),rr2)
            pygame.draw.circle(surf,(60,26,12),(rx2-rr2//3,ry2-rr2//3),rr2//2)
            pygame.draw.circle(surf,(30,10,5),(rx2,ry2),rr2,2)
        # Magma vents — glowing columns
        for vx,vy in [(350,200),(800,750),(1200,190),(1600,770),(560,750),(1050,200)]:
            vs=pygame.Surface((40,60),pygame.SRCALPHA)
            for vi in range(4):
                va=60-vi*15
                pygame.draw.ellipse(vs,(255,120,0,va),(10-vi*2,vi*14,20+vi*4,16))
            surf.blit(vs,(vx-20,vy-50))
            pygame.draw.circle(surf,(255,80,0),(vx,vy),6)
        # Lava river path — wide glowing band
        pygame.draw.rect(surf,(75,22,8),(0,PATH_Y-PATH_H,SCREEN_W,PATH_H*2))
        # Lava surface shimmer
        ls=pygame.Surface((SCREEN_W,PATH_H*2),pygame.SRCALPHA)
        for x in range(0,SCREEN_W,20):
            la=rng.randint(5,20)
            pygame.draw.line(ls,(255,150,0,la),(x,0),(x+10,PATH_H*2))
        surf.blit(ls,(0,PATH_Y-PATH_H))
        # Lava ripples
        for x in range(0,SCREEN_W,28):
            pygame.draw.line(surf,(105,38,4),(x,PATH_Y-PATH_H+5),(x+14,PATH_Y-PATH_H+5),2)
            pygame.draw.line(surf,(105,38,4),(x,PATH_Y+PATH_H-5),(x+14,PATH_Y+PATH_H-5),2)
        # Hot glowing edges
        for i in range(4):
            a=50-i*12
            eg=pygame.Surface((SCREEN_W,2),pygame.SRCALPHA)
            pygame.draw.rect(eg,(220,60,0,a),(0,0,SCREEN_W,2))
            surf.blit(eg,(0,PATH_Y-PATH_H+i))
            surf.blit(eg,(0,PATH_Y+PATH_H-i-1))
        # Ember particles on path
        rng2=random.Random(13)
        for _ in range(50):
            ex2=rng2.randint(0,SCREEN_W); ey2=rng2.randint(PATH_Y-PATH_H+2,PATH_Y+PATH_H-2)
            ec=rng2.randint(100,200)
            pygame.draw.circle(surf,(255,ec,0),(ex2,ey2),rng2.randint(1,3))
        # Start / End
        pygame.draw.rect(surf,(100,28,8),(0,PATH_Y-PATH_H,14,PATH_H*2),border_radius=3)
        txt(surf,"S",(7,PATH_Y),(255,80,40),font_sm,center=True)
        pygame.draw.rect(surf,(28,90,8),(SCREEN_W-14,PATH_Y-PATH_H,14,PATH_H*2),border_radius=3)
        txt(surf,"E",(SCREEN_W-7,PATH_Y),(80,255,40),font_sm,center=True)

    def run(self):
        self.paused = False
        # Pause menu buttons
        pmenu_w, pmenu_h = 403, 288
        pmenu_x, pmenu_y = SCREEN_W//2 - pmenu_w//2, SCREEN_H//2 - pmenu_h//2
        btn_resume = pygame.Rect(pmenu_x+58, pmenu_y+101, pmenu_w-115, 69)
        btn_exit   = pygame.Rect(pmenu_x+58, pmenu_y+190, pmenu_w-115, 69)

        # Speed x2 button (top-left area, below wave info)
        btn_speed = pygame.Rect(26, 78, 115, 37)
        # Skip wave button rect — must match the draw rect below (151, 78, 144, 37)
        btn_skip  = pygame.Rect(151, 78, 144, 37)

        while self.running:
            raw_dt = min(self.clock.tick(FPS)/1000.0, 0.05)
            dt = raw_dt * (2.0 if self.speed_x2 else 1.0)
            self.anim_t += raw_dt
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: pygame.quit(); sys.exit()

                # Dev console gets F3 before anything else
                if self.dev_console.handle_event(ev, self):
                    continue

                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    if self.game_over or self.win:
                        self.running = False  # go back to lobby
                    else:
                        self.paused = not self.paused

                if self.paused:
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        if btn_resume.collidepoint(ev.pos):
                            self.paused = False
                        elif btn_exit.collidepoint(ev.pos):
                            self.running = False
                    continue  # skip game input while paused

                if not self.game_over:
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        # Speed x2 toggle
                        if btn_speed.collidepoint(ev.pos):
                            self.speed_x2 = not self.speed_x2
                        # Skip wave button (visible after 10s)
                        wave_in_progress = self.wave_mgr.state in ("spawning", "waiting")
                        skip_visible = (wave_in_progress and self.wave_mgr.wave_elapsed >= 10.0
                                        and not self.wave_mgr.extra_queue
                                        and self.wave_mgr.wave < MAX_WAVES)
                        if skip_visible and btn_skip.collidepoint(ev.pos):
                            # Start next wave in parallel — current enemies keep going
                            if not self.wave_mgr.extra_queue:
                                self.wave_mgr.skip_wave()
                        self.money += self.ui.handle_click(ev.pos, self.units, self.money, self.effects, self.enemies)
                        # Clown key collection
                        if self._key_mgr:
                            if self._key_mgr.handle_click(ev.pos):
                                keys_now = total_clown_keys()
                                self.ui.show_msg(f"Key fragment! {keys_now}/{CLOWN_KEYS_TOTAL}", 2.5)
                if ev.type == pygame.KEYDOWN:
                    # Tower hotkeys 1-5
                    tower_keys = {pygame.K_1:0, pygame.K_2:1, pygame.K_3:2,
                                  pygame.K_4:3, pygame.K_5:4}
                    if ev.key in tower_keys and not self.game_over:
                        slot_idx = tower_keys[ev.key]
                        mx2t, my2t = pygame.mouse.get_pos()
                        self.money += self.ui.select_slot_by_key(
                            slot_idx, (mx2t, my2t), self.units, self.money)
                    if ev.key == pygame.K_a: self.money += 1000
                    # E = upgrade selected tower
                    if ev.key == pygame.K_e and self.ui.open_unit:
                        u2=self.ui.open_unit; cost=u2.upgrade_cost()
                        if cost and self.money>=cost:
                            u2.upgrade(); self.money-=cost
                            self.ui.show_msg(f"Upgraded to Lv{u2.level}!",1.5)
                        elif not cost:
                            self.ui.show_msg("Already max level!",1.5)
                        else:
                            self.ui.show_msg("Not enough money!",1.5)
                    # X = sell selected tower (30% refund)
                    if ev.key == pygame.K_x and self.ui.open_unit:
                        refund=self.ui.sell_unit(self.ui.open_unit,self.units)
                        self.money+=refund
                        self.ui.show_msg(f"Sold! +${refund}",2.0)
                    if ev.key == pygame.K_q:
                        if self.wave_mgr.state in ("prep","between","spawning"):
                            self.wave_mgr.spawn_queue = []
                            self.wave_mgr.state = "waiting"
                        elif self.wave_mgr.state == "waiting" and len(self.enemies) == 0:
                            self.wave_mgr.state = "between"
                            self.wave_mgr.prep_timer = 0.1
                    if ev.key == pygame.K_f:
                        for u in self.units:
                            if isinstance(u, Assassin) and u.ability and u.level >= 2:
                                if u.ability.ready():
                                    u.ability.activate(self.enemies, self.effects)
                                    break
                    if ev.key == pygame.K_s:
                        self._debug_spawn = not getattr(self, '_debug_spawn', False)
                        if self._debug_spawn:
                            self.wave_mgr.state = "waiting"
                            d = Enemy(1); d.hp = 100000; d.maxhp = 100000; d.speed = Enemy.BASE_SPEED
                            self.enemies.append(d)
                        else:
                            self.wave_mgr.state = "between"; self.wave_mgr.prep_timer = 0.1

            if not self.paused and not self.game_over:
                self.update(dt)
            self.draw()

            # Draw pause menu on top
            if self.paused:
                self._draw_pause_menu(btn_resume, btn_exit, pmenu_x, pmenu_y, pmenu_w, pmenu_h)

            # Dev console tick (handles deferred actions like boss launch) and draw
            self.dev_console.tick(self)
            self.dev_console.draw(self.screen, raw_dt)

            pygame.display.flip()
        self._restore_enemies()

    def _draw_pause_menu(self, btn_resume, btn_exit, px, py, pw, ph):
        surf = self.screen
        draw_rect_alpha(surf, C_BLACK, (0, 0, SCREEN_W, SCREEN_H), 155)
        # Panel gradient
        draw_rect_gradient(surf, (22,28,48), (14,18,34), (px,py,pw,ph), alpha=248, brad=24)
        pygame.draw.rect(surf, (70,85,140), (px, py, pw, ph), 3, border_radius=24)
        draw_rect_alpha(surf, (100,120,255), (px+20, py, pw-40, 3), 200, brad=3)
        # Title
        draw_glow_circle(surf, (60,80,200), (SCREEN_W//2, py+50), 80, 28)
        txt(surf, "⏸  PAUSED", (SCREEN_W//2, py+50), C_WHITE,
            pygame.font.SysFont("consolas", 37, bold=True), center=True)
        pygame.draw.line(surf, (40,50,80), (px+30, py+84), (px+pw-30, py+84), 1)
        # Resume button
        mx, my = pygame.mouse.get_pos()
        hov_r = btn_resume.collidepoint(mx, my)
        draw_rect_gradient(surf, (52,155,72) if hov_r else (36,102,52),
                           (32,105,46) if hov_r else (22,68,32), btn_resume, 235, brad=12)
        draw_rect_alpha(surf,(255,255,255),(btn_resume.x,btn_resume.y,btn_resume.w,btn_resume.h//3),18,brad=12)
        pygame.draw.rect(surf, (90,230,110) if hov_r else (55,175,75), btn_resume, 2, border_radius=12)
        txt(surf, "▶  Resume", btn_resume.center, C_WHITE, font_lg, center=True)
        # Exit button
        hov_e = btn_exit.collidepoint(mx, my)
        draw_rect_gradient(surf, (152,40,40) if hov_e else (100,28,28),
                           (102,24,24) if hov_e else (66,16,16), btn_exit, 235, brad=12)
        pygame.draw.rect(surf, (230,90,90) if hov_e else (160,55,55), btn_exit, 2, border_radius=12)
        txt(surf, "✕  Exit to Lobby", btn_exit.center, C_WHITE, font_lg, center=True)

    def update(self, dt):
        self.wave_mgr.update(dt,self.enemies)

        # necromancer summons
        for n in [e for e in self.enemies if isinstance(e,Necromancer) and e.alive]:
            if n.should_summon():
                for _ in range(5):
                    s2=Enemy(self.wave_mgr.wave); s2.free_kill=True; s2.x=n.x; self.enemies.append(s2)

        # enemy movement
        dead_reached=[]
        for e in self.enemies:
            if e.alive and e.update(dt): dead_reached.append(e)
            if e.alive and getattr(e, '_shadow_marked', 0) > 0:
                e._shadow_marked = max(0.0, e._shadow_marked - dt)
        for e in dead_reached:
            self.player_hp=max(0,self.player_hp-max(1,int(e.hp))); e.alive=False
        if dead_reached: self._defeat_this_frame=True
        if self.player_hp<=0: self.game_over=True

        # units
        for u in self.units: u.update(dt,self.enemies,self.effects,self.money)

        # tick Clown global confusion cooldown exactly once per frame
        if Clown._CONFUSE_CD > 0:
            Clown._CONFUSE_CD = max(0.0, Clown._CONFUSE_CD - dt)

        # Clown Lv3+ pushback: process once per frame regardless of Clown count
        has_lv3_clown = any(isinstance(u, Clown) and u.level >= 3 for u in self.units)
        if has_lv3_clown:
            for e in self.enemies:
                if e.alive and getattr(e, '_clown_pushback', False):
                    e._clown_pushback = False
                    if random.random() < 0.05:
                        e.x -= TILE

        # VoltCrawler chain-zap on death
        for e in self.enemies:
            if not e.alive and isinstance(e, VoltCrawler) and e._chain_triggered:
                e._chain_triggered = False   # consume flag
                for other in self.enemies:
                    if other.alive and dist((other.x, other.y), (e.x, e.y)) <= VoltCrawler.CHAIN_RADIUS:
                        other.take_damage(VoltCrawler.CHAIN_DAMAGE)
                # visual burst
                s_burst = pygame.Surface((VoltCrawler.CHAIN_RADIUS*2+20,
                                          VoltCrawler.CHAIN_RADIUS*2+20), pygame.SRCALPHA)
                # just schedule a quick flash effect via a lambda-style minimal class
                class _ZapFlash:
                    def __init__(self, ox, oy, r):
                        self.ox=ox; self.oy=oy; self.r=r; self.t=0.35
                    def update(self, dt):
                        self.t-=dt; return self.t>0
                    def draw(self, surf):
                        prog=self.t/0.35; alpha=int(180*prog)
                        sz=pygame.Surface((self.r*2+20,self.r*2+20),pygame.SRCALPHA)
                        pygame.draw.circle(sz,(100,220,255,alpha),(self.r+10,self.r+10),
                                           int(self.r*(1-prog)+12),3)
                        surf.blit(sz,(int(self.ox)-self.r-10,int(self.oy)-self.r-10))
                self.effects.append(_ZapFlash(e.x, e.y, VoltCrawler.CHAIN_RADIUS))

        # TimeBender time-slow pulse — halve fire-rate of towers in range for 2s
        for e in self.enemies:
            if e.alive and isinstance(e, TimeBender) and e.pulse_fired:
                for u in self.units:
                    if dist((u.px, u.py), (e.x, e.y)) <= TimeBender.PULSE_RADIUS:
                        u._time_slow_timer = TimeBender.PULSE_DURATION

        # Apply TimeBender slow to unit fire-rates (double cd_left, clamped)
        for u in self.units:
            tslow = getattr(u, '_time_slow_timer', 0.0)
            if tslow > 0:
                u._time_slow_timer = max(0.0, tslow - dt)
                # Double the cd each frame they are slowed (effectively halves attack speed)
                u.cd_left = min(getattr(u, 'firerate', 9999) * 2.0, u.cd_left + dt)

        # CursedWitch pulse — same mechanic as TimeBender
        for e in self.enemies:
            if e.alive and isinstance(e, CursedWitch) and e.pulse_fired:
                for u in self.units:
                    if dist((u.px, u.py), (e.x, e.y)) <= CursedWitch.PULSE_RADIUS:
                        u._time_slow_timer = CursedWitch.PULSE_DURATION

        # DoomBringer pulse — same mechanic as TimeBender
        for e in self.enemies:
            if e.alive and isinstance(e, DoomBringer) and e.pulse_fired:
                for u in self.units:
                    if dist((u.px, u.py), (e.x, e.y)) <= DoomBringer.PULSE_RADIUS:
                        u._time_slow_timer = DoomBringer.PULSE_DURATION

        # HellGateKeeper pulse
        for e in self.enemies:
            if e.alive and isinstance(e, HellGateKeeper) and e.pulse_fired:
                for u in self.units:
                    if dist((u.px, u.py), (e.x, e.y)) <= HellGateKeeper.PULSE_RADIUS:
                        u._time_slow_timer = HellGateKeeper.PULSE_DURATION

        # breaker death spawn
        new_enemies=[]
        for e in self.enemies:
            if not e.alive and isinstance(e,BreakerEnemy):
                Sp=random.choice(BREAKER_POOL); baby=Sp(self.wave_mgr.wave)
                baby.x=e.x; baby.free_kill=True; new_enemies.append(baby)
        # AbyssalSpawn death split (like Breaker)
        for e in self.enemies:
            if not e.alive and isinstance(e, AbyssalSpawn):
                baby = HellHound(self.wave_mgr.wave)
                baby.x = e.x + random.uniform(-20,20); baby.free_kill = True
                new_enemies.append(baby)
        self.enemies=[e for e in self.enemies if e.alive]+new_enemies

        # boss ref
        gds=[e for e in self.enemies if isinstance(e,GraveDigger) and e.alive]
        self._boss_enemy=gds[0] if gds else (self._boss_enemy if self._boss_enemy and self._boss_enemy.alive else None)

        if not self.wave_mgr._lmoney_paid and self.wave_mgr.wave>=1:
            lm=self.wave_mgr.wave_lmoney()
            if lm: self.money+=lm; self.ui.show_msg(f"+{lm} Wave start!",2.0)
            self.wave_mgr._lmoney_paid=True

        if self.wave_mgr.state=="waiting" and len(self.enemies)==0 and not self.wave_mgr._bonus_paid:
            bm=self.wave_mgr.wave_bmoney()
            if bm: self.money+=bm; self.ui.show_msg(f"+{bm} Wave Clear!",2.5)
            self.wave_mgr._bonus_paid=True

        if self._defeat_this_frame:
            self.money+=200; self.ui.show_msg("+200 Consolation",2.0); self._defeat_this_frame=False

        if self.wave_mgr.state=="done" and len(self.enemies)==0:
            if not self.win:  # only on the first frame of victory
                reward = DIFF_COIN_REWARDS.get(self._difficulty_name, 0)
                if reward > 0:
                    self._win_coins_earned = reward
                    add_shop_coins(reward)
                else:
                    self._win_coins_earned = 0
            self.win=True

        self.effects=[ef for ef in self.effects if ef.update(dt)]
        self.ui.update(dt)
        if self._key_mgr:
            self._key_mgr.update(dt)

    def draw(self):
        self.draw_map()
        # Башни с hidden_detection — обнаруживают только врагов в своём радиусе
        hd_units = [u for u in self.units if getattr(u, 'hidden_detection', False)]
        mx,my=pygame.mouse.get_pos()
        for u in self.units: u.draw(self.screen)
        for e in self.enemies:
            if not e.alive: continue
            hov=dist((e.x,e.y),(mx,my))<e.radius+5
            if hov: continue
            # Враг обнаружен только если находится в радиусе хотя бы одной башни с HD
            detected = any(
                dist((e.x, e.y), (u.px, u.py)) <= u.range_tiles * TILE
                for u in hd_units
            )
            e.draw(self.screen, detected=detected)
        for ef in self.effects: ef.draw(self.screen)
        # Draw and tick global death particles
        global _GLOBAL_EFFECTS
        _GLOBAL_EFFECTS = [p for p in _GLOBAL_EFFECTS if p.update(1/FPS)]
        for p in _GLOBAL_EFFECTS: p.draw(self.screen)
        # Draw in-game clown key fragments
        if self._key_mgr:
            self._key_mgr.draw(self.screen, self.anim_t)
            self._key_mgr.draw_hud(self.screen, self.anim_t)
        self.ui.draw(self.screen,self.units,self.money,self.wave_mgr,
                     self.player_hp,self.player_maxhp,self.enemies,self._boss_enemy)
        # ── Speed x2 button ───────────────────────────────────────────────────
        btn_speed = pygame.Rect(26, 78, 115, 37)
        spd_active = self.speed_x2
        if spd_active:
            draw_rect_gradient(self.screen,(80,50,165),(50,30,115),btn_speed,alpha=242,brad=10)
            draw_rect_alpha(self.screen,(255,255,255),(btn_speed.x,btn_speed.y,btn_speed.w,5),22,brad=10)
            pygame.draw.rect(self.screen,(200,130,255),btn_speed,2,border_radius=10)
            txt(self.screen,"⏩ x2 ON",btn_speed.center,(230,180,255),font_md,center=True)
        else:
            draw_rect_gradient(self.screen,(36,33,68),(22,20,46),btn_speed,alpha=222,brad=10)
            pygame.draw.rect(self.screen,(80,70,130),btn_speed,1,border_radius=10)
            txt(self.screen,"⏩ x2",btn_speed.center,(150,120,210),font_md,center=True)
        # ── Skip wave button (appears after 10s) ──────────────────────────────
        wave_in_progress = self.wave_mgr.state in ("spawning", "waiting")
        skip_visible = (wave_in_progress and self.wave_mgr.wave_elapsed >= 10.0
                        and not self.wave_mgr.extra_queue
                        and self.wave_mgr.wave < MAX_WAVES)
        if skip_visible:
            btn_skip = pygame.Rect(151, 78, 144, 37)
            hov_skip = btn_skip.collidepoint(mx, my)
            if hov_skip:
                draw_rect_gradient(self.screen,(162,92,22),(112,62,12),btn_skip,alpha=242,brad=10)
            else:
                draw_rect_gradient(self.screen,(92,54,12),(62,36,8),btn_skip,alpha=222,brad=10)
            pygame.draw.rect(self.screen,(255,192,70) if hov_skip else (192,132,42),btn_skip,2,border_radius=10)
            draw_rect_alpha(self.screen,(255,255,255),(btn_skip.x,btn_skip.y,btn_skip.w,4),16,brad=10)
            txt(self.screen,"⏭ SKIP",btn_skip.center,(255,220,110),font_md,center=True)
        # ── Game Over ─────────────────────────────────────────────────────────
        if self.game_over:
            draw_rect_alpha(self.screen,C_BLACK,(0,0,SCREEN_W,SCREEN_H),175)
            gvs=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
            for rv in range(500,0,-50):
                av=max(0,int(32*(1-rv/500)))
                pygame.draw.circle(gvs,(180,0,0,av),(SCREEN_W//2,SCREEN_H//2),rv)
            self.screen.blit(gvs,(0,0))
            pw,ph=600,220; px2,py2=SCREEN_W//2-pw//2,SCREEN_H//2-ph//2
            draw_rect_gradient(self.screen,(50,10,10),(26,5,5),(px2,py2,pw,ph),alpha=242,brad=20)
            pygame.draw.rect(self.screen,(200,40,40),(px2,py2,pw,ph),3,border_radius=20)
            draw_rect_alpha(self.screen,(255,80,80),(px2,py2,pw,4),120,brad=20)
            skx,sky=SCREEN_W//2,py2+65
            pygame.draw.circle(self.screen,(180,30,30),(skx,sky),30)
            pygame.draw.circle(self.screen,(220,60,60),(skx,sky),26)
            pygame.draw.circle(self.screen,(20,5,5),(skx-8,sky-4),7)
            pygame.draw.circle(self.screen,(20,5,5),(skx+8,sky-4),7)
            pygame.draw.rect(self.screen,(20,5,5),(skx-9,sky+8,18,8),border_radius=2)
            txt(self.screen,"GAME OVER",(SCREEN_W//2,py2+118),C_RED,font_xl,center=True)
            txt(self.screen,"Press ESC to return to lobby",(SCREEN_W//2,py2+162),(180,100,100),font_md,center=True)
        elif self.win:
            t_win = self.anim_t if hasattr(self,'anim_t') else 0.0
            draw_rect_alpha(self.screen, C_BLACK, (0,0,SCREEN_W,SCREEN_H), 160)

            # Gold radial glow
            gvs2 = pygame.Surface((SCREEN_W,SCREEN_H), pygame.SRCALPHA)
            for rv2 in range(600,0,-50):
                av2 = max(0, int(30*(1-rv2/600)))
                pygame.draw.circle(gvs2,(200,170,0,av2),(SCREEN_W//2,SCREEN_H//2),rv2)
            self.screen.blit(gvs2,(0,0))

            # ── Panel ──────────────────────────────────────────────────────────
            pw2,ph2 = 700, 340
            px3,py3 = SCREEN_W//2-pw2//2, SCREEN_H//2-ph2//2
            draw_rect_gradient(self.screen,(38,58,18),(18,34,8),(px3,py3,pw2,ph2),alpha=248,brad=22)
            pygame.draw.rect(self.screen,(100,220,60),(px3,py3,pw2,ph2),3,border_radius=22)
            draw_rect_alpha(self.screen,(180,255,80),(px3,py3,pw2,5),130,brad=22)

            # ── Spinning star burst ────────────────────────────────────────────
            star_cx, star_cy = SCREEN_W//2, py3+72
            for si2 in range(8):
                sa = math.radians(t_win*60 + si2*45)
                sxp = star_cx + int(math.cos(sa)*32)
                syp = star_cy + int(math.sin(sa)*32)
                pygame.draw.circle(self.screen, C_GOLD, (sxp,syp), 5)
                pygame.draw.circle(self.screen, (255,240,160), (sxp,syp), 2)
            pygame.draw.circle(self.screen, C_GOLD, (star_cx,star_cy), 18)
            pygame.draw.circle(self.screen, (255,240,160),(star_cx,star_cy), 10)

            # ── YOU WIN heading ────────────────────────────────────────────────
            txt(self.screen,"★  YOU WIN!  ★",
                (SCREEN_W//2, py3+128), C_GREEN, font_xl, center=True)

            # ── Difficulty badge ───────────────────────────────────────────────
            dcol = DIFFICULTIES.get(self._difficulty_name,{}).get("color", C_WHITE)
            dname = self._difficulty_name.upper()
            dbadge_f = pygame.font.SysFont("consolas", 16, bold=True)
            dbw = dbadge_f.size(dname)[0]+24
            dbr = pygame.Rect(SCREEN_W//2-dbw//2, py3+160, dbw, 26)
            draw_rect_alpha(self.screen, dcol, dbr, 55, brad=8)
            pygame.draw.rect(self.screen, dcol, dbr, 1, border_radius=8)
            txt(self.screen, dname, dbr.center, dcol, dbadge_f, center=True)

            # ── Divider ───────────────────────────────────────────────────────
            pygame.draw.line(self.screen,(60,100,40),
                             (px3+30,py3+196),(px3+pw2-30,py3+196),1)

            # ── Coin reward row ────────────────────────────────────────────────
            reward = self._win_coins_earned
            coin_y = py3+222
            reward_f = pygame.font.SysFont("consolas",22,bold=True)
            label_f  = pygame.font.SysFont("consolas",13)
            if reward > 0:
                # animated coin pulse
                pulse_r = abs(math.sin(t_win*3.0))
                coin_r_draw = int(18 + pulse_r*4)
                # coin icon (circle with C)
                coin_cx2 = SCREEN_W//2 - 100
                coin_s2 = pygame.Surface((coin_r_draw*2+4,coin_r_draw*2+4),pygame.SRCALPHA)
                pygame.draw.circle(coin_s2,(200,160,0,220),(coin_r_draw+2,coin_r_draw+2),coin_r_draw)
                pygame.draw.circle(coin_s2,(255,220,60,255),(coin_r_draw+2,coin_r_draw+2),coin_r_draw,3)
                coin_lbl = pygame.font.SysFont("consolas",14,bold=True).render("¢",True,(255,240,100))
                coin_s2.blit(coin_lbl,(coin_r_draw+2-coin_lbl.get_width()//2,
                                       coin_r_draw+2-coin_lbl.get_height()//2))
                self.screen.blit(coin_s2,(coin_cx2-coin_r_draw-2, coin_y-coin_r_draw-2))

                # "+350 Shop Coins" text
                txt(self.screen, f"+{reward}",
                    (coin_cx2+30, coin_y), C_GOLD, reward_f)
                txt(self.screen, "shop coins earned!",
                    (coin_cx2+30+reward_f.size(f"+{reward}")[0]+10, coin_y+4),
                    (180,200,140), label_f)

                # Running total
                total_coins = get_shop_coins()
                tot_f = pygame.font.SysFont("consolas",12)
                txt(self.screen, f"Total: {total_coins} coins",
                    (SCREEN_W//2, coin_y+36), (120,160,100), tot_f, center=True)
            else:
                txt(self.screen,"No coins awarded (Sandbox or already rewarded)",
                    (SCREEN_W//2, coin_y),(80,100,70),label_f,center=True)

            # ── Return hint ────────────────────────────────────────────────────
            txt(self.screen,"Press ESC to return to lobby",
                (SCREEN_W//2,py3+ph2-32),(120,200,80),font_md,center=True)


# ── Sandbox Game Mode ──────────────────────────────────────────────────────────
class SandboxGame(Game):
    """Infinite-money sandbox: custom enemies, custom loadout, chosen map."""

    def __init__(self, sb_cfg, screen_override=None):
        # Pick difficulty multipliers for money rewards (or neutral if none)
        diff_name = sb_cfg.get("diff_rewards") or "Hard"
        super().__init__(difficulty=diff_name,
                         loadout=sb_cfg.get("loadout"),
                         screen_override=screen_override)

        self._sandbox_mode   = True
        self._sb_cfg         = sb_cfg
        self._sb_map         = sb_cfg.get("map", "Easy")
        self._sb_enemy_cfg   = sb_cfg.get("enemies", {})   # {EnemyClass: count}
        self._sb_diff_rewards= sb_cfg.get("diff_rewards")  # None = no wave money

        # Infinite money
        self.money = 999_999_999

        # Override map selection
        self._difficulty_name = self._sb_map

        # Override key manager to use Sandbox source
        if not is_clown_unlocked():
            self._key_mgr = InGameKeyManager("Sandbox")
        else:
            self._key_mgr = None

        # Sandbox panel state
        self._sb_panel_open  = False
        self._sb_panel_scroll= 0
        self._sb_spawn_counts= {ecls: cnt for ecls, cnt in self._sb_enemy_cfg.items() if cnt > 0}
        self._build_sb_panel_rects()

        # Spawn initial enemies
        self._sandbox_spawn_all()

    def _sandbox_spawn_all(self):
        """Spawn all configured enemies onto the field."""
        for ecls, count in self._sb_spawn_counts.items():
            for j in range(count):
                e = ecls() if ecls is GraveDigger else ecls(1)
                e.x = -80 - j * 55
                self.enemies.append(e)

    def _build_sb_panel_rects(self):
        """Build the in-game sandbox panel rects (spawner button + panel)."""
        self._sb_spawn_btn = pygame.Rect(SCREEN_W - 188, 78, 162, 38)

        # Panel (shown when open) — fixed position, content scrolls inside
        self._sb_panel_rect = pygame.Rect(SCREEN_W - 380, 122, 354, 580)
        self._sb_panel_scroll = 0   # pixel scroll offset

        ALL_ENEMIES = [
            # ── Standard ──
            (Enemy,           "Normal",       (160, 50,  50),  Enemy.BASE_HP),
            (TankEnemy,       "Tank",         (100, 60,  20),  TankEnemy.BASE_HP),
            (ScoutEnemy,      "Scout",        (40,  140, 180), ScoutEnemy.BASE_HP),
            (HiddenEnemy,     "Hidden",       (100, 200, 100), HiddenEnemy.BASE_HP),
            (BreakerEnemy,    "Breaker",      (140, 100, 20),  BreakerEnemy.BASE_HP),
            (ArmoredEnemy,    "Armored",      (80,  90,  110), ArmoredEnemy.BASE_HP),
            (NormalBoss,      "Boss",         (180, 140, 20),  NormalBoss.BASE_HP),
            (SlowBoss,        "SlowBoss",     (200, 140, 30),  SlowBoss.BASE_HP),
            (HiddenBoss,      "HiddenBoss",   (80,  160, 80),  NormalBoss.BASE_HP),
            (Necromancer,     "Necromancer",  (100, 0,   160), Necromancer.BASE_HP),
            (GraveDigger,     "GraveDigger",  (30,  100, 30),  GraveDigger.BASE_HP),
            # ── Sandbox-exclusive ──
            (GlassEnemy,      "Glass",        (160, 220, 255), GlassEnemy.BASE_HP),
            (SteelGolem,      "SteelGolem",   (120, 140, 160), SteelGolem.BASE_HP),
            (RegeneratorEnemy,"Regen",        (40,  200, 90),  RegeneratorEnemy.BASE_HP),
            (PhantomBoss,     "Phantom",      (160, 60,  220), PhantomBoss.BASE_HP),
            (SwarmBoss,       "SwarmQueen",   (220, 120, 30),  SwarmBoss.BASE_HP),
            (AbyssLord,       "AbyssLord",    (80,  0,   160), AbyssLord.BASE_HP),
            # ── Weak starters ──
            (BlobEnemy,       "Blob",         (40,  200, 80),  BlobEnemy.BASE_HP),
            (PaperEnemy,      "Paper",        (220, 215, 170), PaperEnemy.BASE_HP),
            (ZombieEnemy,     "Zombie",       (90,  160, 50),  ZombieEnemy.BASE_HP),
            (BabyDragonEnemy, "BabyDragon",   (220, 90,  30),  BabyDragonEnemy.BASE_HP),
            # ── Mid-game ──
            (MirrorShield,    "MirrorShield", (180, 200, 220), MirrorShield.BASE_HP),
            (ShadowStepper,   "ShadowStep",   (130, 60,  220), ShadowStepper.BASE_HP),
            (VoltCrawler,     "VoltCrawler",  (60,  200, 255), VoltCrawler.BASE_HP),
            (IronMaiden,      "IronMaiden",   (160, 155, 145), IronMaiden.BASE_HP),
            (TimeBender,      "TimeBender",   (240, 200, 50),  TimeBender.BASE_HP),
            # ── Demonic (Hell) ──
            (HellHound,       "HellHound",    (220, 60,  15),  HellHound.BASE_HP),
            (AbyssalSpawn,    "AbyssSpawn",   (200, 30,  30),  AbyssalSpawn.BASE_HP),
            (InfernoWyrm,     "InfernoWyrm",  (255, 100, 0 ),  InfernoWyrm.BASE_HP),
            (AshWraith,       "AshWraith",    (160, 145, 130), AshWraith.BASE_HP),
            (SoulReaper,      "SoulReaper",   (180, 0,   80),  SoulReaper.BASE_HP),
            (DemonKnight,     "DemonKnight",  (100, 20,  180), DemonKnight.BASE_HP),
            (CursedWitch,     "CursedWitch",  (180, 0,   220), CursedWitch.BASE_HP),
            (BrimstoneGolem,  "BrimGolem",    (200, 70,  0 ),  BrimstoneGolem.BASE_HP),
            (DoomBringer,     "DoomBringer",  (180, 10,  30),  DoomBringer.BASE_HP),
            (HellGateKeeper,  "HellKeeper",   (220, 20,  50),  HellGateKeeper.BASE_HP),
        ]
        self._sb_all_enemies = ALL_ENEMIES
        self._sb_panel_counts = {ecls: 1 for ecls, _, _, _ in ALL_ENEMIES}

        # Row geometry is computed dynamically in draw (scroll-relative)
        # but we keep fixed-size logical rects for click detection (rebuilt each draw)
        self._sb_panel_rows  = []
        self._sb_panel_minus = []
        self._sb_panel_plus  = []
        self._sb_panel_send  = []
        self._SB_ROW_H = 44
        self._SB_ROW_GAP = 6
        self._SB_HEADER_H = 48   # height before first row

    def _sb_panel_max_scroll(self):
        n = len(self._sb_all_enemies)
        rh = self._SB_ROW_H + self._SB_ROW_GAP
        content_h = self._SB_HEADER_H + n * rh
        visible_h = self._sb_panel_rect.height - 4
        return max(0, content_h - visible_h)

    def _draw_sb_panel(self):
        surf = self.screen
        mx, my = pygame.mouse.get_pos()

        # ── Spawn toggle button ──
        hov = self._sb_spawn_btn.collidepoint(mx, my)
        bg_col = (20,80,50) if self._sb_panel_open else (15,55,35)
        draw_rect_alpha(surf, bg_col, self._sb_spawn_btn, 230, brad=8)
        pygame.draw.rect(surf, (60,220,120), self._sb_spawn_btn, 2, border_radius=8)
        label_s = "✕ SPAWNER" if self._sb_panel_open else "* SPAWNER"
        txt(surf, label_s, self._sb_spawn_btn.center, (80,255,150), font_sm, center=True)

        if not self._sb_panel_open:
            return

        pr = self._sb_panel_rect
        rh = self._SB_ROW_H
        rg = self._SB_ROW_GAP
        HDR = self._SB_HEADER_H

        # Clamp scroll
        max_scroll = self._sb_panel_max_scroll()
        self._sb_panel_scroll = max(0, min(self._sb_panel_scroll, max_scroll))
        sc = self._sb_panel_scroll

        # ── Panel background ──
        draw_rect_alpha(surf, (12,18,30), pr, 245, brad=12)
        pygame.draw.rect(surf, (40,200,100), pr, 2, border_radius=12)

        # Header (unclipped so it stays fixed)
        hdr_f  = pygame.font.SysFont("consolas", 15, bold=True)
        col_f  = pygame.font.SysFont("consolas", 11)
        txt(surf, "SPAWN ENEMIES", (pr.centerx, pr.y+14), (60,220,120), hdr_f, center=True)
        txt(surf, "enemy           HP     count   send",
            (pr.x+10, pr.y+30), (70,80,100), col_f)

        # ── Clip to scrollable content area ──
        clip = pygame.Rect(pr.x+2, pr.y+HDR, pr.width-14, pr.height-HDR-4)
        old_clip = surf.get_clip()
        surf.set_clip(clip)

        # Rebuild click-detection rects each frame (scroll-relative)
        self._sb_panel_rows  = []
        self._sb_panel_minus = []
        self._sb_panel_plus  = []
        self._sb_panel_send  = []

        nf  = pygame.font.SysFont("consolas", 13, bold=True)
        hf2 = pygame.font.SysFont("consolas", 11)
        btn_f = pygame.font.SysFont("consolas", 14, bold=True)
        send_f = pygame.font.SysFont("consolas", 12, bold=True)

        px = pr.x

        for i, (ecls, ename, ecol, base_hp) in enumerate(self._sb_all_enemies):
            ry = pr.y + HDR + i * (rh + rg) - sc
            row  = pygame.Rect(px+6,   ry,      342, rh)
            rm   = pygame.Rect(px+214, ry+10,   26,  24)
            rp   = pygame.Rect(px+248, ry+10,   26,  24)
            rs   = pygame.Rect(px+282, ry+8,    62,  28)

            self._sb_panel_rows.append(row)
            self._sb_panel_minus.append(rm)
            self._sb_panel_plus.append(rp)
            self._sb_panel_send.append(rs)

            # Skip rows completely outside visible area
            if ry + rh < clip.top or ry > clip.bottom:
                continue

            draw_rect_alpha(surf, ecol, row, 28, brad=6)
            pygame.draw.rect(surf, ecol, row, 1, border_radius=6)

            txt(surf, ename,          (row.x+8, row.y+6),  ecol, nf)
            txt(surf, f"HP:{base_hp}",(row.x+8, row.y+24), (150,160,180), hf2)

            cnt = self._sb_panel_counts.get(ecls, 1)
            draw_rect_alpha(surf, (50,15,15), rm, 200, brad=4)
            draw_rect_alpha(surf, (15,50,15), rp, 200, brad=4)
            pygame.draw.rect(surf, (160,50,50), rm, 1, border_radius=4)
            pygame.draw.rect(surf, (50,160,50), rp, 1, border_radius=4)
            txt(surf, "-", rm.center, (220,80,80),  btn_f, center=True)
            txt(surf, "+", rp.center, (80,220,80),  btn_f, center=True)
            cnt_cx = rm.right + (rp.x - rm.right)//2
            txt(surf, str(cnt), (cnt_cx, rm.centery), (220,220,220), btn_f, center=True)

            hov_s = rs.collidepoint(mx, my)
            draw_rect_alpha(surf, (30,100,60) if hov_s else (20,70,40), rs, 220, brad=5)
            pygame.draw.rect(surf, (60,200,100) if hov_s else (40,140,70), rs, 1, border_radius=5)
            txt(surf, "SEND", rs.center, (100,255,160), send_f, center=True)

        surf.set_clip(old_clip)

        # ── Scrollbar ──
        if max_scroll > 0:
            sb_x = pr.right - 10
            sb_y = pr.y + HDR + 2
            sb_h = pr.height - HDR - 8
            draw_rect_alpha(surf, (30,40,55), (sb_x, sb_y, 7, sb_h), 180, brad=3)
            thumb_h = max(24, int(sb_h * (pr.height - HDR) / max(1, pr.height - HDR + max_scroll)))
            thumb_y = sb_y + int((sb_h - thumb_h) * sc / max(1, max_scroll))
            draw_rect_alpha(surf, (60,200,120), (sb_x, thumb_y, 7, thumb_h), 220, brad=3)
            # scroll hint
            hint_f = pygame.font.SysFont("consolas", 10)
            txt(surf, "▲▼ scroll", (pr.centerx, pr.bottom - 12),
                (50,80,60), hint_f, center=True)

        # Money label below panel
        txt(surf, "∞ MONEY: ∞", (pr.x+8, pr.bottom+8), (60,180,100), font_sm)

    def _handle_sb_panel_click(self, pos):
        if self._sb_spawn_btn.collidepoint(pos):
            self._sb_panel_open = not self._sb_panel_open
            return
        if not self._sb_panel_open:
            return
        # Only process clicks inside the panel
        if not self._sb_panel_rect.collidepoint(pos):
            return
        for i, (ecls, _, _, _) in enumerate(self._sb_all_enemies):
            if i >= len(self._sb_panel_minus):
                break
            rm = self._sb_panel_minus[i]
            rp = self._sb_panel_plus[i]
            rs = self._sb_panel_send[i]
            if rm.collidepoint(pos):
                self._sb_panel_counts[ecls] = max(1, self._sb_panel_counts.get(ecls,1)-1)
                return
            elif rp.collidepoint(pos):
                self._sb_panel_counts[ecls] = min(50, self._sb_panel_counts.get(ecls,1)+1)
                return
            elif rs.collidepoint(pos):
                cnt = self._sb_panel_counts.get(ecls, 1)
                for j in range(cnt):
                    e = ecls() if ecls is GraveDigger else ecls(1)
                    e.x = -60 - j * 55
                    self.enemies.append(e)
                self.ui.show_msg(f"Spawned {cnt}x {ecls.DISPLAY_NAME}!", 1.5)
                return

    def update(self, dt):
        # Keep money infinite
        self.money = 999_999_999
        # No win condition in sandbox
        self.win = False
        # Don't lose HP in sandbox
        super_update_enemies_only(self, dt)

    def draw(self):
        super().draw()
        self._draw_sb_panel()
        # Sandbox label top-center
        sb_f = pygame.font.SysFont("consolas", 14, bold=True)
        txt(self.screen, "🧪 SANDBOX  •  ∞ Money", (SCREEN_W//2, 8),
            (60, 200, 120), sb_f, center=True)

    def run(self):
        self.paused = False
        pmenu_w, pmenu_h = 403, 288
        pmenu_x, pmenu_y = SCREEN_W//2 - pmenu_w//2, SCREEN_H//2 - pmenu_h//2
        btn_resume = pygame.Rect(pmenu_x+58, pmenu_y+101, pmenu_w-115, 69)
        btn_exit   = pygame.Rect(pmenu_x+58, pmenu_y+190, pmenu_w-115, 69)
        btn_speed  = pygame.Rect(26, 78, 115, 37)

        while self.running:
            raw_dt = min(self.clock.tick(FPS)/1000.0, 0.05)
            dt = raw_dt * (2.0 if self.speed_x2 else 1.0)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: pygame.quit(); sys.exit()

                # Dev console gets F3 before anything else
                if self.dev_console.handle_event(ev, self):
                    continue

                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    if self.paused:
                        self.paused = False
                    else:
                        self.paused = not self.paused

                if self.paused:
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        if btn_resume.collidepoint(ev.pos):
                            self.paused = False
                        elif btn_exit.collidepoint(ev.pos):
                            self.running = False
                    continue

                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if btn_speed.collidepoint(ev.pos):
                        self.speed_x2 = not self.speed_x2
                    self._handle_sb_panel_click(ev.pos)
                    self.money += self.ui.handle_click(ev.pos, self.units, self.money,
                                                       self.effects, self.enemies)
                    self.money = 999_999_999  # restore after any purchase

                # Mouse wheel: scroll spawn panel if open and hovered
                if ev.type == pygame.MOUSEWHEEL:
                    if self._sb_panel_open and self._sb_panel_rect.collidepoint(pygame.mouse.get_pos()):
                        self._sb_panel_scroll -= ev.y * 28
                        self._sb_panel_scroll = max(0, min(self._sb_panel_scroll,
                                                           self._sb_panel_max_scroll()))

                if ev.type == pygame.KEYDOWN:
                    tower_keys = {pygame.K_1:0, pygame.K_2:1, pygame.K_3:2,
                                  pygame.K_4:3, pygame.K_5:4}
                    if ev.key in tower_keys:
                        slot_idx = tower_keys[ev.key]
                        mx2t, my2t = pygame.mouse.get_pos()
                        self.ui.select_slot_by_key(slot_idx,(mx2t,my2t),
                                                   self.units,self.money)
                    if ev.key == pygame.K_e and self.ui.open_unit:
                        u2 = self.ui.open_unit
                        cost = u2.upgrade_cost()
                        if cost:
                            u2.upgrade()
                            self.ui.show_msg(f"Upgraded to Lv{u2.level}!", 1.5)
                        else:
                            self.ui.show_msg("Max level!", 1.5)
                    if ev.key == pygame.K_x and self.ui.open_unit:
                        refund = self.ui.sell_unit(self.ui.open_unit, self.units)
                        self.ui.show_msg(f"Sold! +${refund}", 1.5)
                    if ev.key == pygame.K_f:
                        for u in self.units:
                            if isinstance(u, Assassin) and u.ability and u.level >= 2:
                                if u.ability.ready():
                                    u.ability.activate(self.enemies, self.effects)
                                    break

            if not self.paused:
                self._do_sandbox_update(dt)
            self.draw()
            if self.paused:
                self._draw_pause_menu(btn_resume, btn_exit, pmenu_x, pmenu_y, pmenu_w, pmenu_h)
            self.dev_console.tick(self)
            self.dev_console.draw(self.screen, raw_dt)
            pygame.display.flip()
        self._restore_enemies()

    def _do_sandbox_update(self, dt):
        # Enemy movement (no HP loss, sandbox = never lose)
        for e in self.enemies:
            if e.alive:
                reached = e.update(dt)
                if reached:
                    e.x = -80  # loop enemy back to start
                    e.hp = e.maxhp  # reset HP

        # Remove dead enemies (killed by towers)
        self.enemies = [e for e in self.enemies if e.alive]

        # Units attack
        for u in self.units:
            u.update(dt, self.enemies, self.effects, self.money)

        # Clown global CD
        if Clown._CONFUSE_CD > 0:
            Clown._CONFUSE_CD = max(0.0, Clown._CONFUSE_CD - dt)

        # Breaker death spawn
        new_enemies = []
        for e in self.enemies:
            if not e.alive and isinstance(e, BreakerEnemy):
                Sp = random.choice(BREAKER_POOL)
                baby = Sp(1); baby.x = e.x; new_enemies.append(baby)
        self.enemies = [e for e in self.enemies if e.alive] + new_enemies

        # SwarmBoss spawn scouts while alive
        swarm_spawns = []
        for e in self.enemies:
            if e.alive and isinstance(e, SwarmBoss) and e.should_spawn():
                scout = ScoutEnemy(1); scout.x = e.x - 30
                swarm_spawns.append(scout)
        self.enemies += swarm_spawns

        # VoltCrawler chain-zap
        for e in self.enemies:
            if not e.alive and isinstance(e, VoltCrawler) and e._chain_triggered:
                e._chain_triggered = False
                for other in self.enemies:
                    if other.alive and dist((other.x, other.y), (e.x, e.y)) <= VoltCrawler.CHAIN_RADIUS:
                        other.take_damage(VoltCrawler.CHAIN_DAMAGE)

        # TimeBender slow
        for e in self.enemies:
            if e.alive and isinstance(e, TimeBender) and e.pulse_fired:
                for u in self.units:
                    if dist((u.px, u.py), (e.x, e.y)) <= TimeBender.PULSE_RADIUS:
                        u._time_slow_timer = TimeBender.PULSE_DURATION
        # CursedWitch pulse
        for e in self.enemies:
            if e.alive and isinstance(e, CursedWitch) and e.pulse_fired:
                for u in self.units:
                    if dist((u.px, u.py), (e.x, e.y)) <= CursedWitch.PULSE_RADIUS:
                        u._time_slow_timer = CursedWitch.PULSE_DURATION
        # DoomBringer pulse
        for e in self.enemies:
            if e.alive and isinstance(e, DoomBringer) and e.pulse_fired:
                for u in self.units:
                    if dist((u.px, u.py), (e.x, e.y)) <= DoomBringer.PULSE_RADIUS:
                        u._time_slow_timer = DoomBringer.PULSE_DURATION
        # HellGateKeeper pulse
        for e in self.enemies:
            if e.alive and isinstance(e, HellGateKeeper) and e.pulse_fired:
                for u in self.units:
                    if dist((u.px, u.py), (e.x, e.y)) <= HellGateKeeper.PULSE_RADIUS:
                        u._time_slow_timer = HellGateKeeper.PULSE_DURATION
        for u in self.units:
            tslow = getattr(u, '_time_slow_timer', 0.0)
            if tslow > 0:
                u._time_slow_timer = max(0.0, tslow - dt)
                u.cd_left = min(getattr(u, 'firerate', 9999) * 2.0, u.cd_left + dt)
        # AbyssalSpawn death split
        new_spawns = []
        for e in self.enemies:
            if not e.alive and isinstance(e, AbyssalSpawn):
                for _ in range(2):
                    baby = HellHound(1); baby.x = e.x + random.uniform(-20,20)
                    new_spawns.append(baby)
        self.enemies = [e for e in self.enemies if e.alive] + new_spawns

        self.effects = [ef for ef in self.effects if ef.update(dt)]
        self.ui.update(dt)
        self.money = 999_999_999


def super_update_enemies_only(self, dt):
    """Stub — SandboxGame uses _do_sandbox_update instead."""
    pass


if __name__=="__main__":
    pygame.init()

    # Native 1920x1080 fullscreen — no canvas scaling needed
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN | pygame.NOFRAME)
    pygame.display.set_caption("Tower Defense")

    # Load icons now that the display surface exists
    _load_all_icons()

    while True:
        lobby = Lobby(screen)
        result = lobby.run()

        # result is either ("sandbox", cfg_dict) or (difficulty_str, loadout_list)
        if isinstance(result[0], str) and result[0] == "sandbox":
            sb_cfg = result[1]
            SandboxGame(sb_cfg=sb_cfg, screen_override=screen).run()
        else:
            difficulty, loadout = result
            Game(difficulty=difficulty, loadout=loadout, screen_override=screen).run()