import pygame
import math
import os
import random

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

WALL_TILES = {"-", "|", "A", "B", "C", "D", "#"}
LAVA_TILE = "X"

MAPS = [
    [   # Map 1
        ["A","-","-","-","-","-","-","-","-","-","-","-","B"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["C","-","-","-","-","-","-","-","-","-","-","-","D"],
    ],
    [   # Map 2
        ["A","-","-","-","-","-","-","-","-","-","-","-","B"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["C","-","-","-","-","-","-","-","-","-","-","-","D"],
    ],
    [   # Map 3
        ["A","-","-","-","-","-","-","-","-","-","-","-","B"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".","X","X",".",".",".",".",".","X","X",".","|"],
        ["|",".","X",".",".",".",".",".",".",".","X",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".","#","#","#",".",".",".",".","|"],
        ["|",".",".",".",".","#","#","#",".",".",".",".","|"],
        ["|",".",".",".",".","#","#","#",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".","X",".",".",".",".",".",".",".","X",".","|"],
        ["|",".","X","X",".",".",".",".",".","X","X",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["C","-","-","-","-","-","-","-","-","-","-","-","D"],
    ],
    [   # Map 4
        ["A","-","-","-","-","-","-","-","-","-","-","-","B"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["C","-","-","-","-","-","-","-","-","-","-","-","D"],
    ],
    [   # Map 5
        ["A","-","-","-","-","-","-","-","-","-","-","-","B"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["C","-","-","-","-","-","-","-","-","-","-","-","D"],
    ],
    [   # Map 6
        ["A","-","-","-","-","-","-","-","-","-","-","-","B"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".","X","X",".",".",".","X","X",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["C","-","-","-","-","-","-","-","-","-","-","-","D"],

    ],
    [   # Map 7
        ["A","-","-","-","-","-","-","-","-","-","-","-","B"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","X","X",".",".",".","#","#",".",".","|"],
        ["|",".",".","X","X",".",".",".","#","#",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","#","#",".",".",".","X","X",".",".","|"],
        ["|",".",".","#","#",".",".",".","X","X",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["C","-","-","-","-","-","-","-","-","-","-","-","D"],
    ],
    [   # Map 8
        ["A","-","-","-","-","-","-","-","-","-","-","-","B"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".","#","#",".",".",".","#","#",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["|",".",".",".",".",".",".",".",".",".",".",".","|"],
        ["C","-","-","-","-","-","-","-","-","-","-","-","D"],
    ]
]

def load_sprite(filename, size=TILE_SIZE, rotation=0):
    path = os.path.join("sprites", filename)
    img = pygame.image.load(path).convert_alpha()
    img = pygame.transform.scale(img, (size, size))
    if rotation != 0:
        img = pygame.transform.rotate(img, rotation)
    return img

SPRITES = {
    "-": load_sprite("wall_edge.png"),
    "|": load_sprite("wall_edge.png", rotation=90),
    "X": load_sprite("lava.png"),
    "A": load_sprite("wall_corner.png", rotation=90),
    "B": load_sprite("wall_corner.png"),
    "C": load_sprite("wall_corner.png", rotation=180),
    "D": load_sprite("wall_corner.png", rotation=-90),
    "#": load_sprite("wall_middle.png")
}

FLOOR_SPRITES = [
    load_sprite("floor_1.png"),
    load_sprite("floor_2.png"),
    load_sprite("floor_3.png")
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
        # Walls always block
        if tile in WALL_TILES:
            return False
        # Lava blocks only when walking (not dashing)
        if tile == LAVA_TILE and not dashing:
            return False

    return True

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
dash_speed = 14
dash_duration = 175
stamina_max = 3.0
stamina_regen_rate = 0.5

# Load character sprites
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

# Position character inside the map
game_map, floor_choices = pick_map()
screen_width, screen_height = win.get_size()
offset_x = (screen_width - WIDTH * TILE_SIZE) // 2
offset_y = (screen_height - HEIGHT * TILE_SIZE) // 2

# Start at map center
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

# ======================
# MAIN LOOP
# ======================
run = True
while run:
    dt = clock.tick(60)

    # --- Events ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            run = False

        if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            # Pick a new map
            game_map, floor_choices = pick_map()
            # Reset player position (optional - here we set to map center)
            x = offset_x + (WIDTH // 2) * TILE_SIZE
            y = offset_y + 1 * TILE_SIZE
            # Reset movement state if needed
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

        # Dash
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

    # --- Movement ---
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

    # Dash vs walk
    speed = vel
    if is_dashing:
        speed = dash_speed
        dash_timer -= dt
        if dash_timer <= 0:
            # Dash ended → check if standing in lava
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
                        run = False

            # now reset dash state
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

    # --- After movement ---
    if is_dashing and dash_timer <= 0:
        # Dash ended, check if we're inside lava
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
                    run = False

    # --- Stamina regen ---
    if stamina < stamina_max:
        stamina += stamina_regen_rate * (dt / 1000.0)
        if stamina > stamina_max:
            stamina = stamina_max

    # --- Animation ---
    if moving:
        frame_timer += dt
        if frame_timer >= frame_delay:
            frame_timer = 0
            frame_index = (frame_index + 1) % 3
    else:
        frame_index = 0

    # --- Draw ---
    win.fill((0, 0, 0))
    draw_map(win, game_map, floor_choices, offset_x, offset_y)

    # Draw character
    char = animations[last_direction][frame_index]
    win.blit(char, (x, y))

    # Stamina bars
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

    pygame.display.update()

pygame.quit()
