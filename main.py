import pygame
import sys
import math
import os
import random
from pathlib import Path
from enemies import spawn_enemies, Enemy  # added: import enemy helpers
import pause  # NEW: pause + death screens
import powerups  # NEW: powerup selection UI

BASE_DIR = Path(__file__).parent
def asset_path(*parts):
    return str(BASE_DIR.joinpath(*parts))

# ======================
# GAME LOOP
# ======================
def run_game(screen=None, difficulty: str = "normal"):
    """Run the game loop. If `screen` (a pygame Surface / display) is provided the game will use it
       instead of creating a new fullscreen window — this allows returning to the menu cleanly."""
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
    
    # Sword sprite
    sword_img = load_sprite("sword.png", size=48)
    attack_duration = 250  # ms swing
    attack_cooldown = 300  # ms cooldown after swing
    attacking = False
    attack_timer = 0
    cooldown_timer = 0
    swing_start_angle = 0
    swing_arc = 120  # degrees of swing
    sword_damage = 5
    attack_hits = set()  # track enemies hit this swing (store id(enemy))

    # Trap sprites
    trap_off_img = load_sprite("trap_off.png")
    trap_on_img = load_sprite("trap_on.png")
    trap_toggle_interval = 1500  # ms (1.5s toggle)
    trap_timer = 0
    trap_active = False

    FLOOR_SPRITES = [
        load_sprite("floor_1.png"),
        load_sprite("floor_2.png"),
        load_sprite("floor_3.png"),
        load_sprite("floor_4.png"),
        load_sprite("floor_5.png"),
        load_sprite("floor_6.png")
    ]

    def pick_map():
        game_map = random.choice(MAPS)
        floor_choices = [[None for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if game_map[y][x] == ".":
                    floor_choices[y][x] = random.choice(FLOOR_SPRITES)
        return game_map, floor_choices

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
    vel = 4
    dash_speed = 16
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

    game_map, floor_choices = pick_map()
    screen_width, screen_height = win.get_size()
    offset_x = (screen_width - WIDTH * TILE_SIZE) // 2
    offset_y = (screen_height - HEIGHT * TILE_SIZE) // 2

    x = offset_x + (WIDTH // 2) * TILE_SIZE
    y = offset_y + 1 * TILE_SIZE

    # --- SHOW POWERUP SELECTION BEFORE THE ROUND STARTS ---
    # record any chooser elapsed time so we can restore spawn grace later when it's initialized
    chooser_elapsed_pending = 0
    try:
        snap = win.copy()
    except Exception:
        snap = None
    try:
        pick, elapsed_ms = powerups.choose_powerup(snap, win)
        chooser_elapsed_pending = int(elapsed_ms or 0)
        # apply powerup effects
        if pick:
            ptype = str(pick.get("type", "")).lower()
            if ptype == "damage":
                sword_damage += int(pick.get("amount", 0))
            elif ptype == "attackspeed":
                try:
                    amt = float(pick.get("amount", 0.2))
                    # reduce attack cooldown by percentage (e.g. 0.2 -> 20%)
                    attack_cooldown = int(max(0, attack_cooldown * (1.0 - amt)))
                except Exception:
                    pass
            elif ptype == "dashspeed":
                try:
                    amt = float(pick.get("amount", 0.2))
                    # reduce dash cooldown (time to recover stamina) by `amt` percent.
                    # stamina_regen_rate is in units per second; to shorten time by amt, multiply by 1/(1-amt).
                    if stamina_regen_rate > 0:
                        stamina_regen_rate = stamina_regen_rate * (1.0 / (1.0 - amt))
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
    except Exception:
        chooser_elapsed_pending = 0

    # spawn enemies
    enemies = spawn_enemies(game_map, count=6, tile_size=TILE_SIZE, offset_x=offset_x, offset_y=offset_y, valid_tile=".", enemy_size=48, speed=1.5, kind="mix")

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
    # If the chooser ran before this point, add back the time it consumed so grace isn't reduced
    try:
        spawn_grace_timer += int(chooser_elapsed_pending or 0)
    except Exception:
        pass
    chooser_elapsed_pending = 0

    invincible_duration = 2000    # 2 seconds invincibility after losing a heart (increased)
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
    hearts = max_hearts

    heart_full = load_sprite("heart_1.png", size=48)
    heart_empty = load_sprite("heart_0.png", size=48)
    heart_spacing = 0
    on_trap_prev = False

    run = True
    while run:
        dt = clock.tick(60)

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

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # pause overlay
                try:
                    snapshot = win.copy()
                except Exception:
                    snapshot = None
                res = pause.show_pause_overlay(snapshot, win)
                if res and res[0] == "resume":
                    # simply continue
                    continue
                if res and res[0] == "options":
                    # lazy import menu to open options UI
                    try:
                        import menu
                        opt_res = menu.show_options(snapshot, win)
                        if opt_res and opt_res[0] == "resolution_changed":
                            new_size = opt_res[1]
                            pygame.display.set_mode(new_size)
                            screen_width, screen_height = win.get_size()
                            offset_x = (screen_width - WIDTH * TILE_SIZE) // 2
                            offset_y = (screen_height - HEIGHT * TILE_SIZE) // 2
                    except Exception:
                        pass
                    continue
                if res and res[0] == "menu":
                    return

            if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                game_map, floor_choices = pick_map()
                x = offset_x + (WIDTH // 2) * TILE_SIZE
                y = offset_y + 1 * TILE_SIZE
                pressed_dirs.clear()
                is_dashing = False
                frame_index = 0
                # --- SHOW POWERUP SELECTION AGAIN ON MAP CHANGE ---
                try:
                    snap = win.copy()
                except Exception:
                    snap = None
                elapsed_here = 0
                try:
                    pick, elapsed_here = powerups.choose_powerup(snap, win)
                    elapsed_here = int(elapsed_here or 0)
                    # apply powerup effects
                    if pick:
                        ptype = str(pick.get("type", "")).lower()
                        if ptype == "damage":
                            sword_damage += int(pick.get("amount", 0))
                        elif ptype == "attackspeed":
                            try:
                                amt = float(pick.get("amount", 0.2))
                                attack_cooldown = int(max(0, attack_cooldown * (1.0 - amt)))
                            except Exception:
                                pass
                        elif ptype == "dashspeed":
                            try:
                                amt = float(pick.get("amount", 0.2))
                                if stamina_regen_rate > 0:
                                    stamina_regen_rate = stamina_regen_rate * (1.0 / (1.0 - amt))
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
                except Exception:
                    elapsed_here = 0
                enemies = spawn_enemies(game_map, count=6, tile_size=TILE_SIZE, offset_x=offset_x, offset_y=offset_y, valid_tile=".", enemy_size=48, speed=1.5, kind="mix")
                # grant temporary grace period after respawn / map change (1.5s) and account for chooser time
                spawn_grace_timer = 1500 + elapsed_here

            if event.type == pygame.KEYDOWN and event.key in key_to_dir:
                d = key_to_dir[event.key]
                if d not in pressed_dirs:
                    pressed_dirs.append(d)
                if not is_dashing:
                    last_direction = pressed_dirs[-1]

            if event.type == pygame.KEYUP and event.key in key_to_dir:
                d = key_to_dir[event.key]
                if d in pressed_dirs:
                    pressed_dirs.remove(d)
                if not is_dashing:
                    if pressed_dirs:
                        last_direction = pressed_dirs[-1]
                    else:
                        frame_index = 0

            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if not is_dashing and stamina >= 1.0 and pressed_dirs:
                    is_dashing = True
                    dash_timer = dash_duration
                    stamina -= 1.0
                    dx_tmp, dy_tmp = 0, 0
                    if "left" in pressed_dirs: dx_tmp -= 1
                    if "right" in pressed_dirs: dx_tmp += 1
                    if "up" in pressed_dirs: dy_tmp -= 1
                    if "down" in pressed_dirs: dy_tmp += 1
                    if dx_tmp != 0 and dy_tmp != 0:
                        norm = math.sqrt(dx_tmp*dx_tmp + dy_tmp*dy_tmp)
                        dx_tmp /= norm
                        dy_tmp /= norm
                    dash_dir = (dx_tmp, dy_tmp)

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
                if "left" in pressed_dirs and keys[pygame.K_a]:
                    dx -= 1
                if "right" in pressed_dirs and keys[pygame.K_d]:
                    dx += 1
                if "up" in pressed_dirs and keys[pygame.K_w]:
                    dy -= 1
                if "down" in pressed_dirs and keys[pygame.K_s]:
                    dy += 1
                if dx != 0 and dy != 0:
                    norm = math.sqrt(dx*dx + dy*dy)
                    dx /= norm
                    dy /= norm

        moving = dx != 0 or dy != 0

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
                            try:
                                pause.show_death_screen(win)
                            except Exception:
                                pass
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
                        try:
                            pause.show_death_screen(win)
                        except Exception:
                            pass
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
                        pause.show_death_screen(win)
                    except Exception:
                        pass
                    return

        on_trap_prev = on_trap_now

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
        draw_shadow(win, x, y, char_size, game_map, offset_x, offset_y)
        # draw/update death particle debris (map-grounded)
        update_and_draw_particles(dt, win)

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
                # pass callbacks; per-enemy view logic lives inside Enemy.update
                e.update(dt, player_center, make_is_walkable(e.size), on_trap, is_lava, is_wall)
        # spawn particles for enemies that died THIS FRAME
        for e in enemies:
            if (not e.alive) and getattr(e, "_died_this_frame", False):
                try:
                    spawn_death_particles(e)
                except Exception:
                    pass
                # clear the marker so we only spawn once
                try:
                    e._died_this_frame = False
                except Exception:
                    pass

        # Draw enemies
        for e in enemies:
            if e.alive:
                e.draw(win)

        # --- NEW: enemy projectiles can hit the player (mage magic) ---
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
                    pyp = p.get('y', 0.0)
                    dxp = pxp - pcx
                    dyp = pyp - pcy
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
                            try:
                                pause.show_death_screen(win)
                            except Exception:
                                pass
                            return
                        break
                 if proj_hit:
                    break

        # Enemy -> player collision (damage)
        # smaller hitbox for player (inset on all sides)
        inset = 10
        player_rect = pygame.Rect(int(x) + inset, int(y) + inset, char_size - inset*2, char_size - inset*2)
        # direct enemy collision damage should also not apply while dashing
        if invincible_timer <= 0 and spawn_grace_timer <= 0 and not is_dashing:
             for e in enemies:
                 # skip dead enemies and skip direct contact damage from mages (they damage via projectiles)
                 if not e.alive or getattr(e, "can_cast", False):
                      continue
                 if e.rect().colliderect(player_rect):
                      hearts -= 1
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
                      kb_force = 20.0   # greatly reduced knockback strength
                      player_kb_vx = nx * kb_force
                      player_kb_vy = ny * kb_force
                      player_kb_time = player_kb_duration
                      invincible_timer = invincible_duration
                      # flash player and enemy briefly
                      player_flash_timer = player_flash_duration
                      try:
                          e.flash_timer = e.flash_duration
                      except Exception:
                          pass
                      if hearts <= 0:
                          try:
                              pause.show_death_screen(win)
                          except Exception:
                              pass
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
            if fill > 0:
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

            radius = 50
            sword_center_x = px + radius * math.cos(math.radians(current_angle))
            sword_center_y = py + radius * math.sin(math.radians(current_angle))

            rotated_sword = pygame.transform.rotate(sword_img, -current_angle)
            rect = rotated_sword.get_rect(center=(sword_center_x, sword_center_y))
            win.blit(rotated_sword, rect.topleft)

            # Hit detection (accurate enough): check each alive enemy center against arc and reach
            sword_reach = 64  # effective reach in pixels from player center
            for e in enemies:
                if not e.alive:
                    continue
                eid = id(e)
                if eid in attack_hits:
                    continue
                # enemy center
                ecx = e.x + e.size / 2
                ecy = e.y + e.size / 2
                vx = ecx - px
                vy = ecy - py
                dist = math.hypot(vx, vy)
                # allow hit if enemy rectangle intersects reach circle (account for enemy size)
                if dist > sword_reach + (e.size / 2):
                    continue
                # angle to enemy (degrees)
                ang = math.degrees(math.atan2(vy, vx))
                diff = (ang - current_angle + 180) % 360 - 180
                if abs(diff) <= (swing_arc / 2):
                    # line-of-sight check: sample along ray from player to enemy and ensure no wall tile blocks it.
                    los_clear = True
                    if not getattr(e, "can_fly", False):
                        if dist > 1e-4:
                            dirx = vx / dist
                            diry = vy / dist
                            step = 8
                            steps = max(1, int(dist // step))
                            for s in range(1, steps + 1):
                                sx = px + dirx * (s * step)
                                sy = py + diry * (s * step)
                                tx = int((sx - offset_x) // TILE_SIZE)
                                ty = int((sy - offset_y) // TILE_SIZE)
                                if tx < 0 or tx >= WIDTH or ty < 0 or ty >= HEIGHT:
                                    los_clear = False
                                    break
                                if game_map[ty][tx] in WALL_TILES:
                                    los_clear = False
                                    break
                        else:
                            los_clear = True
                    if not los_clear:
                        continue
                    # hit: deal damage and apply knockback away from player
                    e.apply_damage(sword_damage, kb_x=vx, kb_y=vy, kb_force=48, kb_duration=160)
                    attack_hits.add(eid)

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
        for i in range(total_hearts):
            hx = start_x + i * (heart_w + heart_spacing)
            img = heart_full if i < hearts else heart_empty
            win.blit(img, (hx, heart_y))

        pygame.display.update()

# ======================
# START GAME
# ======================
if __name__ == "__main__":
    # show the menu first; the menu will call main.run_game(SCREEN) when PLAY is pressed
    import menu
    menu.run_menu()
