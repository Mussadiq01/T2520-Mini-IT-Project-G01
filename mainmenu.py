import pygame, sys
import main  # dungeon game file (must have run_game())
from pathlib import Path

BASE_DIR = Path(__file__).parent

def asset_path(*parts):
    return str(BASE_DIR.joinpath(*parts))

pygame.init()

# ---------------------
# Button class
# ---------------------
class Button:
    def __init__(self, image, pos, text_input, font, base_color, hovering_color):
        self.image = image
        self.x_pos = pos[0]
        self.y_pos = pos[1]
        self.font = font
        self.base_color, self.hovering_color = base_color, hovering_color
        self.text_input = text_input
        self.text = self.font.render(self.text_input, True, self.base_color)
        if self.image is None:
            self.image = self.text
        self.rect = self.image.get_rect(center=(self.x_pos, self.y_pos))
        self.text_rect = self.text.get_rect(center=(self.x_pos, self.y_pos))

    def update(self, screen):
        if self.image is not None:
            screen.blit(self.image, self.rect)
        screen.blit(self.text, self.text_rect)

    def checkForInput(self, position):
        return self.rect.collidepoint(position)

    def changeColor(self, position):
        if self.rect.collidepoint(position):
            self.text = self.font.render(self.text_input, True, self.hovering_color)
        else:
            self.text = self.font.render(self.text_input, True, self.base_color)


# ---------------------
# Resolution setup
# ---------------------
screen_info = pygame.display.Info()
SCREEN_W, SCREEN_H = screen_info.current_w, screen_info.current_h
SCREEN = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)

# ---------------------
# Scaling helpers
# ---------------------
def get_font(size):
    """Font size based on 1080p scaling"""
    base_height = 1080
    scale = SCREEN_H / base_height
    font_path = asset_path("sprites", "font.ttf")
    try:
        # load project font (absolute path)
        return pygame.font.Font(font_path, int(size * scale))
    except Exception:
        # fallback to system font if file missing or invalid
        return pygame.font.SysFont(None, int(size * scale))

def load_and_scale(path, width_ratio=5):
    """Load image and scale to fraction of screen width; path is project-relative (e.g. 'sprites/Img.png')"""
    full_path = asset_path(*path.split("/"))
    try:
        img = pygame.image.load(full_path).convert_alpha()
    except Exception:
        # create a visible placeholder if file missing
        new_width = SCREEN_W // width_ratio
        new_height = new_width
        img = pygame.Surface((new_width, new_height), pygame.SRCALPHA)
        img.fill((200, 200, 200, 255))
        pygame.draw.line(img, (150, 0, 0), (0, 0), (new_width, new_height), 5)
        pygame.draw.line(img, (150, 0, 0), (0, new_height), (new_width, 0), 5)
        return img
    new_width = SCREEN_W // width_ratio
    scale = new_width / img.get_width()
    new_height = int(img.get_height() * scale)
    return pygame.transform.scale(img, (new_width, new_height))

# ---------------------
# Load sprites
# ---------------------
BG_path = asset_path("sprites", "Background.png")
try:
    BG = pygame.transform.scale(pygame.image.load(BG_path).convert(), (SCREEN_W, SCREEN_H))
except Exception:
    BG = pygame.Surface((SCREEN_W, SCREEN_H))
    BG.fill((30, 30, 30))  # neutral background when image missing

PLAY_IMG = load_and_scale("sprites/Play Rect.png", 4)      # ~25% screen width
OPTIONS_IMG = load_and_scale("sprites/Options Rect.png", 4)
QUIT_IMG = load_and_scale("sprites/Quit Rect.png", 4)

# ---------------------
# Game state
# ---------------------
state = "menu"

while True:
    mouse_pos = pygame.mouse.get_pos()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if state == "menu":
            if event.type == pygame.MOUSEBUTTONDOWN:
                if PLAY_BUTTON.checkForInput(mouse_pos):
                    state = "play"
                if OPTIONS_BUTTON.checkForInput(mouse_pos):
                    state = "options"
                if QUIT_BUTTON.checkForInput(mouse_pos):
                    pygame.quit()
                    sys.exit()

        elif state == "options":
            if event.type == pygame.MOUSEBUTTONDOWN:
                if OPTIONS_BACK.checkForInput(mouse_pos):
                    state = "menu"

        elif state == "play":
            # nothing here — handled by main.run_game()
            pass

    # ---------------------
    # Drawing
    # ---------------------
    if state == "menu":
        SCREEN.blit(BG, (0, 0))

        # Title
        MENU_TEXT = get_font(80).render("MAIN MENU", True, "#b68f40")
        SCREEN.blit(MENU_TEXT, MENU_TEXT.get_rect(center=(SCREEN_W//2, SCREEN_H//6)))

        # Buttons (relative to screen center)
        PLAY_BUTTON = Button(PLAY_IMG, (SCREEN_W//2, SCREEN_H//2 - SCREEN_H//6),
                             "PLAY", get_font(50), "#d7fcd4", "White")
        OPTIONS_BUTTON = Button(OPTIONS_IMG, (SCREEN_W//2, SCREEN_H//2),
                                "OPTIONS", get_font(50), "#d7fcd4", "White")
        QUIT_BUTTON = Button(QUIT_IMG, (SCREEN_W//2, SCREEN_H//2 + SCREEN_H//6),
                             "QUIT", get_font(50), "#d7fcd4", "White")

        for button in [PLAY_BUTTON, OPTIONS_BUTTON, QUIT_BUTTON]:
            button.changeColor(mouse_pos)
            button.update(SCREEN)

    elif state == "options":
        SCREEN.fill("white")

        OPTIONS_TEXT = get_font(45).render("This is the OPTIONS screen.", True, "Black")
        SCREEN.blit(OPTIONS_TEXT, OPTIONS_TEXT.get_rect(center=(SCREEN_W//2, SCREEN_H//3)))

        OPTIONS_BACK = Button(None, (SCREEN_W//2, SCREEN_H - SCREEN_H//4),
                              "BACK", get_font(50), "Black", "Green")
        OPTIONS_BACK.changeColor(mouse_pos)
        OPTIONS_BACK.update(SCREEN)

    elif state == "play":
        main.run_game()   # now returns instead of quitting pygame
        state = "menu"    # go back to menu when run_game() finishes

    pygame.display.update()
