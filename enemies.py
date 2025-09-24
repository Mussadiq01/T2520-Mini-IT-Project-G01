from typing import Callable, List, Optional, Tuple, Dict
from pathlib import Path
# NEW: required imports
import math
import random
import pygame

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

        # special-case marker for slimes (spawn sets this)
        self.is_slime = False

        # casting (mage) state
        self.can_cast = can_cast
        self.cast_cooldown = cast_cooldown
        self.cast_timer = random.randint(0, cast_cooldown)  # stagger initial casts slightly
        self.projectile_speed = projectile_speed
        self.projectiles: List[Dict[str, float]] = []  # each: {'x','y','vx','vy','speed'}
        self.cast_stop_distance = cast_stop_distance

        # Visual flash when hit
        self.flash_timer = 0            # ms remaining to show red flash
        self.flash_duration = 180      # ms length of flash

        # Knockback state (applied over short duration)
        self.kb_vx = 0.0
        self.kb_vy = 0.0
        self.kb_time = 0               # ms remaining for knockback
        self.kb_duration = 160         # duration of knockback in ms

        # prejump state: when true the enemy displays the jump sprite for a short time
        # before performing the actual jump to the landing spot.
        self.prejumping = False
        self.prejump_timer = 0
        self.prejump_duration = 500  # ms to show the "about to jump" sprite
        self._landing: Optional[Tuple[float, float]] = None
        # jump animation bookkeeping (start pos & peak height)
        self._jump_start: Optional[Tuple[float, float]] = None
        self.jump_height = max(12.0, float(self.size) * 0.6)
        # slime hop control (slimes hop when wandering instead of walking)
        # limit to one jump every 1.2s (configurable)
        self.hop_cooldown = 1200  # ms between hops
        # stagger initial hop so they don't all jump immediately
        self.hop_timer = random.randint(0, self.hop_cooldown)
        # maximum jump distance (approx in pixels): 4 tiles ~= 4 * size
        self.max_jump_distance = float(self.size) * 4.0
        # trap damage cooldown (prevent per-frame damage); enemies take trap damage when on trap
        self.trap_damage_timer = 0
        self.trap_damage_cooldown = 500  # ms between trap damage tick for an enemy
        # preparing (short pre-jump) state (defensive init in case not set elsewhere)
        self.preparing = False
        self.preparing_timer = 0
        self.preparing_duration = getattr(self, "preparing_duration", 120)

        # NEW: roaming / follow / separation defaults
        self.home_x = x
        self.home_y = y
        self.follow_range = 320.0        # slightly longer sight: enemies notice player from farther away
        self.roam_radius = 120.0         # wander radius around home when not chasing
        self.wander_target: Optional[Tuple[float, float]] = None
        self.wander_timer = 0            # ms left before picking new wander target
        self.wander_cooldown = 1800      # ms between wander target picks

        # Separation tuning (used to nudge movement before attempting collisions)
        self.separation_radius = max(24.0, self.size * 1.2)
        self.separation_strength = 0.6   # how strongly separation influences movement

        # marker used to let external code (main) know this enemy died THIS FRAME
        self._died_this_frame = False

        self.stun_timer = 0  # ms remaining for shield stun
        # POISON state
        self.poison_stacks = 0           # number of poison stacks
        self.poison_tick_interval = 1500 # ms between ticks
        self.poison_tick_timer = 0       # countdown timer
        self.poison_green_timer = 0      # ms for green flash on tick
        self.poison_green_duration = 140
        # damage event queue (collected by main each frame)
        self._damage_events: List[Dict[str, float]] = []
        # NEW: kind tag for scoring
        self.kind: str = "unknown"

        # NEW: optional boss flags and timers (used only when is_boss is True)
        self.is_boss: bool = False
        # dash settings
        self.can_dash: bool = False
        self.dash_cooldown: int = 4000       # ms between dashes
        self._dash_cd_timer: int = random.randint(int(self.dash_cooldown * 0.5), self.dash_cooldown)
        self.dash_duration: int = 200        # ms dash duration (applied via knockback)
        self.dash_force: float = 28.0        # strength of dash knockback impulse
        # summon settings
        self.summon_cooldown: int = 6000     # ms between summon waves
        self._summon_timer: int = self.summon_cooldown
        self.summon_count: int = 2           # zombies per wave
        self.max_minions: int = 6            # max non-boss allies alive
        # NEW: allow choosing minion type: "zombie" (default) or "mage"
        self.summon_kind: str = "zombie"

        # NEW: boss teleport settings
        self.can_teleport: bool = False
        self.teleport_cooldown: int = 5000
        self._teleport_timer: int = self.teleport_cooldown
        self.teleport_near_player: bool = True  # try to find a valid tile near player

        # NEW: boss mage volley settings
        self.volley_count: int = 1        # projectiles per cast (spread around aim)
        self.volley_spread_deg: float = 30.0
        self.volley_ring: bool = False    # occasionally fire a full ring
        self.volley_ring_count: int = 16  # number in the ring when enabled
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.size, self.size)

    def _push_damage_event(self, amount: int, color: Tuple[int, int, int]) -> None:
        try:
            self._damage_events.append({
                'x': self.x + self.size / 2.0,
                'y': self.y - 6.0,
                'amt': int(max(0, amount)),
                'color': color,
            })
        except Exception:
            pass

    def drain_damage_events(self) -> List[Dict[str, float]]:
        ev = self._damage_events
        self._damage_events = []
        return ev

    def take_damage(self, amount: int = 1) -> None:
        self.hp -= amount
        # normal damage indicator (red)
        try:
            if amount > 0:
                self._push_damage_event(amount, (200, 40, 40))
        except Exception:
            pass
        if self.hp <= 0:
            self.alive = False
            # mark for external consumers to spawn death particles once
            try:
                self._died_this_frame = True
            except Exception:
                pass

    def apply_damage(self, amount: int, kb_x: float = 0.0, kb_y: float = 0.0, kb_force: float = 40.0, kb_duration: int = 160) -> None:
        """Apply damage, start flash, and setup knockback away from (0,0) direction vector kb_x,kb_y."""
        self.take_damage(amount)
        # flash
        self.flash_timer = self.flash_duration
        # set knockback only if still alive (optional) or always allow slight displacement
        norm = math.hypot(kb_x, kb_y)
        if norm > 1e-6:
            nx = kb_x / norm
            ny = kb_y / norm
            # scale knockback by size so small enemies move a bit more visually
            scale = 48.0 / max(16.0, float(self.size))
            self.kb_vx = nx * kb_force * scale
            self.kb_vy = ny * kb_force * scale
            self.kb_time = kb_duration
            self.kb_duration = kb_duration

    def apply_poison(self, stacks: int = 1) -> None:
        """Apply/stack poison. Each stack deals 1 dmg per tick. Resets timer if not running."""
        try:
            self.poison_stacks += max(0, int(stacks))
            if self.poison_stacks > 0 and self.poison_tick_timer <= 0:
                self.poison_tick_timer = self.poison_tick_interval
        except Exception:
            pass

    def update(
        self,
        dt: int,
        player_pos: Tuple[int, int],
        is_walkable: Callable[[float, float], bool],
        on_trap: Optional[Callable[[int, int], bool]] = None,
        is_lava: Optional[Callable[[float, float], bool]] = None,
        is_wall: Optional[Callable[[float, float], bool]] = None,
        on_projectile_break: Optional[Callable[[float, float, Dict[str, float]], None]] = None
    ) -> None:
        if not self.alive:
            return

        # Always tick hit flash even when stunned (prevents stuck red tint)
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer < 0:
                self.flash_timer = 0
        # Poison green flash timer
        if self.poison_green_timer > 0:
            self.poison_green_timer -= dt
            if self.poison_green_timer < 0:
                self.poison_green_timer = 0

        # --- SHIELD STUN LOGIC ---
        if hasattr(self, "stun_timer") and self.stun_timer > 0:
            self.stun_timer -= dt
            if self.stun_timer > 0:
                # While stunned, existing projectiles should keep flying; just don't cast new ones
                if self.can_cast and self.projectiles:
                    pruned: List[Dict[str, float]] = []
                    for p in self.projectiles:
                        # move scaled similar to other movement
                        p['x'] += p['vx'] * p['speed'] * (dt / 16.0)
                        p['y'] += p['vy'] * p['speed'] * (dt / 16.0)
                        # advance rotational angle (spin is degrees per second)
                        try:
                            p['angle'] = (p.get('angle', 0.0) + p.get('spin', 0.0) * (dt / 1000.0)) % 360.0
                        except Exception:
                            p['angle'] = p.get('angle', 0.0)
                        # prune if hit wall / OOB
                        try:
                            hit_wall = False
                            if is_wall is not None:
                                hit_wall = bool(is_wall(p['x'], p['y']))
                            if hit_wall:
                                try:
                                    if on_projectile_break:
                                        on_projectile_break(p['x'], p['y'], p)
                                except Exception:
                                    pass
                                continue
                            pruned.append(p)
                        except Exception:
                            pruned.append(p)
                    self.projectiles = pruned
                return  # skip movement/attacks while stunned

        # process knockback first (applied over kb_duration)
        if self.kb_time > 0 and (abs(self.kb_vx) > 1e-6 or abs(self.kb_vy) > 1e-6):
            frac = min(dt, self.kb_time) / float(max(1, self.kb_duration))
            dx_k = self.kb_vx * frac
            dy_k = self.kb_vy * frac
            # attempt full move, else try axis-separated, else cancel remaining kb
            new_x = self.x + dx_k
            new_y = self.y + dy_k
            # Ghosts ignore all collision checks - just move
            if self.can_fly:
                self.x = new_x
                self.y = new_y
            else:
                try:
                    if is_walkable(new_x, new_y):
                        self.x = new_x
                        self.y = new_y
                    else:
                        moved = False
                        if is_walkable(self.x + dx_k, self.y):
                            self.x += dx_k
                            moved = True
                        if is_walkable(self.x, self.y + dy_k):
                            self.y += dy_k
                            moved = True
                        if not moved:
                            # blocked -> cancel remaining knockback
                            self.kb_vx = 0.0
                            self.kb_vy = 0.0
                            self.kb_time = 0
                except Exception:
                    # defensive fallback
                    self.x = new_x
                    self.y = new_y
            self.kb_time -= dt
            if self.kb_time <= 0:
                self.kb_vx = 0.0
                self.kb_vy = 0.0
                self.kb_time = 0

        # trap damage cooldown tick
        if getattr(self, "trap_damage_timer", 0) > 0:
            self.trap_damage_timer -= dt
            if self.trap_damage_timer < 0:
                self.trap_damage_timer = 0
        # Poison ticking: deals damage every interval while alive
        if self.poison_stacks > 0 and self.alive:
            self.poison_tick_timer -= dt
            if self.poison_tick_timer <= 0:
                # deal damage equal to stacks as poison (green indicator)
                dmg = int(max(1, self.poison_stacks))
                try:
                    self.hp -= dmg
                except Exception:
                    pass
                # start green flash and queue a green indicator
                self.poison_green_timer = self.poison_green_duration
                try:
                    self._push_damage_event(dmg, (60, 200, 60))
                except Exception:
                    pass
                # reset interval for next tick
                self.poison_tick_timer += self.poison_tick_interval
                # handle death
                if self.hp <= 0:
                    self.alive = False
                    try:
                        self._died_this_frame = True
                    except Exception:
                        pass

        px, py = player_pos
        cx = self.x + self.size / 2
        cy = self.y + self.size / 2
        dx = px - cx
        dy = py - cy
        dist = math.hypot(dx, dy)
        if dist > 1:
            to_player_nx = dx / dist
            to_player_ny = dy / dist
        else:
            to_player_nx = to_player_ny = 0.0

        # NEW: Boss abilities (only active when flagged as a boss)
        if getattr(self, "is_boss", False):
            # Dash toward player using the built-in knockback for a short burst
            if getattr(self, "can_dash", False):
                try:
                    self._dash_cd_timer -= dt
                except Exception:
                    self._dash_cd_timer = getattr(self, "dash_cooldown", 4000)
                if self._dash_cd_timer <= 0 and dist > self.size * 1.25:
                    try:
                        force = float(getattr(self, "dash_force", 28.0))
                        dur = int(getattr(self, "dash_duration", 200))
                        self.kb_vx = to_player_nx * force
                        self.kb_vy = to_player_ny * force
                        self.kb_time = dur
                        self.kb_duration = dur
                    except Exception:
                        pass
                    # reset cooldown
                    self._dash_cd_timer = int(getattr(self, "dash_cooldown", 4000))

            # NEW: Teleport near or onto player on cooldown (primarily for mage bosses)
            if getattr(self, "can_teleport", False):
                try:
                    self._teleport_timer -= dt
                except Exception:
                    self._teleport_timer = int(getattr(self, "teleport_cooldown", 5000))
                if self._teleport_timer <= 0:
                    # desired landing around player's center; try exact, then nearby offsets
                    t_size = self.size
                    tx = px - t_size / 2
                    ty = py - t_size / 2
                    placed = False
                    try:
                        if is_walkable(tx, ty):
                            self.x, self.y = tx, ty
                            placed = True
                        else:
                            # try a few offsets around player
                            for rad in (t_size * 0.5, t_size, t_size * 1.5, t_size * 2.0):
                                for k in range(8):
                                    ang = (math.pi * 2.0) * (k / 8.0)
                                    lx = (px + math.cos(ang) * rad) - t_size / 2
                                    ly = (py + math.sin(ang) * rad) - t_size / 2
                                    if is_walkable(lx, ly):
                                        self.x, self.y = lx, ly
                                        placed = True
                                        break
                                if placed:
                                    break
                    except Exception:
                        # fallback: snap anyway (can be inside wall if callback fails)
                        self.x, self.y = tx, ty
                        placed = True
                    # reset cooldown regardless
                    self._teleport_timer = int(getattr(self, "teleport_cooldown", 5000))

            # Summon zombies or mages near the boss, capped by max_minions
            try:
                self._summon_timer -= dt
            except Exception:
                self._summon_timer = int(getattr(self, "summon_cooldown", 6000))
            if self._summon_timer <= 0 and self.group is not None:
                try:
                    alive_others = [g for g in self.group if (g is not self) and getattr(g, "alive", False)]
                    cap = int(getattr(self, "max_minions", 6))
                    if len(alive_others) < cap:
                        to_spawn = min(int(getattr(self, "summon_count", 2)), cap - len(alive_others))
                        for _ in range(max(0, to_spawn)):
                            m_size = max(28, int(self.size * 0.8))
                            placed = False
                            for _try in range(14):
                                ang = random.uniform(0, 2 * math.pi)
                                rad = random.uniform(self.size * 1.0, self.size * 3.5)
                                mcx = (self.x + self.size/2) + math.cos(ang) * rad
                                mcy = (self.y + self.size/2) + math.sin(ang) * rad
                                mx = mcx - m_size / 2
                                my = mcy - m_size / 2
                                try:
                                    if is_walkable(mx, my):
                                        # build sprites and minion type
                                        kind = (getattr(self, "summon_kind", "zombie") or "zombie").lower()
                                        if kind == "mage":
                                            direction_files = {
                                                "down":  ["mdown_idle.png","mdown_walk1.png","mdown_walk2.png"],
                                                "left":  ["mleft_idle.png","mleft_walk1.png","mleft_walk2.png"],
                                                "right": ["mright_idle.png","mright_walk1.png","mright_walk2.png"],
                                                "up":    ["mup_idle.png","mup_walk1.png","mup_walk2.png"],
                                                "idle":  ["mup_idle.png"]
                                            }
                                            try:
                                                sprite_dict = load_enemy_sprites(direction_files, m_size)
                                            except Exception:
                                                sprite_dict = None
                                            m = Enemy(
                                                mx, my, m_size,
                                                speed=max(0.7, self.speed * 0.75),
                                                hp=12,
                                                sprites=sprite_dict,
                                                can_cast=True,
                                                cast_cooldown=3800,
                                                projectile_speed=3.0,
                                                cast_stop_distance=140
                                            )
                                            m.kind = "mage"
                                            # projectile image try-load
                                            sprites_dir = Path(__file__).parent.joinpath("sprites")
                                            fp = sprites_dir.joinpath("mage_magic.png")
                                            if fp.exists():
                                                try:
                                                    img = pygame.image.load(str(fp)).convert_alpha()
                                                    size_px = max(20, int(m_size * 0.7))
                                                    m.projectile_img = pygame.transform.scale(img, (size_px, size_px))
                                                except Exception:
                                                    m.projectile_img = None
                                            else:
                                                m.projectile_img = None
                                        else:
                                            # zombie fallback
                                            direction_files = {
                                                "down":  ["zdown_idle.png",  "zdown_walk1.png",  "zdown_walk2.png"],
                                                "left":  ["zleft_idle.png",  "zleft_walk1.png",  "zleft_walk2.png"],
                                                "right": ["zright_idle.png", "zright_walk1.png", "zright_walk2.png"],
                                                "up":    ["zup_idle.png",    "zup_walk1.png",    "zup_walk2.png"],
                                                "idle":  ["zdown_idle.png"]
                                            }
                                            try:
                                                sprite_dict = load_enemy_sprites(direction_files, m_size)
                                            except Exception:
                                                sprite_dict = None
                                            m = Enemy(mx, my, m_size, speed=max(0.9, self.speed * 0.85), hp=12, sprites=sprite_dict)
                                            m.kind = "zombie"
                                        m.group = self.group
                                        self.group.append(m)
                                        placed = True
                                        break
                                except Exception:
                                    pass
                            # if not placed, skip silently
                except Exception:
                    pass
                self._summon_timer = int(getattr(self, "summon_cooldown", 6000))

        px, py = player_pos
        cx = self.x + self.size / 2
        cy = self.y + self.size / 2
        dx = px - cx
        dy = py - cy
        dist = math.hypot(dx, dy)
        if dist > 1:
            to_player_nx = dx / dist
            to_player_ny = dy / dist
        else:
            to_player_nx = to_player_ny = 0.0

        # helper: attempt to nudge out of a non-walkable location
        def try_unstuck():
            if is_walkable(self.x, self.y):
                return False
            # try small offsets (increasing radius)
            steps = [self.size * f for f in (0.25, 0.5, 1.0, 1.5, 2.0)]
            dirs = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
            for step in steps:
                for dxs,dys in dirs:
                    cand_x = self.x + dxs * step
                    cand_y = self.y + dys * step
                    try:
                        if is_walkable(cand_x, cand_y):
                            self.x = cand_x
                            self.y = cand_y
                            return True
                    except Exception:
                        continue
            return False

        # Decide whether to chase player or wander around home
        # Ghosts (can_fly) always chase regardless of follow_range
        chasing = dist <= self.follow_range or self.can_fly

        # default LOS-blocked flag (used later); ensure it's always defined
        los_blocked = False

        # If we have an is_wall callback and this enemy is not a ghost,
        # require a simple LOS check (sample along line) before aggroing.
        # Note: LOS only disables chasing — wandering/hopping still runs below.
        if not self.can_fly and is_wall is not None and dist > 1e-4:
            # NEW: proximity override so walls right next to the player don't block aggro
            near_dist = max(self.size * 2.0, 72.0)
            if dist <= near_dist:
                los_clear = True
            else:
                los_clear = True
                # sample points along ray from enemy center to player center
                steps = max(3, int(dist // max(8.0, self.size * 0.25)))
                # use steps+1 in denominator so we never sample the exact player center;
                # also ignore the last ~15% of samples to avoid false blocks when hugging walls
                ignore_tail = max(1, int(steps * 0.15))
                for s in range(1, max(1, steps - ignore_tail) + 1):
                    t = s / float(steps + 1)
                    sx = cx + (px - cx) * t
                    sy = cy + (py - cy) * t
                    try:
                        if is_wall(sx, sy):
                            los_clear = False
                            break
                    except Exception:
                        # on callback error assume blocked to be safe
                        los_clear = False
                        break
            if not los_clear:
                # only cancel chasing; do NOT prevent wandering below
                chasing = False
                los_blocked = True

        # ensure desired direction/speed have default values so later code can safely reference them
        desired_nx = 0.0
        desired_ny = 0.0
        desired_speed = 0.0

        # SLIME: decrement hop timer every frame (so they can hop while chasing or wandering)
        if getattr(self, "is_slime", False):
            self.hop_timer -= dt
            if self.hop_timer < 0:
                self.hop_timer = 0

        # desired direction (before separation is applied)
        if chasing:
            desired_nx = to_player_nx
            desired_ny = to_player_ny
            desired_speed = self.speed

            # Slime chase behaviour: attempt a hop toward the player when ready (instead of walking)
            if getattr(self, "is_slime", False) and not self.prejumping and not self.preparing and self.hop_timer <= 0:
                # Only attempt if player within jumpable distance but not overlapping
                if dist > (self.size * 0.6) and dist <= getattr(self, "max_jump_distance", self.size * 3.0):
                    landing_x = px - self.size / 2
                    landing_y = py - self.size / 2
                    # prefer exact center, else try small offsets
                    found = False
                    try:
                        if is_walkable(landing_x, landing_y):
                            self.preparing = True
                            self.preparing_timer = self.preparing_duration
                            self._landing = (landing_x, landing_y)
                            found = True
                        else:
                            for ox in (-1, 0, 1):
                                for oy in (-1, 0, 1):
                                    cand_x = landing_x + ox * self.size
                                    cand_y = landing_y + oy * self.size
                                    try:
                                        if is_walkable(cand_x, cand_y):
                                            self.preparing = True
                                            self.preparing_timer = self.preparing_duration
                                            self._landing = (cand_x, cand_y)
                                            found = True
                                            break
                                    except Exception:
                                        continue
                                if found:
                                    break
                    except Exception:
                        pass
                    if found:
                        # reset hop timer to cooldown (prevents immediate repeat)
                        self.hop_timer = self.hop_cooldown
                        # slimes do not walk toward player while preparing
                        desired_speed = 0.0

        else:
            # wandering behaviour: pick a wander target near home every so often
            if self.wander_target is None or self.wander_timer <= 0:
                ang = random.random() * 2.0 * math.pi
                r = random.random() * self.roam_radius
                tx = self.home_x + r * math.cos(ang)
                ty = self.home_y + r * math.sin(ang)
                self.wander_target = (tx, ty)
                self.wander_timer = self.wander_cooldown
            else:
                self.wander_timer -= dt

            # For non-slime enemies, walk toward the wander target; slimes hop (handled below).
            if not getattr(self, "is_slime", False) and self.wander_target is not None:
                wt_x, wt_y = self.wander_target
                wx = wt_x - cx
                wy = wt_y - cy
                wd = math.hypot(wx, wy)
                if wd > 1e-4:
                    desired_nx = wx / wd
                    desired_ny = wy / wd
                    desired_speed = self.speed
                else:
                    desired_nx = desired_ny = 0.0
                    desired_speed = 0.0

            # Slimes shouldn't walk while wandering — they perform short hops toward the wander target.
            if getattr(self, "is_slime", False):
                # if ready, attempt a short hop toward the wander target
                if self.hop_timer <= 0 and not self.preparing and not self.prejumping:
                    wt_x, wt_y = self.wander_target
                    dxwt = wt_x - cx
                    dywt = wt_y - cy
                    dwt = math.hypot(dxwt, dywt)
                    if dwt > 1e-4:
                        hop_dist = min(dwt, self.max_jump_distance)
                        nxh = dxwt / dwt
                        nyh = dywt / dwt
                        landing_cx = cx + nxh * hop_dist
                        landing_cy = cy + nyh * hop_dist
                        landing_x = landing_cx - self.size / 2
                        landing_y = landing_cy - self.size / 2
                        try:
                            if is_walkable(landing_x, landing_y):
                                self.preparing = True
                                self.preparing_timer = self.preparing_duration
                                self._landing = (landing_x, landing_y)
                                self.hop_timer = self.hop_cooldown
                        except Exception:
                            pass
                # slimes do not walk while wandering — they hop instead
                desired_speed = 0.0
                wt_x, wt_y = self.wander_target
                wx = wt_x - cx
                wy = wt_y - cy
                wd = math.hypot(wx, wy)
                if wd > 1e-4:
                    desired_nx = wx / wd
                    desired_ny = wy / wd
                else:
                    desired_nx = desired_ny = 0.0
                desired_speed = 0.0

        # --- LOCAL SEPARATION: compute small repulsion from nearby allies BEFORE moving ---
        sep_x = 0.0
        sep_y = 0.0
        if self.group:
            for other in self.group:
                if other is self or not other.alive:
                    continue
                dxo = (self.x + self.size / 2.0) - (other.x + other.size / 2.0)
                dyo = (self.y + self.size / 2.0) - (other.y + other.size / 2.0)
                dn = math.hypot(dxo, dyo)
                if dn < 1e-6:
                    # jitter to avoid exact overlap
                    ang = random.random() * 2.0 * math.pi
                    dxo = math.cos(ang) * 0.1
                    dyo = math.sin(ang) * 0.1
                    dn = math.hypot(dxo, dyo)
                if dn < self.separation_radius:
                    # repulsion proportional to closeness (closer => stronger)
                    f = (self.separation_radius - dn) / self.separation_radius
                    sep_x += (dxo / dn) * f
                    sep_y += (dyo / dn) * f
        # normalize separation and scale
        sep_len = math.hypot(sep_x, sep_y)
        if sep_len > 1e-6:
            sep_x = (sep_x / sep_len) * self.separation_strength
            sep_y = (sep_y / sep_len) * self.separation_strength
        else:
            sep_x = sep_y = 0.0

        # Combine desired direction with separation nudging
        nx = desired_nx + sep_x
        ny = desired_ny + sep_y
        nlen = math.hypot(nx, ny)
        if nlen > 1e-4:
            nx /= nlen
            ny /= nlen
        else:
            nx = ny = 0.0

        # keep original desired direction for facing (so wandering enemies face their movement target,
        # and chasing enemies still face the player)
        orig_nx, orig_ny = desired_nx, desired_ny
        # If this enemy is a mage that decided to stop moving to cast, show the idle sprite
        # but preserve the last facing direction so the idle sprite matches the last movement.
        if self.can_cast and chasing and dist <= self.cast_stop_distance and not self.prejumping:
            # map current facing to a canonical direction vector for facing calculation
            facing_map = {
                "left":  (-1.0,  0.0),
                "right": ( 1.0,  0.0),
                "up":    ( 0.0, -1.0),
                "down":  ( 0.0,  1.0),
                "idle":  ( 0.0,  1.0)  # default idle -> down
            }
            orig_nx, orig_ny = facing_map.get(self.facing, (0.0, 1.0))
            # reset animation frame so the idle frame shows immediately
            self.frame = 0
            self.frame_timer = 0

        # --- Slime special behaviour: do NOT walk toward player, but still attempt to detect lava
        # and trigger the prejump logic (jump over lava) when appropriate.
        if getattr(self, "is_slime", False) and self.can_jump_lava and is_lava is not None and (abs(nx) > 1e-4 or abs(ny) > 1e-4):
            # reuse the existing lava scanning logic (search ahead from slime center)
            cx_center = self.x + self.size / 2
            cy_center = self.y + self.size / 2
            STEP = max(8, int(self.size / 2))
            MAX_DIST = max(48, int(self.size)) * 6
            samples = max(1, int(MAX_DIST / STEP))
            half = self.size / 2
            lateral_offsets = [-half + 4, 0, half - 4]
            perp_x = -ny
            perp_y = nx
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
                min_extra = max(1, int(self.size / STEP))
                max_extra = min(8, samples - end_idx)
                TILE_SEARCH = max(48, int(self.size))
                found = False
                for extra in range(min_extra, max_extra + 1):
                    k = end_idx + extra
                    base_cx = cx_center + nx * STEP * k
                    base_cy = cy_center + ny * STEP * k
                    for ox_mult in (-1, 0, 1):
                        for oy_mult in (-1, 0, 1):
                            landing_cx = base_cx + ox_mult * TILE_SEARCH
                            landing_cy = base_cy + oy_mult * TILE_SEARCH
                            landing_x = landing_cx - self.size / 2
                            landing_y = landing_cy - self.size / 2
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
                            blocked = False
                            for m in range(1, k + 1):
                                sx = cx_center + nx * STEP * m
                                sy = cy_center + ny * STEP * m
                                for lo in lateral_offsets:
                                    lx = sx + perp_x * lo
                                    ly = sy + perp_y * lo
                                    if is_lava(lx, ly):
                                        blocked = True
                                        break
                                if blocked:
                                    break
                            if blocked:
                                continue
                            self.prejumping = True
                            self.prejump_timer = self.prejump_duration
                            self._landing = (landing_x, landing_y)
                            # record jump start so we can animate the arc
                            self._jump_start = (self.x, self.y)
                            # ensure jump peak scales with size
                            self.jump_height = max(12.0, float(self.size) * 0.6)
                            found = True
                            break
                        if found:
                            break
                    if found:
                        break
            # slimes do not perform normal walking movement
            # continue normally (prejump will handle the landing when triggered)
            # fall through to rest of update (but do not set self.x/self.y walking)
            pass

        # Preparing -> start flight: handle a short preparing phase before in-air
        if getattr(self, "preparing", False):
            self.preparing_timer -= dt
            if self.preparing_timer <= 0:
                # begin flight (prejumping) using previously stored landing
                if self._landing is not None:
                    # ensure landing distance is within max allowed (safety)
                    land_cx = self._landing[0] + self.size / 2
                    land_cy = self._landing[1] + self.size / 2
                    cur_cx = self.x + self.size / 2
                    cur_cy = self.y + self.size / 2
                    dd = math.hypot(land_cx - cur_cx, land_cy - cur_cy)
                    if dd <= self.max_jump_distance + 1e-6:
                        self.prejumping = True
                        self.prejump_timer = self.prejump_duration
                        self._jump_start = (self.x, self.y)
                    else:
                        # landing too far — cancel
                        self._landing = None
                self.preparing = False
                self.preparing_timer = 0

        # If currently in prejump (in-air) state, animate and land when timer ends.
        if self.prejumping:
            self.prejump_timer -= dt
            start_x, start_y = (self._jump_start if self._jump_start is not None else (self.x, self.y))
            land_x, land_y = (self._landing if self._landing is not None else (start_x, start_y))
            t = 1.0 - max(0, self.prejump_timer) / float(max(1, self.prejump_duration))  # 0 -> 1
            peak = self.jump_height
            arc = peak * 4.0 * t * (1.0 - t)
            self.x = start_x + (land_x - start_x) * t
            self.y = start_y + (land_y - start_y) * t - arc
            if self.prejump_timer <= 0:
                if self._landing and is_walkable(self._landing[0], self._landing[1]):
                    self.x, self.y = self._landing
                self.prejumping = False
                self.prejump_timer = 0
                self._landing = None
                self._jump_start = None
        else:
            move = desired_speed * (dt / 16.0)
            # mage: if within stop distance, don't move toward player (prevent bumping)
            if self.can_cast and chasing and dist <= self.cast_stop_distance:
                move = 0.0
            target_x = self.x + nx * move
            target_y = self.y + ny * move

            # Ghosts ignore ALL collision and move freely
            if self.can_fly:
                self.x = target_x
                self.y = target_y
            else:
                # If target spot is directly walkable, move normally
                if is_walkable(target_x, target_y):
                    self.x = target_x
                    self.y = target_y
                else:
                    # fallback behaviour: try axis-separated moves as before
                    if not self.prejumping:
                        moved = False
                        if is_walkable(target_x, self.y):
                            self.x = target_x
                            moved = True
                        elif is_walkable(self.x, target_y):
                            self.y = target_y
                            moved = True
                        if not moved:
                            # Small "unstuck" attempts:
                            # try stepping a few small distances backwards along the desired vector
                            back_steps = [self.size * f for f in (0.25, 0.5, 1.0, 1.5)]
                            for step in back_steps:
                                cand_x = self.x - desired_nx * step
                                cand_y = self.y - desired_ny * step
                                if is_walkable(cand_x, cand_y):
                                    self.x = cand_x
                                    self.y = cand_y
                                    moved = True
                                    break
                            # if still stuck, try small perpendicular nudges
                            if not moved:
                                perp_candidates = [(-desired_ny, desired_nx), (desired_ny, -desired_nx)]
                                for perp in perp_candidates:
                                    for step in back_steps:
                                        cand_x = self.x + perp[0] * step
                                        cand_y = self.y + perp[1] * step
                                        if is_walkable(cand_x, cand_y):
                                            self.x = cand_x
                                            self.y = cand_y
                                            moved = True
                                            break
                                    if moved:
                                        break
                            # if still not moved, leave position unchanged (will retry next frame)
        # Final defensive unstuck: skip for ghosts since they can phase through walls
        if not self.can_fly:
            try:
                try_unstuck()
            except Exception:
                pass

        # --- traps: enemies take damage from traps (uses on_trap callback passed from main)
        # Flying enemies (ghosts) should NOT take trap damage — skip for can_fly.
        if on_trap is not None and not getattr(self, "can_fly", False):
            cx_center = self.x + self.size / 2
            cy_center = self.y + self.size / 2
            try:
                if on_trap(cx_center, cy_center):
                    # only apply damage when cooldown expired
                    if getattr(self, "trap_damage_timer", 0) <= 0:
                        # -5 health and slight upward knockback
                        try:
                            self.apply_damage(5, kb_x=0.0, kb_y=-1.0, kb_force=20.0, kb_duration=120)
                        except Exception:
                            # fallback to direct hp subtraction
                            try:
                                self.take_damage(5)
                            except Exception:
                                pass
                        self.trap_damage_timer = getattr(self, "trap_damage_cooldown", 500)
            except Exception:
                # defensive: ignore trap callback errors
                pass

        # Enemies ignore traps (no damage/knockback)

        # Simple separation to avoid stacking (gentle, respects map) — keep as fallback but tuned
        if self.group:
            # reduce the previous fallback overlap push — the new local separation reduces stacking earlier
            sep = self.size * 0.55
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
                        push_x += (dxo / d) * overlap * 0.35
                        push_y += (dyo / d) * overlap * 0.35
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

        # determine facing (use orig direction so wandering faces target and chasing faces player)
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
            # Only cast when actively chasing the player.
            # When not chasing, gently randomise/reset the timer so a re-entry doesn't immediately fire.
            if chasing:
                self.cast_timer -= dt
                if self.cast_timer <= 0:
                    # spawn projectile(s) toward player center
                    pc_x = self.x + self.size / 2
                    pc_y = self.y + self.size / 2
                    px, py = player_pos
                    vx = px - pc_x
                    vy = py - pc_y
                    vd = math.hypot(vx, vy)
                    if vd > 1e-4:
                        vx /= vd
                        vy /= vd
                        # NEW: boss volley casting (multi-shot and optional ring)
                        if getattr(self, "is_boss", False) and getattr(self, "volley_count", 1) > 1:
                            # spread fan toward the player
                            spread = float(getattr(self, "volley_spread_deg", 60.0))
                            n = int(getattr(self, "volley_count", 7))
                            base_ang = math.degrees(math.atan2(vy, vx))
                            if n <= 1:
                                angles = [base_ang]
                            else:
                                angles = [base_ang + (-spread/2.0 + spread*(i/(n-1))) for i in range(n)]
                            for ang_deg in angles:
                                rad = math.radians(ang_deg)
                                dvx, dvy = math.cos(rad), math.sin(rad)
                                self.projectiles.append({
                                    'x': pc_x,
                                    'y': pc_y,
                                    'vx': dvx,
                                    'vy': dvy,
                                    'speed': self.projectile_speed,
                                    'angle': ang_deg,
                                    'spin': random.uniform(-360.0, 360.0)
                                })
                            # occasional ring burst around the boss
                            if getattr(self, "volley_ring", False):
                                ring_n = int(getattr(self, "volley_ring_count", 16))
                                ring_n = max(6, ring_n)
                                for i in range(ring_n):
                                    ang = (2.0 * math.pi) * (i / float(ring_n))
                                    dvx, dvy = math.cos(ang), math.sin(ang)
                                    self.projectiles.append({
                                        'x': pc_x,
                                        'y': pc_y,
                                        'vx': dvx,
                                        'vy': dvy,
                                        'speed': self.projectile_speed,
                                        'angle': math.degrees(ang),
                                        'spin': random.uniform(-360.0, 360.0)
                                    })
                        else:
                            # default single shot
                            self.projectiles.append({
                                'x': pc_x,
                                'y': pc_y,
                                'vx': vx,
                                'vy': vy,
                                'speed': self.projectile_speed,
                                'angle': math.degrees(math.atan2(vy, vx)),
                                'spin': random.uniform(-360.0, 360.0)
                            })
                        self.cast_timer = self.cast_cooldown
            else:
                # keep some headroom on the timer to avoid instant fire after gaining aggro
                # pick a value between 20% and 100% of cooldown if timer would otherwise be small
                if self.cast_timer <= int(self.cast_cooldown * 0.2):
                    self.cast_timer = random.randint(int(self.cast_cooldown * 0.2), self.cast_cooldown)

            # move projectiles and prune only on wall / out-of-bounds
            pruned: List[Dict[str, float]] = []
            for p in self.projectiles:
                # move scaled similar to other movement
                p['x'] += p['vx'] * p['speed'] * (dt / 16.0)
                p['y'] += p['vy'] * p['speed'] * (dt / 16.0)
                # advance rotational angle (spin is degrees per second)
                try:
                    p['angle'] = (p.get('angle', 0.0) + p.get('spin', 0.0) * (dt / 1000.0)) % 360.0
                except Exception:
                    p['angle'] = p.get('angle', 0.0)
                 # only remove projectile if it hits a wall or goes out of bounds (is_wall -> True)
                try:
                    hit_wall = False
                    if is_wall is not None:
                        hit_wall = bool(is_wall(p['x'], p['y']))
                    # if it hit a wall (or is out-of-bounds as defined by is_wall), drop it
                    if hit_wall:
                        # notify external handler (e.g. main) so it can spawn break particles
                        try:
                            if on_projectile_break:
                                on_projectile_break(p['x'], p['y'], p)
                        except Exception:
                            pass
                        # drop (do not append)
                        continue
                    # otherwise, keep projectile (it can pass through lava/traps/etc.)
                    pruned.append(p)
                except Exception:
                    # defensive: if callback fails, keep projectile so it can be handled later
                    pruned.append(p)
            self.projectiles = pruned

    def draw(self, surface: pygame.Surface, offset_x: int = 0, offset_y: int = 0) -> None:
        if not self.alive or not self.sprites:
            return
        # Draw shadow under enemy (ground position). For jumping slimes compute ground position and scale.
        # ground center (cx_ground, cy_ground) defaults to foot center beneath current x/y
        cx = self.x + self.size / 2 + offset_x
        cy = self.y + self.size / 2 + offset_y
        shadow_w = int(self.size * 0.9)
        shadow_h = int(self.size * 0.32)
        shadow_x = int(self.x + offset_x + (self.size - shadow_w) / 2)
        shadow_y = int(self.y + offset_y + self.size - shadow_h / 2)
        # If prejumping, compute ground interpolation (start->landing) and shrink shadow by height factor
        if self.prejumping and self._jump_start is not None and self._landing is not None:
            # recover same t used in update
            t = 1.0 - max(0, self.prejump_timer) / float(max(1, self.prejump_duration))
            s_x, s_y = self._jump_start
            l_x, l_y = self._landing
            ground_x = s_x + (l_x - s_x) * t
            ground_y = s_y + (l_y - s_y) * t
            shadow_x = int(ground_x + offset_x + (self.size - shadow_w) / 2)
            shadow_y = int(ground_y + offset_y + self.size - shadow_h / 2)
            # height fraction (0..1)
            height_frac = (4.0 * t * (1.0 - t))  # 0..1 peaked at t=0.5
            # shrink shadow as height grows
            sh_w = max(6, int(shadow_w * (1.0 - 0.5 * height_frac)))
            sh_h = max(3, int(shadow_h * (1.0 - 0.6 * height_frac)))
        else:
            sh_w = shadow_w
            sh_h = shadow_h
        try:
            sh_surf = pygame.Surface((sh_w, sh_h), pygame.SRCALPHA)
            pygame.draw.ellipse(sh_surf, (0, 0, 0, 120), sh_surf.get_rect())
            surface.blit(sh_surf, (shadow_x, shadow_y))
        except Exception:
            pass
        # Rendering: show preparing sprite briefly, then in-air uses normal (idle) image, landing returns to normal.
        if getattr(self, "preparing", False) and isinstance(self.sprites, dict) and "jump" in self.sprites:
            frames = self.sprites.get("jump") or []
            if not frames:
                return
            img = frames[self.frame % len(frames)]
        else:
            if isinstance(self.sprites, dict):
                if self.prejumping:
                    # in-air: display the normal (idle) sprite so the slime looks "in flight" but not showing preparing image
                    frames = self.sprites.get("idle") or self.sprites.get("down") or []
                else:
                    frames = self.sprites.get(self.facing) or self.sprites.get("down") or []
                if not frames:
                    return
                img = frames[self.frame % len(frames)]
            else:
                frames = list(self.sprites)
                if not frames:
                    return
                img = frames[self.frame % len(frames)]
        # tint layers: red when hit, green when poison ticks (green overrides red briefly)
        draw_img = img
        if getattr(self, "poison_green_timer", 0) > 0:
            try:
                draw_img = img.copy()
                draw_img.fill((60, 200, 60, 0), special_flags=pygame.BLEND_RGBA_ADD)
            except Exception:
                draw_img = img
        elif getattr(self, "flash_timer", 0) > 0:
            try:
                draw_img = img.copy()
                draw_img.fill((200, 40, 40, 0), special_flags=pygame.BLEND_RGBA_ADD)
            except Exception:
                draw_img = img
        surface.blit(draw_img, (int(self.x) + offset_x, int(self.y) + offset_y))

        # draw projectiles (if any) — use image when available, otherwise fallback to circle
        if self.can_cast and self.projectiles:
            proj_img = getattr(self, "projectile_img", None)
            for p in self.projectiles:
                px = int(p['x']) + offset_x
                py = int(p['y']) + offset_y
                if proj_img:
                    # rotate projectile image by its per-projectile angle (if present)
                    ang = int(p.get('angle', 0.0))
                    try:
                        rimg = pygame.transform.rotate(proj_img, -ang)
                        rect = rimg.get_rect(center=(px, py))
                        surface.blit(rimg, rect.topleft)
                    except Exception:
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
    speed: float = 1,
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
        def _clamp_pos(x_val: float, size_px: int) -> float:
            """Clamp top-left x/y so the enemy rect remains fully inside the map pixel bounds."""
            min_x = offset_x
            min_y = offset_y
            max_x = offset_x + WIDTH * tile_size - size_px
            max_y = offset_y + HEIGHT * tile_size - size_px
            # clamp both axes when called individually by caller (we'll call twice)
            return max(min_x, min(x_val, max_x))

        if kind_choice == "slime":
            s_size = max(16, int(enemy_size * 0.75))  # slimes slightly smaller
            s_speed = 0.0                             # slimes move by jumping
            s_hp = 10
            sprite_dict = load_enemy_sprites(slime_files, s_size) or None
            ex = tlx + (tile_size - s_size) / 2
            ey = tly + (tile_size - s_size) / 2
            # clamp so enemy is fully inside map bounds
            ex = _clamp_pos(ex, s_size)
            ey = max(offset_y, min(ey, offset_y + HEIGHT * tile_size - s_size))
            e = Enemy(ex, ey, s_size, speed=s_speed, hp=s_hp, sprites=sprite_dict, can_jump_lava=False)
            e.is_slime = True
            e.kind = "slime"  # NEW: tag for scoring
            # more measured hop cadence; start staggered so they don't all jump immediately
            e.hop_cooldown = 1200
            # bias initial hop timer to a shorter value so slimes will attempt a hop soon after spawning
            e.hop_timer = random.randint(0, max(0, e.hop_cooldown // 3))
            # keep the "preparing to jump" pose a bit longer so players have extra reaction time
            # default preparing_duration was small; extend it for slimes only
            e.preparing_duration = max(220, int(getattr(e, "preparing_duration", 120)))
            # adjust jump reach
            e.max_jump_distance = float(s_size) * 3.5
            return e
        if kind_choice == "ghost":
            g_size = enemy_size 
            g_speed = max(0.3, speed * 0.3)  # Reduced to be slowest
            g_hp = 5
            sprite_dict = load_enemy_sprites(ghost_files, g_size) or None
            # make ghost sprites slightly transparent if loaded
            if sprite_dict:
                for key, frames in sprite_dict.items():
                    for surf in frames:
                        try:
                            surf.set_alpha(240)
                        except Exception:
                            pass
            ex = tlx + (tile_size - g_size) / 2
            ey = tly + (tile_size - g_size) / 2
            # clamp positions so ghosts don't end up partially outside the map
            ex = _clamp_pos(ex, g_size)
            ey = max(offset_y, min(ey, offset_y + HEIGHT * tile_size - g_size))
            e = Enemy(ex, ey, g_size, speed=g_speed, hp=g_hp, sprites=sprite_dict, can_fly=True)
            e.kind = "ghost"  # NEW: tag for scoring
            return e
        if kind_choice == "mage":
            m_size = enemy_size
            m_speed = max(0.6, speed * 0.8)  # Increased to be second fastest
            m_hp = 15
            sprite_dict = load_enemy_sprites(mage_files, m_size) or None
            ex = tlx + (tile_size - m_size) / 2
            ey = tly + (tile_size - m_size) / 2
            ex = _clamp_pos(ex, m_size)
            ey = max(offset_y, min(ey, offset_y + HEIGHT * tile_size - m_size))
            e = Enemy(
                ex, ey, m_size,
                speed=m_speed,
                hp=m_hp,
                sprites=sprite_dict,
                can_cast=True,
                cast_cooldown=5000,  # Increased from 3000 to 5000ms (5 seconds between casts)
                projectile_speed=3.0,
                cast_stop_distance=140
            )
            e.kind = "mage"  # NEW: tag for scoring
            # attempt to load the single projectile PNG "mage_magic.png" from sprites/
            sprites_dir = Path(__file__).parent.joinpath("sprites")
            fp = sprites_dir.joinpath("mage_magic.png")
            if fp.exists():
                try:
                    img = pygame.image.load(str(fp)).convert_alpha()
                    # make projectile much bigger (increase multiplier)
                    size_px = max(24, int(m_size * 0.8))  # increased from 12/0.5 to 24/0.8
                    e.projectile_img = pygame.transform.scale(img, (size_px, size_px))
                except Exception:
                    e.projectile_img = None
            else:
                e.projectile_img = None
            return e
        # default: zombie
        z_size = enemy_size
        z_speed = speed * 0.8  # Changed to 80% of base speed
        z_hp = 10
        sprite_dict = load_enemy_sprites(zombie_files, z_size) or None
        ex = tlx + (tile_size - z_size) / 2
        ey = tly + (tile_size - z_size) / 2
        ex = _clamp_pos(ex, z_size)
        ey = max(offset_y, min(ey, offset_y + HEIGHT * tile_size - z_size))
        e = Enemy(ex, ey, z_size, speed=z_speed, hp=z_hp, sprites=sprite_dict)
        e.kind = "zombie"  # NEW: tag for scoring
        return e
    # spawn the requested number of enemies at shuffled candidate locations
    for i in range(min(count, len(candidates))):
        tlx, tly = candidates[i]
        if kind == "mix":
            chosen = random.choice(["zombie", "slime", "ghost", "mage"])
        else:
            chosen = kind
        enemies.append(make_enemy(chosen, tlx, tly))

    # assign group reference so enemies can avoid stacking
    for e in enemies:
        e.group = enemies

    return enemies