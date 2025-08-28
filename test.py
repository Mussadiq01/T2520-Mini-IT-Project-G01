import pygame
import os

# Initialize pygame
pygame.init()

# Constants
WINDOW_SIZE = 528
GRID_SIZE = 11
TILE_SIZE = WINDOW_SIZE // GRID_SIZE

# Create window
screen = pygame.display.set_mode((WINDOW_SIZE, WINDOW_SIZE))
pygame.display.set_caption("Manual Tile Designer")

# Load textures
texture_files = ["lava.png", "floor_1.png", "floor_2.png", "floor_3.png", "wall_edge.png", "wall_corner.png", "trap_opened.png", "trap_closed.png"]
textures = []

for filename in texture_files:
    path = os.path.join("objects", filename)
    if os.path.exists(path):
        image = pygame.image.load(path).convert()
        image = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
        textures.append(image)
    else:
        print(f"Warning: {filename} not found in objects/")

# Start with blank map (None = empty)
tilemap = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

# Keep track of which texture is selected
selected_texture = 0

# Undo history stack
history = []

# Main loop
running = True
mouse_down_left = False
mouse_down_right = False

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            # Cycle textures with arrow keys
            if event.key == pygame.K_RIGHT:
                selected_texture = (selected_texture + 1) % len(textures)
            elif event.key == pygame.K_LEFT:
                selected_texture = (selected_texture - 1) % len(textures)

            # Undo (Ctrl + Z)
            elif event.key == pygame.K_z and pygame.key.get_mods() & pygame.KMOD_CTRL:
                if history:
                    row, col, prev_tile = history.pop()
                    tilemap[row][col] = prev_tile

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_x, mouse_y = event.pos
            col = mouse_x // TILE_SIZE
            row = mouse_y // TILE_SIZE

            if event.button == 1:  # Left click start
                mouse_down_left = True
                # Save history for undo
                history.append((row, col, tilemap[row][col]))
                tilemap[row][col] = textures[selected_texture]

            elif event.button == 3:  # Right click start
                mouse_down_right = True
                history.append((row, col, tilemap[row][col]))
                tilemap[row][col] = None

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                mouse_down_left = False
            elif event.button == 3:
                mouse_down_right = False

    # Handle continuous painting/erasing
    if mouse_down_left or mouse_down_right:
        mouse_x, mouse_y = pygame.mouse.get_pos()
        col = mouse_x // TILE_SIZE
        row = mouse_y // TILE_SIZE
        if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
            if mouse_down_left:
                if tilemap[row][col] != textures[selected_texture]:
                    history.append((row, col, tilemap[row][col]))
                    tilemap[row][col] = textures[selected_texture]
            elif mouse_down_right:
                if tilemap[row][col] is not None:
                    history.append((row, col, tilemap[row][col]))
                    tilemap[row][col] = None

    # Draw the grid
    screen.fill((0, 0, 0))
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if tilemap[row][col] is not None:
                screen.blit(tilemap[row][col], (col * TILE_SIZE, row * TILE_SIZE))

    # Draw grid lines
    for x in range(0, WINDOW_SIZE, TILE_SIZE):
        pygame.draw.line(screen, (100, 100, 100), (x, 0), (x, WINDOW_SIZE))
    for y in range(0, WINDOW_SIZE, TILE_SIZE):
        pygame.draw.line(screen, (100, 100, 100), (0, y), (WINDOW_SIZE, y))

    # Draw selected texture preview in corner
    if textures:
        preview = textures[selected_texture]
        pygame.draw.rect(screen, (255, 255, 0), (5, 5, TILE_SIZE + 4, TILE_SIZE + 4), 2)
        screen.blit(preview, (7, 7))

    pygame.display.flip()

pygame.quit()
