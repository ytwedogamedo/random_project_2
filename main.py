import random

import pygame as pg


"""
Main file responsible for a very basic wave shooter game.

This file is intentionally kept as one file for now so it is easier to follow.
Later, the classes could be split into settings.py, sprites.py, and main.py like
Rohnin's project, but that would add more files before the game needs them.

Big idea of the game:
1. Pygame opens a window.
2. The Game class runs the main loop.
3. Every loop checks input, updates objects, then draws everything.
4. The player survives monsters with a mouse aimed projectile launcher.
5. If the player clears wave 10, the player wins.

Useful Pygame ideas used in this file:
- Surface: an image or drawing area.
- Rect: a rectangle that stores position and size.
- Sprite: an object pygame can update, draw, and collide.
- Group: a collection of sprites that can be updated/drawn together.
- Vector2: stores x and y together for movement math.
- dt: delta time, the time passed since the last frame.
"""

# Date of Last Update 24hr time
__updated__ = '2026-04-17 00:26:28'

# TODO Add sound effects for shooting and getting hit
# TODO Add simple image assets later if I want it to look less like shapes
# TODO Add more enemy types if the basic version feels too easy
# TODO Balance monster speed/health after playtesting all 10 waves


# basic settings for the game window, title, and win condition
WIDTH = 960  # width of the pygame window in pixels
HEIGHT = 640  # height of the pygame window in pixels
FPS = 60  # frames per second, controls how often the game loop tries to run
TITLE = "Wave Shooter"  # text shown at the top of the pygame window
MAX_WAVE = 10  # once this wave is cleared, the player wins
MAX_HEALTH = 6  # number of hits the player can take before game over

# colors are split into variables so the draw code is easier to tweak later
BG_COLOR = (18, 22, 31)  # dark color behind the arena
ARENA_COLOR = (28, 38, 53)  # main rectangle where the game happens
GRID_COLOR = (38, 52, 72)  # subtle grid lines inside the arena
PLAYER_COLOR = (90, 220, 255)  # blue player circle
PLAYER_HIT_COLOR = (255, 255, 255)  # white flash after player takes damage
MONSTER_COLOR = (255, 110, 110)  # normal red monster circle
TANK_COLOR = (255, 155, 95)  # orange tank monster circle
PROJECTILE_COLOR = (255, 240, 130)  # yellow bullets and launcher barrel
TEXT_COLOR = (240, 245, 255)  # bright text color
MUTED_TEXT_COLOR = (170, 185, 205)  # dimmer text for controls and empty health
ACCENT_COLOR = (120, 255, 160)  # green accent for health/win text
DANGER_COLOR = (255, 90, 90)  # red accent for game over text


def make_circle_surface(radius, color):
    # helper for making simple circular sprite images without needing asset files
    # SRCALPHA lets the surface have a transparent background instead of a black square
    # radius is half the circle's width, so the full surface needs radius * 2
    image = pg.Surface((radius * 2, radius * 2), pg.SRCALPHA)
    # draw the circle in the middle of that transparent square
    pg.draw.circle(image, color, (radius, radius), radius)
    return image


# Projectile sprite class used for shots fired by the player.
class Projectile(pg.sprite.Sprite):
    # projectile class handles the bullets that fly toward the mouse cursor
    def __init__(self, game, position, direction):
        # putting the projectile in both groups lets it get updated/drawn and checked for hits
        # all_sprites means it will be drawn and updated with everything else
        # projectiles means it can be checked against the monsters group later
        super().__init__(game.all_sprites, game.projectiles)
        self.game = game  # store game reference so the projectile can read dt and arena
        # Vector2 stores x and y together and makes movement math easier
        self.pos = pg.Vector2(position)  # projectile starts at the player's current position
        # direction is already normalized, so multiplying it creates the bullet speed
        self.velocity = direction * 760  # pixels per second
        self.radius = 5  # size of the bullet circle
        self.damage = 1  # how much health this bullet removes from a monster
        # image is what pygame draws, rect is what pygame uses for position/collision
        self.image = make_circle_surface(self.radius, PROJECTILE_COLOR)
        self.rect = self.image.get_rect(center=self.pos)

    def update(self):  # called every frame by self.all_sprites.update()
        # bullets move every frame using delta time so speed is framerate independent
        self.pos += self.velocity * self.game.dt
        # after moving the vector position, update the rect so drawing/collision matches
        self.rect.center = self.pos

        # deleting the projectile once it leaves the arena keeps groups clean
        # inflate gives a little extra room so bullets do not disappear exactly on the edge
        if not self.game.arena.inflate(60, 60).collidepoint(self.pos):
            self.kill()


# Enemy sprite class that chases the player.
class Monster(pg.sprite.Sprite):
    # monsters are the enemies that constantly move toward the player
    def __init__(self, game, position, speed, health, radius=16, color=MONSTER_COLOR, score_value=100):
        # each monster goes into all_sprites for drawing and monsters for enemy-specific logic
        super().__init__(game.all_sprites, game.monsters)
        self.game = game  # lets the monster know where the player is
        self.pos = pg.Vector2(position)  # exact x/y position of the monster
        self.speed = speed  # movement speed in pixels per second
        self.health = health  # current monster health
        self.max_health = health  # saved in case I want health bars later
        self.radius = radius  # bigger radius means a bigger enemy
        self.score_value = score_value  # points added when this monster dies
        self.image = make_circle_surface(self.radius, color)  # visual circle for the monster
        # center puts the monster at the spawn position instead of placing its corner there
        self.rect = self.image.get_rect(center=self.pos)

    def update(self):  # called every frame while the monster is alive
        # this vector math makes mobs chase the player from any direction
        # subtracting positions gives the direction from monster to player
        offset = self.game.player.pos - self.pos
        if offset.length_squared() > 0:
            # normalize turns the offset into only a direction, then speed controls movement amount
            self.pos += offset.normalize() * self.speed * self.game.dt
        # keep the pygame rect lined up with the vector position
        self.rect.center = self.pos

    def take_damage(self, amount):
        # if health reaches zero the monster is removed from the sprite groups
        self.health -= amount
        if self.health <= 0:
            # score is stored in the Game class because it belongs to the whole run
            self.game.score += self.score_value
            self.kill()


# Player sprite class that handles movement, shooting, health, and hit flashing.
class Player(pg.sprite.Sprite):
    # player class controls movement, shooting, and health
    def __init__(self, game, position):
        # player only needs all_sprites because it is not part of monsters/projectiles groups
        super().__init__(game.all_sprites)
        self.game = game  # store game reference so the player can access arena, dt, and timers
        self.pos = pg.Vector2(position)  # exact x/y position of the player
        self.speed = 285  # player speed in pixels per second
        self.radius = 18  # player circle size
        self.health = MAX_HEALTH  # starts with full health every new run
        self.fire_delay = 0.16  # seconds between shots
        self.fire_timer = 0  # counts down until the next shot is allowed
        # two images are used so the player can flash white after taking damage
        self.normal_image = make_circle_surface(self.radius, PLAYER_COLOR)
        self.hit_image = make_circle_surface(self.radius, PLAYER_HIT_COLOR)
        self.image = self.normal_image
        self.rect = self.image.get_rect(center=self.pos)

    def update(self):  # frame-by-frame player update
        # the player updates movement first, then shooting, then syncs the rect
        self.handle_movement()
        self.handle_shooting()
        self.update_hit_flash()
        self.rect.center = self.pos

    def handle_movement(self):  # gets keyboard input and moves the player
        # WASD movement uses a vector so diagonal movement can be normalized
        keys = pg.key.get_pressed()
        # start with no movement, then add to x/y depending on which keys are held
        move = pg.Vector2(0, 0)

        if keys[pg.K_w]:  # move up
            move.y -= 1
        if keys[pg.K_s]:  # move down
            move.y += 1
        if keys[pg.K_a]:  # move left
            move.x -= 1
        if keys[pg.K_d]:  # move right
            move.x += 1

        if move.length_squared() > 0:
            # without normalize, diagonal movement would be faster than straight movement
            move = move.normalize()

        # dt means "delta time", which keeps movement consistent even if FPS changes a bit
        self.pos += move * self.speed * self.game.dt
        # clamping keeps the player inside the one little arena area
        # max makes sure the player is not too far left/top
        # min makes sure the player is not too far right/bottom
        self.pos.x = max(self.game.arena.left + self.radius, min(self.pos.x, self.game.arena.right - self.radius))
        self.pos.y = max(self.game.arena.top + self.radius, min(self.pos.y, self.game.arena.bottom - self.radius))

    def handle_shooting(self):  # fires projectiles while left mouse is held
        # cooldown timer stops the player from firing every single frame
        self.fire_timer = max(0, self.fire_timer - self.game.dt)
        if not pg.mouse.get_pressed()[0] or self.fire_timer > 0:
            return

        # subtracting positions gives a vector that points from player to mouse
        direction = pg.Vector2(pg.mouse.get_pos()) - self.pos
        if direction.length_squared() == 0:
            return

        # create a new projectile headed at the current mouse position
        Projectile(self.game, self.pos, direction.normalize())
        # reset the cooldown so another bullet cannot spawn until fire_delay passes
        self.fire_timer = self.fire_delay

    def update_hit_flash(self):
        # blinking white after damage makes it clear the player was hit
        # multiplying the timer by 12 makes the flash blink several times per second
        if self.game.invulnerable_timer > 0 and int(self.game.invulnerable_timer * 12) % 2 == 0:
            self.image = self.hit_image
        else:
            self.image = self.normal_image


# Main game class that owns the window, assets, game state, and game loop.
class Game:
    # main game class that owns the screen, groups, loop, and wave system
    def __init__(self):
        # pg.init starts up pygame modules like display, font, events, and input
        pg.init()
        # set_mode creates the actual window that the player sees
        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        pg.display.set_caption(TITLE)
        self.clock = pg.time.Clock()  # clock controls FPS and gives delta time
        self.font_name = pg.font.match_font("arial")  # basic font for all text
        self.running = True  # when this becomes False, the main loop ends
        # state controls what mode the game is in: start, playing, paused, won, game_over
        self.state = "start"
        # Rect stores the arena position and size: left, top, width, height
        self.arena = pg.Rect(110, 90, 740, 460)
        self.restart_game()

    def restart_game(self):  # resets the game variables and creates a fresh player
        # this resets the run back to wave one for start screen or replay
        self.wave = 1  # start at wave one
        self.score = 0  # score resets on a new run
        self.wave_spawned = False  # False means the current wave has not created enemies yet
        self.wave_timer = 0.75  # short delay before the first wave spawns
        self.invulnerable_timer = 0  # damage cooldown after player is hit
        # sprite groups make it easy to update/draw/check many objects at once
        self.all_sprites = pg.sprite.Group()  # every sprite that should update/draw
        self.monsters = pg.sprite.Group()  # only enemies
        self.projectiles = pg.sprite.Group()  # only player bullets
        # instantiate the player after the groups exist so Player can add itself to all_sprites
        self.player = Player(self, self.arena.center)

    def run(self):  # keeps the game running until the player quits
        # standard game loop: events, update, draw
        while self.running:
            # clock.tick returns milliseconds since last frame, so divide by 1000 for seconds
            self.dt = self.clock.tick(FPS) / 1000
            self.events()
            self.update()
            self.draw()

        pg.quit()

    def start_wave(self):  # creates all monsters for the current wave
        # each new wave adds more enemies and slowly raises difficulty
        self.wave_spawned = True
        # formulas make later waves harder without writing separate code for every wave
        monster_count = 4 + self.wave * 2  # wave 1 has 6, wave 10 has 24
        monster_speed = 90 + self.wave * 12  # enemies move faster each wave
        monster_health = 1 + (self.wave - 1) // 3  # health goes up every 3 waves

        # this loop creates each enemy for the wave
        for index in range(monster_count):
            if self.wave >= 4 and index % 6 == 0:
                # tank monsters appear in later waves and take more shots to kill
                Monster(
                    self,
                    self.random_spawn_position(),
                    monster_speed * 0.72,
                    monster_health + 2,
                    radius=22,
                    color=TANK_COLOR,
                    score_value=175,
                )
            else:
                Monster(
                    self,
                    self.random_spawn_position(),  # each monster gets a random edge spawn
                    monster_speed + random.randint(-10, 25),  # small random speed difference
                    monster_health,
                )

    def random_spawn_position(self):  # chooses where monsters enter the arena
        # monsters spawn around the edge of the arena instead of on top of the player
        margin = 30
        # choosing a random side keeps enemies coming from different directions
        side = random.choice(("top", "bottom", "left", "right"))

        if side == "top":
            # random x on top side
            return random.randint(self.arena.left + margin, self.arena.right - margin), self.arena.top + margin
        if side == "bottom":
            # random x on bottom side
            return random.randint(self.arena.left + margin, self.arena.right - margin), self.arena.bottom - margin
        if side == "left":
            # random y on left side
            return self.arena.left + margin, random.randint(self.arena.top + margin, self.arena.bottom - margin)
        # random y on right side
        return self.arena.right - margin, random.randint(self.arena.top + margin, self.arena.bottom - margin)

    def events(self):  # checks keyboard, mouse, and window events
        # event loop handles quitting, pausing, and restarting from menu/end states
        for event in pg.event.get():
            # QUIT happens when the player clicks the window X button
            if event.type == pg.QUIT:
                self.running = False

            if event.type == pg.KEYDOWN:
                # escape exits the whole game
                if event.key == pg.K_ESCAPE:
                    self.running = False
                elif event.key == pg.K_p and self.state in {"playing", "paused"}:
                    # this switches between playing and paused using one key
                    self.state = "paused" if self.state == "playing" else "playing"
                elif event.key in {pg.K_RETURN, pg.K_r} and self.state in {"start", "won", "game_over"}:
                    # restart before setting playing so all sprites and scores reset correctly
                    self.restart_game()
                    self.state = "playing"

    def update(self):  # updates game logic, but only while actually playing
        # only the active play state should update game logic
        if self.state != "playing":
            return

        # this timer counts down player invincibility after getting hit
        self.invulnerable_timer = max(0, self.invulnerable_timer - self.dt)

        if not self.wave_spawned:
            # before a wave starts, count down so the player gets a moment to breathe
            self.wave_timer = max(0, self.wave_timer - self.dt)
            if self.wave_timer <= 0:
                self.start_wave()

        # this calls update() on player, monsters, and projectiles
        self.all_sprites.update()
        self.handle_collisions()
        self.check_wave_progress()

    def handle_collisions(self):  # handles projectile hits and player damage
        # bullets damage monsters and disappear on contact
        # groupcollide compares every monster to every projectile using circle collision
        # False means monsters are not automatically killed by pygame
        # True means projectiles are deleted automatically after hitting
        hits = pg.sprite.groupcollide(self.monsters, self.projectiles, False, True, pg.sprite.collide_circle)
        for monster, projectiles in hits.items():
            # projectiles is a list in case multiple bullets hit the same monster this frame
            for projectile in projectiles:
                monster.take_damage(projectile.damage)

        # brief invulnerability prevents health from draining instantly on touch
        if self.invulnerable_timer > 0:
            return

        if pg.sprite.spritecollide(self.player, self.monsters, False, pg.sprite.collide_circle):
            self.player.health -= 1
            # after damage, wait a short time before the player can be hurt again
            self.invulnerable_timer = 0.85
            if self.player.health <= 0:
                self.state = "game_over"

    def check_wave_progress(self):  # decides if the player won or should go to the next wave
        # clearing wave 10 wins, otherwise the next wave starts after a short pause
        # if the wave has not started or monsters are still alive, do nothing yet
        if not self.wave_spawned or self.monsters:
            return

        if self.wave >= MAX_WAVE:
            self.state = "won"
        else:
            self.wave += 1
            self.wave_spawned = False
            # this creates the "Wave incoming" pause between waves
            self.wave_timer = 1.25

    def draw(self):  # draws one complete frame to the screen
        # draw order matters: background first, sprites next, ui/overlay last
        self.screen.fill(BG_COLOR)
        self.draw_arena()
        # all_sprites.draw draws each sprite's image at its rect
        self.all_sprites.draw(self.screen)

        if self.state == "playing":
            self.draw_launcher()
            self.draw_crosshair()

        self.draw_hud()

        if self.state != "playing":
            self.draw_overlay()

        # flip pushes everything we just drew onto the visible window
        pg.display.flip()

    def draw_arena(self):  # draws the one little room where the game happens
        # simple arena visuals using pygame shapes instead of image assets
        pg.draw.rect(self.screen, ARENA_COLOR, self.arena, border_radius=14)

        # vertical grid lines
        for x in range(self.arena.left + 40, self.arena.right, 40):
            pg.draw.line(self.screen, GRID_COLOR, (x, self.arena.top), (x, self.arena.bottom), 1)
        # horizontal grid lines
        for y in range(self.arena.top + 40, self.arena.bottom, 40):
            pg.draw.line(self.screen, GRID_COLOR, (self.arena.left, y), (self.arena.right, y), 1)

        # outline around the arena so the boundary is clear
        pg.draw.rect(self.screen, (80, 105, 140), self.arena, 3, border_radius=14)

    def draw_launcher(self):  # draws the small gun barrel pointing toward the mouse
        # small barrel shows the mouse-aimed projectile launcher direction
        direction = pg.Vector2(pg.mouse.get_pos()) - self.player.pos
        if direction.length_squared() == 0:
            return

        direction = direction.normalize()
        # start/end make a short line starting from the player toward the mouse
        start = self.player.pos + direction * 12
        end = self.player.pos + direction * 34
        pg.draw.line(self.screen, PROJECTILE_COLOR, start, end, 7)
        pg.draw.circle(self.screen, PROJECTILE_COLOR, end, 5)

    def draw_hud(self):  # draws wave, score, controls, and health
        # heads-up display shows wave number, enemies left, score, controls, and health
        self.draw_text(f"Wave {self.wave}/{MAX_WAVE}", 28, TEXT_COLOR, 28, 20)
        self.draw_text(f"Monsters Left: {len(self.monsters)}", 22, TEXT_COLOR, 28, 56)
        self.draw_text(f"Score: {self.score}", 22, TEXT_COLOR, 28, 84)
        self.draw_text("Move: WASD  Shoot: Hold Left Click  Pause: P", 19, MUTED_TEXT_COLOR, 28, HEIGHT - 40)

        if self.state == "playing" and not self.wave_spawned:
            # tells the player why no monsters are currently moving
            self.draw_text_center(f"Wave {self.wave} incoming...", 32, ACCENT_COLOR, 70)

        for index in range(MAX_HEALTH):
            # draw filled health circles first, then outlined empty circles
            center = (WIDTH - 34 - index * 28, 38)
            if index < self.player.health:
                pg.draw.circle(self.screen, ACCENT_COLOR, center, 10)
            else:
                pg.draw.circle(self.screen, MUTED_TEXT_COLOR, center, 10, 2)

    def draw_crosshair(self):  # draws the mouse aiming helper
        # crosshair helps aim the projectile launcher with the mouse
        mouse_x, mouse_y = pg.mouse.get_pos()
        pg.draw.circle(self.screen, TEXT_COLOR, (mouse_x, mouse_y), 12, 2)
        pg.draw.line(self.screen, TEXT_COLOR, (mouse_x - 18, mouse_y), (mouse_x + 18, mouse_y), 2)
        pg.draw.line(self.screen, TEXT_COLOR, (mouse_x, mouse_y - 18), (mouse_x, mouse_y + 18), 2)

    def draw_overlay(self):  # draws the menus and end screens
        # overlay is reused for start screen, pause screen, win screen, and game over
        # this transparent surface darkens the whole game behind the menu text
        shade = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        shade.fill((0, 0, 0, 130))
        self.screen.blit(shade, (0, 0))

        # choose the text depending on the current game state
        if self.state == "start":
            title = "Wave Shooter"
            subtitle = "Survive every wave and clear wave 10 to win."
            prompt = "Press Enter to start"
            title_color = TEXT_COLOR
        elif self.state == "paused":
            title = "Paused"
            subtitle = "Take a breath. The monsters are frozen too."
            prompt = "Press P to continue"
            title_color = TEXT_COLOR
        elif self.state == "won":
            title = "You Win"
            subtitle = f"All 10 waves cleared. Final score: {self.score}"
            prompt = "Press Enter or R to play again"
            title_color = ACCENT_COLOR
        else:
            title = "Game Over"
            subtitle = f"You reached wave {self.wave}. Final score: {self.score}"
            prompt = "Press Enter or R to retry"
            title_color = DANGER_COLOR

        self.draw_text_center(title, 58, title_color, HEIGHT // 2 - 86)
        self.draw_text_center(subtitle, 27, TEXT_COLOR, HEIGHT // 2 - 22)
        self.draw_text_center(prompt, 25, ACCENT_COLOR, HEIGHT // 2 + 42)

    def draw_text(self, text, size, color, x, y):  # draws normal left-aligned text
        # helper for left-aligned hud text
        font = pg.font.Font(self.font_name, size)
        surface = font.render(text, True, color)
        self.screen.blit(surface, (x, y))

    def draw_text_center(self, text, size, color, y):  # draws centered menu text
        # helper for centered menu text
        font = pg.font.Font(self.font_name, size)
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(WIDTH // 2, y))
        self.screen.blit(surface, rect)


if __name__ == "__main__":
    # this only runs when this file is started directly with python main.py
    # it creates a Game object and starts the game loop
    Game().run()
