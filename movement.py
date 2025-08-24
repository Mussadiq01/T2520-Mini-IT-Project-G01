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
char_size = 64
vel = 4
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
    "up":    [up_idle, up_walk1, up_idle, up_walk2],
    "down":  [down_idle, down_walk1, down_idle, down_walk2],
    "left":  [left_idle, left_walk1, left_idle, left_walk2],
    "right": [right_idle, right_walk1, right_idle, right_walk2],
}

# --- Key mapping ---
key_to_dir = {
    pygame.K_w: "up",
    pygame.K_s: "down",
    pygame.K_a: "left",
    pygame.K_d: "right",
}

# --- Walkable Box ---
box_size = 512
box_x = (screen_info.current_w - box_size) // 2
box_y = (screen_info.current_h - box_size) // 2
box_rect = pygame.Rect(box_x, box_y, box_size, box_size)

# --- Character state ---
x = box_rect.centerx - char_size // 2
y = box_rect.centery - char_size // 2
pressed_dirs = []       # tracks order of key presses
last_direction = "down" # default facing
frame_index = 0
frame_timer = 0
frame_delay = 80  # ms between frames

# --- Main Loop ---
run = True
while run:
    dt = clock.tick(60)

    # --- Events ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            run = False

        if event.type == pygame.KEYDOWN and event.key in key_to_dir:
            d = key_to_dir[event.key]
            if d not in pressed_dirs:
                pressed_dirs.append(d)   # add to order list
            last_direction = pressed_dirs[-1]  # newest direction wins

        if event.type == pygame.KEYUP and event.key in key_to_dir:
            d = key_to_dir[event.key]
            if d in pressed_dirs:
                pressed_dirs.remove(d)
            if pressed_dirs:
                last_direction = pressed_dirs[-1]  # fallback to previous
            else:
                frame_index = 0  # idle when no keys pressed

    # --- Movement ---
    keys = pygame.key.get_pressed()
    dx, dy = 0, 0

    if "left" in pressed_dirs and keys[pygame.K_a]:
        dx -= 1
    if "right" in pressed_dirs and keys[pygame.K_d]:
        dx += 1
    if "up" in pressed_dirs and keys[pygame.K_w]:
        dy -= 1
    if "down" in pressed_dirs and keys[pygame.K_s]:
        dy += 1

    moving = dx != 0 or dy != 0

    # normalize diagonal movement
    if dx != 0 and dy != 0:
        norm = math.sqrt(dx*dx + dy*dy)
        dx /= norm
        dy /= norm

    x += dx * vel
    y += dy * vel

    # clamp inside box
    if x < box_rect.left: x = box_rect.left
    if x > box_rect.right - char_size: x = box_rect.right - char_size
    if y < box_rect.top: y = box_rect.top
    if y > box_rect.bottom - char_size: y = box_rect.bottom - char_size

    # --- Animation ---
    if moving:
        frame_timer += dt
        if frame_timer >= frame_delay:
            frame_timer = 0
            frame_index = (frame_index + 1) % len(animations[last_direction])
    else:
        frame_index = 0  # idle

    # --- Draw ---
    win.fill((0, 0, 0))
    pygame.draw.rect(win, (200, 200, 200), box_rect)       # gray area
    pygame.draw.rect(win, (255, 0, 0), box_rect, 2)        # red outline

    char = animations[last_direction][frame_index]
    win.blit(char, (x, y))

    pygame.display.update()

pygame.quit()
