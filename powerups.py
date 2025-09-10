import pygame
from pathlib import Path
import random
import sounds  # added for selection SFX

# ensure MASTER_VOLUME exists
try:
    if not hasattr(sounds, 'MASTER_VOLUME'):
        sounds.MASTER_VOLUME = 1.0
except Exception:
    pass

def _apply_master_volume():
    mv = getattr(sounds, 'MASTER_VOLUME', 1.0)
    try: pygame.mixer.music.set_volume(mv)
    except Exception: pass
    try:
        chs = pygame.mixer.get_num_channels()
        for i in range(chs):
            try: pygame.mixer.Channel(i).set_volume(mv)
            except Exception: pass
    except Exception: pass

def _build_blur(snapshot, target_size):
    if snapshot:
        try:
            sw, sh = snapshot.get_size()
            small = pygame.transform.smoothscale(snapshot, (max(1, sw//12), max(1, sh//12)))
            return pygame.transform.smoothscale(small, target_size)
        except Exception:
            pass
    s = pygame.Surface(target_size)
    s.fill((18,18,20))
    return s

def _get_font(size):
    base = Path(__file__).parent
    for ext in ("ttf","otf"):
        p = base.joinpath("sprites", f"font.{ext}")
        if p.exists():
            try:
                return pygame.font.Font(str(p), size)
            except Exception:
                break
    return pygame.font.SysFont("arial", size, bold=True)

# helper: wrap text into up to `max_lines` lines and return a surface
def _wrap_render(font, text, color, max_width, max_lines=2, line_spacing=2):
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = w if cur == "" else cur + " " + w
        if font.size(test)[0] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)

    surfaces = [font.render(line, True, color) for line in lines]
    if not surfaces:
        return pygame.Surface((0, 0), pygame.SRCALPHA)
    width = max(s.get_width() for s in surfaces)
    height = sum(s.get_height() for s in surfaces) + (len(surfaces) - 1) * line_spacing
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    y = 0
    for s in surfaces:
        surf.blit(s, ((width - s.get_width()) // 2, y))
        y += s.get_height() + line_spacing
    return surf

def choose_powerup(snapshot, screen_surface):
    """Display 3 cards (damage/attackspeed/dashspeed/speed). Returns (pick_dict_or_None, elapsed_ms)."""
    sw, sh = screen_surface.get_size()

    # --- load UI backdrop and fonts first (per request) ---
    bg = _build_blur(snapshot, (sw, sh))
    title_f = _get_font(36)
    info_f = _get_font(18)
    clock = pygame.time.Clock()
    # preload selection sound (idempotent)
    try:
        sounds.preload('SelectSound')
    except Exception:
        pass
    # prepare overlay and title once
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    # layout will determine title position later, create surface now
    title_surf = title_f.render("Choose a Powerup", True, (230, 230, 230))

    # start timing so we can report how long the chooser was open (to preserve grace timer)
    start_ticks = pygame.time.get_ticks()

    # --- now load the card image (keep native size after optional up/downscale) ---
    base = Path(__file__).parent
    card_img = None
    try:
        p = base.joinpath("sprites", "damage_card.png")
        if p.exists():
            orig = pygame.image.load(str(p)).convert_alpha()
            ow, oh = orig.get_size()
            if ow <= 40 and oh <= 56:
                try:
                    up_w, up_h = ow * 12, oh * 12
                    card_img = pygame.transform.smoothscale(orig, (up_w, up_h))
                except Exception:
                    card_img = orig
            elif ow >= 160 * 12 or oh >= 220 * 12:
                try:
                    small = pygame.transform.smoothscale(orig, (max(1, ow // 12), max(1, oh // 12)))
                    card_img = small
                except Exception:
                    card_img = orig
            else:
                card_img = orig
    except Exception:
        card_img = None

    if card_img is None:
        card_img = pygame.Surface((160, 220), pygame.SRCALPHA)
        card_img.fill((80, 80, 80))
        pygame.draw.rect(card_img, (200, 200, 200), card_img.get_rect(), 3)

    # load specific images for each powerup (fallback to generic card_img)
    card_images = {}
    keys_and_files = {
        "damage": "damage_card.png",
        "attackspeed": "attackspeed_card.png",
        "dashspeed": "dashspeed_card.png",
        "speed": "speed_card.png",
    }
    for key, fname in keys_and_files.items():
        fp = base.joinpath("sprites", fname)
        if fp.exists():
            try:
                im = pygame.image.load(str(fp)).convert_alpha()
                # scale to the chosen card base size for consistent layout
                im = pygame.transform.smoothscale(im, (card_img.get_width(), card_img.get_height()))
                card_images[key] = im
            except Exception:
                card_images[key] = card_img
        else:
            card_images[key] = card_img

    # define candidate powerups
    pool = [
        {"id": "damage", "type": "damage", "amount": 5, "label": "+5 Damage"},
        {"id": "attackspeed", "type": "attackspeed", "amount": 0.20, "label": "+20% Attack Speed"},
        {"id": "dashspeed", "type": "dashspeed", "amount": 0.20, "label": "+20% Dash Recovery"},
        {"id": "speed", "type": "speed", "walk_mult": 0.25, "dash_mult": 0.20, "label": "+25% Speed"}
    ]

    # randomly pick three distinct cards to show
    choices = random.sample(pool, 3)

    # layout using the card's native size; increase vertical offset to avoid label overlap
    card_w, card_h = card_img.get_width(), card_img.get_height()
    gap = 40
    total_w = card_w * 3 + gap * 2
    start_x = (sw - total_w) // 2
    # move cards further down so labels and title have breathing room
    y = (sh - card_h) // 2 + 10    # increased from +40 to +80
    cards = [pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h) for i in range(3)]

    # now we know title position; move it up relative to the cards to avoid overlap
    title_rect = title_surf.get_rect(center=(sw // 2, y - 35))

    # compute a safe hover scale so an enlarged card won't overlap adjacent slots
    slot_width = card_w + gap
    # ensure at least 1.0; slightly reduce to keep margin
    safe_scale = min(1.18, max(1.0, (slot_width - 8) / float(card_w) * 0.92))
    hover_scale = safe_scale
    label_margin_hover = 30
    label_margin_normal = 22

    # label colors (normal / hovered) - green shades
    label_color_normal = (80, 200, 120)
    label_color_hover = (120, 240, 140)

    # main event/draw loop (single, consistent loop)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                i = random.randint(0, 2)
                pick = choices[i]
                elapsed = pygame.time.get_ticks() - start_ticks
                try: sounds.play_sfx('SelectSound')
                except Exception: pass
                _apply_master_volume()
                return pick, elapsed
            if ev.type == pygame.KEYDOWN:
                pass  # ESC ignored intentionally
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                for i, r in enumerate(cards):
                    if r.collidepoint((mx, my)):
                        pick = choices[i]
                        elapsed = pygame.time.get_ticks() - start_ticks
                        try: sounds.play_sfx('SelectSound')
                        except Exception: pass
                        _apply_master_volume()
                        return pick, elapsed

        # draw background + dark overlay
        screen_surface.blit(bg, (0, 0))
        screen_surface.blit(overlay, (0, 0))
        # title (no panel behind per previous request) placed above the moved-down cards
        # ensure title does not overlap the top of the screen; reduced offset to bring title closer
        title_y = max(12, y - card_h // 2 - 20)
        title_rect = title_surf.get_rect(center=(sw // 2, title_y))
        screen_surface.blit(title_surf, title_rect)

        mx, my = pygame.mouse.get_pos()
        for i, r in enumerate(cards):
            hovered = r.collidepoint((mx, my))

            # select the proper image for this choice
            choice_id = choices[i].get("id", "damage")
            img_src = card_images.get(choice_id, card_img)

            if hovered:
                # enlarge hovered card (scale up) but respect safe hover_scale
                scale = hover_scale
                swidth = int(card_w * scale)
                sheight = int(card_h * scale)
                try:
                    img = pygame.transform.smoothscale(img_src, (swidth, sheight))
                except Exception:
                    img = img_src
                rect = img.get_rect(center=r.center)

                # clamp horizontally so it doesn't draw off-screen
                if rect.left < 8:
                    rect.left = 8
                if rect.right > sw - 8:
                    rect.right = sw - 8

                # backing for the card (slightly transparent black) to improve readability
                try:
                    back = pygame.Surface((rect.width + 8, rect.height + 8), pygame.SRCALPHA)
                    back.fill((0, 0, 0, 160))
                    screen_surface.blit(back, (rect.left - 4, rect.top - 4))
                except Exception:
                    pygame.draw.rect(screen_surface, (0, 0, 0), rect.inflate(6, 6))

                screen_surface.blit(img, rect.topleft)
                try:
                    pygame.draw.rect(screen_surface, (0, 0, 0), rect, 2)
                except Exception:
                    pass

                # label with semi-transparent background below the scaled rect (wrapped, up to 2 lines)
                max_label_w = max(80, min(swidth - 16, sw - 40))
                lbl_surf = _wrap_render(info_f, choices[i].get("label", ""), label_color_hover, max_label_w)
                lbl_rect = lbl_surf.get_rect(center=(rect.centerx, rect.bottom + label_margin_hover))
                 # clamp label to screen bottom
                if lbl_rect.bottom > sh - 8:
                    lbl_rect.bottom = sh - 8
                bg_rect = lbl_rect.inflate(10, 6)
                try:
                    s_bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                    s_bg.fill((0, 0, 0, 160))
                    screen_surface.blit(s_bg, bg_rect.topleft)
                except Exception:
                    pygame.draw.rect(screen_surface, (0,0,0), bg_rect)
                screen_surface.blit(lbl_surf, lbl_rect)
            else:
                # draw card at native size centered in slot, with small black backing and thin outline
                rect = img_src.get_rect(center=r.center)
                try:
                    back = pygame.Surface((rect.width + 6, rect.height + 6), pygame.SRCALPHA)
                    back.fill((0, 0, 0, 160))
                    screen_surface.blit(back, (rect.left - 3, rect.top - 3))
                except Exception:
                    pygame.draw.rect(screen_surface, (0, 0, 0), rect.inflate(6, 6))
                screen_surface.blit(img_src, rect.topleft)
                try:
                    pygame.draw.rect(screen_surface, (0, 0, 0), rect, 2)
                except Exception:
                    pass

                max_label_w = max(80, card_w - 16)
                lbl_surf = _wrap_render(info_f, choices[i].get("label", ""), label_color_normal, max_label_w)
                lbl_rect = lbl_surf.get_rect(center=(rect.centerx, rect.bottom + label_margin_normal))
                if lbl_rect.bottom > sh - 8:
                    lbl_rect.bottom = sh - 8
                bg_rect = lbl_rect.inflate(8, 6)
                try:
                    s_bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                    s_bg.fill((0, 0, 0, 140))
                    screen_surface.blit(s_bg, bg_rect.topleft)
                except Exception:
                    pygame.draw.rect(screen_surface, (0,0,0), bg_rect)
                screen_surface.blit(lbl_surf, lbl_rect)

        pygame.display.update()
        clock.tick(60)
