import pygame
import sys
import math
import os
import random
from pathlib import Path
from enemies import spawn_enemies, Enemy  # added: import enemy helpers
import pause  # NEW: pause + death screens
import powerups  # NEW: powerup selection UI
import sounds  # NEW: gameplay music volume reference
from weapons import WEAPON_LIST  # NEW: weapon definitions
import save  # ADDED: ensure save module imported for high score persistence

BASE_DIR = Path(__file__).parent
def asset_path(*parts):
    return str(BASE_DIR.joinpath(*parts))

# gameplay music helpers (added)
_game_music_started = False

def resource_path(relative_path):
    """ Get the absolute path to a resource, works for dev & for PyInstaller .exe """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def _find_play_music(mode: str | None = None):
    base = Path(__file__).parent
    snd_dir = base.joinpath('sounds')
    if not snd_dir.exists():
        return None
    # prefer an explicit endless music file when running endless mode
    try:
        if isinstance(mode, str) and mode.lower() == "endless":
            for ext in ("ogg", "mp3", "wav"):
                p = snd_dir.joinpath(f"EndlessBGM.{ext}")
                if p.exists():
                    return str(p)
    except Exception:
        pass
    for ext in ("ogg", "mp3", "wav"):
        p = snd_dir.joinpath(f"PlayBGM.{ext}")
        if p.exists():
            return str(p)
    for name in ("game", "gameplay", "bgm_play", "level", "run"):
        for ext in ("ogg", "mp3", "wav"):
            p = snd_dir.joinpath(f"{name}.{ext}")
            if p.exists():
                return str(p)
    return None

def _start_play_music(mode: str | None = None):
    global _game_music_started
    if _game_music_started:
        try:
            if pygame.mixer.music.get_busy():
                return
            else:
                _game_music_started = False
        except Exception:
            _game_music_started = False
    try:
        path = _find_play_music(mode)
        if path:
            pygame.mixer.music.load(path)
            vol = getattr(sounds, 'MASTER_VOLUME', 1.0)
            pygame.mixer.music.set_volume(vol)
            pygame.mixer.music.play(-1)
            _game_music_started = True
    except Exception:
        pass

# ======================
# GAME LOOP
# ======================
def run_game(screen=None, difficulty: str = "normal", mode: str = "main"):
    """Run the game loop. If `screen` (a pygame Surface / display) is provided the game will use it
       instead of creating a new fullscreen window — this allows returning to the menu cleanly.
       `mode` is currently accepted for compatibility with menu.run_menu and is not used."""
    # --- Common init ---
    created_display = False
    if screen is None:
        pygame.init()
        screen_info = pygame.display.Info()
        win = pygame.display.set_mode((screen_info.current_w, screen_info.current_h), pygame.FULLSCREEN)
        pygame.display.set_caption("Walking Character + Map")
        created_display = True
    else:
        # reuse the provided display surface (menu's SCREEN)
        win = screen
    clock = pygame.time.Clock()
    _start_play_music(mode)  # start gameplay music (mode selects EndlessBGM for endless)

    # ======================
    # MAP DATA AND LOADER
    # ======================
    TILE_SIZE = 48
    WIDTH = 13
    HEIGHT = 13

    WALL_TILES = {"-", "|", "A", "B", "C", "D", "#", "0", "I"}
    LAVA_TILE = "X"
    TRAP_TILE = "T"

    def load_map_from_file(filename):
        """Load a map file from project maps/ folder. If missing, return a default floor map.
           Ensures result is exactly HEIGHT x WIDTH by padding/truncating."""
        full_path = asset_path("maps", filename)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                raw_lines = [list(line.rstrip("\n")) for line in f.readlines()]
        else:
            print(f"Warning: map file not found: {full_path}. Using empty floor map.")
            raw_lines = [['.' for _ in range(WIDTH)] for _ in range(HEIGHT)]

        # Normalize to HEIGHT x WIDTH
        lines = []
        for r in range(HEIGHT):
            if r < len(raw_lines):
                row = raw_lines[r]
                if len(row) < WIDTH:
                    row = row + ['.'] * (WIDTH - len(row))
                elif len(row) > WIDTH:
                    row = row[:WIDTH]
            else:
                row = ['.'] * WIDTH
            lines.append(row)
        return lines

    # --- Add MAPS definition so pick_map() can use it ---
    MAPS = [load_map_from_file(f"map{i}.txt") for i in range(1, 16)]

    # Original staged non‑repeating normal progression: (1-5), (6-10), (11-15)
    stage_indices = [list(range(0,5)), list(range(5,10)), list(range(10,15))]
    for lst in stage_indices:
        random.shuffle(lst)
    current_stage = 0
    index_in_stage = 0

    # NEW: endless mode flag
    is_endless = str(mode).lower() == "endless"

    # Helper to reshuffle and restart stage order (used by endless)
    def _reset_stage_order():
        nonlocal stage_indices, current_stage, index_in_stage
        stage_indices = [list(range(0,5)), list(range(5,10)), list(range(10,15))]
        for lst in stage_indices:
            random.shuffle(lst)
        current_stage = 0
        index_in_stage = 0

    # Boss levels: inserted AFTER normal levels 5, 10, 15 -> total 18 levels (15 normal + 3 boss)
    # Boss map always uses map1 (index 0) and may repeat even if map1 already appeared as a normal level.
    def get_boss_map():
        game_map = MAPS[0]
        floor_choices = [[None for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if game_map[y][x] == ".":
                    floor_choices[y][x] = random.choice(FLOOR_SPRITES)
        return game_map, floor_choices

    def pick_normal_map():
        nonlocal current_stage, index_in_stage
        while current_stage < len(stage_indices) and index_in_stage >= len(stage_indices[current_stage]):
            current_stage += 1
            index_in_stage = 0
        if current_stage >= len(stage_indices):
            return None
        idx = stage_indices[current_stage][index_in_stage]
        index_in_stage += 1
        game_map = MAPS[idx]
        floor_choices = [[None for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if game_map[y][x] == ".":
                    floor_choices[y][x] = random.choice(FLOOR_SPRITES)
        return game_map, floor_choices

    def load_sprite(filename, size=TILE_SIZE, rotation=0):
        """Load sprite from project sprites/ folder. Return visible placeholder on failure."""
        full_path = asset_path("sprites", filename)
        try:
            img = pygame.image.load(full_path).convert_alpha()
            img = pygame.transform.scale(img, (size, size))
            if rotation != 0:
                img = pygame.transform.rotate(img, rotation)
            return img
        except Exception:
            # visible placeholder (keeps program running when sprites missing)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            surf.fill((140, 140, 140, 255))
            line_w = max(1, size // 12)
            pygame.draw.line(surf, (200, 30, 30), (0, 0), (size, size), line_w)
            pygame.draw.line(surf, (200, 30, 30), (0, size), (size, 0), line_w)
            if rotation != 0:
                surf = pygame.transform.rotate(surf, rotation)
            return surf

    # NOTE: Ensure the sprites directory contains the required PNGs used below.
    SPRITES = {
        "-": load_sprite("wall_edge.png"),
        "|": load_sprite("wall_side.png"),
        "I": load_sprite("wall_side.png", rotation=180),
        "X": load_sprite("lava.png"),
        "A": pygame.transform.flip(load_sprite("wall_corner_1.png"), True, False),
        "B": load_sprite("wall_corner_1.png"),
        "C": pygame.transform.flip(load_sprite("wall_corner_2.png"), True, False),
        "D": load_sprite("wall_corner_2.png"),
        "0": load_sprite("wall_middle_1.png"),
        "#": load_sprite("wall_middle_2.png"),
        "T": load_sprite("trap_off.png")
    }
    
    # --- WEAPON SYSTEM (replaces single hardcoded sword) ---
    current_weapon_index = 0
    current_weapon = WEAPON_LIST[current_weapon_index]
    # NEW: resolve which weapons are owned (always include Sword) and pick equipped weapon if valid
    try:
        _saved = save.load_player_data() or {}
        _owned_names = set(_saved.get("weapons_owned") or [])
        _equipped_name = (_saved.get("equipped_weapon") or "").strip()
        # NEW: read upgrade levels per weapon (Lv1..Lv4)
        _weapon_upgrades = dict(_saved.get("weapons_upgrades") or {})
        # NEW: equipped armor
        _equipped_armor = (_saved.get("equipped_armor") or "").strip()
    except Exception:
        _owned_names = set()
        _equipped_name = ""
        _weapon_upgrades = {}
        _equipped_armor = ""
    _owned_names.add("Sword")
    # Ensure Sword is equipped by default for first-time players
    if (not _equipped_name) or all(w.name != _equipped_name for w in WEAPON_LIST):
        try:
            sword_idx = next(i for i, w in enumerate(WEAPON_LIST) if w.name == "Sword")
            current_weapon_index = sword_idx
            current_weapon = WEAPON_LIST[sword_idx]
            try:
                save.save_player_data({"equipped_weapon": "Sword"})
            except Exception:
                pass
        except StopIteration:
            pass
    # NEW: armor flags
    equipped_swiftness = (_equipped_armor == "Swiftness Armor")
    equipped_tank = (_equipped_armor == "Tank Armor")
    swiftness_outline = equipped_swiftness
    tank_outline = equipped_tank
    # NEW: Life Armor (+1 heart + red outline)
    equipped_life = (_equipped_armor == "Life Armor")
    life_outline = equipped_life
    # NEW: Regen Armor (heal + outline)
    equipped_regen = (_equipped_armor == "Regen Armor")
    regen_outline = equipped_regen
    # NEW: Thorns Armor (retaliate + green outline)
    equipped_thorns = (_equipped_armor == "Thorns Armor")
    thorns_outline = equipped_thorns
    # NEW: surface for outline reuse
    outline_surface = None

    owned_weapon_indices = {i for i, w in enumerate(WEAPON_LIST) if w.name in _owned_names}
    if _equipped_name:
        try:
            current_weapon_index = next(i for i, w in enumerate(WEAPON_LIST) if w.name == _equipped_name)
            current_weapon = WEAPON_LIST[current_weapon_index]
        except Exception:
            pass
    # NEW: player projectile state
    current_projectile_img = None
    player_projectiles = []  # each: {'x','y','vx','vy','life','damage','img','radius'}

    sword_img = load_sprite(current_weapon.sprite_name, size=48)
    attack_duration = current_weapon.swing_ms
    attack_cooldown = current_weapon.cooldown_ms
    attacking = False
    attack_timer = 0
    cooldown_timer = 0
    swing_start_angle = 0
    swing_arc = current_weapon.arc_deg
    sword_damage = current_weapon.damage
    attack_hits = set()
    # NEW: bonus damage that applies to player projectiles (e.g., sunball)
    projectile_damage_bonus = 0
    # NEW: total accumulated +Damage powerup bonus (used for Thorns scaling)
    damage_powerup_total = 0
    # NEW: upgrade-derived damage bonuses (melee + projectile)
    upgrade_damage_bonus = 0
    projectile_upgrade_damage = 0

    # Helper: compute cumulative damage bonus for levels 2..4 -> +1, +3, +6
    def _calc_upgrade_bonus_for_level(level: int) -> int:
        # level 1 => 0, 2 => 1, 3 => 1+2, 4 => 1+2+3
        ladder = [1, 2, 3]
        if level is None:
            return 0
        try:
            lvl = int(level)
        except Exception:
            lvl = 1
        bonus = 0
        for i in range(1, min(lvl, 4)):
            bonus += ladder[i-1]
        return bonus

    def _get_upgrade_level_for(name: str) -> int:
        try:
            return int(_weapon_upgrades.get(name, 1))
        except Exception:
            return 1

    def _recompute_weapon_stats_for_current():
        nonlocal sword_img, attack_duration, attack_cooldown, swing_arc, sword_damage, attack_hits, current_projectile_img, upgrade_damage_bonus, projectile_upgrade_damage
        # sprite & timings already set by caller if needed
        # apply upgrade bonuses
        upgrade_damage_bonus = _calc_upgrade_bonus_for_level(_get_upgrade_level_for(current_weapon.name))
        projectile_upgrade_damage = upgrade_damage_bonus
        sword_damage = current_weapon.damage + upgrade_damage_bonus
        # NEW: apply armor damage bonus (+5) if Swiftness Armor equipped
        if equipped_swiftness:
            sword_damage += 5
            projectile_upgrade_damage += 5
        attack_hits.clear()
        # load projectile sprite (if any)
        current_projectile_img = None
        if current_weapon.projectile_damage > 0:
            try:
                current_projectile_img = load_sprite(current_weapon.projectile_sprite or "sunball.png", size=32)
            except Exception:
                current_projectile_img = None

    # Poison level from powerups (stacks)
    poison_level = 0

    # --- SHIELD POWERUP STATE ---
    shield_count = 0
    shield_angle = 0.0
    shield_img = load_sprite("shield.png", size=48)
    if shield_img is None:
        shield_img = pygame.Surface((48, 48), pygame.SRCALPHA)
        pygame.draw.circle(shield_img, (0, 255, 255), (24, 24), 20)  # Cyan circle as fallback
    shield_radius = 64  # distance from player center
    shield_stun_duration = 500  # ms

    # Stun indicator sprite (native size)
    try:
        stunned_img = pygame.image.load(asset_path("sprites", "stunned.png")).convert_alpha()
    except Exception:
        # fallback to scaled loader if native load fails
        stunned_img = load_sprite("stunned.png", size=48)

    # Trap sprites
    trap_off_img = load_sprite("trap_off.png")
    trap_on_img = load_sprite("trap_on.png")
    trap_toggle_interval = 1500  # ms (1.5s toggle)
    trap_timer = 0
    trap_active = False

    # NEW: portal to go to next level after clearing
    portal_img = load_sprite("portal.png", size=TILE_SIZE)
    portal_active = False
    portal_rect = None

    FLOOR_SPRITES = [
        load_sprite("floor_1.png"),
        load_sprite("floor_2.png"),
        load_sprite("floor_3.png"),
        load_sprite("floor_4.png"),
        load_sprite("floor_5.png"),
        load_sprite("floor_6.png")
    ]

    # REMOVED duplicate random pick_map; staged pick_map defined earlier
    # def pick_map():
    #     ... old random implementation ...

    # NOTE: Removed an earlier redundant call to pick_map() that consumed the first map before play started.
    # game_map, floor_choices = pick_map()  # (removed to ensure all 15 maps are played)
    # level_number = 1 if game_map else 0  # (duplicate; real initialization occurs below)

    def draw_map(win, game_map, floor_choices, offset_x, offset_y, trap_active):
        for y in range(HEIGHT):
            for x in range(WIDTH):
                tile = game_map[y][x]
                if tile == ".":
                    sprite = floor_choices[y][x]
                elif tile == "T":
                    sprite = trap_on_img if trap_active else trap_off_img
                else:
                    sprite = SPRITES[tile]
                win.blit(sprite, (offset_x + x*TILE_SIZE, offset_y + y*TILE_SIZE))
    
    def draw_crosshair(win, player_pos):
        mx, my = pygame.mouse.get_pos()
        px, py = player_pos
        angle = math.atan2(my - py, mx - px)

        radius = 50  # distance from player
        cross_x = px + radius * math.cos(angle)
        cross_y = py + radius * math.sin(angle)

        # small circle as crosshair marker
        pygame.draw.circle(win, (255, 255, 255), (int(cross_x), int(cross_y)), 8, 4)
    
    def draw_shadow(win, x, y, char_size, game_map, offset_x, offset_y):
        # Shadow ellipse dimensions
        shadow_w = char_size * 0.8
        shadow_h = char_size * 0.4
        shadow_x = x + (char_size - shadow_w) / 2
        shadow_y = y + char_size - shadow_h / 2

        shadow = pygame.Surface((int(shadow_w), int(shadow_h)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 100), shadow.get_rect())
        win.blit(shadow, (shadow_x, shadow_y))

    def can_move(new_x, new_y, game_map, dashing=False):
        foot_width = char_size // 2
        foot_height = 10
        foot_x = new_x + (char_size - foot_width) // 2
        foot_y = new_y + char_size - foot_height - 5
        foot_rect = pygame.Rect(foot_x, foot_y, foot_width, foot_height)

        for px, py in [
            (foot_rect.left, foot_rect.bottom - 1),
            (foot_rect.right - 1, foot_rect.bottom - 1),
            (foot_rect.centerx, foot_rect.bottom - 1)
        ]:
            tile_x = int((px - offset_x) // TILE_SIZE)
            tile_y = int((py - offset_y) // TILE_SIZE)

            if tile_x < 0 or tile_x >= WIDTH or tile_y < 0 or tile_y >= HEIGHT:
                return False
            
            tile = game_map[tile_y][tile_x]
            if tile in WALL_TILES:
                return False
            if tile == LAVA_TILE and not dashing:
                return False

        return True
    
    def precompute_rotations(image, step=3):
        rotations = {}
        for angle in range(0, 360, step):
            rotations[angle] = pygame.transform.rotate(image, -angle)
        return rotations

    sword_rotations = precompute_rotations(sword_img, step=3)
    # (ensure projectile sprite for initial weapon if needed)
    if current_weapon.projectile_damage > 0:
        try:
            current_projectile_img = load_sprite(current_weapon.projectile_sprite or "sunball.png", size=48)
        except Exception:
            current_projectile_img = None

    # APPLY saved weapon upgrade bonuses (damage for melee and projectiles)
    _recompute_weapon_stats_for_current()

    # ======================
    # CHARACTER SETUP
    # ======================
    def load_char_sprite(name, size):
        """Load character sprite from project sprites/ folder or return placeholder."""
        full_path = asset_path("sprites", name)
        try:
            img = pygame.image.load(full_path).convert_alpha()
            return pygame.transform.scale(img, (size, size))
        except Exception:
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            surf.fill((90, 120, 200, 255))
            pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), max(1, size//16))
            return surf

    char_size = 48
    # base speeds
    vel = 4
    dash_speed = 16
    # NEW: Swiftness Armor speed buffs
    if equipped_swiftness:
        vel = int(round(vel * 1.5))  # +50% move speed
        dash_speed = int(round(dash_speed * 1.5))  # +50% dash speed
    dash_duration = 200
    stamina_max = 3.0
    stamina_regen_rate = 0.5

    animations = {
        "up": [
            load_char_sprite("up_idle.png", char_size),
            load_char_sprite("up_walk1.png", char_size),
            load_char_sprite("up_walk2.png", char_size)
        ],
        "down": [
            load_char_sprite("down_idle.png", char_size),
            load_char_sprite("down_walk1.png", char_size),
            load_char_sprite("down_walk2.png", char_size)
        ],
        "left": [
            load_char_sprite("left_idle.png", char_size),
            load_char_sprite("left_walk1.png", char_size),
            load_char_sprite("left_walk2.png", char_size)
        ],
        "right": [
            load_char_sprite("right_idle.png", char_size),
            load_char_sprite("right_walk1.png", char_size),
            load_char_sprite("right_walk2.png", char_size)
        ]
    }

    key_to_dir = {
        pygame.K_w: "up",
        pygame.K_s: "down",
        pygame.K_a: "left",
        pygame.K_d: "right"
    }

    # Helper: map a movement vector to a facing direction
    def dir_from_vector(dx: float, dy: float, last_dir: str) -> str:
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return last_dir
        if abs(dx) >= abs(dy):
            return "right" if dx > 0 else "left"
        else:
            return "down" if dy > 0 else "up"

    game_map, floor_choices = pick_normal_map()
    # NEW: endless mode — recycle maps when the staged set is exhausted
    if is_endless and (not game_map):
        _reset_stage_order()
        res0 = pick_normal_map()
        if res0:
            game_map, floor_choices = res0
    level_number = 1 if game_map else 0  # NEW: level counter
    is_boss_level = False  # track if current level is a boss level
    normal_levels_completed = 0  # how many normal (non-boss) levels fully cleared

    # NEW: dynamic enemy count per level range (non-boss levels)
    def enemy_count_for_level(level_num: int, is_boss: bool) -> int:
        if is_endless:
            # simple, stable scaling for endless (no bosses)
            if level_num <= 6:
                return 6
            if level_num <= 12:
                return 8
            return 10
        if is_boss:
            return 1  # boss level handled separately
        if 1 <= level_num <= 5:
            return 6
        if 7 <= level_num <= 11:
            return 8
        if 13 <= level_num <= 17:
            return 10
        # fallback (covers any unexpected normal levels)
        return 6

    # NEW: per-level enemy scaling (HP and speed)
    def _level_scalars(level_num: int):
        """Return (hp_mult, speed_mult) based on visible level number."""
        # Endless: clamp to highest tier after level 17 so difficulty doesn't drop
        if is_endless and level_num > 17:
            return 4.0, 1.6
        if 7 <= level_num <= 11:
            return 2.0, 1.3   # CHANGED: 2x HP, 30% faster
        if 13 <= level_num <= 17:
            return 4.0, 1.6   # 4x HP, 60% faster
        return 1.0, 1.0

    def _apply_level_scaling(enemies_list, level_num: int):
        hp_mult, spd_mult = _level_scalars(level_num)
        if hp_mult == 1.0 and spd_mult == 1.0:
            return
        for e in enemies_list:
            # HP scale
            try:
                e.hp = int(math.ceil(e.hp * hp_mult))
            except Exception:
                pass
            # Move speed scale
            try:
                e.speed *= spd_mult
            except Exception:
                pass
            # Make slimes hop a bit more often when "faster"
            try:
                if getattr(e, "is_slime", False) and getattr(e, "hop_cooldown", None) is not None:
                    e.hop_cooldown = max(300, int(e.hop_cooldown / spd_mult))
            except Exception:
                pass

    # NEW: per-level points multiplier (affects scoring only)
    def _level_points_multiplier(level_num: int) -> float:
        if 7 <= level_num <= 11:
            return 1.5
        if 13 <= level_num <= 17:
            return 2.0
        return 1.0

    screen_width, screen_height = win.get_size()
    offset_x = (screen_width - WIDTH * TILE_SIZE) // 2
    offset_y = (screen_height - HEIGHT * TILE_SIZE) // 2

    x = offset_x + (WIDTH // 2) * TILE_SIZE
    y = offset_y + 1 * TILE_SIZE

    # --- SHOW POWERUP SELECTION BEFORE THE ROUND STARTS ---
    # REMOVED: pre-round powerup selection; powerups are now granted only after a round is completed.
    # (Handled exclusively inside do_map_transition after all enemies are defeated.)

    # spawn enemies
    enemies = spawn_enemies(game_map, count=enemy_count_for_level(level_number, is_boss_level), tile_size=TILE_SIZE, offset_x=offset_x, offset_y=offset_y, valid_tile=".", enemy_size=48, speed=1.5, kind="mix")
    # NEW: scale newly spawned enemies by level
    _apply_level_scaling(enemies, level_number)
    # preload sounds
    try: sounds.preload('HitSound')
    except Exception: pass
    try: sounds.preload('Damaged')
    except Exception: pass
    try: sounds.preload('Dash')
    except Exception: pass

    # NEW: death handler -> convert points to coins, save, and show death screen
    def _on_player_death():
        # delegate to game-over so death and quit share the same flow
        _on_game_over()

    # NEW: unified game-over flow (used on death or when quitting from pause/closing window)
    def _on_game_over():
        nonlocal score
        # Endless: no coins, update high score instead
        if is_endless:
            try:
                data = save.load_player_data() or {}
                prev = int(data.get("endless_high_score", 0))
                if int(score) > prev:
                    data["endless_high_score"] = int(score)
                    save.save_player_data(data)
                # fetch (possibly updated) best for display
                best_endless = int((save.load_player_data() or {}).get("endless_high_score", 0))
            except Exception:
                best_endless = 0
            # show death screen (coins 0, use high_score param to display endless best)
            try:
                from pause import show_death_screen
                show_death_screen(win, score=int(score), coins=0, high_score=best_endless)
            except Exception:
                pass
            return  # ENDLESS path finished
        # UPDATED: campaign high score safeguard
        coins_gained = int(score // 50)
        try:
            data = save.load_player_data() or {}
            prev_main = int(data.get("high_score", 0))
            if int(score) > prev_main:
                data["high_score"] = int(score)
            data["coins"] = int(data.get("coins", 0)) + coins_gained
            save.save_player_data(data)
        except Exception:
            pass
        # show Game Over screen with score/coins
        try:
            pause.show_death_screen(win, score=score, coins=coins_gained)
        except Exception:
            pass

    # NEW: unified game-win flow (used after beating all 18 levels)
    def _on_game_win():
        nonlocal score
        # Double the points at the end on win
        final_score = int(score) * 2
        coins_gained = int(final_score // 50)
        try:
            data = save.load_player_data() or {}
            data["coins"] = int(data.get("coins", 0)) + coins_gained
            # update high_score for main-mode runs if beaten by final_score
            try:
                prev_hs = int(data.get("high_score", 0))
            except Exception:
                prev_hs = 0
            if int(final_score) > prev_hs:
                data["high_score"] = int(final_score)
            save.save_player_data(data)
        except Exception:
            pass
        try:
            pause.show_victory_screen(win, score=final_score, coins=coins_gained)
        except Exception:
            pass

    # NEW: level transition state (auto when all enemies dead)
    level_transitioning = False
    game_finished = False  # NEW: flag when all maps used
    # NEW: one-time per round flag (after clear we show picker, then spawn portal)
    round_cleared = False

    # helper: pick a bottom-most '.' tile near center for the portal
    def _find_portal_spot(cur_map):
        center_x = WIDTH // 2
        # scan from bottom upwards, prefer positions near center
        for ty in range(HEIGHT - 2, -1, -1):
            order = [center_x]
            for k in range(1, WIDTH):
                if center_x - k >= 0: order.append(center_x - k)
                if center_x + k < WIDTH: order.append(center_x + k)
            for tx in order:
                try:
                    if cur_map[ty][tx] == '.':
                        px = offset_x + tx * TILE_SIZE
                        py = offset_y + ty * TILE_SIZE
                        return px, py
                except Exception:
                    continue
        # fallback: near bottom center
        return offset_x + center_x * TILE_SIZE, offset_y + max(0, HEIGHT - 2) * TILE_SIZE

    def do_map_transition():
        nonlocal game_map, floor_choices, x, y, pressed_dirs, is_dashing, frame_index, enemies, spawn_grace_timer, level_transitioning, vel, dash_speed, attack_cooldown, stamina_regen_rate, sword_damage, projectile_damage_bonus, shield_count, poison_level, game_finished, level_number, is_boss_level, normal_levels_completed, portal_active, portal_rect, round_cleared
        if level_transitioning or game_finished:
            return
        level_transitioning = True
        # hide portal immediately on transition
        portal_active = False
        portal_rect = None
        elapsed_here = 0

        # NEW: Endless — no bosses, never finish; recycle maps forever
        if is_endless:
            res = pick_normal_map()
            if res is None:
                _reset_stage_order()
                res = pick_normal_map()
            game_map, floor_choices = res
            level_number += 1
            is_boss_level = False
            # Reset player state & spawn enemies
            x = offset_x + (WIDTH // 2) * TILE_SIZE
            y = offset_y + 1 * TILE_SIZE
            pressed_dirs.clear()
            is_dashing = False
            frame_index = 0
            enemies = spawn_enemies(game_map, count=enemy_count_for_level(level_number, False), tile_size=TILE_SIZE, offset_x=offset_x, offset_y=offset_y, valid_tile=".", enemy_size=48, speed=1.5, kind="mix")
            _apply_level_scaling(enemies, level_number)
            spawn_grace_timer = 1500 + int(elapsed_here)
            round_cleared = False
            level_transitioning = False
            return

        # Determine next level type (non-endless)
        if is_boss_level:
            # just finished a boss level
            if normal_levels_completed >= 15:
                game_finished = True
                level_transitioning = False
                # NEW: show victory screen after final boss
                _on_game_win()
                return
            next_is_boss = False
        else:
            # just finished a normal level
            normal_levels_completed += 1
            next_is_boss = normal_levels_completed in (5, 10, 15)

        if next_is_boss:
            res = get_boss_map()
        else:
            res = pick_normal_map()
            if res is None:
                # No more normal maps left (should only happen after collecting all 15)
                game_finished = True
                level_transitioning = False
                # NEW: show victory screen when no maps remain
                _on_game_win()
                return
        game_map, floor_choices = res
        level_number += 1  # increment visible level count (includes boss levels)
        is_boss_level = next_is_boss

        # Reset player state & spawn enemies
        x = offset_x + (WIDTH // 2) * TILE_SIZE
        y = offset_y + 1 * TILE_SIZE
        pressed_dirs.clear()
        is_dashing = False
        frame_index = 0
        enemies = []
        if is_boss_level:
            try:
                # CHANGED: spawn bosses per boss level
                enemies = []
                mid_x = offset_x + (WIDTH // 2) * TILE_SIZE
                mid_y = offset_y + (HEIGHT // 2) * TILE_SIZE
                if level_number == 18:
                    # NEW: spawn BOTH zombie and mage bosses on level 18
                    z_list = spawn_enemies(
                        game_map,
                        count=1,
                        tile_size=TILE_SIZE,
                        offset_x=offset_x,
                        offset_y=offset_y,
                        valid_tile=".",
                        enemy_size=64,
                        speed=1.2,
                        kind="zombie"
                    ) or []
                    m_list = spawn_enemies(
                        game_map,
                        count=1,
                        tile_size=TILE_SIZE,
                        offset_x=offset_x,
                        offset_y=offset_y,
                        valid_tile=".",
                        enemy_size=64,
                        speed=1.2,
                        kind="mage"
                    ) or []
                    enemies = z_list + m_list
                    # place them symmetrically around center and set boss stats
                    if len(enemies) >= 1:
                        e_z = enemies[0]
                        try:
                            e_z.x = mid_x - e_z.size / 2 - 2 * TILE_SIZE
                            e_z.y = mid_y - e_z.size / 2
                            e_z.is_boss = True
                            e_z.hp = 750
                            e_z.kind = "boss"
                            # make it a bit more threatening (dash like level 6 boss)
                            e_z.can_dash = True
                            e_z.dash_cooldown = 2000
                            e_z.dash_duration = 200
                            e_z.dash_force = 44.0
                            e_z.speed = max(getattr(e_z, "speed", 1.2) * 1.2, 1.5)
                            e_z.summon_cooldown = 3500
                            e_z.summon_count = 2
                            e_z.max_minions = 8
                        except Exception:
                            pass
                    if len(enemies) >= 2:
                        e_m = enemies[1]
                        try:
                            e_m.x = mid_x - e_m.size / 2 + 2 * TILE_SIZE
                            e_m.y = mid_y - e_m.size / 2
                            e_m.is_boss = True
                            e_m.hp = 750
                            e_m.kind = "boss"
                            # ensure mage abilities are enabled (similar to level 12 boss)
                            e_m.can_cast = True
                            e_m.cast_cooldown = 2400
                            e_m.projectile_speed = 3.6
                            e_m.volley_count = 7
                            e_m.volley_spread_deg = 80.0
                            e_m.volley_ring = True
                            e_m.volley_ring_count = 14
                            e_m.can_teleport = True
                            e_m.teleport_cooldown = 4500
                            e_m.summon_cooldown = 5000
                            e_m.summon_count = 1
                            e_m.max_minions = 6
                            e_m.summon_kind = "mage"
                            e_m.speed = max(getattr(e_m, "speed", 1.2) * 1.15, 1.4)
                        except Exception:
                            pass
                else:
                    # existing single-boss logic (Level 6: zombie, Level 12: mage)
                    boss_kind = "mage" if level_number == 12 else "zombie"
                    enemies = spawn_enemies(
                        game_map,
                        count=1,
                        tile_size=TILE_SIZE,
                        offset_x=offset_x,
                        offset_y=offset_y,
                        valid_tile=".",
                        enemy_size=64,
                        speed=1.2,
                        kind=boss_kind
                    )
                    if enemies:
                        # center boss (approximate)
                        e0 = enemies[0]
                        try:
                            e0.x = mid_x - e0.size / 2
                            e0.y = mid_y - e0.size / 2
                        except Exception:
                            pass
                        try:
                            if level_number == 6:
                                e0.is_boss = True
                                e0.hp = 100
                                e0.can_dash = True
                                e0.summon_cooldown = 3500
                                e0.summon_count = 2
                                e0.max_minions = 8
                                e0.speed = max(getattr(e0, "speed", 1.2) * 1.25, 1.6)
                                e0.dash_cooldown = 2000
                                e0.dash_speed = 44.0
                                e0.kind = "boss"
                            elif level_number == 12:
                                e0.is_boss = True
                                e0.kind = "boss"
                                e0.can_cast = True
                                e0.hp = 160
                                e0.speed = max(getattr(e0, "speed", 1.2) * 1.15, 1.4)
                                e0.cast_cooldown = 2400
                                e0.projectile_speed = 3.6
                                e0.volley_count = 7
                                e0.volley_spread_deg = 80.0
                                e0.volley_ring = True
                                e0.volley_ring_count = 14
                                e0.can_teleport = True
                                e0.teleport_cooldown = 4500
                                e0.summon_cooldown = 5000
                                e0.summon_count = 1
                                e0.max_minions = 6
                                e0.summon_kind = "mage"
                        except Exception:
                            pass
            except Exception:
                enemies = []
        else:
            enemies = spawn_enemies(game_map, count=enemy_count_for_level(level_number, is_boss_level), tile_size=TILE_SIZE, offset_x=offset_x, offset_y=offset_y, valid_tile=".", enemy_size=48, speed=1.5, kind="mix")
        # NEW: scale newly spawned enemies by (new) level_number
        _apply_level_scaling(enemies, level_number)
        spawn_grace_timer = 1500 + int(elapsed_here)
        # NEW: reset round-cleared gate for the new level
        round_cleared = False
        level_transitioning = False

    # --- DEATH PARTICLES SYSTEM ---
    # Each particle: {'x','y','vx','vy','size','color',(optional) 'life_ms'}
    death_particles = []

    def spawn_death_particles(enemy: Enemy, count: int = None):
        """Spawn pixel debris from an enemy's current sprite. If sprite pixels are transparent skip them."""
        # choose a surface to sample pixels from (prefer current facing frame)
        surf = None
        try:
            if enemy.sprites:
                if isinstance(enemy.sprites, dict):
                    frames = enemy.sprites.get(enemy.facing) or enemy.sprites.get("idle") or []
                else:
                    frames = list(enemy.sprites)
                if frames:
                    surf = frames[0]
        except Exception:
            surf = None
        # fallback small solid surface
        if surf is None:
            surf = pygame.Surface((enemy.size, enemy.size), pygame.SRCALPHA)
            surf.fill((180, 60, 60))

        surf_w, surf_h = surf.get_size()
        # number of particles proportional to enemy area (clamped)
        if count is None:
            count = max(8, min(40, (enemy.size * enemy.size) // 64))

        for _ in range(count):
            # pick a random pixel within sprite; skip transparent pixels up to a few tries
            col = None
            for _try in range(6):
                sx = random.randint(0, surf_w - 1)
                sy = random.randint(0, surf_h - 1)
                try:
                    c = surf.get_at((sx, sy))
                except Exception:
                    c = pygame.Color(200, 60, 60, 255)
                # skip fully transparent pixels
                if getattr(c, "a", 255) == 0:
                    continue
                # FORCE OPAQUE: ignore any source alpha, use full opacity
                col = (c.r, c.g, c.b, 255)
                break
            if col is None:
                col = (180, 60, 60, 255)

            # world position: enemy top-left + sampled pixel offset
            px = enemy.x + (sx if 'sx' in locals() else enemy.size//2)
            py = enemy.y + (sy if 'sy' in locals() else enemy.size//2)

            # initial velocity: scatter outward and upward a bit
            vx = random.uniform(-1.8, 1.8) * (1.0 + enemy.size / 48.0)
            vy = random.uniform(-3.5, -1.0) * (1.0 + enemy.size / 48.0)

            death_particles.append({
                'x': px,
                'y': py,
                'vx': vx,
                'vy': vy,
                'size': max(2, int(enemy.size * 0.12)),
                'color': col,
                'life': random.randint(900, 1800)  # ms before fade/remove (kept for potential logic)
            })

    def update_and_draw_particles(dt: int, surface: pygame.Surface):
        """Update death_particles physics and draw them. Particles fall under gravity and continue past the bottom of the screen until off-bound."""
        gravity = 0.9 * (dt / 16.0)
        screen_h = surface.get_height()
        # work on a copy so removals are safe
        for p in list(death_particles):
            # physics
            p['vy'] += gravity
            p['x'] += p['vx'] * (dt / 16.0)
            p['y'] += p['vy'] * (dt / 16.0)

            # NOTE: DO NOT settle at bottom — allow particles to continue falling off-screen.
            # lifetime (kept but not used for alpha fade)
            p['life'] -= dt

            # DRAW OPAQUE: use stored color but force alpha to fully opaque
            col = p['color'][:3] + (255,)
            try:
                rect = pygame.Rect(int(p['x']), int(p['y']), p['size'], p['size'])
                s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                s.fill(col)
                surface.blit(s, rect.topleft)
            except Exception:
                pass

            # remove when particle has gone off the bottom of the surface (plus a small margin)
            if p['y'] > screen_h + p['size'] + 50:
                try:
                    death_particles.remove(p)
                except Exception:
                    pass

    # --- END death particles ---

    # Player damage / invincibility / knockback state
    invincible_timer = 0                     # ms remaining of invulnerability after taking hit
    spawn_grace_timer = 1500                 # ms grace period on spawn / map change (1.5s yellow overlay)
    # REMOVED: chooser_elapsed_pending credit — no pre-round powerup picker anymore.

    invincible_duration = 1000    # 1 seconds invincibility after losing a heart (increased)
    player_kb_vx = 0.0
    player_kb_vy = 0.0
    player_kb_time = 0            # ms remaining for knockback
    player_kb_duration = 200      # duration of knockback in ms
    # short on-hit red tint for player (independent from full invincibility)
    player_flash_timer = 0
    player_flash_duration = 300   # ms red tint when damaged

    pressed_dirs = []
    last_direction = "down"
    frame_index = 0
    frame_timer = 0
    frame_delay = 120

    stamina = stamina_max
    is_dashing = False
    dash_timer = 0
    dash_dir = (0, 0)

    current_angle = 0.0
    player_center = (x + char_size // 2, y + char_size // 2)

    hearts = 3
    # set starting max hearts / XP multiplier by difficulty and initialize current hearts
    diff_map = {
        "easy":   (4, 0.75),
        "normal": (3, 1.0),
        "hard":   (1, 2.0)
    }
    max_hearts, xp_multiplier = diff_map.get(str(difficulty).lower(), (3, 1.0))
    # NEW: Life Armor grants +1 max heart
    if equipped_life:
        max_hearts += 1
    hearts = max_hearts
    # NEW: keep difficulty name for conditional scoring
    difficulty_name = str(difficulty).lower()
    # NEW: Regen Armor timers
    regen_interval_ms = 15000
    regen_timer_ms = 0
    # NEW: Thorns Armor damage (per hit to attacker)
    # (Was a flat 5; now it scales with +Damage powerups.)
    # Base retaliation (before powerups):
    base_thorns_damage = 5
    thorns_damage = base_thorns_damage

    # Helper to compute weapon's non‑powerup baseline (base weapon + upgrades + swiftness armor bonus)
    def _compute_weapon_base_damage():
        return (current_weapon.damage +
                upgrade_damage_bonus +
                (5 if equipped_swiftness else 0))

    # Track baseline so we can detect additive powerup bonus each frame
    baseline_weapon_damage_no_powerups = _compute_weapon_base_damage()

    heart_full = load_sprite("heart_1.png", size=48)
    heart_empty = load_sprite("heart_0.png", size=48)
    heart_spacing = 0
    on_trap_prev = False

    run = True
    # NEW: cheat sequence tracking to unlock Q insta-kill
    cheat_sequence = "descend"
    cheat_progress = 0
    cheat_unlocked = False

    # Floating damage indicators (use bundled font if available)
    dmg_indicators = []  # each: {'x','y','text','color','life','vy'}
    # NEW: score counter
    score = 0
    try:
        font_path = None
        for ext in ("ttf", "otf"):
            cand = asset_path("sprites", f"font.{ext}")
            if os.path.exists(cand):
                font_path = cand
                break
        dmg_font = pygame.font.Font(font_path, 22) if font_path else pygame.font.SysFont("arial", 22, bold=True)
        # NEW: level font (smaller)
        level_font = pygame.font.Font(font_path, 24) if font_path else pygame.font.SysFont("arial", 24, bold=True)
    except Exception:
        dmg_font = None
        try:
            level_font = pygame.font.SysFont("arial", 24, bold=True)
        except Exception:
            level_font = None
    while run:
        dt = clock.tick(60)
        # refresh armor flag from save in case player equipped it in shop before resuming
        try:
            _latest = save.load_player_data() or {}
            eq_arm = (_latest.get("equipped_armor") or "").strip()
            swiftness_outline = (eq_arm == "Swiftness Armor")
            tank_outline = (eq_arm == "Tank Armor")
            life_outline = (eq_arm == "Life Armor")
            regen_outline = (eq_arm == "Regen Armor")
            thorns_outline = (eq_arm == "Thorns Armor")
            # NEW: ensure thorns reflects accumulated damage powerups if armor equipped mid‑run
            if thorns_outline:
                thorns_damage = base_thorns_damage + damage_powerup_total
        except Exception:
            pass

        # decrement player invincibility & knockback timers
        if invincible_timer > 0:
            invincible_timer -= dt
            if invincible_timer < 0:
                invincible_timer = 0
        # decrement spawn grace timer (yellow overlay + damage immunity)
        if spawn_grace_timer > 0:
            spawn_grace_timer -= dt
            if spawn_grace_timer < 0:
                spawn_grace_timer = 0
        # decrement player flash timer for red tint
        if player_flash_timer > 0:
            player_flash_timer -= dt
            if player_flash_timer < 0:
                player_flash_timer = 0

        # Update trap timer
        trap_timer += dt
        if trap_timer >= trap_toggle_interval:
            trap_timer = 0
            trap_active = not trap_active

        # Timers update
        if attacking:
            attack_timer -= dt
            if attack_timer <= 0:
                attacking = False
                attack_timer = 0
        if cooldown_timer > 0:
            cooldown_timer -= dt
            if cooldown_timer < 0:
                cooldown_timer = 0
        # NEW: Regen Armor healing tick (only accumulate when missing hearts)
        if regen_outline:
            if hearts < max_hearts:
                regen_timer_ms += dt
                if regen_timer_ms >= regen_interval_ms:
                    hearts = min(max_hearts, hearts + 1)
                    regen_timer_ms = 0
            else:
                regen_timer_ms = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Show Game Over on hard window close and persist 50:1 conversion
                _on_game_over()
                return
            # Track movement key presses/releases to determine facing priority
            if event.type == pygame.KEYDOWN:
                # REMOVED: weapon switching via number keys (1-5)
                # if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                #     new_idx = event.key - pygame.K_1
                #     if new_idx in owned_weapon_indices and new_idx != current_weapon_index:
                #         load_weapon(new_idx)
                if event.key in key_to_dir:
                    d = key_to_dir[event.key]
                    if d in pressed_dirs:
                        pressed_dirs.remove(d)
                    pressed_dirs.append(d)
                # NEW: track cheat sequence 'descend' to unlock Q
                ch = getattr(event, 'unicode', '')
                if not cheat_unlocked and ch:
                    ch = ch.lower()
                    if ch == cheat_sequence[cheat_progress:cheat_progress+1]:
                        cheat_progress += 1
                        if cheat_progress == len(cheat_sequence):
                            cheat_unlocked = True
                            print("Cheat unlocked: Q will now clear all enemies.")
                    else:
                        cheat_progress = 1 if ch == cheat_sequence[0] else 0
            if event.type == pygame.KEYUP:
                if event.key in key_to_dir:
                    d = key_to_dir[event.key]
                    if d in pressed_dirs:
                        pressed_dirs.remove(d)

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # pause overlay
                try:
                    snapshot = win.copy()
                except Exception:
                    snapshot = None
                # Freeze grace timer while paused: measure paused duration and credit it back
                pause_start = pygame.time.get_ticks()
                res = pause.show_pause_overlay(snapshot, win)
                try:
                    paused_ms = max(0, pygame.time.get_ticks() - pause_start)
                    spawn_grace_timer += paused_ms
                except Exception:
                    pass
                if res and res[0] == "resume":
                    # simply continue
                    continue
                if res and res[0] == "options":
                    # open options, then go back to pause menu instead of resuming
                    while True:
                        try:
                            import menu  # ensure menu module is available before calling show_options
                            opt_start = pygame.time.get_ticks()
                            opt_res = menu.show_options(snapshot, win)
                            try:
                                paused_ms2 = max(0, pygame.time.get_ticks() - opt_start)
                                spawn_grace_timer += paused_ms2
                            except Exception:
                                pass
                            if opt_res and opt_res[0] == "resolution_changed":
                                new_size = opt_res[1]
                                pygame.display.set_mode(new_size)
                                screen_width, screen_height = win.get_size()
                                offset_x = (screen_width - WIDTH * TILE_SIZE) // 2
                                offset_y = (screen_height - HEIGHT * TILE_SIZE) // 2
                        except Exception:
                            pass
                        # after closing options, show the pause overlay again
                        pause_start2 = pygame.time.get_ticks()
                        res2 = pause.show_pause_overlay(snapshot, win)
                        try:
                            paused_ms3 = max(0, pygame.time.get_ticks() - pause_start2)
                            spawn_grace_timer += paused_ms3
                        except Exception:
                            pass
                        if res2 and res2[0] == "options":
                            # loop back into options again
                            continue
                        if res2 and res2[0] == "menu":
                            # quitting to menu -> Game Over + coin conversion (50:1)
                            _on_game_over()
                            return
                        # default: resume game
                        break
                    continue
                if res and res[0] == "menu":
                    # quitting to menu -> Game Over + coin conversion (50:1)
                    _on_game_over()
                    return

            # REPLACED: developer hotkey — insta-clear all enemies (now requires cheat unlocked)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q and cheat_unlocked:
                for e in enemies:
                    if getattr(e, "alive", False):
                        e.alive = False
                        try:
                            e._died_this_frame = True
                        except Exception:
                            pass
                        # clear active projectiles from casters
                        try:
                            if getattr(e, "projectiles", None) is not None:
                                e.projectiles.clear()
                        except Exception:
                            pass

            if event.type == pygame.KEYUP:
                if event.key in key_to_dir:
                    d = key_to_dir[event.key]
                    if d in pressed_dirs:
                        pressed_dirs.remove(d)

            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if not is_dashing and stamina >= 1.0:
                    # Determine dash direction from current key state; fallback to last_direction
                    keys = pygame.key.get_pressed()
                    dx_tmp, dy_tmp = 0, 0
                    if keys[pygame.K_a]:
                        dx_tmp -= 1
                    if keys[pygame.K_d]:
                        dx_tmp += 1
                    if keys[pygame.K_w]:
                        dy_tmp -= 1
                    if keys[pygame.K_s]:
                        dy_tmp += 1
                    if dx_tmp == 0 and dy_tmp == 0:
                        if last_direction == "left":
                            dx_tmp = -1
                        elif last_direction == "right":
                            dx_tmp = 1
                        elif last_direction == "up":
                            dy_tmp = -1
                        elif last_direction == "down":
                            dy_tmp = 1
                    if dx_tmp != 0 or dy_tmp != 0:
                        norm = math.hypot(dx_tmp, dy_tmp)
                        dx_tmp /= norm
                        dy_tmp /= norm
                        # Face the dash direction immediately
                        last_direction = dir_from_vector(dx_tmp, dy_tmp, last_direction)
                        dash_dir = (dx_tmp, dy_tmp)
                        is_dashing = True
                        dash_timer = dash_duration
                        stamina -= 1.0
                        try:
                            sounds.play_sfx('Dash')
                        except Exception:
                            pass

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not attacking and cooldown_timer <= 0:
                    attacking = True
                    attack_timer = attack_duration
                    cooldown_timer = attack_duration + attack_cooldown
                    mx, my = pygame.mouse.get_pos()
                    px = x + char_size // 2
                    py = y + char_size // 2
                    player_center = (px, py)
                    swing_start_angle = math.degrees(math.atan2(my - py, mx - px))
                    attack_hits.clear()
                    # NEW: spawn projectile (for weapons like The Descender)
                    if current_weapon.projectile_damage > 0 and current_projectile_img:
                        dxp = mx - px
                        dyp = my - py
                        dist = math.hypot(dxp, dyp) or 1.0
                        dxn = dxp / dist
                        dyn = dyp / dist
                        speed = current_weapon.projectile_speed  # pixels / second
                        proj_life = current_weapon.projectile_life_ms
                        # small forward offset so it doesn't instantly collide with player
                        start_offset = 28
                        sx = px + dxn * start_offset
                        sy = py + dyn * start_offset
                        player_projectiles.append({
                            'x': sx,
                            'y': sy,
                            'vx': dxn * speed,
                            'vy': dyn * speed,
                            'life': proj_life,
                            # CHANGED: include upgrade damage bonus for projectiles
                            'damage': current_weapon.projectile_damage + projectile_damage_bonus + projectile_upgrade_damage,
                            'img': current_projectile_img,
                            'radius': max(10, current_projectile_img.get_width() // 2)
                        })

        # --- APPLY PLAYER KNOCKBACK (if active) ---
        knocked = False
        if player_kb_time > 0:
            knocked = True
            frac = min(dt, player_kb_time) / float(max(1, player_kb_duration))
            dx_k = player_kb_vx * frac
            dy_k = player_kb_vy * frac
            new_x = x + dx_k
            new_y = y + dy_k
            try:
                if can_move(new_x, new_y, game_map, dashing=False):
                    x, y = new_x, new_y
                else:
                    if can_move(x + dx_k, y, game_map, dashing=False):
                        x += dx_k
                    elif can_move(x, y + dy_k, game_map, dashing=False):
                        y += dy_k
                    else:
                        player_kb_vx = player_kb_vy = 0.0
                        player_kb_time = 0
            except Exception:
                x, y = new_x, new_y
            player_kb_time -= dt
            if player_kb_time <= 0:
                player_kb_vx = player_kb_vy = 0.0
                player_kb_time = 0

        dx, dy = 0, 0
        if is_dashing:
            dx, dy = dash_dir
        else:
            keys = pygame.key.get_pressed()
            if knocked:
                dx = dy = 0
            else:
                # Use current key state for movement so walking doesn't depend on pressed_dirs
                if keys[pygame.K_a]:
                    dx -= 1
                if keys[pygame.K_d]:
                    dx += 1
                if keys[pygame.K_w]:
                    dy -= 1
                if keys[pygame.K_s]:
                    dy += 1
                if dx != 0 and dy != 0:
                    norm = math.sqrt(dx*dx + dy*dy)
                    dx /= norm
                    dy /= norm

        moving = dx != 0 or dy != 0

        # Update facing: prefer most-recent pressed direction if held; fallback to vector
        if not is_dashing:
            if pressed_dirs:
                last_direction = pressed_dirs[-1]
            elif moving:
                last_direction = dir_from_vector(dx, dy, last_direction)

        speed = vel
        if is_dashing:
            speed = dash_speed
            dash_timer -= dt
            if dash_timer <= 0:
                foot_width = char_size // 2
                foot_height = 10
                foot_x = x + (char_size - foot_width) // 2
                foot_y = y + char_size - foot_height
                foot_rect = pygame.Rect(foot_x, foot_y, foot_width, foot_height)
                for pxp, pyp in [
                    (foot_rect.left, foot_rect.bottom - 1),
                    (foot_rect.right - 1, foot_rect.bottom - 1),
                    (foot_rect.centerx, foot_rect.bottom - 1)
                ]:
                    tile_x = int((pxp - offset_x) // TILE_SIZE)
                    tile_y = int((pyp - offset_y) // TILE_SIZE)
                    if 0 <= tile_x < WIDTH and 0 <= tile_y < HEIGHT:
                        if game_map[tile_y][tile_x] == LAVA_TILE:
                            # death by lava
                            try: sounds.play_sfx('LavaDeath.mp3')
                            except Exception: pass
                            _on_player_death()
                            return
                is_dashing = False
                if pressed_dirs:
                    last_direction = pressed_dirs[-1]

        new_x = x + dx * speed
        new_y = y + dy * speed

        if can_move(new_x, new_y, game_map, is_dashing):
            x, y = new_x, new_y
        else:
            if can_move(x + dx * speed, y, game_map, is_dashing):
                x += dx * speed
            elif can_move(x, y + dy * speed, game_map, is_dashing):
                y += dy * speed

        # dash end / lava check: when dash_timer expires, validate player isn't standing on lava and stop dashing
        if is_dashing and dash_timer <= 0:
            foot_width = char_size // 2
            foot_height = 10
            foot_x = x + (char_size - foot_width) // 2
            foot_y = y + char_size - foot_height
            foot_rect = pygame.Rect(foot_x, foot_y, foot_width, foot_height)
            for pxp, pyp in [
                (foot_rect.left, foot_rect.bottom - 1),
                (foot_rect.right - 1, foot_rect.bottom - 1),
                (foot_rect.centerx, foot_rect.bottom - 1)
            ]:
                tile_x = int((pxp - offset_x) // TILE_SIZE)
                tile_y = int((pyp - offset_y) // TILE_SIZE)
                if 0 <= tile_x < WIDTH and 0 <= tile_y < HEIGHT:
                    if game_map[tile_y][tile_x] == LAVA_TILE:
                        # death by lava
                        try: sounds.play_sfx('LavaDeath.mp3')
                        except Exception: pass
                        _on_player_death()
                        return
            is_dashing = False
            if pressed_dirs:
                last_direction = pressed_dirs[-1]

        # Always check traps
        foot_width = char_size // 2
        foot_height = 10
        foot_x = x + (char_size - foot_width) // 2
        foot_y = y + char_size - foot_height
        foot_rect = pygame.Rect(foot_x, foot_y, foot_width, foot_height)

        on_trap_now = False
        for pxp, pyp in [
            (foot_rect.left, foot_rect.bottom - 1),
            (foot_rect.right - 1, foot_rect.bottom - 1),
            (foot_rect.centerx, foot_rect.bottom - 1)
        ]:
            tile_x = int((pxp - offset_x) // TILE_SIZE)
            tile_y = int((pyp - offset_y) // TILE_SIZE)
            if 0 <= tile_x < WIDTH and 0 <= tile_y < HEIGHT:
                if game_map[tile_y][tile_x] == TRAP_TILE and trap_active:
                    on_trap_now = True
                    break

        if on_trap_now and not on_trap_prev:
            # only apply trap damage if not in spawn grace
            if spawn_grace_timer <= 0:
                hearts -= 1
                invincible_timer = invincible_duration
                player_flash_timer = player_flash_duration
                # give player knockback & invincibility when hit by trap
                pcx = x + char_size / 2
                pcy = y + char_size / 2
                # reduced upward knockback
                player_kb_vx = 0.0
                player_kb_vy = -20.0
                player_kb_time = player_kb_duration
                if hearts <= 0:
                    try:
                        # play death sfx already handled elsewhere if needed
                        pass
                    except Exception:
                        pass
                    _on_player_death()
                    return

        on_trap_prev = on_trap_now

        # NEW: portal collision -> go to next level
        if portal_active and portal_rect and foot_rect.colliderect(portal_rect):
            portal_active = False
            try:
                sounds.play_sfx('SelectSound')
            except Exception:
                pass
            do_map_transition()
            # after calling transition we skip further checks this frame
            # (drawing below will reflect new map on next iteration)

        if stamina < stamina_max:
            stamina += stamina_regen_rate * (dt / 1000.0)
            if stamina > stamina_max:
                stamina = stamina_max

        if moving:
            frame_timer += dt
            if frame_timer >= frame_delay:
                frame_timer = 0
                frame_index = (frame_index + 1) % 3
        else:
            frame_index = 0

        angle = int(current_angle) // 3 * 3

        win.fill((0, 0, 0))
        draw_map(win, game_map, floor_choices, offset_x, offset_y, trap_active)
        # NEW: draw portal if active
        if portal_active and portal_rect:
            try:
                win.blit(portal_img, portal_rect.topleft)
            except Exception:
                pygame.draw.rect(win, (120, 0, 180), portal_rect)
        # NEW: draw score at top of screen (left-aligned to map)
        try:
            if level_font:
                sc = level_font.render(f"Score: {score}", True, (255, 255, 255))
                top_y = max(10, offset_y - 100)
                win.blit(sc, (offset_x, top_y))
        except Exception:
            pass
        draw_shadow(win, x, y, char_size, game_map, offset_x, offset_y)
        # draw/update death particle debris (map-grounded)
        update_and_draw_particles(dt, win)
        # Floating damage indicators: update and draw
        try:
            pruned = []
            for ind in dmg_indicators:
                ind['life'] -= dt
                ind['y'] += ind['vy'] * dt
                if ind['life'] > 0 and dmg_font is not None:
                    # fade alpha near the end
                    a = 255
                    if ind['life'] < 200:
                        a = max(0, int(255 * (ind['life'] / 200.0)))
                    # composite outlined text
                    outline_w = 2
                    base = dmg_font.render(ind['text'], True, ind['color'])
                    outline = dmg_font.render(ind['text'], True, (0, 0, 0))
                    w = base.get_width() + outline_w * 2
                    h = base.get_height() + outline_w * 2
                    comp = pygame.Surface((w, h), pygame.SRCALPHA)
                    for ox, oy in [(-outline_w, 0), (outline_w, 0), (0, -outline_w), (0, outline_w),
                                   (-outline_w, -outline_w), (outline_w, -outline_w), (-outline_w, outline_w), (outline_w, outline_w)]:
                        comp.blit(outline, (ox + outline_w, oy + outline_w))
                    comp.blit(base, (outline_w, outline_w))
                    if a < 255:
                        comp.set_alpha(a)
                    win.blit(comp, (int(ind['x'] - comp.get_width() / 2), int(ind['y'])))
                if ind['life'] > 0:
                    pruned.append(ind)
            dmg_indicators = pruned
        except Exception:
            pass

        def make_is_walkable(size):
            def is_walkable(new_x: float, new_y: float) -> bool:
                foot_width = int(size * 0.5)
                foot_height = 10
                foot_x = int(new_x + (size - foot_width) / 2)
                foot_y = int(new_y + size - foot_height)
                for pxp, pyp in [
                    (foot_x, foot_y + foot_height - 1),
                    (foot_x + foot_width - 1, foot_y + foot_height - 1),
                    (foot_x + foot_width // 2, foot_y + foot_height - 1)
                ]:
                    tile_x = int((pxp - offset_x) // TILE_SIZE)
                    tile_y = int((pyp - offset_y) // TILE_SIZE)
                    if tile_x < 0 or tile_x >= WIDTH or tile_y < 0 or tile_y >= HEIGHT:
                        return False
                    tile = game_map[tile_y][tile_x]
                    if tile in WALL_TILES:
                        return False
                    if tile == LAVA_TILE:
                        return False
                return True
            return is_walkable

        def on_trap(px: int, py: int) -> bool:
            tile_x = int((px - offset_x) // TILE_SIZE)
            tile_y = int((py - offset_y) // TILE_SIZE)
            if 0 <= tile_x < WIDTH and 0 <= tile_y < HEIGHT:
                return game_map[tile_y][tile_x] == TRAP_TILE and trap_active
            return False

        def is_lava(px: float, py: float) -> bool:
            tile_x = int((px - offset_x) // TILE_SIZE)
            tile_y = int((py - offset_y) // TILE_SIZE)
            if 0 <= tile_x < WIDTH and 0 <= tile_y < HEIGHT:
                return game_map[tile_y][tile_x] == LAVA_TILE
            return False

        # new: wall test used by enemy projectiles (True for wall tiles or out-of-bounds)
        def is_wall(px: float, py: float) -> bool:
            tile_x = int((px - offset_x) // TILE_SIZE)
            tile_y = int((py - offset_y) // TILE_SIZE)
            # treat out-of-bounds as a blocking wall so projectiles disappear there
            if tile_x < 0 or tile_x >= WIDTH or tile_y < 0 or tile_y >= HEIGHT:
                return True
            return game_map[tile_y][tile_x] in WALL_TILES

        # Update enemies
        for e in enemies:
            if e.alive:
                e.update(dt, player_center, make_is_walkable(e.size), on_trap, is_lava, is_wall)
            # --- Bleed processing (if any weapon applied bleed) ---
            if getattr(e, 'bleed_time', 0) > 0 and e.alive:
                e.bleed_time -= dt
                e.bleed_tick_timer = getattr(e, 'bleed_tick_timer', 0) - dt
                if e.bleed_tick_timer <= 0:
                    e.bleed_tick_timer = getattr(e, 'bleed_interval', 100)
                    # apply 1 damage (true damage style)
                    try:
                        # removed unexpected 'show_damage' kwarg so apply_damage actually runs
                        e.apply_damage(1, kb_x=0, kb_y=0, kb_force=0, kb_duration=0)
                    except Exception:
                        # fallback: prefer 'hp' over 'health'
                        try:
                            if hasattr(e, 'hp'):
                                e.hp -= 1
                            else:
                                e.health -= 1
                        except Exception:
                            pass

        # Collect damage events from enemies after update
        for e in enemies:
            try:
                for ev in e.drain_damage_events():
                    dmg_indicators.append({
                        'x': float(ev.get('x', getattr(e, 'x', 0) + getattr(e, 'size', 0) / 2)),
                        'y': float(ev.get('y', getattr(e, 'y', 0))),
                        'text': f"-{int(ev.get('amt', 0))}",
                        'color': tuple(ev.get('color', (200, 40, 40))),
                        'life': 600,
                        'vy': -0.04
                    })
            except Exception:
                pass
        # spawn particles for enemies that died THIS FRAME
        for e in enemies:
            if (not e.alive) and getattr(e, "_died_this_frame", False):
                # NEW: special reward for level 18 bosses
                if getattr(e, "is_boss", False) and level_number == 18:
                    try:
                        score += 5000
                    except Exception:
                        pass
                else:
                    try:
                        kind = getattr(e, "kind", "")
                        pts = { "ghost": 50, "mage": 150, "slime": 100, "zombie": 100 }.get(kind, 100)
                        lvl_mult = _level_points_multiplier(level_number)
                        score += int(pts * lvl_mult * xp_multiplier)
                    except Exception:
                        pass
                    # CHANGED: Boss bonus scales with difficulty (easy=.75, normal=1.0, hard=2.0)
                    try:
                        if getattr(e, "is_boss", False):
                            base = 1000

                            score += int(base * xp_multiplier)
                    except Exception:
                        pass
                try:
                    spawn_death_particles(e)
                except Exception:
                    pass
                try:
                    e._died_this_frame = False
                except Exception:
                    pass

        # NEW: auto transition when all enemies are dead
        if not level_transitioning:
            try:
                if enemies and all((not en.alive) for en in enemies):
                    if not round_cleared:
                        # show powerup picker immediately after last kill
                        try:
                            snap = win.copy()
                        except Exception:
                            snap = None
                        was_playing = False
                        try:
                            was_playing = pygame.mixer.music.get_busy()
                            if was_playing:
                                pygame.mixer.music.pause()
                        except Exception:
                            pass
                        try:
                            sounds.preload('LevelUp')
                            sounds.play_sfx('LevelUp')
                        except Exception:
                            pass
                        pick, _elapsed = (None, 0)
                        try:
                            pick, _elapsed = powerups.choose_powerup(snap, win)
                        except Exception:
                            pass
                        # resume gameplay bgm
                        try:
                            if was_playing:
                                pygame.mixer.music.stop()
                                globals()['_game_music_started'] = False
                                _start_play_music(mode)
                        except Exception:
                            pass
                        # apply powerup effects
                        if pick:
                            ptype = str(pick.get("type", "")).lower()
                            if ptype == "damage":
                                amt = int(pick.get("amount", 0))
                                sword_damage += amt
                                projectile_damage_bonus += amt
                                # NEW: track and apply to thorns
                                damage_powerup_total += amt
                                if thorns_outline:
                                    thorns_damage = base_thorns_damage + damage_powerup_total
                            elif ptype == "attackspeed":
                                try:
                                    amt = float(pick.get("amount", 0.2))
                                    attack_cooldown = int(max(0, attack_cooldown * (1.0 - amt)))
                                except Exception:
                                    pass
                            elif ptype == "dashspeed":
                                try:
                                    amt = float(pick.get("amount",  0.2))
                                    stamina_regen_rate = max(0.0, stamina_regen_rate * (1.0 + amt))
                                except Exception:
                                    pass
                            elif ptype == "speed":
                                try:
                                    walk_mult = float(pick.get("walk_mult", 0.25))
                                    dash_mult = float(pick.get("dash_mult", 0.20))
                                    vel = vel * (1.0 + walk_mult)
                                    dash_speed = dash_speed * (1.0 + dash_mult)
                                except Exception:
                                    pass
                            elif ptype == "shield":
                                shield_count += int(pick.get("amount", 1))
                            elif ptype == "poison":
                                try:
                                    poison_level += int(pick.get("amount", 1))
                                except Exception:
                                    poison_level += 1
                        # mark cleared and spawn portal at bottom-center
                        round_cleared = True
                        try:
                            cx = WIDTH // 2
                            ty = HEIGHT - 2  # prefer second-to-last row
                            # if target tile isn't walkable, search sideways on same row
                            placed = False
                            for dx_off in [0] + [i for k in range(1, WIDTH) for i in (-k, k)]:
                                tx = cx + dx_off
                                if 0 <= tx < WIDTH and 0 <= ty < HEIGHT and game_map[ty][tx] == '.':
                                    pxp = offset_x + tx * TILE_SIZE
                                    pyp = offset_y + ty * TILE_SIZE
                                    portal_rect = pygame.Rect(pxp, pyp, TILE_SIZE, TILE_SIZE)
                                    portal_active = True
                                    placed = True
                                    break
                            if not placed:
                                # fallback to helper scan from bottom up near center
                                pxp, pyp = _find_portal_spot(game_map)
                                portal_rect = pygame.Rect(pxp, pyp, TILE_SIZE, TILE_SIZE)
                                portal_active = True
                        except Exception:
                            # ultimate fallback: bottom-center pixel cell
                            pxp = offset_x + (WIDTH // 2) * TILE_SIZE
                            pyp = offset_y + max(0, HEIGHT - 2) * TILE_SIZE
                            portal_rect = pygame.Rect(pxp, pyp, TILE_SIZE, TILE_SIZE)
                            portal_active = True
            except Exception:
                pass

        if game_finished:
            return  # exit game loop

        # Draw enemies
        for e in enemies:
            if e.alive:
                e.draw(win)
                # Stun indicator overlay using stunned.png above enemy while stunned
                if getattr(e, 'stun_timer', 0) > 0 and stunned_img is not None:
                    try:
                        icon = stunned_img
                        cx = int(e.x + e.size/2)
                        top = int(e.y) - 10
                        rect = icon.get_rect(center=(cx, top))
                        win.blit(icon, rect.topleft)
                    except Exception:
                        pass

        # === PLAYER PROJECTILES (The Descender: sunball) ===
       
        if player_projectiles:
            updated_proj = []
            for p in player_projectiles:
                # advance
                p['life'] -= dt
                if p['life'] <= 0:
                    continue
                p['x'] += p['vx'] * (dt / 1000.0)
                p['y'] += p['vy'] * (dt / 1000.0)



                cx = p['x']
                cy = p['y']
                # only remove if out of bounds; allow passing through walls, traps, lava
                tile_x = int((cx - offset_x) // TILE_SIZE)
                tile_y = int((cy - offset_y) // TILE_SIZE)
                if tile_x < 0 or tile_x >= WIDTH or tile_y < 0 or tile_y >= HEIGHT:
                    continue
                # NOTE: no wall collision check here so sunball goes through walls/traps/lava
                # if game_map[tile_y][tile_x] in WALL_TILES:
                #     continue

                # collide with enemies
                hit_enemy = False
                for e in enemies:
                    if not getattr(e, "alive", True):
                        continue
                    ex = e.x + e.size / 2
                    ey = e.y + e.size / 2
                    dist = math.hypot(ex - cx, ey - cy)
                    if dist <= p['radius'] + e.size * 0.45:
                        # apply damage + modest knockback along projectile direction
                        try:
                            dir_len = math.hypot(p['vx'], p['vy']) or 1.0
                            nx = p['vx'] / dir_len
                            ny = p['vy'] / dir_len
                            e.apply_damage(p['damage'], kb_x=nx, kb_y=ny, kb_force=42, kb_duration=140)
                        except Exception:
                            # fallback: prefer 'hp' over 'health'
                            try:
                                if hasattr(e, 'hp'):
                                    e.hp -= p['damage']
                                else:
                                    e.health -= p['damage']
                            except Exception:
                                pass
                        # bleed / stun / poison inheritance (reuse current weapon effects)
                        if getattr(current_weapon, 'stun_ms', 0) > 0:
                            try: e.stun_timer = max(getattr(e, 'stun_timer', 0), current_weapon.stun_ms)
                            except Exception: pass
                        if getattr(current_weapon, 'bleed_duration_ms', 0) > 0 and getattr(current_weapon, 'bleed_interval_ms', 0) > 0:
                            try:
                                e.bleed_time = current_weapon.bleed_duration_ms
                                e.bleed_interval = current_weapon.bleed_interval_ms
                                e.bleed_tick_timer = 0
                            except Exception:
                                pass
                        if poison_level > 0:
                            try: e.apply_poison(poison_level)
                            except Exception: pass
                        try: sounds.play_sfx('HitSound')
                        except Exception: pass
                        hit_enemy = True
                        break
                if hit_enemy:
                    continue

                updated_proj.append(p)
            player_projectiles = updated_proj

        # Draw enemies
        for e in enemies:
            if e.alive:
                e.draw(win)
                # Stun indicator overlay using stunned.png above enemy while stunned
                if getattr(e, 'stun_timer', 0) > 0 and stunned_img is not None:
                    try:
                        icon = stunned_img
                        cx = int(e.x + e.size/2)
                        top = int(e.y) - 10
                        rect = icon.get_rect(center=(cx, top))
                        win.blit(icon, rect.topleft)
                    except Exception:
                        pass
        # Draw player projectiles after enemies (so they appear above ground but below player)
        if player_projectiles:
            for p in player_projectiles:
                img = p.get('img')
                if img:
                    rect = img.get_rect(center=(int(p['x']), int(p['y'])))
                    win.blit(img, rect.topleft)
                else:
                    pygame.draw.circle(win, (255, 200, 80), (int(p['x']), int(p['y'])), p['radius'])

        # --- NEW: enemy projectiles can hit the player (mage magic) --- retaliation for Thorns
        # use player_center computed from previous frame; handle once per frame
        # projectiles should not hurt the player while invincible, during spawn grace,
        # or while the player is actively dashing
        if invincible_timer <= 0 and spawn_grace_timer <= 0 and not is_dashing:
             proj_hit = False
             pcx, pcy = player_center
             for e in enemies:
                 if not e.alive or not getattr(e, "projectiles", None):
                     continue
                 for p in list(e.projectiles):
                    # projectile position
                    pxp = p.get('x', 0.0)
                    py_proj = p.get('y', 0.0)
                    dxp = pxp - pcx
                    dyp = py_proj - pcy
                    pdist = math.hypot(dxp, dyp)
                    # choose projectile radius from image if available
                    proj_radius = 12
                    proj_img = getattr(e, "projectile_img", None)
                    if proj_img:
                        proj_radius = max(8, proj_img.get_width() // 2)
                    else:
                        proj_radius = max(8, int(e.size * 0.12))
                    if pdist <= proj_radius:
                        # projectile hit player
                        hearts -= 1
                        try: sounds.play_sfx('Damaged')
                        except Exception: pass
                        # Thorns retaliation: damage the caster
                        if thorns_outline:
                            try:
                                ex = e.x + e.size / 2
                                ey = e.y + e.size / 2
                                rdx = (ex - pcx)
                                rdy = (ey - pcy)
                                nrm = math.hypot(rdx, rdy) or 1.0
                                e.apply_damage(thorns_damage, kb_x=rdx / nrm, kb_y=rdy / nrm, kb_force=26, kb_duration=140)
                            except Exception:
                                try:
                                    if hasattr(e, 'hp'):
                                        e.hp -= thorns_damage
                                    else:
                                        e.health -= thorns_damage
                                except Exception:
                                    pass
                        # knockback away from projectile direction
                        try:
                            vx = p.get('vx', 0.0)
                            vy = p.get('vy', 0.0)
                            kb_force = 30.0
                            player_kb_vx = vx * kb_force
                            player_kb_vy = vy * kb_force
                            player_kb_time = player_kb_duration
                        except Exception:
                            pass
                        # Tank Armor: stun the attacker when their projectile hits you
                        if tank_outline:
                            try:
                                e.stun_timer = max(getattr(e, 'stun_timer', 0), shield_stun_duration)
                            except Exception:
                                pass
                        invincible_timer = invincible_duration
                        player_flash_timer = player_flash_duration
                        # remove the projectile
                        try:
                            e.projectiles.remove(p)
                        except Exception:
                            pass
                        proj_hit = True
                        # check death
                        if hearts <= 0:
                            _on_player_death()
                            return
                        break
                 if proj_hit:
                    break

        # Enemy -> player collision (damage) --- add Thorns retaliation on contact
        # smaller hitbox for player (inset on all sides)
        inset = 10
        player_rect = pygame.Rect(int(x) + inset, int(y) + inset, char_size - inset*2, char_size - inset*2)
        if invincible_timer <= 0 and spawn_grace_timer <= 0 and not is_dashing:
             for e in enemies:
                 if not e.alive or getattr(e, "can_cast", False) or getattr(e, "stun_timer", 0) > 0:
                      continue
                 if e.rect().colliderect(player_rect):
                      hearts -= 1
                      try: sounds.play_sfx('Damaged')
                      except Exception: pass
                      ecx = e.x + e.size / 2
                      ecy = e.y + e.size / 2
                      pcx = x + char_size / 2
                      pcy = y + char_size / 2
                      kb_x = pcx - ecx
                      kb_y = pcy - ecy
                      norm = math.hypot(kb_x, kb_y)
                      if norm > 1e-6:
                         nx = kb_x / norm
                         ny = kb_y / norm
                      else:
                         nx, ny = 0.0, -1.0
                      # Thorns retaliation: damage the attacker (knock them away from player)
                      if thorns_outline:
                          try:
                              # ensure up-to-date scaling (redundant safeguard)
                              thorns_damage = base_thorns_damage + damage_powerup_total
                              e.apply_damage(thorns_damage, kb_x=-nx, kb_y=-ny, kb_force=26, kb_duration=140)
                          except Exception:
                              try:
                                  if hasattr(e, 'hp'):
                                      e.hp -= thorns_damage
                                  else:
                                      e.health -= thorns_damage
                              except Exception:
                                  pass
                      # Apply knockback to player only if NOT wearing Tank Armor
                      if not tank_outline:
                          kb_force = 20.0
                          player_kb_vx = nx * kb_force
                          player_kb_vy = ny * kb_force
                          player_kb_time = player_kb_duration
                      # Reflect knockback to attacker when wearing Tank Armor
                      if tank_outline:
                          try:
                              e.kb_vx = -nx * 10
                              e.kb_vy = -ny * 10
                              e.kb_time = max(getattr(e, 'kb_time', 0), 140)
                          except Exception:
                              pass
                          try:
                              e.stun_timer = max(getattr(e, 'stun_timer', 0), shield_stun_duration)
                          except Exception:
                              pass
                      invincible_timer = invincible_duration
                      player_flash_timer = player_flash_duration
                      try:
                          e.flash_timer = e.flash_duration
                      except Exception:
                          pass
                      if hearts <= 0:
                          _on_player_death()
                          return
                      break

        # Then draw character
        char = animations[last_direction][frame_index]
        # spawn grace: yellow overlay; damage flash: red overlay (spawn grace takes precedence)
        draw_char = char
        if spawn_grace_timer > 0:
            # When grace is nearly over, blink the yellow tint to signal impending end.
            try:
                blink_threshold = 800  # ms before end when blinking starts
                blink_period = 200     # ms blink interval
                if spawn_grace_timer <= blink_threshold:
                    blink_on = (pygame.time.get_ticks() // blink_period) % 2 == 0
                else:
                    blink_on = True
                if blink_on:
                    draw_char = char.copy()
                    # soft yellow tint
                    draw_char.fill((200, 180, 60, 0), special_flags=pygame.BLEND_RGBA_ADD)
                else:
                    draw_char = char
            except Exception:
                draw_char = char
        elif player_flash_timer > 0:
            try:
                draw_char = char.copy()
                draw_char.fill((180, 40, 40, 0), special_flags=pygame.BLEND_RGBA_ADD)
            except Exception:
                draw_char = char
        win.blit(draw_char, (x, y))
        # NEW: outlines for equipped armors using mask edges (no filled circle)
        try:
            m_draw = pygame.mask.from_surface(draw_char)
        except Exception:
            m_draw = None
        if swiftness_outline and m_draw:
            try:
                pts = m_draw.outline()
                if pts and len(pts) >= 3:
                    pts_t = [(x + p[0], y + p[1]) for p in pts]
                    pygame.draw.polygon(win, (255, 220, 40), pts_t, 3)
            except Exception:
                pass
        if tank_outline and m_draw:
            try:
                pts = m_draw.outline()
                if pts and len(pts) >= 3:
                    pts_t = [(x + p[0], y + p[1]) for p in pts]
                    pygame.draw.polygon(win, (245, 245, 245), pts_t, 3)
            except Exception:
                pass
        # NEW: Life Armor red outline
        if life_outline and m_draw:
            try:
                pts = m_draw.outline()
                if pts and len(pts) >= 3:
                    pts_t = [(x + p[0], y + p[1]) for p in pts]
                    pygame.draw.polygon(win, (220, 60, 60), pts_t, 3)
            except Exception:
                pass
        # NEW: Regen Armor blue outline
        if regen_outline and m_draw:
            try:
                pts = m_draw.outline()
                if pts and len(pts) >= 3:
                    pts_t = [(x + p[0], y + p[1]) for p in pts]
                    pygame.draw.polygon(win, (80, 160, 255), pts_t, 3)
            except Exception:
                pass
        # NEW: Thorns Armor green outline
        if thorns_outline and m_draw:
            try:
                pts = m_draw.outline()
                if pts and len(pts) >= 3:
                    pts_t = [(x + p[0], y + p[1]) for p in pts]
                    pygame.draw.polygon(win, (60, 200, 80), pts_t, 3)
            except Exception:
                pass
        # Update player_center
        char_rect = char.get_rect(topleft=(x, y))
        player_center = char_rect.center

        # Crosshair
        draw_crosshair(win, player_center)

        # HUD: stamina bars
        bar_x = offset_x
        bar_y = offset_y - 40
        BAR_W, BAR_H = 60, 20
        spacing = 10
        for i in range(3):
            x_pos = bar_x + i * (BAR_W + spacing)
            y_pos = bar_y
            pygame.draw.rect(win, (128, 128, 128), (x_pos, y_pos, BAR_W, BAR_H))
            fill = min(1.0, max(0.0, stamina - i))
            if fill >  0:
                fill_w = int(BAR_W * fill)
                pygame.draw.rect(win, (225, 225, 225), (x_pos, y_pos, fill_w, BAR_H))
        # Attack cooldown bar
        bar_w, bar_h = 100, 12
        bar_x = offset_x
        bar_y = offset_y - 60
        pygame.draw.rect(win, (100, 100, 100), (bar_x, bar_y, bar_w, bar_h))  # bg
        if cooldown_timer > 0:
           
            ratio = 1 - (cooldown_timer / (attack_duration + attack_cooldown))
            fill_w = int(bar_w * ratio)
            pygame.draw.rect(win, (255, 0, 0), (bar_x, bar_y, fill_w, bar_h))
        else:
            pygame.draw.rect(win, (0, 200, 0), (bar_x, bar_y, bar_w, bar_h))  # ready

        # Attack drawing and hit detection
        if attacking:
            px, py = player_center
            progress = 1 - (attack_timer / attack_duration)  # 0 → 1
            current_angle = swing_start_angle - swing_arc/2 + swing_arc * progress

            # --- Dagger (arc=0) uses a thrust animation: radius grows with progress ---
            if swing_arc == 0:
                # Ease-out thrust (fast out, tiny retract at very end)
                thrust_out = min(1.0, progress * 1.15)
                ease = 1 - (1 - thrust_out) * (1 - thrust_out)
                max_len = 68
                base_len = 12
                current_len = base_len + ease * (max_len - base_len)
                # slight retract during last  10% for visual snap
                if progress > 0.9:
                    retract = (progress - 0.9) / 0.1
                    current_len -= retract * 10

                # position the sword image along the thrust direction
                dx_dir = math.cos(math.radians(swing_start_angle))
                dy_dir = math.sin(math.radians(swing_start_angle))
                sword_center_x = px + current_len * dx_dir
                sword_center_y = py + current_len * dy_dir
            else:
                radius = 50
                sword_center_x = px + radius * math.cos(math.radians(current_angle))
                sword_center_y = py + radius * math.sin(math.radians(current_angle))

            rotated_sword = pygame.transform.rotate(sword_img, - (swing_start_angle if swing_arc == 0 else current_angle))
            rect = rotated_sword.get_rect(center=(sword_center_x, sword_center_y))
            win.blit(rotated_sword, rect.topleft)

            # Hit detection
            sword_reach = 64
            if swing_arc == 0:
                # REVISED: segment-vs-circle test for thrust, with LOS and effects; defines thickness
                dx_dir = math.cos(math.radians(swing_start_angle))
                dy_dir = math.sin(math.radians(swing_start_angle))
                # recompute current_len to match rendering above
                thrust_out = min(1.0, progress * 1.15)
                ease = 1 - (1 - thrust_out) * (1 - thrust_out)
                max_len = 68
                base_len = 12

                current_len = base_len + ease * (max_len - base_len)
                if progress > 0.9:
                    retract = (progress - 0.9) / 0.1
                    current_len -= retract * 10

                thickness = 12  # half-width of thrust "ray" to allow forgiving hits

                for e in enemies:
                    if not e.alive:
                        continue
                    eid = id(e)
                    if eid in attack_hits:
                        continue

                    ecx = e.x + e.size / 2
                    ecy = e.y + e.size / 2
                    # vector from player to enemy center
                    vx = ecx - px
                    vy = ecy - py
                    # projection length of enemy vector onto thrust direction
                    proj = vx * dx_dir + vy * dy_dir
                    # if behind the player or beyond thrust tip (plus small radius), skip
                    if proj < 0 or proj > current_len + e.size * 0.35:
                        continue
                    # perpendicular distance from line to enemy center
                    perp_x = vx - proj * dx_dir
                    perp_y = vy - proj * dy_dir
                    perp_dist = math.hypot(perp_x, perp_y)
                    if perp_dist <= thickness + e.size * 0.30:
                        # simple LOS for non-flying enemies
                        los_blocked = False
                        if not getattr(e, 'can_fly', False):
                            samples = int(max(1, proj // 12))
                            for s in range(1, samples + 1):
                                sx = px + dx_dir * (proj * s / samples)
                                sy = py + dy_dir * (proj * s / samples)
                                tx = int((sx - offset_x) // TILE_SIZE)
                                ty = int((sy - offset_y) // TILE_SIZE)
                                if tx < 0 or tx >= WIDTH or ty < 0 or ty >= HEIGHT or game_map[ty][tx] in WALL_TILES:
                                    los_blocked = True
                                    break
                        if los_blocked:
                            continue

                        # apply damage and effects
                        e.apply_damage(sword_damage, kb_x=dx_dir, kb_y=dy_dir, kb_force=38, kb_duration=110)
                        if getattr(current_weapon, 'stun_ms', 0) > 0:
                            try:
                                e.stun_timer = max(getattr(e, 'stun_timer', 0), current_weapon.stun_ms)
                            except Exception:
                                pass
                        if getattr(current_weapon, 'bleed_duration_ms', 0) > 0 and getattr(current_weapon, 'bleed_interval_ms', 0) > 0:
                            try:
                                e.bleed_time = current_weapon.bleed_duration_ms
                                e.bleed_interval = current_weapon.bleed_interval_ms
                                e.bleed_tick_timer = 0
                            except Exception:
                                pass
                        if poison_level > 0:
                            try:
                                e.apply_poison(poison_level)
                            except Exception:
                                pass
                        try:
                            sounds.play_sfx('HitSound')
                        except Exception:
                            pass
                        attack_hits.add(eid)
            else:
                for e in enemies:
                    if not e.alive:
                        continue
                    eid = id(e)
                    if eid in attack_hits:
                        continue
                    ecx = e.x + e.size / 2
                    ecy = e.y + e.size / 2
                    vx = ecx - px
                    vy = ecy - py
                    dist = math.hypot(vx, vy)
                    if dist > sword_reach + (e.size / 2):
                        continue
                    ang = math.degrees(math.atan2(vy, vx))
                    diff = (ang - current_angle + 180) % 360 - 180
                    if abs(diff) <= (swing_arc / 2):
                        los_clear = True
                        if not getattr(e, 'can_fly', False):
                            if dist > 1e-4:
                               
                                dirx = vx / dist
                                diry = vy / dist
                                step = 8
                                steps = max(1, int(dist // step))
                                for s in range(1, steps + 1):
                                    sx = px + dirx * (s * step)
                                    sy = py + diry * (s * step)
                                    if math.hypot(ecx - sx, ecy - sy) <= (e.size * 0.6):
                                        break
                                    tx = int((sx - offset_x) // TILE_SIZE)
                                    ty = int((sy - offset_y) // TILE_SIZE)
                                    if tx < 0 or tx >= WIDTH or ty < 0 or ty >= HEIGHT:
                                        los_clear = False; break
                                    if game_map[ty][tx] in WALL_TILES:
                                        los_clear = False; break
                        if not los_clear:
                            continue
                        e.apply_damage(sword_damage, kb_x=vx, kb_y=vy, kb_force=48, kb_duration=160)
                        if getattr(current_weapon, 'stun_ms', 0) > 0:
                            try: e.stun_timer = max(getattr(e, 'stun_timer', 0), current_weapon.stun_ms)
                            except Exception: pass
                        # Apply bleed if weapon has bleed
                        if getattr(current_weapon, 'bleed_duration_ms', 0) > 0 and getattr(current_weapon, 'bleed_interval_ms', 0) > 0:
                            try:
                                e.bleed_time = current_weapon.bleed_duration_ms
                                e.bleed_interval = current_weapon.bleed_interval_ms
                                e.bleed_tick_timer = 0
                            except Exception:
                                pass
                        if poison_level > 0:
                            try: e.apply_poison(poison_level)
                            except Exception: pass
                        try: sounds.play_sfx('HitSound')
                        except Exception: pass
                        attack_hits.add(eid)

            # Projectile break logic unchanged below
            # --- New: allow sword to break mage projectiles ---
            # check every enemy projectile and remove if within swing arc+reach
            proj_reach = 48  # slightly shorter reach for projectiles
            for e in enemies:
                if not e.alive or not getattr(e, "projectiles", None):
                    continue
                # iterate copy because we may remove entries
                for p in list(e.projectiles):
                    pxp = p['x']
                    pyp = p['y']
                    # dagger (arc==0): use thrust segment intersection instead of arc-angle gating
                    if swing_arc == 0:
                        # thrust direction and current thrust length (match rendering logic above)
                        dx_dir = math.cos(math.radians(swing_start_angle))
                        dy_dir = math.sin(math.radians(swing_start_angle))
                        thrust_out = min(1.0, progress * 1.15)
                        ease = 1 - (1 - thrust_out) * (1 - thrust_out)
                        max_len = 68
                        base_len = 12
                        current_len_seg = base_len + ease * (max_len - base_len)
                        if progress > 0.9:
                            retract = (progress - 0.9) / 0.1
                            current_len_seg -= retract * 10
                        # projectile radius from image/size
                        proj_img = getattr(e, "projectile_img", None)
                        proj_radius = max(8, proj_img.get_width() // 2) if proj_img else max(8, int(e.size * 0.12))
                        # segment-vs-point distance with radius
                        vxp = pxp - px
                        vyp = pyp - py
                        proj_on = vxp * dx_dir + vyp * dy_dir
                        if proj_on < 0 or proj_on > (current_len_seg + proj_radius + 6):
                            continue
                        perp_x = vxp - proj_on * dx_dir
                        perp_y = vyp - proj_on * dy_dir
                        perp_dist = math.hypot(perp_x, perp_y)
                        thickness = 12  # half-width of the deflect "ray"
                        if perp_dist <= (thickness + proj_radius):
                            try:
                                e.projectiles.remove(p)
                            except Exception:
                                pass
                        continue  # handled thrust case
                    vxp = pxp - px
                    vyp = pyp - py
                    pdist = math.hypot(vxp, vyp)
                    if pdist > proj_reach + max(6, e.size * 0.1):
                        continue
                    pang = math.degrees(math.atan2(vyp, vxp))
                    pdiff = (pang - current_angle + 180) % 360 - 180
                    if abs(pdiff) <= (swing_arc / 2):
                        # destroy the projectile (it "breaks")
                        try:
                            e.projectiles.remove(p)
                        except Exception:
                            pass
                        # (no enemy flash here so mages don't turn red when their orb is broken)

        # Draw hearts using the configured max_hearts for the chosen difficulty
        total_hearts = max_hearts

        heart_w = heart_full.get_width()
        heart_h = heart_full.get_height()
        margin = 0
        start_x = offset_x + WIDTH * TILE_SIZE - (total_hearts * heart_w) - margin
        heart_y = bar_y + (bar_h - heart_h) // 2
        # NEW: draw Level directly above the hearts (centered over the heart row)
        try:
            if level_font and level_number > 0:
                if not is_endless:
                    lvl_surf = level_font.render(f"Level {level_number}", True, (255, 255, 255))
                else:
                    # Endless: show a static label (no level number)
                    lvl_surf = level_font.render("Endless", True, (255, 255, 255))
                hearts_w = total_hearts * heart_w + max(0, total_hearts - 1) * heart_spacing
                lvl_x = start_x + (hearts_w - lvl_surf.get_width()) // 2
                lvl_y = heart_y - lvl_surf.get_height() - 6
                win.blit(lvl_surf, (lvl_x, lvl_y))
        except Exception:
            pass
        for i in range(total_hearts):
            hx = start_x + i * (heart_w + heart_spacing)
            img = heart_full if i < hearts else heart_empty
            win.blit(img, (hx, heart_y))

        # --- SHIELD LOGIC: update shield angle ---
        if shield_count > 0:
            shield_angle = (shield_angle + 3 * (dt / 1000.0)) % (2 * math.pi)  # Slower rotation: 0.5 radians per second

        # --- DRAW SHIELD(S) ---
        if shield_count > 0:
            for i in range(shield_count):
                angle = shield_angle + (2 * math.pi * i / shield_count)
                px, py = player_center
                sx = int(px + shield_radius * math.cos(angle) - shield_img.get_width() // 2)
                sy = int(py + shield_radius * math.sin(angle) - shield_img.get_height() // 2)
                win.blit(shield_img, (sx, sy))

        # --- SHIELD COLLISION WITH ENEMIES ---
        if shield_count > 0:
            for enemy in enemies:
                if not getattr(enemy, "alive", True):
                    continue
                ex, ey = enemy.x + enemy.size // 2, enemy.y + enemy.size // 2
                for i in range(shield_count):
                    angle = shield_angle + (2 * math.pi * i / shield_count)
                    px, py = player_center
                    sx = px + shield_radius * math.cos(angle)
                    sy = py + shield_radius * math.sin(angle)
                    dist = math.hypot(ex - sx, ey - sy)
                    if dist < (enemy.size // 2 + shield_img.get_width() // 2):
                        if not hasattr(enemy, "stun_timer") or enemy.stun_timer <= 0:
                            enemy.stun_timer = shield_stun_duration
                        dx = ex - sx
                        dy = ey - sy
                        norm = math.hypot(dx, dy)
                        if norm > 1e-3:
                            enemy.kb_vx = (dx / norm) * 8
                            enemy.kb_vy = (dy / norm) * 8
                            enemy.kb_time = 120

        # --- SHIELD COLLISION WITH PROJECTILES ---
        for enemy in enemies:
            if hasattr(enemy, "projectiles"):
                for proj in list(enemy.projectiles):
                    px_proj = proj.get("x", 0)

                    py_proj = proj.get("y", 0)
                    for i in range(shield_count):
                        angle = shield_angle + (2 * math.pi * i / shield_count)
                        px, py = player_center
                        sx = px + shield_radius * math.cos(angle)
                        sy = py + shield_radius * math.sin(angle)
                        dist = math.hypot(px_proj - sx, py_proj - sy)
                        if dist < (shield_img.get_width() // 2 + 8):
                            enemy.projectiles.remove(proj)
                            break

        pygame.display.update()
        
# ======================
# START GAME
# ======================
if __name__ == "__main__":
    # show the menu first; the menu will call main.run_game(SCREEN) when PLAY is pressed
    import menu
    menu.run_menu()