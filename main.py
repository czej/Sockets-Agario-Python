import pygame
import sys
import random
# import math
# import time

from pygame.locals import QUIT, MOUSEMOTION

cell_count = 2000
map_size = 2000
spawn_size = 25
respawn_cells = True
player_color = (255, 0, 0)
background_color = (0, 0, 0)
text_color = (255, 255, 255)

# WIDTH = 1280
# HEIGHT = 720
cells = []
is_alive = True

# counter = 0
# frame_rate = 30
# start_time = 0
# frame_rate_delay = 0.5


class Cell():
    def __init__(self, x, y, color, radius):
        self.radius = radius
        self.color = color
        self.pos_x = x
        self.pos_y = y

    def draw(self, surface, x, y):
        pygame.draw.circle(surface, self.color, (x, y), int(self.radius))


# class Player(Cell):
#     def __init__(self, x, y, color, radius, name):
#         super().__init__(x, y, color, radius)

#     def draw(self, surface, x, y):
#         super().draw(surface, x, y)
#         text = FONT.render(str(round(self.radius)), False, text_color)

#     def collision_check(self):
#         ...


if __name__ == "__main__":
    FPS = 30

    pygame.init()

    pygame.display.set_caption("Agar.io")

    FONT = pygame.font.Font("freesansbold.ttf", 32)
    BIGFONT = pygame.font.Font("freesansbold.ttf", 72)

    CLOCK = pygame.time.Clock()
    SCREEN = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)

    # spawn point cells
    for i in range(cell_count):
        new_cell = Cell(
            random.randint(-map_size, map_size),
            random.randint(-map_size, map_size),
            (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            ),
            5,
        )
        cells.append(new_cell)

    # spawn player
    # player = Player(0, 0, player_color, spawn_size, "Player")

    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            # if event.type == MOUSEMOTION and is_alive:
            #     mouse_x, mouse_y = event.pos
            # else:
            #     mouse_x = WIDTH / 2
            #     mouse_y = HEIGHT / 2

        # if is_alive:
        #     player.collide_check()

        for cell in cells:
            cell.draw(SCREEN, cell.pos_x, cell.pos_y)

        WIDTH, HEIGHT = pygame.display.get_surface().get_size()
        pygame.display.update()
        CLOCK.tick(FPS)
        SCREEN.fill(background_color)
