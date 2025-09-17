import pygame
import sys
from pathlib import Path
import os
import sounds  # added for click SFX and master volume
import save    # NEW: save/load utilities

# master volume helper (non-breaking; defaults to 1.0)
try:
    if not hasattr(sounds, 'MASTER_VOLUME'):
        sounds.MASTER_VOLUME = 1.0
except Exception:
    pass

def _apply_master_volume():
    mv = getattr(sounds, 'MASTER_VOLUME', 1.0)
    try:
        pygame.mixer.music.set_volume(mv)
    except Exception:
        pass
    try:
        chs = pygame.mixer.get_num_channels()
        for i in range(chs):
            try:
                pygame.mixer.Channel(i).set_volume(mv)
            except Exception:
                pass
    except Exception:
        pass

pygame.init()

# Screen setup - start fullscreen (toggleable with F11)
display_info = pygame.display.Info()
SCREEN_W, SCREEN_H = display_info.current_w, display_info.current_h
# create fullscreen surface and track state
SCREEN = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
pygame.display.set_caption("Descend")
is_fullscreen = True

# player currency shown in shop (from other code)
PLAYER_COINS = 10000

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
    """Top-level Options UI. Operates on provided surface and returns ("resume", None)."""
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

    # original master volume snapshot (keeps old behavior if sounds missing)
    orig_vol = getattr(sounds, 'MASTER_VOLUME', pygame.mixer.music.get_volume() if pygame.mixer.get_init() else 1.0)
    vol = orig_vol

    # Precompute panel & apply/back rects so event handling can reference them
    panel_w, panel_h = 700, 300
    panel = pygame.Rect((sw-panel_w)//2, (sh-panel_h)//2, panel_w, panel_h)
    apply_r = pygame.Rect(panel.right-200, panel.bottom-60, 80, 36)
    back_r = pygame.Rect(panel.right-100, panel.bottom-60, 80, 36)

    # place slider relative to the panel so spacing is consistent; make it full-width-ish inside panel
    slider_rect = pygame.Rect(panel.left + 40, panel.top + 140, panel.width - 80, 8)
    handle_w = 14
    dragging = False
    clock_local = pygame.time.Clock()

    # preload select sound and honor current master volume
    try:
        sounds.preload('SelectSound')
    except Exception:
        pass
    _apply_master_volume()

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                # discard changes, restore original
                try:
                    pygame.mixer.music.set_volume(orig_vol)
                    sounds.MASTER_VOLUME = orig_vol
                except Exception:
                    pass
                _apply_master_volume()
                try:
                    sounds.play_sfx('SelectSound')
                except Exception:
                    pass
                return ("resume", None)
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx,my = ev.pos
                if slider_rect.collidepoint((mx,my)):
                    dragging = True
            if ev.type == pygame.MOUSEBUTTONUP:
                # stop dragging and treat a release as a click for Apply/Back
                dragging = False
                mx, my = ev.pos
                if apply_r.collidepoint((mx, my)):
                    # commit changes
                    try:
                        sounds.MASTER_VOLUME = vol
                        pygame.mixer.music.set_volume(vol)
                    except Exception:
                        pass
                    _apply_master_volume()
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    return ("resume", None)
                if back_r.collidepoint((mx, my)):
                    # revert changes
                    try:
                        pygame.mixer.music.set_volume(orig_vol)
                        sounds.MASTER_VOLUME = orig_vol
                    except Exception:
                        pass
                    _apply_master_volume()
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    return ("resume", None)
            if ev.type == pygame.MOUSEMOTION and dragging:
                mx, my = ev.pos
                t = (mx - slider_rect.left) / slider_rect.width
                t = max(0.0, min(1.0, t))
                vol = t
                # live preview (music only)
                try:
                    pygame.mixer.music.set_volume(vol)
                except Exception:
                    pass

        # draw
        screen_surface.blit(blurred, (0,0))
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0,0,0,120))
        screen_surface.blit(overlay, (0,0))

        pygame.draw.rect(screen_surface, (40,40,40), panel)
        pygame.draw.rect(screen_surface, (120,120,120), panel, 4)

        # move title a bit lower to add spacing from the top box line
        t_s = title_font_local.render("Options", True, (200,200,200))
        screen_surface.blit(t_s, t_s.get_rect(center=(sw//2, panel.top+48)))

        # audio label placed above the slider with more vertical spacing
        lbl = button_font_local.render("Audio Volume", True, (220,220,220))
        screen_surface.blit(lbl, (panel.left+40, panel.top+110))

        # draw slider using panel-relative rect
        pygame.draw.rect(screen_surface, (80,80,80), slider_rect)
        handle_x = slider_rect.left + int(vol * slider_rect.width)
        handle_rect = pygame.Rect(handle_x - handle_w//2, slider_rect.top - 6, handle_w, 20)
        pygame.draw.rect(screen_surface, (200,200,200), handle_rect)

        pygame.draw.rect(screen_surface, (180,180,180), apply_r)
        pygame.draw.rect(screen_surface, (180,180,180), back_r)
        a_surf = apply_font.render("Apply", True, (0,0,0))
        b_surf = apply_font.render("Back", True, (0,0,0))
        screen_surface.blit(a_surf, a_surf.get_rect(center=apply_r.center))
        screen_surface.blit(b_surf, b_surf.get_rect(center=back_r.center))

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
                try:
                    sounds.play_sfx('SelectSound')
                except Exception:
                    pass
                return ("resume", None)
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if resume_rect.collidepoint((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    return ("resume", None)
                if options_rect.collidepoint((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    return ("options", None)
                if shop_rect.collidepoint((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    return ("shop", None)
                if quit_rect.collidepoint((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
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

def show_shop(snapshot, screen_surface):
    """Simple shop UI: two horizontally-scrollable rows (weapons, armor).
    Uses `sprites/sword.png` as a placeholder for all items.
    Returns when user closes the shop (Back/Quit to Menu).
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

    title_f = get_font(44)
    item_f = get_font(16)
    btn_f = get_font(20)
    clock_local = pygame.time.Clock()
    # NEW: preload select sound for all shop buttons
    try:
        sounds.preload('SelectSound')
    except Exception:
        pass

    # load coin icon for top-right panel and set coins value
    base = Path(__file__).parent
    coin_img = None
    try:
        p = base.joinpath("sprites", "coin.png")
        if p.exists():
            coin_img = pygame.image.load(str(p)).convert_alpha()
            coin_img = pygame.transform.smoothscale(coin_img, (36, 36))
    except Exception:
        coin_img = None
    if coin_img is None:
        coin_img = pygame.Surface((36, 36), pygame.SRCALPHA)
        pygame.draw.circle(coin_img, (212, 175, 55), (18, 18), 16)

    coins = PLAYER_COINS

    # per-item descriptions (unique for each item) - make available for resolver
    weapons_desc = {
        "Sword": "A sharp blade for close combat.",
        "Mallet": "A heavy mallet that stuns enemies.",
        "Dagger": "Fast and precise, ideal for quick strikes.",
        "Katana": "A finely balanced blade with reach and speed.",
        "The Descender": "A mysterious, powerful blade favored by champions."
    }

    # armors are materials (not specific pieces) — descriptions describe material properties
    armors_desc = {
        "Wood": "Light material, offers minimal protection.",
        "Iron": "Reliable material with balanced protection.",
        "Diamond": "Exceptional durability and high protection.",
        "Gold": "Soft but flashy; low protection, high weight.",
        "Leather": "Flexible and light; eases movement."
    }

    # items (placeholders)
    weapons = ["Sword", "Mallet", "Dagger", "Katana", "The Descender"]
    armors = ["Armor 1", "Armor 2", "Armor 3", "Armor 4", "Armor 5"]

    # purchased / inventory state persists while shop is open (can be saved later)
    # First weapon (Sword) is already unlocked
    weapons_purchased = set(["Sword"])
    armors_purchased = set()
    weapons_upgrades = {name: 0 for name in weapons}

    # NEW: load previously owned + equipped weapon from save.json
    initial_equipped_idx = None
    try:
        saved = save.load_player_data() or {}
        owned = saved.get("weapons_owned")
        if isinstance(owned, list):
            for w in owned:
                if w in weapons:
                    weapons_purchased.add(w)
        eq_name = (saved.get("equipped_weapon") or "").strip()
        if eq_name in weapons:
            initial_equipped_idx = weapons.index(eq_name)
    except Exception:
        pass

    # NEW: helper to persist purchases into save.json
    def persist_shop_state():
        try:
            data = save.load_player_data() or {}
            data["weapons_owned"] = sorted(list(weapons_purchased))
            save.save_player_data(data)
        except Exception:
            pass

    # NEW: helper to persist the equipped weapon
    def persist_equipped_weapon(name: str):
        try:
            data = save.load_player_data() or {}
            data["equipped_weapon"] = name
            # ensure equipped is in owned
            lst = set(data.get("weapons_owned") or [])
            lst.add(name)
            data["weapons_owned"] = sorted(lst)
            save.save_player_data(data)
        except Exception:
            pass

    # small helper to resolve a textual description for an item name consistently
    def resolve_desc(item_name: str) -> str:
        # prefer exact mapping first
        if item_name in weapons_desc:
            return weapons_desc[item_name]
        if item_name in armors_desc:
            return armors_desc[item_name]
        # try substring matches (e.g. "Sword 1" -> "Sword")
        for k, v in weapons_desc.items():
            if k and k in item_name:
                return v
        for k, v in armors_desc.items():
            if k and k in item_name:
                return v
        # fallback heuristic (keeps preview/modal consistent)
        if "Sword" in item_name or "Bow" in item_name or "Axe" in item_name or "Dagger" in item_name or "Spear" in item_name:
            return "A sharp blade. Effective at close range."
        if "Armor" in item_name or "Chestplate" in item_name or "Helmet" in item_name or "Shield" in item_name or "Boots" in item_name or "Greaves" in item_name:
            return "Protective gear. Reduces incoming damage."
        return "A reliable item."

    # Modal item detail view (shows large image, description, Buy/Back)
    def show_item_page(item_name: str, item_image: pygame.Surface):
        sw2, sh2 = screen_surface.get_size()
        # build blurred background from the current screen for the modal
        try:
            snap2 = screen_surface.copy()
        except Exception:
            snap2 = None
        if snap2:
            try:
                small = pygame.transform.smoothscale(snap2, (max(1, sw2//12), max(1, sh2//12)))
                bg = pygame.transform.smoothscale(small, (sw2, sh2))
            except Exception:
                bg = load_background("Background", (sw2, sh2))
        else:
            bg = load_background("Background", (sw2, sh2))

        title_font = get_font(36)
        body_font = get_font(18)
        small_font = get_font(16)
        # simple text wrapper for descriptions
        def wrap_text(text: str, font: pygame.font.Font, max_w: int):
            words = text.split()
            if not words:
                return []
            lines = []
            cur = words[0]
            for w in words[1:]:
                test = cur + " " + w
                if font.size(test)[0] <= max_w:
                    cur = test
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
            return lines
        panel_w, panel_h = min(800, sw2-160), min(520, sh2-160)
        panel = pygame.Rect((sw2-panel_w)//2, (sh2-panel_h)//2, panel_w, panel_h)
        buy_rect = pygame.Rect(panel.left + 40, panel.bottom - 80, 140, 48)
        back_rect = pygame.Rect(panel.right - 180, panel.bottom - 80, 140, 48)
        purchased = False
        # start purchased state from persistent sets so page reflects prior buys
        purchased = (item_name in weapons_purchased) or (item_name in armors_purchased)
        clock_modal = pygame.time.Clock()
        # choose description & price heuristically from name
        price = 50 if "Sword" in item_name or "Bow" in item_name or "Axe" in item_name or "Dagger" in item_name or "Spear" in item_name else 35 if "Armor" in item_name or "Chestplate" in item_name else 20

        # resolve description using helper (consistent with bottom preview)
        desc = resolve_desc(item_name)

        # fallback heuristic (matches bottom preview logic)
        if not desc:
            if "Sword" in item_name:
                desc = "A sharp blade for close combat."
            elif "Armor" in item_name:
                desc = "Protective gear. Reduces incoming damage."
            else:
                desc = "A reliable item."
 
        while True:
            dtm = clock_modal.tick(60)
            # NEW: precompute action rects before event handling (so clicks work this frame)
            equip_rect = pygame.Rect(panel.left + 40, panel.bottom - 80, 140, 48)
            upgrade_rect = pygame.Rect(panel.left + 200, panel.bottom - 80, 140, 48)

            for ev2 in pygame.event.get():
                if ev2.type == pygame.QUIT:
                    return ("menu", None)
                if ev2.type == pygame.KEYDOWN and ev2.key == pygame.K_ESCAPE:
                    return ("back", None)
                if ev2.type == pygame.MOUSEBUTTONDOWN and ev2.button == 1:
                    mx2,my2 = ev2.pos
                    if not purchased:
                        if buy_rect.collidepoint((mx2,my2)):
                            # mark as purchased — persist to outer shop state
                            purchased = True
                            try:
                                if item_name in weapons:
                                    weapons_purchased.add(item_name)
                                    persist_shop_state()  # save owned weapons
                                elif item_name in armors:
                                    armors_purchased.add(item_name)
                            except Exception:
                                weapons_purchased.add(item_name)
                                persist_shop_state()
                            # NEW: click SFX
                            try: sounds.play_sfx('SelectSound')
                            except Exception: pass
                        # NEW: make "Back" work when not purchased
                        elif back_rect.collidepoint((mx2,my2)):
                            # NEW: click SFX
                            try: sounds.play_sfx('SelectSound')
                            except Exception: pass
                            return ("back", None)
                    else:
                        # after purchase show Equip / Upgrade buttons
                        if equip_rect.collidepoint((mx2,my2)):
                            try:
                                if item_name in weapons:
                                    weapons_purchased.add(item_name)
                                    persist_shop_state()
                                    persist_equipped_weapon(item_name)
                                elif item_name in armors:
                                    armors_purchased.add(item_name)
                            except Exception:
                                weapons_purchased.add(item_name)
                                persist_shop_state()
                                persist_equipped_weapon(item_name)
                            # NEW: click SFX
                            try: sounds.play_sfx('SelectSound')
                            except Exception: pass
                            return ("equip", item_name)
                        if upgrade_rect.collidepoint((mx2,my2)):
                            # NEW: click SFX
                            try: sounds.play_sfx('SelectSound')
                            except Exception: pass
                            return ("upgrade", item_name)
                        if back_rect.collidepoint((mx2,my2)):
                            # NEW: click SFX
                            try: sounds.play_sfx('SelectSound')
                            except Exception: pass
                            return ("back", None)

            # draw modal
            screen_surface.blit(bg, (0,0))
            overlay = pygame.Surface((sw2, sh2), pygame.SRCALPHA)
            overlay.fill((0,0,0,160))
            screen_surface.blit(overlay, (0,0))

            pygame.draw.rect(screen_surface, (28,28,28), panel)
            pygame.draw.rect(screen_surface, (140,140,140), panel, 3)
            title_s = title_font.render(item_name, True, (220,220,220))
            screen_surface.blit(title_s, title_s.get_rect(topleft=(panel.left+24, panel.top+18)))

            # large image area (center-left)
            img_w = min(panel_w//2, 320)
            img_h = img_w
            try:
                big_img = pygame.transform.smoothscale(item_image, (img_w, img_h))
            except Exception:
                big_img = pygame.Surface((img_w, img_h))
                big_img.fill((100,100,100))
            screen_surface.blit(big_img, (panel.left+24, panel.top+70))

            # description text on the right
            tx = panel.left + 24 + img_w + 20
            ty = panel.top + 70
            # wrap description to fit the right area
            desc_area_w = panel.right - tx - 24
            wrapped = wrap_text(desc, body_font, max(10, desc_area_w))
            # limit how many lines fit in the area (leave space for price and buttons)
            max_lines = max(1, (panel_h - 160) // (body_font.get_linesize() + 2))
            for i, line in enumerate(wrapped[:max_lines]):
                surf = body_font.render(line, True, (200,200,200))
                screen_surface.blit(surf, (tx, ty + i * (body_font.get_linesize() + 2)))
            # price line under wrapped description (or after them)
            price_y = ty + (min(len(wrapped), max_lines)) * (body_font.get_linesize() + 2) + 8
            p_surf = body_font.render(f"Price: {price} gold", True, (200,200,200))
            screen_surface.blit(p_surf, (tx, price_y))

            # buttons: show Buy + Back initially; after purchase show Equip + Upgrade + Back
            if not purchased:
                pygame.draw.rect(screen_surface, (200,200,200), buy_rect)
                buy_color = (0,200,0) if buy_rect.collidepoint(pygame.mouse.get_pos()) else (0,0,0)
                screen_surface.blit(small_font.render("Buy", True, buy_color), small_font.render("Buy", True, buy_color).get_rect(center=buy_rect.center))
            else:
                # post-purchase actions: Equip and Upgrade (use precomputed rects)
                pygame.draw.rect(screen_surface, (200,200,200), equip_rect)
                pygame.draw.rect(screen_surface, (200,200,200), upgrade_rect)
                eq_col = (0,200,0) if equip_rect.collidepoint(pygame.mouse.get_pos()) else (0,0,0)
                cur_level = weapons_upgrades.get(item_name, 0) if item_name in weapons_upgrades else 0
                if cur_level >= 3:
                    up_label = "Max"
                    up_col = (80,80,80)
                else:
                    up_label = "Upgrade"
                    up_col = (0,200,0) if upgrade_rect.collidepoint(pygame.mouse.get_pos()) else (0,0,0)
                screen_surface.blit(small_font.render("Equip", True, eq_col), small_font.render("Equip", True, eq_col).get_rect(center=equip_rect.center))
                screen_surface.blit(small_font.render(up_label, True, up_col), small_font.render(up_label, True, up_col).get_rect(center=upgrade_rect.center))

            # Back button (always present)
            pygame.draw.rect(screen_surface, (200,200,200), back_rect)
            back_color = (0,200,0) if back_rect.collidepoint(pygame.mouse.get_pos()) else (0,0,0)
            screen_surface.blit(small_font.render("Back", True, back_color), small_font.render("Back", True, back_color).get_rect(center=back_rect.center))

            pygame.display.update()

    # load weapon images for each weapon (use project sprites when available)
    weapons_imgs = {}
    img_size = 96
    _img_map = {
        "Sword": "sword_pic.png",
        "Mallet": "mallet_pic.png",
        "Dagger": "dagger_pic.png",
        "Katana": "katana_pic.png",
        "The Descender": "the_descender_pic.png",
    }
    base = Path(__file__).parent
    for wname, fname in _img_map.items():
        try:
            p = base.joinpath("sprites", fname)
            if p.exists():
                img = pygame.image.load(str(p)).convert_alpha()
                img = pygame.transform.smoothscale(img, (img_size, img_size))
                weapons_imgs[wname] = img
        except Exception:
            pass
    # generic fallback graphic for missing images
    generic_img = pygame.Surface((img_size, img_size), pygame.SRCALPHA)
    pygame.draw.polygon(generic_img, (200,200,200), [(8,img_size-8),(img_size//2,8),(img_size-8,img_size-8)])
    for name in weapons:
        weapons_imgs.setdefault(name, generic_img)

    # load placeholder image
    base = Path(__file__).parent
    sword_img = None
    try:
        p = base.joinpath("sprites", "armor_pic.png")
        if p.exists():
            sword_img = pygame.image.load(str(p)).convert_alpha()
            sword_img = pygame.transform.smoothscale(sword_img, (96, 96))
    except Exception:
        sword_img = None
    if sword_img is None:
        sword_img = pygame.Surface((96, 96), pygame.SRCALPHA)
        pygame.draw.polygon(sword_img, (200, 200, 200), [(8,88),(48,8),(88,88)])

    # scrolling state (px offsets)
    weapons_offset = 0
    armors_offset = 0
    # selection/focus state
    weapons_selected = 0
    armors_selected = 0
    focused_row = "weapons"  # or "armors"
    # equipped indices (None == nothing equipped)
    weapons_equipped = initial_equipped_idx  # NEW: preselect equipped from save
    armors_equipped = None
    row_gap = 220
    margin_x = 120
    item_w = 120
    spacing = 40

    back_rect = pygame.Rect((sw//2 - 100, sh - 120, 200, 56))

    # bigger arrows, centered vertically relative to item box
    arrow_w = 64
    arrow_h = 64

    # Helper: compact text with ellipsis to fit width
    def ellipsize(text: str, font: pygame.font.Font, max_w: int) -> str:
        try:
            if font.size(text)[0] <= max_w:
                return text
        except Exception:
            return text
        ell = '...'
        lo, hi = 0, len(text)
        best = text
        while lo < hi:
            mid = (lo + hi) // 2
            cand = text[:mid].rstrip() + ell
            try:
                if font.size(cand)[0] <= max_w:
                    best = cand
                    lo = mid + 1
                else:
                    hi = mid
            except Exception:
                break
        return best

    # Helper: wrap item names into up to two centered lines within max width
    def wrap_name_lines(text: str, font: pygame.font.Font, max_w: int, max_lines: int = 2):
        words = (text or "").split()
        if not words:
            return [""]
        lines = []
        i = 0
        while i < len(words) and len(lines) < max_lines:
            cur = words[i]
            i += 1
            while i < len(words):
                test = cur + " " + words[i]
                try:
                    fits = font.size(test)[0] <= max_w
                except Exception:
                    fits = True
                if fits:
                    cur = test
                    i += 1
                else:
                    break
            lines.append(cur)
            if len(lines) == max_lines and i < len(words):
                rest = " ".join([lines[-1]] + words[i:])
                lines[-1] = ellipsize(rest, font, max_w)
                break
        return lines

    while True:
        # reset click state each frame so old clicks don't persist
        clicked_pos = None
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return ("menu", None)
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return ("resume", None)
                if ev.key == pygame.K_TAB:
                    # toggle focused row
                    focused_row = "armors" if focused_row == "weapons" else "weapons"
                if ev.key == pygame.K_RIGHT:
                    # move selection in focused row
                    if focused_row == "weapons":
                        weapons_selected = min(len(weapons)-1, weapons_selected+1)
                    else:
                        armors_selected = min(len(armors)-1, armors_selected+1)
                if ev.key == pygame.K_LEFT:
                    if focused_row == "weapons":
                        weapons_selected = max(0, weapons_selected-1)
                    else:
                        armors_selected = max(0, armors_selected-1)
            if ev.type == pygame.MOUSEBUTTONDOWN:
                # only treat left-click as selection/click
                if ev.button == 1:
                    if back_rect.collidepoint(ev.pos):
                        # NEW: click SFX on back button
                        try: sounds.play_sfx('SelectSound')
                        except Exception: pass
                        return ("resume", None)
                    # record click position for later per-row handling
                    clicked_pos = ev.pos
                # allow horizontal scroll with wheel
                if ev.button == 4:  # wheel up
                    weapons_offset += 40
                    armors_offset += 40
                if ev.button == 5:  # wheel down
                    weapons_offset -= 40
                    armors_offset -= 40

                # other buttons ignored for click selection

        # clamp scrolling so user can't scroll too far
        max_scroll = max(0, (len(weapons) * (item_w + spacing)) - (sw - margin_x*2))
        weapons_offset = max(-max_scroll, min(0, weapons_offset))
        armors_offset = max(-max_scroll, min(0, armors_offset))

        screen_surface.blit(blurred, (0,0))
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0,0,0,140))
        screen_surface.blit(overlay, (0,0))

        # draw coin panel in the top-right corner
        coin_panel = pygame.Rect(sw - 220, 12, 200, 48)
        try:
            pygame.draw.rect(screen_surface, (40,40,40), coin_panel)
            pygame.draw.rect(screen_surface, (120,120,120), coin_panel, 2)
            # blit coin image at left side of the panel
            screen_surface.blit(coin_img, (coin_panel.left + 8, coin_panel.top + (coin_panel.height - coin_img.get_height())//2))
            coin_font = get_font(20)
            coin_surf = coin_font.render(f"{coins}", True, (212,175,55))
            screen_surface.blit(coin_surf, coin_surf.get_rect(midleft=(coin_panel.left + 56, coin_panel.centery)))
        except Exception:
            # defensive: ignore coin panel drawing errors
            pass

        panel_w, panel_h = sw - 160, sh - 160
        panel = pygame.Rect((80, 80, panel_w, panel_h))
        pygame.draw.rect(screen_surface, (30,30,30), panel)
        pygame.draw.rect(screen_surface, (120,120,120), panel, 3)

        title_surf = title_f.render("Shop", True, (220,220,220))
        screen_surface.blit(title_surf, title_surf.get_rect(center=(sw//2, panel.top + 36)))

        # draw weapons row
        # moved weapons row a bit down so it has breathing room
        y_weapons = panel.top + 120
        # compute available visible area and center rows when content is narrower
        visible_left = panel.left + margin_x
        visible_w = panel_w - margin_x*2
        total_weapons_w = max(0, len(weapons) * (item_w + spacing) - spacing)
        if total_weapons_w < visible_w:
            x_start_weapons = panel.left + (panel_w - total_weapons_w) // 2
        else:
            x_start_weapons = panel.left + margin_x
        # same for armors (computed later), default x_start for weapons usage below:
        x_start = x_start_weapons

        # center the "Weapons" label above the row
        w_label = item_f.render("Weapons", True, (200,200,200))
        screen_surface.blit(w_label, w_label.get_rect(center=(panel.left + panel_w//2, y_weapons - 22)))

        # left/right arrow rects for weapons
        # arrows: larger and vertically centered on the item boxes, slightly inset horizontally
        w_left_rect = pygame.Rect(panel.left + 24, y_weapons + (item_w - arrow_h)//2, arrow_w, arrow_h)
        w_right_rect = pygame.Rect(panel.right - 24 - arrow_w, y_weapons + (item_w - arrow_h)//2, arrow_w, arrow_h)
        pygame.draw.rect(screen_surface, (80,80,80), w_left_rect)
        pygame.draw.rect(screen_surface, (80,80,80), w_right_rect)
        screen_surface.blit(item_f.render("<", True, (220,220,220)), (w_left_rect.left+12, w_left_rect.top+6))
        screen_surface.blit(item_f.render(">", True, (220,220,220)), (w_right_rect.left+12, w_right_rect.top+6))

        for i, name in enumerate(weapons):
            x = x_start_weapons + i * (item_w + spacing) + weapons_offset
            item_rect = pygame.Rect(x, y_weapons, item_w, 120)
             # only draw if visible
            if item_rect.right >= panel.left + 10 and item_rect.left <= panel.right - 10:
                pygame.draw.rect(screen_surface, (50,50,50), item_rect)
                img = weapons_imgs.get(name, sword_img)
                try:
                    screen_surface.blit(img, img.get_rect(center=item_rect.center))
                except Exception:
                    screen_surface.blit(sword_img, sword_img.get_rect(center=item_rect.center))
                # Draw name in up to two lines
                try:
                    max_name_w = item_w + 16
                    name_lines = wrap_name_lines(name, item_f, max_name_w, 2)
                    line_h = item_f.get_linesize()
                    start_y = item_rect.bottom + 6
                    for j, line in enumerate(name_lines):
                        nm = item_f.render(line, True, (220,220,220))
                        screen_surface.blit(nm, nm.get_rect(midtop=(item_rect.centerx, start_y + j * (line_h + 2))))
                except Exception:
                    nm = item_f.render(name, True, (220,220,220))
                    screen_surface.blit(nm, nm.get_rect(midtop=(item_rect.centerx, item_rect.bottom + 8)))

                # show upgrade level if purchased
                lvl = weapons_upgrades.get(name, 0)
                try:
                    lvl_font = get_font(12)
                    lvl_text = lvl_font.render(f"Lv {lvl}", True, (200,200,120))
                    screen_surface.blit(lvl_text, (item_rect.right - lvl_text.get_width() - 6, item_rect.top + 6))
                except Exception:
                    pass

                # dim/lock overlay for items not purchased
                if name not in weapons_purchased:
                    try:
                        lock_s = pygame.Surface((item_rect.width, item_rect.height), pygame.SRCALPHA)
                        lock_s.fill((0,0,0,160))
                        screen_surface.blit(lock_s, item_rect.topleft)
                        lock_font = get_font(14)
                        lock_surf = lock_font.render("Locked", True, (180,80,80))
                        screen_surface.blit(lock_surf, lock_surf.get_rect(center=item_rect.center))
                    except Exception:
                        pygame.draw.rect(screen_surface, (30,30,30), item_rect)

             # outline equipped (green) always; outline focused selection (gold) only when row focused
            if weapons_equipped == i:
                pygame.draw.rect(screen_surface, (0,200,0), item_rect, 3)
            elif i == weapons_selected and focused_row == "weapons":
                pygame.draw.rect(screen_surface, (255,220,80), item_rect, 3)

        # handle clicks on weapon arrows/items
        if clicked_pos:
            mx,my = clicked_pos
            if w_left_rect.collidepoint((mx,my)):
                weapons_selected = max(0, weapons_selected-1)
                focused_row = "weapons"
                # NEW: click SFX
                try: sounds.play_sfx('SelectSound')
                except Exception: pass
            elif w_right_rect.collidepoint((mx,my)):
                weapons_selected = min(len(weapons)-1, weapons_selected+1)
                focused_row = "weapons"
                # NEW: click SFX
                try: sounds.play_sfx('SelectSound')
                except Exception: pass
            else:
                # item clicks
                for i in range(len(weapons)):
                    x = x_start_weapons + i * (item_w + spacing) + weapons_offset
                    item_rect = pygame.Rect(x, y_weapons, item_w, 120)
                    if item_rect.collidepoint((mx,my)):
                        weapons_selected = i
                        focused_row = "weapons"
                        # NEW: click SFX on opening item page
                        try: sounds.play_sfx('SelectSound')
                        except Exception: pass
                        # open item detail page
                        try:
                            res = show_item_page(weapons[i], weapons_imgs.get(weapons[i], sword_img))
                            # persist purchase/equip if requested
                            if res and res[0] == "equip":
                                weapons_purchased.add(res[1])
                                try:
                                    idx = weapons.index(res[1])
                                    weapons_equipped = idx
                                except Exception:
                                    pass
                            # handle upgrade action
                            if res and res[0] == "upgrade":
                                try:
                                    cur = weapons_upgrades.get(res[1], 0)
                                    weapons_upgrades[res[1]] = min(3, cur + 1)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        clicked_pos = None  # NEW: clear click so it doesn't re-trigger
                        break

        # draw armors row
        y_armors = y_weapons + row_gap
        # center the "Armor" label above the armor row
        a_label = item_f.render("Armors", True, (200,200,200))
        # slightly lower the label so there's clearer space from the weapons row
        screen_surface.blit(a_label, a_label.get_rect(center=(panel.left + panel_w//2, y_armors - 20)))

        # left/right arrow rects for armors
        # armor arrows also centered vertically relative to armor box
        a_left_rect = pygame.Rect(panel.left + 24, y_armors + (item_w - arrow_h)//2, arrow_w, arrow_h)
        a_right_rect = pygame.Rect(panel.right - 24 - arrow_w, y_armors + (item_w - arrow_h)//2, arrow_w, arrow_h)
        pygame.draw.rect(screen_surface, (80,80,80), a_left_rect)
        pygame.draw.rect(screen_surface, (80,80,80), a_right_rect)
        screen_surface.blit(item_f.render("<", True, (220,220,220)), (a_left_rect.left+12, a_left_rect.top+6))
        screen_surface.blit(item_f.render(">", True, (220,220,220)), (a_right_rect.left+12, a_right_rect.top+6))

        # compute armors x_start (center when narrow)
        total_armors_w = max(0, len(armors) * (item_w + spacing) - spacing)
        if total_armors_w < visible_w:
            x_start_armors = panel.left + (panel_w - total_armors_w) // 2
        else:
            x_start_armors = panel.left + margin_x

        for i, name in enumerate(armors):
            x = x_start_armors + i * (item_w + spacing) + armors_offset
            item_rect = pygame.Rect(x, y_armors, item_w, 120)
            if item_rect.right >= panel.left + 10 and item_rect.left <= panel.right - 10:
                pygame.draw.rect(screen_surface, (50,50,50), item_rect)
                screen_surface.blit(sword_img, sword_img.get_rect(center=item_rect.center))
                pygame.draw.rect(screen_surface, (0,200,0), item_rect, 3)
            elif i == armors_selected and focused_row == "armors":
                pygame.draw.rect(screen_surface, (255,220,80), item_rect, 3)

        # handle clicks on armor arrows/items
        if clicked_pos:
            mx,my = clicked_pos
            if a_left_rect.collidepoint((mx,my)):
                armors_selected = max(0, armors_selected-1)
                focused_row = "armors"
                # NEW: click SFX
                try: sounds.play_sfx('SelectSound')
                except Exception: pass
            elif a_right_rect.collidepoint((mx,my)):
                armors_selected = min(len(armors)-1, armors_selected+1)
                focused_row = "armors"
                # NEW: click SFX
                try: sounds.play_sfx('SelectSound')
                except Exception: pass
            else:
                for i in range(len(armors)):
                    x = x_start_armors + i * (item_w + spacing) + armors_offset
                    item_rect = pygame.Rect(x, y_armors, item_w, 120)
                    if item_rect.collidepoint((mx,my)):
                        armors_selected = i
                        focused_row = "armors"
                        # NEW: click SFX on opening item page
                        try: sounds.play_sfx('SelectSound')
                        except Exception: pass
                        # open item detail page (armor uses same placeholder image)
                        try:
                            res = show_item_page(armors[i], sword_img)
                            if res and res[0] == "equip":
                                armors_purchased.add(res[1])
                                try:
                                    idx = armors.index(res[1])
                                    armors_equipped = idx
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        clicked_pos = None
                        break

        # center offsets on selection so focused selected item is visible
        # compute desired offsets to center selected item
        visible_left = panel.left + margin_x
        visible_w = panel_w - margin_x*2
        if focused_row == "weapons":
            targ_x = x_start_weapons + weapons_selected * (item_w + spacing)
            desired = visible_left + (visible_w - item_w)//2
            weapons_offset = desired - targ_x
        else:
            targ_x = x_start_armors + armors_selected * (item_w + spacing)
            desired = visible_left + (visible_w - item_w)//2
            armors_offset = desired - targ_x

        # clamp again after centering using per-row scroll limits
        max_scroll_weapons = max(0, total_weapons_w - visible_w)
        max_scroll_armors = max(0, total_armors_w - visible_w)
        weapons_offset = max(-max_scroll_weapons, min(0, weapons_offset))
        armors_offset = max(-max_scroll_armors, min(0, armors_offset))

        # Description preview box at the bottom of the panel for the highlighted item.
        # Place it above the Back button to avoid overlap.
        desc_panel_h = 72
        desc_panel_top = max(panel.top + 120, back_rect.top - 12 - desc_panel_h)
        desc_panel = pygame.Rect(panel.left + 20, desc_panel_top, panel_w - 40, desc_panel_h)
        pygame.draw.rect(screen_surface, (24,24,24), desc_panel)
        pygame.draw.rect(screen_surface, (100,100,100), desc_panel, 2)
        # determine highlighted item (by focused_row)
        if focused_row == "weapons":
            cur_name = weapons[weapons_selected] if 0 <= weapons_selected < len(weapons) else ""
        else:
            cur_name = armors[armors_selected] if 0 <= armors_selected < len(armors) else ""
        # use same resolver as modal so preview and modal match
        cur_desc = resolve_desc(cur_name)
        # render wrapped description inside desc_panel with spacing between name and description
        wrap_font = get_font(16)
        def wrap_text_local(text: str, font: pygame.font.Font, max_w: int):
            words = text.split()
            if not words:
                return []
            lines = []
            cur = words[0]
            for w in words[1:]:
                test = cur + " " + w
                if font.size(test)[0] <= max_w:
                    cur = test
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
            return lines
        pad = 10
        # draw item name first (top of desc panel)
        name_font = get_font(18)
        name_s = name_font.render(cur_name, True, (200,200,120))
        screen_surface.blit(name_s, (desc_panel.left + pad, desc_panel.top + 6))
        # compute description start below the name with extra spacing
        desc_start_y = desc_panel.top + 6 + name_font.get_linesize() + 6
        max_w = desc_panel.width - pad*2
        lines = wrap_text_local(cur_desc, wrap_font, max_w)
        for i, ln in enumerate(lines[:3]):  # limit to 3 lines
            surf = wrap_font.render(ln, True, (210,210,210))
            screen_surface.blit(surf, (desc_panel.left + pad, desc_start_y + i * (wrap_font.get_linesize() + 2)))

        # back button
        pygame.draw.rect(screen_surface, (200,200,200), back_rect)
        back_color = (0,200,0) if back_rect.collidepoint(pygame.mouse.get_pos()) else (0,0,0)
        screen_surface.blit(btn_f.render("Back", True, back_color), btn_f.render("Back", True, back_color).get_rect(center=back_rect.center))

        pygame.display.update()
        clock_local.tick(60)

def show_difficulty(snapshot, screen_surface):
    """Modal to pick difficulty. Returns 'easy'|'normal'|'hard' or None if cancelled."""
    sw, sh = screen_surface.get_size()
    # make blurred background from snapshot if provided
    if snapshot:
        try:
            small = pygame.transform.smoothscale(snapshot, (max(1, sw//12), max(1, sh//12)))
            bg = pygame.transform.smoothscale(small, (sw, sh))
        except Exception:
            bg = load_background("Background", (sw, sh))
    else:
        bg = load_background("Background", (sw, sh))

    title_f = get_font(44)
    desc_f = get_font(18)
    clock_local = pygame.time.Clock()
    # preload select sound (idempotent)
    try:
        sounds.preload('SelectSound')
    except Exception:
        pass
    # adaptive panel size so things fit on small screens
    panel_w = min(900, max(520, sw - 160))
    panel_h = min(420, max(280, int(sh * 0.36)))
    panel = pygame.Rect((sw-panel_w)//2, (sh-panel_h)//2, panel_w, panel_h)

    # horizontal layout for three options
    padding_x = 36
    padding_y = 48
    inner_w = panel_w - padding_x*2
    spacing = 20
    btn_w = int((inner_w - spacing*2) / 3)
    btn_h = 64
    btn_y = panel.top + padding_y + 40

    left_x = panel.left + padding_x
    easy_r = pygame.Rect(left_x, btn_y, btn_w, btn_h)
    normal_r = pygame.Rect(left_x + (btn_w + spacing) * 1, btn_y, btn_w, btn_h)
    hard_r = pygame.Rect(left_x + (btn_w + spacing) * 2, btn_y, btn_w, btn_h)

    # desired presentation: show heart icons and show XP multiplier as gold under hearts
    diff_hearts = {"easy": 4, "normal": 3, "hard": 1}
    diff_xp = {"easy": 0.75, "normal": 1.0, "hard": 2.0}
    # try to load heart sprite (fallback to a drawn square if missing)
    heart_img = None
    try:
        base = Path(__file__).parent
        p = base.joinpath("sprites", "heart_1.png")
        if p.exists():
            heart_img = pygame.image.load(str(p)).convert_alpha()
            heart_img = pygame.transform.smoothscale(heart_img, (28, 28))
    except Exception:
        heart_img = None
    if heart_img is None:
        heart_img = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.polygon(heart_img, (200,50,50), [(14,4),(26,12),(14,26),(2,12)])

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    return None
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if easy_r.collidepoint((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    return "easy"
                if normal_r.collidepoint((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    return "normal"
                if hard_r.collidepoint((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    return "hard"

        # draw
        screen_surface.blit(bg, (0,0))
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen_surface.blit(overlay, (0,0))

        pygame.draw.rect(screen_surface, (28,28,28), panel)
        pygame.draw.rect(screen_surface, (140,140,140), panel, 3)
        title_s = title_f.render("Choose Difficulty", True, (220,220,220))
        screen_surface.blit(title_s, title_s.get_rect(center=(sw//2, panel.top + 34)))

        # draw buttons
        pygame.draw.rect(screen_surface, (200,200,200), easy_r)
        pygame.draw.rect(screen_surface, (200,200,200), normal_r)
        pygame.draw.rect(screen_surface, (200,200,200), hard_r)

        mouse = pygame.mouse.get_pos()
        e_col = (0,200,0) if easy_r.collidepoint(mouse) else (0,0,0)
        n_col = (0,200,0) if normal_r.collidepoint(mouse) else (0,0,0)
        h_col = (0,200,0) if hard_r.collidepoint(mouse) else (0,0,0)

        screen_surface.blit(desc_f.render("Easy", True, e_col), desc_f.render("Easy", True, e_col).get_rect(center=easy_r.center))
        screen_surface.blit(desc_f.render("Normal", True, n_col), desc_f.render("Normal", True, n_col).get_rect(center=normal_r.center))
        screen_surface.blit(desc_f.render("Hard", True, h_col), desc_f.render("Hard", True, h_col).get_rect(center=hard_r.center))

        # render heart icons (centered) and XP multiplier under hearts (gold color)
        def draw_hearts_and_xp(centerx, count, xp_val):
            # hearts row
            spacing_h = 6
            total_w = count * heart_img.get_width() + max(0, count-1) * spacing_h
            start_x = int(centerx - total_w / 2)
            y_hearts = btn_y + btn_h + 8
            for i in range(count):
                hx = start_x + i * (heart_img.get_width() + spacing_h)
                screen_surface.blit(heart_img, (hx, y_hearts))
            # xp text under hearts (gold)
            gold = (212, 175, 55)
            xp_font = get_font(16)
            xp_s = xp_font.render(f"{xp_val:.2f}x Points", True, gold)
            screen_surface.blit(xp_s, xp_s.get_rect(center=(centerx, y_hearts + heart_img.get_height() + 14)))

        draw_hearts_and_xp(easy_r.centerx, diff_hearts["easy"], diff_xp["easy"])
        draw_hearts_and_xp(normal_r.centerx, diff_hearts["normal"], diff_xp["normal"])
        draw_hearts_and_xp(hard_r.centerx, diff_hearts["hard"], diff_xp["hard"])

        # hint line at bottom
        hint_f = get_font(14)
        hint_s = hint_f.render("Press Esc to cancel", True, (160,160,160))
        screen_surface.blit(hint_s, hint_s.get_rect(center=(sw//2, panel.bottom - 22)))

        pygame.display.update()
        clock_local.tick(60)

# Menu background music helpers (added)
_menu_music_started = False

def _find_menu_music():
    base = Path(__file__).parent
    snd_dir = base.joinpath("sounds")
    if not snd_dir.exists():
        return None
    for ext in ("ogg", "mp3", "wav"):
        p = snd_dir.joinpath(f"MainMenuBGM.{ext}")
        if p.exists():
            return str(p)
    for name in ("menu_music", "menu_theme", "music_menu", "menu", "background"):
        for ext in ("ogg", "mp3", "wav"):
            p = snd_dir.joinpath(f"{name}.{ext}")
            if p.exists():
                return str(p)
    return None

def start_menu_music():
    global _menu_music_started
    if _menu_music_started:
        return
    try:
        path = _find_menu_music()
        if path:
            pygame.mixer.music.load(path)
            vol = getattr(sounds, 'MASTER_VOLUME', 1.0)
            pygame.mixer.music.set_volume(vol)
            pygame.mixer.music.play(-1)
            _menu_music_started = True
    except Exception:
        pass

def stop_menu_music():
    global _menu_music_started
    if not _menu_music_started:
        return
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    _menu_music_started = False

def run_menu():
    global SCREEN, SCREEN_W, SCREEN_H, is_fullscreen
    clock = pygame.time.Clock()
    # make fonts a bit smaller
    title_font = get_font(64)    # reduced from 80
    button_font = get_font(32)   # reduced from 40

    # short-lived toast timestamp (ms since pygame init); 0 == hidden
    saved_msg_until = 0

    # helper to (re)create background and buttons using current SCREEN size
    def create_assets():
        nonlocal background, buttons, btn_w, btn_h, btn_x, btn_y_start, btn_gap
        global SCREEN_W, SCREEN_H  # ensure globals are updated when we (re)create assets
        SCREEN_W, SCREEN_H = SCREEN.get_size()
        background = load_background("Background", (SCREEN_W, SCREEN_H))
        # Button layout (recompute positions for current size)
        btn_w, btn_h = 300, 60
        btn_x = (SCREEN_W - btn_w) // 2
        # shift start a little higher to fit 5 buttons
        btn_y_start = SCREEN_H // 2 - 2 * btn_h - 20
        btn_gap = 30
        buttons = [
            Button("PLAY",    (btn_x, btn_y_start + 0*(btn_h+btn_gap)), btn_w, btn_h, button_font, (200,255,200), (255,255,255)),
            Button("SHOP",    (btn_x, btn_y_start + 1*(btn_h+btn_gap)), btn_w, btn_h, button_font, (200,255,200), (255,255,255)),
            Button("OPTIONS", (btn_x, btn_y_start + 2*(btn_h+btn_gap)), btn_w, btn_h, button_font, (200,255,200), (255,255,255)),
            Button("SAVE",    (btn_x, btn_y_start + 3*(btn_h+btn_gap)), btn_w, btn_h, button_font, (200,255,200), (255,255,255)),  # NEW
            Button("QUIT",    (btn_x, btn_y_start + 4*(btn_h+btn_gap)), btn_w, btn_h, button_font, (200,255,200), (255,255,255)),
        ]
        # preload select sound (idempotent)
        try:
            sounds.preload('SelectSound')
        except Exception:
            pass

    # initial assets
    background = None
    buttons = []
    btn_w = btn_h = btn_x = btn_y_start = btn_gap = 0
    create_assets()
    start_menu_music()  # start looping menu music

    def run_options(snapshot):
        return show_options(snapshot, SCREEN)

    # small helper to perform save and show toast
    def _do_save():
        nonlocal saved_msg_until
        try:
            # merge into existing save instead of overwriting (preserves weapons_owned, etc.)
            data = save.load_player_data() or {}
            data["coins"] = PLAYER_COINS
            data["master_volume"] = getattr(sounds, 'MASTER_VOLUME', 1.0)
            data["resolution"] = list(SCREEN.get_size())
            data["fullscreen"] = bool(is_fullscreen)
            # optional: ensure at least Sword is present (won't overwrite existing list)
            data.setdefault("weapons_owned", ["Sword"])
            save.save_player_data(data)
            try:
                sounds.play_sfx('SelectSound')
            except Exception:
                pass
            # show toast for 1.2s regardless of success; optionally could differentiate
            saved_msg_until = pygame.time.get_ticks() + 1200
        except Exception:
            # still show feedback
            saved_msg_until = pygame.time.get_ticks() + 1200

    while True:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_menu_music()
                pygame.quit()
                sys.exit()

            # toggle fullscreen/windowed with F11 (ensure we recreate assets after change)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                is_fullscreen = not is_fullscreen
                try:
                    info = pygame.display.Info()
                    if is_fullscreen:
                        SCREEN = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
                    else:
                        SCREEN = pygame.display.set_mode((1280, 720))
                except Exception:
                    # fallback: try toggle_fullscreen then recreate assets
                    try:
                        pygame.display.toggle_fullscreen()
                    except Exception:
                        pass
                # after mode change recreate background and buttons
                SCREEN_W, SCREEN_H = SCREEN.get_size()
                create_assets()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # use the click position from the event (avoid stale mouse_pos issues)
                mx, my = event.pos
                if buttons[0].is_clicked((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    try:
                        snap = SCREEN.copy()
                    except Exception:
                        snap = None
                    chosen = show_difficulty(snap, SCREEN)
                    if chosen is None:
                        pass
                    else:
                        stop_menu_music()  # stop before entering game
                        import main
                        main.run_game(SCREEN, difficulty=chosen)
                        start_menu_music()  # resume after returning from game
                    create_assets()
                elif buttons[1].is_clicked((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    try:
                        snap = SCREEN.copy()
                    except Exception:
                        snap = None
                    res = show_shop(snap, SCREEN)
                    if res and res[0] == "menu":
                        stop_menu_music()
                        return
                elif buttons[2].is_clicked((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    opt_res = run_options(background)
                    if opt_res and opt_res[0] == "resolution_changed":
                        new_size = opt_res[1]
                        is_fullscreen = False
                        SCREEN = pygame.display.set_mode(new_size)
                        SCREEN_W, SCREEN_H = SCREEN.get_size()
                        create_assets()
                elif buttons[3].is_clicked((mx, my)):
                    # NEW: SAVE
                    _do_save()
                elif buttons[4].is_clicked((mx, my)):
                    try:
                        sounds.play_sfx('SelectSound')
                    except Exception:
                        pass
                    stop_menu_music()
                    pygame.quit()
                    sys.exit()
        # draw background and grey square border
        SCREEN.blit(background, (0, 0))
        border_margin = 20
        # align border with the current screen size each frame
        screen_rect = SCREEN.get_rect()
        border_rect = screen_rect.inflate(-2*border_margin, -2*border_margin)
        pygame.draw.rect(SCREEN, (120, 120, 120), border_rect, 8)

        # Title
        title_surf = title_font.render("Descend", True, (182, 143, 64))
        SCREEN.blit(title_surf, title_surf.get_rect(center=(SCREEN_W//2, SCREEN_H//4)))

        # Buttons
        for btn in buttons:
            btn.update(mouse_pos)
            btn.draw(SCREEN)

        # NEW: brief "Saved!" toast near bottom-center when save is triggered
        if saved_msg_until > 0 and pygame.time.get_ticks() < saved_msg_until:
            try:
                toast_font = get_font(20)
                msg = toast_font.render("Saved!", True, (0, 0, 0))
                pad_x, pad_y = 14, 8
                box = pygame.Surface((msg.get_width()+pad_x*2, msg.get_height()+pad_y*2), pygame.SRCALPHA)
                box.fill((220, 220, 220, 220))
                # place toast at bottom-right to avoid covering centered buttons
                margin = 24
                bx = max(0, SCREEN_W - box.get_width() - margin)
                by = max(0, SCREEN_H - box.get_height() - margin)
                SCREEN.blit(box, (bx, by))
                SCREEN.blit(msg, (bx+pad_x, by+pad_y))
            except Exception:
                pass

        pygame.display.update()
        clock.tick(60)   # limit to 60 FPS
