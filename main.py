import pygame
import sys
import math
import os
import random

# ======================
# GAME LOOP
# ======================
def run_game():
    # --- Common init ---
    pygame.init()
    screen_info = pygame.display.Info()
    win = pygame.display.set_mode((screen_info.current_w, screen_info.current_h), pygame.FULLSCREEN)
    pygame.display.set_caption("Walking Character + Map")
    clock = pygame.time.Clock()

    # ======================
    # MAP DATA AND LOADER
    # ======================
    TILE_SIZE = 48
    WIDTH = 13
    HEIGHT = 13

    WALL_TILES = {"-", "|", "A", "B", "C", "D", "#", "0", "I"}
    LAVA_TILE = "X"

    def load_map_from_file(filename):
        path = os.path.join("maps", filename)
        with open(path, "r") as f:
            lines = [list(line.strip()) for line in f.readlines()]
        return lines

    MAPS = [
        load_map_from_file("map1.txt"),
        load_map_from_file("map2.txt"),
        load_map_from_file("map3.txt"),
        load_map_from_file("map4.txt"),
        load_map_from_file("map5.txt"),
        load_map_from_file("map6.txt"),
        load_map_from_file("map7.txt"),
        load_map_from_file("map8.txt"),
    ]

    def load_sprite(filename, size=TILE_SIZE, rotation=0):
        path = os.path.join("sprites", filename)
        img = pygame.image.load(path).convert_alpha()
        img = pygame.transform.scale(img, (size, size))
        if rotation != 0:
            img = pygame.transform.rotate(img, rotation)
        return img

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
        "#": load_sprite("wall_middle_2.png")
    }
    
    # Sword sprite
    sword_img = load_sprite("sword.png", size=48)
    attack_duration = 250  # ms swing
    attack_cooldown = 600  # ms cooldown after swing
    attacking = False
    attack_timer = 0
    cooldown_timer = 0
    swing_start_angle = 0
    swing_arc = 120  # degrees of swing

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

    def draw_map(win, game_map, floor_choices, offset_x, offset_y):
        for y in range(HEIGHT):
            for x in range(WIDTH):
                tile = game_map[y][x]
                if tile == ".":
                    sprite = floor_choices[y][x]
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
        path = os.path.join("sprites", name)
        return pygame.transform.scale(
            pygame.image.load(path).convert_alpha(),
            (size, size)
        )

    char_size = 48
    vel = 4
    dash_speed = 16
    dash_duration = 175
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

    pressed_dirs = []
    last_direction = "down"
    frame_index = 0
    frame_timer = 0
    frame_delay = 120

    stamina = stamina_max
    is_dashing = False
    dash_timer = 0
    dash_dir = (0, 0)

    # initialize values that were referenced before assignment
    current_angle = 0.0
    # simple initial player_center based on x,y
    player_center = (x + char_size // 2, y + char_size // 2)

    run = True
    while run:
        dt = clock.tick(60)

        # Timers should be updated each frame, not just when events occur
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
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                return  # back to menu

            if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                game_map, floor_choices = pick_map()
                x = offset_x + (WIDTH // 2) * TILE_SIZE
                y = offset_y + 1 * TILE_SIZE
                pressed_dirs.clear()
                is_dashing = False
                frame_index = 0

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

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # left click
                if not attacking and cooldown_timer <= 0:
                    attacking = True
                    attack_timer = attack_duration
                    cooldown_timer = attack_duration + attack_cooldown
                    # Lock swing start angle toward mouse; compute player center now
                    mx, my = pygame.mouse.get_pos()
                    px = x + char_size // 2
                    py = y + char_size // 2
                    player_center = (px, py)
                    swing_start_angle = math.degrees(math.atan2(my - py, mx - px))

        dx, dy = 0, 0
        if is_dashing:
            dx, dy = dash_dir
        else:
            keys = pygame.key.get_pressed()
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
                # check for lava under feet after dash ends
                foot_width = char_size // 2
                foot_height = 10
                foot_x = x + (char_size - foot_width) // 2
                foot_y = y + char_size - foot_height
                foot_rect = pygame.Rect(foot_x, foot_y, foot_width, foot_height)
                for px, py in [
                    (foot_rect.left, foot_rect.bottom - 1),
                    (foot_rect.right - 1, foot_rect.bottom - 1),
                    (foot_rect.centerx, foot_rect.bottom - 1)
                ]:
                    tile_x = int((px - offset_x) // TILE_SIZE)
                    tile_y = int((py - offset_y) // TILE_SIZE)
                    if 0 <= tile_x < WIDTH and 0 <= tile_y < HEIGHT:
                        if game_map[tile_y][tile_x] == LAVA_TILE:
                            print("You died in lava!")
                            return  # back to menu
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

        if is_dashing and dash_timer <= 0:
            foot_width = char_size // 2
            foot_height = 10
            foot_x = x + (char_size - foot_width) // 2
            foot_y = y + char_size - foot_height
            foot_rect = pygame.Rect(foot_x, foot_y, foot_width, foot_height)
            for px, py in [
                (foot_rect.left, foot_rect.bottom - 1),
                (foot_rect.right - 1, foot_rect.bottom - 1),
                (foot_rect.centerx, foot_rect.bottom - 1)
            ]:
                tile_x = int((px - offset_x) // TILE_SIZE)
                tile_y = int((py - offset_y) // TILE_SIZE)
                if 0 <= tile_x < WIDTH and 0 <= tile_y < HEIGHT:
                    if game_map[tile_y][tile_x] == LAVA_TILE:
                        print("You died in lava!")
                        return  # back to menu

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

        # Use current_angle only after initialization (we initialized it above)
        angle = int(current_angle) // 3 * 3  # snap to nearest 3°
        # rotated_sword = sword_rotations[angle]  # not used directly here

        win.fill((0, 0, 0))
        draw_map(win, game_map, floor_choices, offset_x, offset_y)

        # Draw shadow first (under character)
        draw_shadow(win, x, y, char_size, game_map, offset_x, offset_y)

        # Then draw character
        char = animations[last_direction][frame_index]
        win.blit(char, (x, y))

        # Update player_center based on current x,y for drawing and aiming
        char_rect = char.get_rect(topleft=(x, y))
        player_center = char_rect.center

        # Crosshair
        draw_crosshair(win, player_center)

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

        pygame.display.update()

# ======================
# START GAME
# ======================
if __name__ == "__main__":
    run_game()
