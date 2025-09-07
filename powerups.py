import pygame
from pathlib import Path
import random

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

def choose_powerup(snapshot, screen_surface):
    """Display 3 cards (all damage cards for now). Returns (pick_dict_or_None, elapsed_ms)."""
    sw, sh = screen_surface.get_size()

    # --- load UI backdrop and fonts first (per request) ---
    bg = _build_blur(snapshot, (sw, sh))
    title_f = _get_font(36)
    info_f = _get_font(18)
    clock = pygame.time.Clock()

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

    # layout using the card's native size; move the cards down a bit (+40 px)
    card_w, card_h = card_img.get_width(), card_img.get_height()
    gap = 40
    total_w = card_w * 3 + gap * 2
    start_x = (sw - total_w) // 2
    y = (sh - card_h) // 2 + 40    # moved down by 40 pixels
    cards = [pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h) for i in range(3)]

    # now we know title position
    title_rect = title_surf.get_rect(center=(sw // 2, y - 48))

    # main event/draw loop (single, consistent loop)
    while True:
        for ev in pygame.event.get():
            # Do NOT allow skip; QUIT picks a random card
            if ev.type == pygame.QUIT:
                i = random.randint(0, 2)
                pick = {"id": f"damage_{random.randint(1000,9999)}", "type": "damage", "amount": 5}
                elapsed = pygame.time.get_ticks() - start_ticks
                return pick, elapsed
            if ev.type == pygame.KEYDOWN:
                # ignore ESC so players must pick a card
                pass
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                for i, r in enumerate(cards):
                    if r.collidepoint((mx, my)):
                        pick = {"id": f"damage_{random.randint(1000,9999)}", "type": "damage", "amount": 5}
                        elapsed = pygame.time.get_ticks() - start_ticks
                        return pick, elapsed

        # draw background + dark overlay
        screen_surface.blit(bg, (0, 0))
        screen_surface.blit(overlay, (0, 0))
        # title (no panel behind per previous request) placed above the moved-down cards
        screen_surface.blit(title_surf, title_rect)

        mx, my = pygame.mouse.get_pos()
        for i, r in enumerate(cards):
            hovered = r.collidepoint((mx, my))

            if hovered:
                # enlarge hovered card (scale up) and draw centered on original rect
                scale = 1.18
                swidth = int(card_w * scale)
                sheight = int(card_h * scale)
                try:
                    img = pygame.transform.smoothscale(card_img, (swidth, sheight))
                except Exception:
                    img = card_img
                rect = img.get_rect(center=r.center)

                # small black backing (previous behavior) and thin outline
                pygame.draw.rect(screen_surface, (0, 0, 0), rect.inflate(6, 6))
                screen_surface.blit(img, rect.topleft)
                try:
                    pygame.draw.rect(screen_surface, (0, 0, 0), rect, 2)
                except Exception:
                    pygame.draw.rect(screen_surface, (0, 0, 0), rect.inflate(6,6))

                # label positioned relative to the enlarged rect
                lbl = info_f.render("+5 Damage", True, (220, 200, 80))
                screen_surface.blit(lbl, lbl.get_rect(center=(rect.centerx, rect.bottom + 18)))
            else:
                # draw card at native size centered in slot, with small black backing and thin outline
                rect = card_img.get_rect(center=r.center)
                pygame.draw.rect(screen_surface, (0, 0, 0), rect.inflate(6, 6))
                screen_surface.blit(card_img, rect.topleft)
                try:
                    pygame.draw.rect(screen_surface, (0, 0, 0), rect, 2)
                except Exception:
                    pygame.draw.rect(screen_surface, (0, 0, 0), rect.inflate(6, 6))

                lbl = info_f.render("+5 Damage", True, (200, 200, 200))
                screen_surface.blit(lbl, lbl.get_rect(center=(rect.centerx, rect.bottom + 18)))

        pygame.display.update()
        clock.tick(60)
        pygame.display.update()
        clock.tick(60)
