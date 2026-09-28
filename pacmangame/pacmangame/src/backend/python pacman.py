import pygame
import sys
import random
from enum import Enum

# ---------- Constants ----------
TILE = 24
ROWS, COLS = 21, 19
WIDTH, HEIGHT = COLS * TILE, ROWS * TILE + 40  # extra 40px for HUD
FPS = 60

BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
YELLOW  = (255, 235, 59)
BLUE    = (25, 25, 112)
RED     = (255, 82, 82)
PINK    = (255, 143, 171)
CYAN    = (0, 229, 255)
ORANGE  = (255, 160, 0)
FRIGHT  = (33, 33, 222)

# Maze legend:
# '#' wall  '.' dot  'o' power pellet  ' ' empty  '-' ghost door
MAZE = [
"###################",
"#........#........#",
"#o##.###.#.###.##o#",
"#.................#",
"#.##.#.#####.#.##.#",
"#....#...#...#....#",
"####.###.#.###.####",
"####.#.......#.####",
"####.#.##-##.#.####",
"#......#---#......#",
"####.#.#####.#.####",
"####.#.......#.####",
"####.#.#####.#.####",
"#........#........#",
"#.##.###.#.###.##.#",
"#o..#..........#..#",
"###.#.#.#####.#.###",
"###.#.#.....#.#.###",
"#.....#.###.#.....#",
"###################",
]

class Dir(Enum):
    UP    = (0, -1)
    DOWN  = (0, 1)
    LEFT  = (-1, 0)
    RIGHT = (1, 0)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("PAC-MAN")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 28)
big_font = pygame.font.Font(None, 64)

# ---------- Board ----------
class Board:
    def __init__(self, layout):
        self.grid = [list(row) for row in layout]
        self.dots = 0
        for y, row in enumerate(self.grid):
            for x, ch in enumerate(row):
                if ch in ('.', 'o'):
                    self.dots += 1

    def is_wall(self, x, y):
        if 0 <= x < COLS and 0 <= y < ROWS:
            return self.grid[y][x] == '#'
        return True

    def at(self, x, y):
        if 0 <= x < COLS and 0 <= y < ROWS:
            return self.grid[y][x]
        return '#'

    def eat(self, x, y):
        """Eat a dot/pellet at tile. Returns 'dot', 'power', or None."""
        if self.grid[y][x] == '.':
            self.grid[y][x] = ' '
            self.dots -= 1
            return 'dot'
        if self.grid[y][x] == 'o':
            self.grid[y][x] = ' '
            self.dots -= 1
            return 'power'
        return None

# ---------- Actors ----------
class Actor:
    def __init__(self, x, y, color, speed):
        self.tile_x, self.tile_y = x, y
        self.px = x * TILE
        self.py = y * TILE
        self.color = color
        self.speed = speed
        self.dir = None
        self.next_dir = None
        self.mouth = 0

    def tile_centered(self):
        return (self.px % TILE == 0 and self.py % TILE == 0)

    def can_move(self, d, board):
        if d is None:
            return False
        nx = self.tile_x + d.value[0]
        ny = self.tile_y + d.value[1]
        return not board.is_wall(nx, ny)

    def update_tile(self):
        self.tile_x = round(self.px / TILE)
        self.tile_y = round(self.py / TILE)

    def draw(self, surf):
        cx, cy = self.px + TILE // 2, self.py + TILE // 2 + 40
        pygame.draw.circle(surf, self.color, (cx, cy), TILE // 2 - 2)

class Pacman(Actor):
    def __init__(self, x, y):
        super().__init__(x, y, YELLOW, 3)

    def move(self, board):
        if self.tile_centered():
            self.update_tile()
            if self.next_dir and self.can_move(self.next_dir, board):
                self.dir = self.next_dir
            if not self.can_move(self.dir, board):
                self.dir = None
        if self.dir:
            self.px += self.dir.value[0] * self.speed
            self.py += self.dir.value[1] * self.speed
            self.mouth = (self.mouth + 1) % 30

    def draw(self, surf):
        cx, cy = self.px + TILE // 2, self.py + TILE // 2 + 40
        # base angle for facing direction
        if self.dir == Dir.LEFT:
            base = 180
        elif self.dir == Dir.UP:
            base = 90
        elif self.dir == Dir.DOWN:
            base = 270
        else:
            base = 0
        mouth_angle = 30 + 15 * abs(15 - self.mouth) // 15
        v1 = pygame.math.Vector2(1, 0).rotate(base - mouth_angle)
        v2 = pygame.math.Vector2(1, 0).rotate(base + mouth_angle)
        pygame.draw.circle(surf, YELLOW, (cx, cy), TILE // 2 - 2)
        pygame.draw.polygon(surf, BLACK, [
            (cx, cy),
            (cx + (TILE // 2) * v1.x, cy + (TILE // 2) * v1.y),
            (cx + (TILE // 2) * v2.x, cy + (TILE // 2) * v2.y),
        ])

class Ghost(Actor):
    COLORS = [RED, PINK, CYAN, ORANGE]

    def __init__(self, x, y, idx):
        super().__init__(x, y, self.COLORS[idx], 2)
        self.home = (x, y)
        self.frightened = 0   # frames remaining
        self.in_house = idx != 0  # first ghost starts out

    def choose_dir(self, board, pac):
        options = [d for d in Dir if self.can_move(d, board)]
        # prevent reversing unless no options
        if self.dir and len(options) > 1:
            rev = Dir((-self.dir.value[0], -self.dir.value[1]))
            options = [d for d in options if d != rev]
        if not options:
            return None
        if self.frightened > 0:
            return random.choice(options)
        # chase: pick option that gets closest to pac-man (simple AI)
        best, best_d = None, 10**9
        for d in options:
            nx, ny = self.tile_x + d.value[0], self.tile_y + d.value[1]
            dist = (nx - pac.tile_x) ** 2 + (ny - pac.tile_y) ** 2
            if dist < best_d:
                best, best_d = d, dist
        return best

    def move(self, board, pac):
        if self.frightened > 0:
            self.frightened -= 1
        if self.tile_centered():
            self.update_tile()
            self.dir = self.choose_dir(board, pac)
        if self.dir:
            self.px += self.dir.value[0] * self.speed
            self.py += self.dir.value[1] * self.speed

    def respawn(self):
        self.px, self.py = self.home[0] * TILE, self.home[1] * TILE
        self.tile_x, self.tile_y = self.home
        self.frightened = 0
        self.dir = None

    def draw(self, surf):
        cx, cy = self.px + TILE // 2, self.py + TILE // 2 + 40
        color = FRIGHT if self.frightened > 0 else self.color
        pygame.draw.circle(surf, color, (cx, cy - 2), TILE // 2 - 2)
        pygame.draw.rect(surf, color, (cx - TILE // 2 + 2, cy - 2, TILE - 4, TILE // 2))
        # eyes
        pygame.draw.circle(surf, WHITE, (cx - 5, cy - 4), 3)
        pygame.draw.circle(surf, WHITE, (cx + 5, cy - 4), 3)
        pygame.draw.circle(surf, BLUE, (cx - 5, cy - 4), 1)
        pygame.draw.circle(surf, BLUE, (cx + 5, cy - 4), 1)

# ---------- Game ----------
def main():
    board = Board(MAZE)
    pac = Pacman(9, 15)
    ghosts = [Ghost(8, 9, 0), Ghost(9, 9, 1), Ghost(10, 9, 2), Ghost(9, 8, 3)]
    score, lives = 0, 3
    state = "play"  # play, win, gameover

    KEYMAP = {pygame.K_UP: Dir.UP, pygame.K_DOWN: Dir.DOWN,
              pygame.K_LEFT: Dir.LEFT, pygame.K_RIGHT: Dir.RIGHT,
              pygame.K_w: Dir.UP, pygame.K_s: Dir.DOWN,
              pygame.K_a: Dir.LEFT, pygame.K_d: Dir.RIGHT}

    while True:
        clock.tick(FPS)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key in KEYMAP:
                    pac.next_dir = KEYMAP[e.key]
                if e.key == pygame.K_r and state != "play":
                    main(); return

        if state == "play":
            pac.move(board)
            for g in ghosts:
                g.move(board, pac)

            # eat dots
            item = board.eat(pac.tile_x, pac.tile_y)
            if item == 'dot':
                score += 10
            elif item == 'power':
                score += 50
                for g in ghosts:
                    g.frightened = 400

            # collisions
            for g in ghosts:
                if g.tile_x == pac.tile_x and g.tile_y == pac.tile_y:
                    if g.frightened > 0:
                        score += 200
                        g.respawn()
                    else:
                        lives -= 1
                        pac = Pacman(9, 15)
                        for gh in ghosts:
                            gh.respawn()
                        if lives <= 0:
                            state = "gameover"

            if board.dots == 0:
                state = "win"

        # ---------- Draw ----------
        screen.fill(BLACK)
        # maze
        for y, row in enumerate(board.grid):
            for x, ch in enumerate(row):
                rect = pygame.Rect(x * TILE, y * TILE + 40, TILE, TILE)
                if ch == '#':
                    pygame.draw.rect(screen, BLUE, rect)
                elif ch == '.':
                    pygame.draw.circle(screen, WHITE, rect.center, 3)
                elif ch == 'o':
                    pygame.draw.circle(screen, WHITE, rect.center, 7)
        # HUD
        screen.blit(font.render(f"SCORE {score}", True, WHITE), (10, 8))
        screen.blit(font.render(f"LIVES {'o' * lives}", True, YELLOW), (WIDTH - 130, 8))

        pac.draw(screen)
        for g in ghosts:
            g.draw(screen)

        if state in ("win", "gameover"):
            msg = "YOU WIN!  Press R" if state == "win" else "GAME OVER  Press R"
            txt = big_font.render(msg, True, YELLOW if state == "win" else RED)
            screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 20))

        pygame.display.flip()

if __name__ == "__main__":
    main()















