import pygame
import math
import random
from typing import Callable, List, Optional, Tuple, Dict
from pathlib import Path

class Enemy:
    """Chasing enemy with optional directional animations."""
    def __init__(
        self,
        x: float,
        y: float,
        size: int,
        speed: float = 1.5,
        hp: int = 1,
        sprites: Optional[Dict[str, List[pygame.Surface]]] = None,
        can_jump_lava: bool = False,  # new: whether this enemy can jump over lava
        can_fly: bool = False,        # new: can pass over walls/lava (ghost)
        can_cast: bool = False,       # new: whether enemy can cast projectiles (mage)
        cast_cooldown: int = 1000,    # ms between casts
        projectile_speed: float = 3.0, # projectile travel speed (pixels/frame scale)
        cast_stop_distance: int = 120  # pixels: mage will stop when within this distance to player
    ):
        self.x = x
        self.y = y
        self.size = size
        self.speed = speed
        self.hp = hp
        self.sprites = sprites  # dict: "up","down","left","right","idle" -> list[Surface]
        self.frame = 0
        self.frame_timer = 0
        self.frame_delay = 150  # ms per frame
        self.alive = True
        self.facing = "idle"
        self.group: Optional[List["Enemy"]] = None  # optional reference set by spawn_enemies
        self.can_jump_lava = can_jump_lava  # store flag
        self.can_fly = can_fly  # flying ignores walkable checks

        # casting (mage) state
        self.can_cast = can_cast
        self.cast_cooldown = cast_cooldown
        self.cast_timer = random.randint(0, cast_cooldown)  # stagger initial casts slightly
        self.projectile_speed = projectile_speed
        self.projectiles: List[Dict[str, float]] = []  # each: {'x','y','vx','vy','speed'}
        self.cast_stop_distance = cast_stop_distance

        # prejump state: when true the enemy displays the jump sprite for a short time
        # before performing the actual jump to the landing spot.
        self.prejumping = False
        self.prejump_timer = 0
        self.prejump_duration = 500  # ms to show the "about to jump" sprite
        self._landing: Optional[Tuple[float, float]] = None

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.size, self.size)

    def take_damage(self, amount: int = 1) -> None:
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False

    def update(
        self,
        dt: int,
        player_pos: Tuple[int, int],
        is_walkable: Callable[[float, float], bool],
        on_trap: Optional[Callable[[int, int], bool]] = None,
        is_lava: Optional[Callable[[float, float], bool]] = None  # new optional callback
    ) -> None:
        if not self.alive:
            return

        px, py = player_pos
        cx = self.x + self.size / 2
        cy = self.y + self.size / 2
        dx = px - cx
        dy = py - cy
        dist = math.hypot(dx, dy)
        if dist > 1:
            nx = dx / dist
            ny = dy / dist
        else:
            nx = ny = 0.0
        # keep original normalized direction for facing (don't overwrite later)
        orig_nx, orig_ny = nx, ny

        # If currently in prejump state, count down and land when timer ends.
        if self.prejumping:
            self.prejump_timer -= dt
            if self.prejump_timer <= 0:
                # attempt landing if recorded and still walkable
                if self._landing and is_walkable(self._landing[0], self._landing[1]):
                    self.x, self.y = self._landing
                # reset prejump state regardless (landing failed -> fallback next frames)
                self.prejumping = False
                self.prejump_timer = 0
                self._landing = None
            # while prejumping we don't perform normal movement this frame
        else:
            move = self.speed * (dt / 16.0)
            # mage: if within stop distance, don't move toward player (prevent bumping)
            if self.can_cast and dist <= self.cast_stop_distance:
                move = 0.0
            target_x = self.x + nx * move
            target_y = self.y + ny * move

            # Flying enemies (ghosts) ignore walkable checks and move freely
            if self.can_fly:
                self.x = target_x
                self.y = target_y
            else:
                # If target spot is directly walkable, move normally
                if is_walkable(target_x, target_y):
                    self.x = target_x
                    self.y = target_y
                else:
                    jumped = False
                    # special-case: try to jump over lava if enemy supports it
                    if self.can_jump_lava and is_lava is not None and (abs(nx) > 1e-4 or abs(ny) > 1e-4):
                        # sample along the movement ray to find lava regions that intersect the slime's body,
                        # then pick a landing point beyond the lava. Sample several lateral offsets so approaches
                        # from any angle are detected (not just when the center goes over lava).
                        cx_center = self.x + self.size / 2
                        cy_center = self.y + self.size / 2
                        STEP = max(8, int(self.size / 2))          # sampling increment (pixels)
                        MAX_DIST = max(48, int(self.size)) * 6     # how far ahead we'll search
                        samples = max(1, int(MAX_DIST / STEP))

                        # lateral offsets to check across slime width (center, left, right)
                        half = self.size / 2
                        # offsets in pixels across the slime; these will be applied along the perpendicular
                        lateral_offsets = [-half + 4, 0, half - 4]
                        # perpendicular unit vector to (nx, ny)
                        perp_x = -ny
                        perp_y = nx

                        # find first lava sample along ray where ANY lateral offset hits lava
                        first_lava_idx = None
                        for i in range(1, samples + 1):
                            sx = cx_center + nx * STEP * i
                            sy = cy_center + ny * STEP * i
                            hit = False
                            for ox in lateral_offsets:
                                lx = sx + perp_x * ox
                                ly = sy + perp_y * ox
                                if is_lava(lx, ly):
                                    hit = True
                                    break
                            if hit:
                                first_lava_idx = i
                                break

                        if first_lava_idx is not None:
                            # find end of contiguous lava region (based on any lateral hit)
                            end_idx = first_lava_idx
                            for j in range(first_lava_idx + 1, samples + 1):
                                sx = cx_center + nx * STEP * j
                                sy = cy_center + ny * STEP * j
                                hit = False
                                for ox in lateral_offsets:
                                    lx = sx + perp_x * ox
                                    ly = sy + perp_y * ox
                                    if is_lava(lx, ly):
                                        hit = True
                                        break
                                if not hit:
                                    end_idx = j
                                    break

                            # try candidate landing sample indices a bit beyond the lava end
                            min_extra = max(1, int(self.size / STEP))
                            max_extra = min(8, samples - end_idx)
                            TILE_SEARCH = max(48, int(self.size))  # use tile-sized steps when searching nearby
                            found = False
                            for extra in range(min_extra, max_extra + 1):
                                k = end_idx + extra
                                # primary candidate center
                                base_cx = cx_center + nx * STEP * k
                                base_cy = cy_center + ny * STEP * k

                                # try a small 3x3 grid of offsets around the base candidate (helps on tight maps)
                                for ox_mult in (-1, 0, 1):
                                    for oy_mult in (-1, 0, 1):
                                        landing_cx = base_cx + ox_mult * TILE_SEARCH
                                        landing_cy = base_cy + oy_mult * TILE_SEARCH
                                        landing_x = landing_cx - self.size / 2
                                        landing_y = landing_cy - self.size / 2

                                        # landing must not be lava across lateral offsets and must be walkable
                                        bad = False
                                        for lo in lateral_offsets:
                                            lx = landing_cx + perp_x * lo
                                            ly = landing_cy + perp_y * lo
                                            if is_lava(lx, ly):
                                                bad = True
                                                break
                                        if bad:
                                            continue
                                        if not is_walkable(landing_x, landing_y):
                                            continue

                                        # ensure path between current position and landing does not cross a wall:
                                        blocked = False
                                        for m in range(1, k + 1):
                                            sx = cx_center + nx * STEP * m
                                            sy = cy_center + ny * STEP * m
                                            for lo in lateral_offsets:
                                                sample_x = sx + perp_x * lo
                                                sample_y = sy + perp_y * lo
                                                sample_tl_x = sample_x - self.size / 2
                                                sample_tl_y = sample_y - self.size / 2
                                                # if sample is not lava and not walkable => it's blocked by wall/obstacle
                                                if (not is_lava(sample_x, sample_y)) and (not is_walkable(sample_tl_x, sample_tl_y)):
                                                    blocked = True
                                                    break
                                            if blocked:
                                                break
                                        if blocked:
                                            continue

                                        # found a safe landing
                                        self.prejumping = True
                                        self.prejump_timer = self.prejump_duration
                                        self._landing = (landing_x, landing_y)
                                        found = True
                                        break
                                    if found:
                                        break
                                if found:
                                    break
                            # if none found, fallback behaviour below will apply
                if not self.prejumping:
                    # fallback behaviour: try axis-separated moves as before
                    if is_walkable(target_x, self.y):
                        self.x = target_x
                    elif is_walkable(self.x, target_y):
                        self.y = target_y

        # Enemies ignore traps (no damage/knockback)

        # Simple separation to avoid stacking (gentle, respects map)
        if self.group:
            sep = self.size * 0.6
            push_x = 0.0
            push_y = 0.0
            for other in self.group:
                if other is self or not other.alive:
                    continue
                dxo = (self.x + self.size / 2) - (other.x + other.size / 2)
                dyo = (self.y + self.size / 2) - (other.y + other.size / 2)
                d = math.hypot(dxo, dyo)
                if d < 1e-4:
                    ang = random.random() * 2 * math.pi
                    dxo = math.cos(ang) * 0.1
                    dyo = math.sin(ang) * 0.1
                    d = math.hypot(dxo, dyo)
                if d < sep:
                    overlap = sep - d
                    # avoid dividing by zero defensively
                    if d != 0:
                        push_x += (dxo / d) * overlap * 0.3
                        push_y += (dyo / d) * overlap * 0.3
            if abs(push_x) > 0.0001 or abs(push_y) > 0.0001:
                nxpos = self.x + push_x
                nypos = self.y + push_y
                if is_walkable(nxpos, nypos):
                    self.x = nxpos
                    self.y = nypos
                else:
                    if is_walkable(nxpos, self.y):
                        self.x = nxpos
                    elif is_walkable(self.x, nypos):
                        self.y = nypos

        # determine facing
        # use original direction for facing so stopped mages still face player
        if abs(orig_nx) < 1e-3 and abs(orig_ny) < 1e-3:
            new_facing = "idle"
        else:
            if abs(orig_nx) > abs(orig_ny):
                new_facing = "left" if orig_nx < 0 else "right"
            else:
                new_facing = "up" if orig_ny < 0 else "down"

        if new_facing != self.facing:
            self.facing = new_facing
            self.frame = 0
            self.frame_timer = 0

        # animate
        if self.sprites:
            if isinstance(self.sprites, dict):
                frames = self.sprites.get(self.facing) or self.sprites.get("down") or []
            else:
                frames = list(self.sprites)
            if len(frames) > 1:
                self.frame_timer += dt
                if self.frame_timer >= self.frame_delay:
                    self.frame_timer = 0
                    self.frame = (self.frame + 1) % len(frames)

        # --- casting / projectiles update (runs every frame) ---
        if self.can_cast:
            # advance cast timer and spawn toward player when ready
            self.cast_timer -= dt
            if self.cast_timer <= 0:
                # spawn projectile toward player center
                pc_x = self.x + self.size / 2
                pc_y = self.y + self.size / 2
                px, py = player_pos
                vx = px - pc_x
                vy = py - pc_y
                vd = math.hypot(vx, vy)
                if vd > 1e-4:
                    vx /= vd
                    vy /= vd
                    self.projectiles.append({
                        'x': pc_x,
                        'y': pc_y,
                        'vx': vx,
                        'vy': vy,
                        'speed': self.projectile_speed
                    })
                self.cast_timer = self.cast_cooldown

            # move projectiles and prune on collision/invalid
            pruned: List[Dict[str, float]] = []
            for p in self.projectiles:
                # move scaled similar to other movement
                p['x'] += p['vx'] * p['speed'] * (dt / 16.0)
                p['y'] += p['vy'] * p['speed'] * (dt / 16.0)
                # simple collision: if projectile point is inside a non-walkable tile, drop it
                # but allow projectiles to pass over lava tiles (use is_lava callback)
                sample_x = p['x'] - (self.size * 0.1)
                sample_y = p['y'] - (self.size * 0.1)
                try:
                    walk_ok = is_walkable(sample_x, sample_y)
                    if walk_ok:
                        # normal free tile -> keep projectile
                        pruned.append(p)
                    else:
                        # not walkable: allow the projectile to continue if that tile is lava
                        if is_lava is not None and is_lava(p['x'], p['y']):
                            pruned.append(p)
                        # otherwise projectile hit a wall/out-of-bounds -> drop (do not append)
                except Exception:
                    # defensive: if callback fails, drop the projectile by default (skip appending)
                    pass
            self.projectiles = pruned

    def draw(self, surface: pygame.Surface, offset_x: int = 0, offset_y: int = 0) -> None:
        if not self.alive or not self.sprites:
            return
        # if currently prejumping and we have a 'jump' sprite, show it
        if self.prejumping and isinstance(self.sprites, dict) and "jump" in self.sprites:
            frames = self.sprites.get("jump") or []
            if not frames:
                return
            img = frames[self.frame % len(frames)]
        else:
            if isinstance(self.sprites, dict):
                frames = self.sprites.get(self.facing) or self.sprites.get("down") or []
                if not frames:
                    return
                img = frames[self.frame % len(frames)]
            else:
                frames = list(self.sprites)
                if not frames:
                    return
                img = frames[self.frame % len(frames)]
        surface.blit(img, (int(self.x) + offset_x, int(self.y) + offset_y))

        # draw projectiles (if any) — use image when available, otherwise fallback to circle
        if self.can_cast and self.projectiles:
            proj_img = getattr(self, "projectile_img", None)
            for p in self.projectiles:
                px = int(p['x']) + offset_x
                py = int(p['y']) + offset_y
                if proj_img:
                    rect = proj_img.get_rect(center=(px, py))
                    surface.blit(proj_img, rect.topleft)
                else:
                    pygame.draw.circle(surface, (160, 80, 255), (px, py), max(3, int(self.size * 0.12)))


def load_enemy_sprites(direction_files: Dict[str, List[str]], size: int) -> Dict[str, List[pygame.Surface]]:
    base = Path(__file__).parent
    sprites_dir = base.joinpath("sprites")
    out: Dict[str, List[pygame.Surface]] = {}
    for direction, files in direction_files.items():
        frames: List[pygame.Surface] = []
        for name in files:
            full = sprites_dir.joinpath(name)
            if full.exists():
                try:
                    img = pygame.image.load(str(full)).convert_alpha()
                    img = pygame.transform.scale(img, (size, size))
                    frames.append(img)
                except Exception:
                    continue
        if frames:
            out[direction] = frames
    return out


def spawn_enemies(
    game_map: List[List[str]],
    count: int,
    tile_size: int,
    offset_x: int,
    offset_y: int,
    valid_tile: str = ".",
    enemy_size: int = 48,
    speed: float = 1.5,
    kind: str = "zombie"  # new: "zombie" (default), "slime", or "mix"
) -> List[Enemy]:
    HEIGHT = len(game_map)
    WIDTH = len(game_map[0]) if HEIGHT > 0 else 0
    candidates: List[Tuple[int, int]] = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if game_map[y][x] == valid_tile:
                tlx = offset_x + x * tile_size
                tly = offset_y + y * tile_size
                candidates.append((tlx, tly))
    random.shuffle(candidates)

    # zombie sprite files (existing)
    zombie_files = {
        "down":  ["zdown_idle.png",  "zdown_walk1.png",  "zdown_walk2.png"],
        "left":  ["zleft_idle.png",  "zleft_walk1.png",  "zleft_walk2.png"],
        "right": ["zright_idle.png", "zright_walk1.png", "zright_walk2.png"],
        "up":    ["zup_idle.png",    "zup_walk1.png",    "zup_walk2.png"],
        "idle":  ["zdown_idle.png"]
    }

    # ghost sprite files (use your project sprite names or placeholders)
    ghost_files = {
        "down":  ["gdown_1.png", "gdown_2.png", "gdown_3.png"],
        "left":  ["gleft_1.png", "gleft_2.png", "gleft_3.png"],
        "right": ["gright_1.png", "gright_2.png", "gright_3.png"],
        "up":    ["gup_1.png", "gup_2.png", "gup_3.png"],
        "idle":  ["gdown_1.png", "gdown_2.png", "gdown_3.png"]
    }

    # mage sprite files
    mage_files = {
        "down":  ["mdown_idle.png","mdown_walk1.png","mdown_walk2.png"],
        "left":  ["mleft_idle.png","mleft_walk1.png","mleft_walk2.png"],
        "right": ["mright_idle.png","mright_walk1.png","mright_walk2.png"],
        "up":    ["mup_idle.png","mup_walk1.png","mup_walk2.png"],
        "idle":  ["mup_idle.png"]
    }

    # new: slime sprite files (use your project sprite names or placeholders)
    slime_files = {
        "down":  ["slime_normal.png"],
        "left":  ["slime_normal.png"],
        "right": ["slime_normal.png"],
        "up":    ["slime_normal.png"],
        "idle":  ["slime_normal.png"],
        "jump":  ["slime_preparingtojump.png"]  # new: sprite shown while about to jump over lava
    }

    enemies: List[Enemy] = []

    def make_enemy(kind_choice: str, tlx: int, tly: int) -> Enemy:
        if kind_choice == "slime":
            s_size = max(16, int(enemy_size * 0.75))  # slimes a bit smaller by default
            s_speed = max(0.1, speed * 0.9)           # slightly slower
            s_hp = 2                                  # tougher than a basic zombie
            sprite_dict = load_enemy_sprites(slime_files, s_size) or None
            ex = tlx + (tile_size - s_size) / 2
            ey = tly + (tile_size - s_size) / 2
            # pass can_jump_lava=True for slimes
            return Enemy(ex, ey, s_size, speed=s_speed, hp=s_hp, sprites=sprite_dict, can_jump_lava=True)
        if kind_choice == "ghost":
            g_size = enemy_size
            g_speed = max(0.5, speed * 1.1)
            g_hp = 1
            sprite_dict = load_enemy_sprites(ghost_files, g_size) or None
            # make ghost sprites slightly transparent if loaded
            if sprite_dict:
                for key, frames in sprite_dict.items():
                    for surf in frames:
                        try:
                            surf.set_alpha(180)
                        except Exception:
                            pass
            ex = tlx + (tile_size - g_size) / 2
            ey = tly + (tile_size - g_size) / 2
            return Enemy(ex, ey, g_size, speed=g_speed, hp=g_hp, sprites=sprite_dict, can_fly=True)
        if kind_choice == "mage":
            m_size = enemy_size
            m_speed = max(0.5, speed * 0.9)
            m_hp = 1
            sprite_dict = load_enemy_sprites(mage_files, m_size) or None
            ex = tlx + (tile_size - m_size) / 2
            ey = tly + (tile_size - m_size) / 2
            # mage can cast; set cast cooldown, projectile speed, and larger stop distance
            e = Enemy(
                ex, ey, m_size,
                speed=m_speed,
                hp=m_hp,
                sprites=sprite_dict,
                can_cast=True,
                cast_cooldown=1500,
                projectile_speed=6.0,
                cast_stop_distance=240  # increased stopping range for mages
            )
            # attempt to load the single projectile PNG "mage_magic.png" from sprites/
            sprites_dir = Path(__file__).parent.joinpath("sprites")
            fp = sprites_dir.joinpath("mage_magic.png")
            if fp.exists():
                try:
                    img = pygame.image.load(str(fp)).convert_alpha()
                    # make projectile noticeably bigger (increase multiplier and minimum)
                    size_px = max(12, int(m_size * 0.5))
                    e.projectile_img = pygame.transform.scale(img, (size_px, size_px))
                except Exception:
                    e.projectile_img = None
            else:
                e.projectile_img = None
            return e
        else:  # default: zombie
            z_size = enemy_size
            z_speed = speed
            z_hp = 1
            sprite_dict = load_enemy_sprites(zombie_files, z_size) or None
            ex = tlx + (tile_size - z_size) / 2
            ey = tly + (tile_size - z_size) / 2
            return Enemy(ex, ey, z_size, speed=z_speed, hp=z_hp, sprites=sprite_dict)

    for i in range(min(count, len(candidates))):
        tlx, tly = candidates[i]
        if kind == "mix":
            # include mage in mixed spawns
            chosen = random.choice(["zombie", "slime", "ghost", "mage"])
        else:
            chosen = kind
        enemies.append(make_enemy(chosen, tlx, tly))

    # assign group reference so enemies can avoid stacking
    for e in enemies:
        e.group = enemies

    return enemies
