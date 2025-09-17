from dataclasses import dataclass
from typing import List

@dataclass
class Weapon:
    name: str
    damage: int
    arc_deg: int          # degrees of swing arc (0 == straight stab)
    cooldown_ms: int      # additional cooldown after swing animation completes
    swing_ms: int         # duration of the active swing / stab animation
    stun_ms: int = 0      # optional stun applied on hit (enemies must have stun_timer attr)
    sprite_name: str = "sword.png"  # sprite filename in sprites/ folder (fallback handled by caller)
    # Bleed effect (optional): during bleed_duration_ms deal 1 damage every bleed_interval_ms
    bleed_duration_ms: int = 0
    bleed_interval_ms: int = 0
    # NEW: optional projectile settings (player‑fired)
    projectile_damage: int = 0          # >0 enables projectile on attack
    projectile_speed: float = 0.0       # pixels / second
    projectile_life_ms: int = 0         # lifespan
    projectile_sprite: str = ""         # sprite filename in sprites/

# Order matters (keys 1-5 map directly to these indices)
WEAPON_LIST: List[Weapon] = [
    Weapon(name="Sword",        damage=5,  arc_deg=120, cooldown_ms=300, swing_ms=250, stun_ms=0,   sprite_name="sword.png"),
    Weapon(name="Mallet",       damage=10,  arc_deg=90,  cooldown_ms=600, swing_ms=250, stun_ms=600, sprite_name="mallet.png"),
    Weapon(name="Dagger",       damage=3,  arc_deg=0,   cooldown_ms=50,  swing_ms=150,  stun_ms=0,   sprite_name="dagger.png"),
    Weapon(name="Katana",       damage=8, arc_deg=360, cooldown_ms=300, swing_ms=300, stun_ms=0,
           bleed_duration_ms=2500, bleed_interval_ms=500, sprite_name="katana.png"),
    Weapon(name="The Descender", damage=15, arc_deg=240, cooldown_ms=200, swing_ms=200, stun_ms=0,
           sprite_name="the_descender.png",
           projectile_damage=5, projectile_speed=800, projectile_life_ms=1000, projectile_sprite="sunball.png"),
]

__all__ = ["Weapon", "WEAPON_LIST"]
