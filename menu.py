import pygame
import sys
from pathlib import Path
import os

pygame.init()

# Screen setup - start fullscreen (toggleable with F11)
display_info = pygame.display.Info()
SCREEN_W, SCREEN_H = display_info.current_w, display_info.current_h
# create fullscreen surface and track state
SCREEN = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
pygame.display.set_caption("Descend")
is_fullscreen = True

# Font helper
def get_font(size):
    # try to load a font file called "font" from the sprites folder (font.ttf / font.otf)
    base = Path(__file__).parent
    for ext in ("ttf", "otf"):
        p = base.joinpath("sprites", f"font.{ext}")
        if p.exists():
            try:
                return pygame.font.Font(str(p), size)
            except Exception:
                pass
    # fallback
    return pygame.font.SysFont("arial", size, bold=True)

def load_background(name, target_size):
    # try common image extensions
    base = Path(__file__).parent
    for ext in ("png", "jpg", "jpeg"):
        p = base.joinpath("sprites", f"{name}.{ext}")
        if p.exists():
            try:
                img = pygame.image.load(str(p)).convert()
                return pygame.transform.scale(img, target_size)
            except Exception:
                break
    # fallback solid surface
    surf = pygame.Surface(target_size)
    surf.fill((30, 30, 30))
    return surf

# Button class
class Button:
    def __init__(self, text, pos, width, height, font, base_color, hover_color):
        self.text = text
        self.rect = pygame.Rect(pos[0], pos[1], width, height)
        self.font = font
        self.base_color = base_color
        self.hover_color = hover_color
        self.current_color = base_color
        self.hovered = False

    def draw(self, surface):
        pygame.draw.rect(surface, self.current_color, self.rect)  # square corners (no border_radius)
        # text turns green when hovered
        text_color = (0, 200, 0) if self.hovered else (0, 0, 0)
        txt_surf = self.font.render(self.text, True, text_color)
        txt_rect = txt_surf.get_rect(center=self.rect.center)
        surface.blit(txt_surf, txt_rect)

    def update(self, mouse_pos):
        if self.rect.collidepoint(mouse_pos):
            self.current_color = self.hover_color
            self.hovered = True
        else:
            self.current_color = self.base_color
            self.hovered = False

    def is_clicked(self, mouse_pos):
        return self.rect.collidepoint(mouse_pos)

def show_options(snapshot, screen_surface):
    """Top-level Options UI. Operates on provided surface and returns:
       ("resolution_changed", (w,h)) or ("resume", None).
    """
    sw, sh = screen_surface.get_size()
    # build blurred background from snapshot if provided
    if snapshot:
        try:
            small = pygame.transform.smoothscale(snapshot, (max(1, sw//12), max(1, sh//12)))
            blurred = pygame.transform.smoothscale(small, (sw, sh))
        except Exception:
            blurred = load_background("Background", (sw, sh))
    else:
        blurred = load_background("Background", (sw, sh))

    # fonts
    title_font_local = get_font(64)
    button_font_local = get_font(32)
    res_font = get_font(11)
    apply_font = get_font(15)

    vol = pygame.mixer.music.get_volume() if pygame.mixer.get_init() else 1.0
    RES_OPTIONS = [(1280,720), (1366,768), (1600,900), (1920,1080), (800,600)]
    # default to current surface size if it matches one of the RES_OPTIONS,
    # otherwise fall back to 1920x1080
    current_size = (sw, sh)
    selected_res = current_size if current_size in RES_OPTIONS else (1920, 1080)

    slider_rect = pygame.Rect(sw//2 - 200, sh//2 - 40, 400, 8)
    handle_w = 14
    dragging = False
    clock_local = pygame.time.Clock()

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return ("resume", None)
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx,my = ev.pos
                if slider_rect.collidepoint((mx,my)):
                    dragging = True
                for i, r in enumerate(RES_OPTIONS):
                    bx = sw//2 - 220 + i*110
                    by = sh//2 + 40
                    br = pygame.Rect(bx, by, 100, 32)
                    if br.collidepoint((mx,my)):
                        selected_res = r
            if ev.type == pygame.MOUSEBUTTONUP:
                dragging = False
            if ev.type == pygame.MOUSEMOTION and dragging:
                mx, my = ev.pos
                t = (mx - slider_rect.left) / slider_rect.width
                t = max(0.0, min(1.0, t))
                vol = t
                try:
                    pygame.mixer.music.set_volume(vol)
                except Exception:
                    pass

        # draw
        screen_surface.blit(blurred, (0,0))
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0,0,0,120))
        screen_surface.blit(overlay, (0,0))

        panel_w, panel_h = 700, 300
        panel = pygame.Rect((sw-panel_w)//2, (sh-panel_h)//2, panel_w, panel_h)
        pygame.draw.rect(screen_surface, (40,40,40), panel)
        pygame.draw.rect(screen_surface, (120,120,120), panel, 4)

        t_s = title_font_local.render("Options", True, (200,200,200))
        screen_surface.blit(t_s, t_s.get_rect(center=(sw//2, panel.top+36)))

        lbl = button_font_local.render("Audio Volume", True, (220,220,220))
        screen_surface.blit(lbl, (panel.left+40, panel.top+80))
        pygame.draw.rect(screen_surface, (80,80,80), slider_rect)
        handle_x = slider_rect.left + int(vol * slider_rect.width)
        handle_rect = pygame.Rect(handle_x - handle_w//2, slider_rect.top - 6, handle_w, 20)
        pygame.draw.rect(screen_surface, (200,200,200), handle_rect)

        lbl2 = button_font_local.render("Resolution", True, (220,220,220))
        screen_surface.blit(lbl2, (panel.left+40, panel.top+140))
        for i, r in enumerate(RES_OPTIONS):
            bx = sw//2 - 220 + i*110
            by = sh//2 + 40
            br = pygame.Rect(bx, by, 100, 32)
            pygame.draw.rect(screen_surface, (90,90,90), br)
            if selected_res == r:
                pygame.draw.rect(screen_surface, (0,160,0), br, 3)
            txt = res_font.render(f"{r[0]}x{r[1]}", True, (0,0,0))
            screen_surface.blit(txt, txt.get_rect(center=br.center))

        apply_r = pygame.Rect(panel.right-200, panel.bottom-60, 80, 36)
        back_r = pygame.Rect(panel.right-100, panel.bottom-60, 80, 36)
        pygame.draw.rect(screen_surface, (180,180,180), apply_r)
        pygame.draw.rect(screen_surface, (180,180,180), back_r)
        a_surf = apply_font.render("Apply", True, (0,0,0))
        b_surf = apply_font.render("Back", True, (0,0,0))
        screen_surface.blit(a_surf, a_surf.get_rect(center=apply_r.center))
        screen_surface.blit(b_surf, b_surf.get_rect(center=back_r.center))

        mx,my = pygame.mouse.get_pos()
        pressed = pygame.mouse.get_pressed()
        if pressed[0]:
            if apply_r.collidepoint((mx,my)):
                if selected_res:
                    return ("resolution_changed", selected_res)
            if back_r.collidepoint((mx,my)):
                return ("resume", None)

        pygame.display.update()
        clock_local.tick(60)

def show_pause_overlay(snapshot, screen_surface):
    """Display pause overlay on given surface.
    Returns:
      ("resume", None) - continue game
      ("options", opt_res) - user chose Options; opt_res is whatever show_options returned (None here)
      ("shop", None) - shop
      ("menu", None) - quit to main menu
    """
    sw, sh = screen_surface.get_size()
    # build blurred background from snapshot if provided
    if snapshot:
        try:
            small = pygame.transform.smoothscale(snapshot, (max(1, sw//12), max(1, sh//12)))
            blurred = pygame.transform.smoothscale(small, (sw, sh))
        except Exception:
            blurred = load_background("Background", (sw, sh))
    else:
        blurred = load_background("Background", (sw, sh))

    title_f = get_font(48)
    btn_f = get_font(28)
    clock_local = pygame.time.Clock()

    # button rects (stacked)
    resume_rect = pygame.Rect((sw//2 - 120, sh//2 - 80, 240, 40))
    options_rect = pygame.Rect((sw//2 - 120, sh//2 - 30, 240, 40))
    shop_rect = pygame.Rect((sw//2 - 120, sh//2 + 20, 240, 40))
    quit_rect = pygame.Rect((sw//2 - 120, sh//2 + 70, 240, 40))

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return ("menu", None)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return ("resume", None)
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if resume_rect.collidepoint((mx, my)):
                    return ("resume", None)
                if options_rect.collidepoint((mx, my)):
                    # signal that Options was requested; do NOT open it here to avoid nesting.
                    return ("options", None)
                if shop_rect.collidepoint((mx, my)):
                    return ("shop", None)
                if quit_rect.collidepoint((mx, my)):
                    return ("menu", None)

        # draw overlay onto provided surface
        screen_surface.blit(blurred, (0,0))
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0,0,0,140))
        screen_surface.blit(overlay, (0,0))

        panel_w, panel_h = 520, 360
        panel = pygame.Rect((sw-panel_w)//2, (sh-panel_h)//2, panel_w, panel_h)
        pygame.draw.rect(screen_surface, (30,30,30), panel)
        pygame.draw.rect(screen_surface, (120,120,120), panel, 3)

        title_surf = title_f.render("Paused", True, (220,220,220))
        screen_surface.blit(title_surf, title_surf.get_rect(center=(sw//2, panel.top + 40)))

        # draw buttons
        pygame.draw.rect(screen_surface, (200,200,200), resume_rect)
        pygame.draw.rect(screen_surface, (200,200,200), options_rect)
        pygame.draw.rect(screen_surface, (200,200,200), shop_rect)
        pygame.draw.rect(screen_surface, (200,200,200), quit_rect)

        screen_surface.blit(btn_f.render("Resume (Esc)", True, (0,0,0)), btn_f.render("Resume (Esc)", True, (0,0,0)).get_rect(center=resume_rect.center))
        screen_surface.blit(btn_f.render("Options", True, (0,0,0)), btn_f.render("Options", True, (0,0,0)).get_rect(center=options_rect.center))
        screen_surface.blit(btn_f.render("Shop", True, (0,0,0)), btn_f.render("Shop", True, (0,0,0)).get_rect(center=shop_rect.center))
        screen_surface.blit(btn_f.render("Quit to Menu", True, (0,0,0)), btn_f.render("Quit to Menu", True, (0,0,0)).get_rect(center=quit_rect.center))

        pygame.display.update()
        clock_local.tick(60)

def run_menu():
    global SCREEN, SCREEN_W, SCREEN_H, is_fullscreen
    clock = pygame.time.Clock()
    # make fonts a bit smaller
    title_font = get_font(64)    # reduced from 80
    button_font = get_font(32)   # reduced from 40

    # helper to (re)create background and buttons using current SCREEN size
    def create_assets():
        nonlocal background, buttons, btn_w, btn_h, btn_x, btn_y_start, btn_gap
        SCREEN_W, SCREEN_H = SCREEN.get_size()
        background = load_background("Background", (SCREEN_W, SCREEN_H))
        # Button layout (recompute positions for current size)
        btn_w, btn_h = 300, 60
        btn_x = (SCREEN_W - btn_w) // 2
        btn_y_start = SCREEN_H // 2 - 2 * btn_h
        btn_gap = 30
        buttons = [
            Button("PLAY",   (btn_x, btn_y_start + 0*(btn_h+btn_gap)), btn_w, btn_h, button_font, (200,255,200), (255,255,255)),
            Button("SHOP",   (btn_x, btn_y_start + 1*(btn_h+btn_gap)), btn_w, btn_h, button_font, (200,255,200), (255,255,255)),
            Button("OPTIONS",(btn_x, btn_y_start + 2*(btn_h+btn_gap)), btn_w, btn_h, button_font, (200,255,200), (255,255,255)),
            Button("QUIT",   (btn_x, btn_y_start + 3*(btn_h+btn_gap)), btn_w, btn_h, button_font, (200,255,200), (255,255,255)),
        ]

    # initial assets
    background = None
    buttons = []
    btn_w = btn_h = btn_x = btn_y_start = btn_gap = 0
    create_assets()

    # Options overlay UI (nested so it can reuse create_assets/context)
    def run_options(snapshot):
        # delegate to top-level show_options using the menu SCREEN
        return show_options(snapshot, SCREEN)

    while True:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # toggle fullscreen/windowed with F11
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                is_fullscreen = not is_fullscreen
                if is_fullscreen:
                    info = pygame.display.Info()
                    SCREEN = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
                else:
                    SCREEN = pygame.display.set_mode((1280, 720))
                # after mode change recreate background and buttons
                SCREEN_W, SCREEN_H = SCREEN.get_size()
                create_assets()

            if event.type == pygame.MOUSEBUTTONDOWN:
                if buttons[0].is_clicked(mouse_pos):
                    # import main lazily to avoid circular import at module load time
                    import main
                    main.run_game(SCREEN)
                elif buttons[1].is_clicked(mouse_pos):
                    # Placeholder: Shop screen
                    pass
                elif buttons[2].is_clicked(mouse_pos):
                    # Placeholder: Options screen
                    # allow opening options directly without snapshot
                    opt_res = run_options(background)
                    if opt_res[0] == "resolution_changed":
                        new_size = opt_res[1]
                        is_fullscreen = False
                        SCREEN = pygame.display.set_mode(new_size)
                        SCREEN_W, SCREEN_H = SCREEN.get_size()
                        create_assets()
                    pass
                elif buttons[3].is_clicked(mouse_pos):
                    pygame.quit()
                    sys.exit()

        # draw background and grey square border
        SCREEN.blit(background, (0, 0))
        border_margin = 20
        border_rect = pygame.Rect(border_margin, border_margin, SCREEN_W - 2*border_margin, SCREEN_H - 2*border_margin)
        pygame.draw.rect(SCREEN, (120, 120, 120), border_rect, 8)  # square corners, grey border

        # Title
        title_surf = title_font.render("Descend", True, (182, 143, 64))
        SCREEN.blit(title_surf, title_surf.get_rect(center=(SCREEN_W//2, SCREEN_H//4)))

        # Buttons
        for btn in buttons:
            btn.update(mouse_pos)
            btn.draw(SCREEN)

        pygame.display.update()
        clock.tick(60)
        clock.tick(60)
        for btn in buttons:
            btn.update(mouse_pos)
            btn.draw(SCREEN)

        pygame.display.update()
        clock.tick(60)
        clock.tick(60)
