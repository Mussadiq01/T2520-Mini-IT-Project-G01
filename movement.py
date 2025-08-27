import pygame
import math
import os

def load_sprite(name, size):
    path = os.path.join("sprites", name)
    return pygame.transform.scale(
        pygame.image.load(path).convert_alpha(),
        (size, size)
    )

pygame.init()

# --- Screen setup ---
screen_info = pygame.display.Info()
win = pygame.display.set_mode((screen_info.current_w, screen_info.current_h), pygame.FULLSCREEN)
pygame.display.set_caption("Walking Character")

# --- Settings ---
char_size = 48
vel = 4
dash_speed = 15       # how fast dashing is
dash_duration = 200   # dash lasts 200 ms
stamina_max = 3.0     # 3 bars
stamina_regen_rate = 0.5   # bars per second
clock = pygame.time.Clock()

# --- Load Sprites ---
up_idle   = load_sprite("up_idle.png", char_size)
up_walk1  = load_sprite("up_walk1.png", char_size)
up_walk2  = load_sprite("up_walk2.png", char_size)

down_idle = load_sprite("down_idle.png", char_size)
down_walk1= load_sprite("down_walk1.png", char_size)
down_walk2= load_sprite("down_walk2.png", char_size)

left_idle = load_sprite("left_idle.png", char_size)
left_walk1= load_sprite("left_walk1.png", char_size)
left_walk2= load_sprite("left_walk2.png", char_size)

right_idle = load_sprite("right_idle.png", char_size)
right_walk1= load_sprite("right_walk1.png", char_size)
right_walk2= load_sprite("right_walk2.png", char_size)

# --- Animations dictionary ---
animations = {
    "up":    [up_idle, up_walk1, up_walk2],
    "down":  [down_idle, down_walk1, down_walk2],
    "left":  [left_idle, left_walk1, left_walk2],
    "right": [right_idle, right_walk1, right_walk2],
}

# --- Key mapping ---
key_to_dir = {
    pygame.K_w: "up",
    pygame.K_s: "down",
    pygame.K_a: "left",
    pygame.K_d: "right",
}

# --- Walkable Box ---
box_size = 528
box_x = (screen_info.current_w - box_size) // 2
box_y = (screen_info.current_h - box_size) // 2
box_rect = pygame.Rect(box_x, box_y, box_size, box_size)

# --- Character state ---
x = box_rect.centerx - char_size // 2
y = box_rect.centery - char_size // 2
pressed_dirs = []
last_direction = "down"
frame_index = 0
frame_timer = 0
frame_delay = 120  # ms between frames

# --- Dash/Stamina state ---
stamina = stamina_max
is_dashing = False
dash_timer = 0
dash_dir = (0, 0)

# --- Main Loop ---
run = True
while run:
    dt = clock.tick(60)

    # --- Events ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            run = False

        # Track key presses/releases even while dashing so state stays fresh,
        # but do NOT change facing while dashing.
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

        # --- Dash ---
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            if not is_dashing and stamina >= 1.0 and pressed_dirs:
                is_dashing = True
                dash_timer = dash_duration
                stamina -= 1.0  # use one bar instantly

                # set dash direction based on current pressed_dirs
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

        # normalize diagonal movement
        if dx != 0 and dy != 0:
            norm = math.sqrt(dx*dx + dy*dy)
            dx /= norm
            dy /= norm

    moving = dx != 0 or dy != 0

    # dash vs walk
    speed = vel
    if is_dashing:
        speed = dash_speed
        dash_timer -= dt
        if dash_timer <= 0:
            is_dashing = False
            # after dash ends, align facing to current input if available
            if pressed_dirs:
                last_direction = pressed_dirs[-1]

    x += dx * speed
    y += dy * speed

    # clamp inside box
    if x < box_rect.left: x = box_rect.left
    if x > box_rect.right - char_size: x = box_rect.right - char_size
    if y < box_rect.top: y = box_rect.top
    if y > box_rect.bottom - char_size: y = box_rect.bottom - char_size

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
    win.fill((0, 0, 0))  # always clear normally
    pygame.draw.rect(win, (0, 0, 0), box_rect)
    pygame.draw.rect(win, (128, 128, 128), box_rect, 4)

    # draw character
    char = animations[last_direction][frame_index]
    win.blit(char, (x, y))

    # --- Stamina bars ---
    bar_x = box_rect.left
    bar_y = box_rect.top - 40
    BAR_W, BAR_H = 60, 20
    spacing = 10  # gap between bars

    for i in range(3):
        x_pos = bar_x + i * (BAR_W + spacing)
        y_pos = bar_y

        # background (empty bar)
        pygame.draw.rect(win, (128, 128, 128), (x_pos, y_pos, BAR_W, BAR_H))

        # filled portion 
        fill = min(1.0, max(0.0, stamina - i))
        if fill > 0:
            fill_w = int(BAR_W * fill)
            pygame.draw.rect(win, (255, 255, 255), (x_pos, y_pos, fill_w, BAR_H))

    pygame.display.update()

pygame.quit()