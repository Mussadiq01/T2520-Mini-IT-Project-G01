import pygame
import sys
from pathlib import Path

pygame.font.init()

def get_font(size):
	# small helper - prefer bundled font if present
	base = Path(__file__).parent
	for ext in ("ttf", "otf"):
		p = base.joinpath("sprites", f"font.{ext}")
		if p.exists():
			try:
				return pygame.font.Font(str(p), size)
			except Exception:
				break
	return pygame.font.SysFont("arial", size, bold=True)

def _build_blur(snapshot, target_size):
	if snapshot:
		try:
			sw, sh = snapshot.get_size()
			small = pygame.transform.smoothscale(snapshot, (max(1, sw//12), max(1, sh//12)))
			return pygame.transform.smoothscale(small, target_size)
		except Exception:
			pass
	# fallback: dark surface
	s = pygame.Surface(target_size)
	s.fill((20,20,20))
	return s

def show_pause_overlay(snapshot, screen_surface):
	"""Block until user chooses Resume / Options / Quit -> returns tuple like ("resume", None) etc."""
	sw, sh = screen_surface.get_size()
	blurred = _build_blur(snapshot, (sw, sh))
	# smaller fonts so labels fit on smaller screens
	title_f = get_font(40)
	btn_f = get_font(22)
	clock = pygame.time.Clock()

	resume_rect = pygame.Rect((sw//2 - 140, sh//2 - 70, 280, 48))
	options_rect = pygame.Rect((sw//2 - 140, sh//2 - 10, 280, 48))
	quit_rect = pygame.Rect((sw//2 - 140, sh//2 + 50, 280, 48))

	while True:
		mouse_pos = pygame.mouse.get_pos()
		for ev in pygame.event.get():
			if ev.type == pygame.QUIT:
				return ("menu", None)
			if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
				return ("resume", None)
			if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
				mx,my = ev.pos
				if resume_rect.collidepoint((mx,my)):
					return ("resume", None)
				if options_rect.collidepoint((mx,my)):
					return ("options", None)
				if quit_rect.collidepoint((mx,my)):
					return ("menu", None)

		screen_surface.blit(blurred, (0,0))
		overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
		overlay.fill((0,0,0,160))
		screen_surface.blit(overlay, (0,0))

		panel_w, panel_h = 520, 300
		panel = pygame.Rect((sw-panel_w)//2, (sh-panel_h)//2, panel_w, panel_h)
		pygame.draw.rect(screen_surface, (30,30,30), panel)
		pygame.draw.rect(screen_surface, (120,120,120), panel, 3)

		title_surf = title_f.render("Paused", True, (220,220,220))
		screen_surface.blit(title_surf, title_surf.get_rect(center=(sw//2, panel.top + 40)))

		pygame.draw.rect(screen_surface, (200,200,200), resume_rect)
		pygame.draw.rect(screen_surface, (200,200,200), options_rect)
		pygame.draw.rect(screen_surface, (200,200,200), quit_rect)

		# Hover feedback: render label green when hovered
		res_color = (0,200,0) if resume_rect.collidepoint(mouse_pos) else (0,0,0)
		opt_color = (0,200,0) if options_rect.collidepoint(mouse_pos) else (0,0,0)
		quit_color = (0,200,0) if quit_rect.collidepoint(mouse_pos) else (0,0,0)
		screen_surface.blit(btn_f.render("Resume (Esc)", True, res_color), btn_f.render("Resume (Esc)", True, res_color).get_rect(center=resume_rect.center))
		screen_surface.blit(btn_f.render("Options", True, opt_color), btn_f.render("Options", True, opt_color).get_rect(center=options_rect.center))
		screen_surface.blit(btn_f.render("Quit to Menu", True, quit_color), btn_f.render("Quit to Menu", True, quit_color).get_rect(center=quit_rect.center))

		pygame.display.update()
		clock.tick(60)

def show_death_screen(screen_surface):
		"""Block until user clicks Quit to Main Menu. Returns when user chooses to quit."""
		sw, sh = screen_surface.get_size()
		clock = pygame.time.Clock()
		# slightly smaller fonts so the title fits comfortably in the panel
		title_f = get_font(40)
		btn_f = get_font(20)

		# create a snapshot to darken background for effect
		try:
			snap = screen_surface.copy()
		except Exception:
			snap = None
		blurred = _build_blur(snap, (sw, sh))

		btn_rect = pygame.Rect((sw//2 - 140, sh//2 + 40, 280, 56))

		while True:
			mouse_pos = pygame.mouse.get_pos()
			for ev in pygame.event.get():
				if ev.type == pygame.QUIT:
					# signal quit to menu
					return ("menu", None)
				if ev.type == pygame.KEYDOWN:
					if ev.key == pygame.K_ESCAPE:
						# treat ESC as quit to menu on death screen
						return ("menu", None)
				if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
					if btn_rect.collidepoint(ev.pos):
						return ("menu", None)

			screen_surface.blit(blurred, (0,0))
			overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
			overlay.fill((0,0,0,180))
			screen_surface.blit(overlay, (0,0))

			panel_w, panel_h = 520, 240
			panel = pygame.Rect((sw-panel_w)//2, (sh-panel_h)//2, panel_w, panel_h)
			pygame.draw.rect(screen_surface, (30,30,30), panel)
			pygame.draw.rect(screen_surface, (150,20,20), panel, 3)

			title = title_f.render("You died!", True, (220, 180, 180))
			screen_surface.blit(title, title.get_rect(center=(sw//2, panel.top + 70)))

			pygame.draw.rect(screen_surface, (200,200,200), btn_rect)
			btn_color = (0,200,0) if btn_rect.collidepoint(mouse_pos) else (0,0,0)
			screen_surface.blit(btn_f.render("Quit to Menu", True, btn_color), btn_f.render("Quit to Menu", True, btn_color).get_rect(center=btn_rect.center))

			pygame.display.update()
			clock.tick(60)
