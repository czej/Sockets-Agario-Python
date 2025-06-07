import socket
import struct
import pygame
import time
from threading import Thread, Lock
from pygame.locals import QUIT, MOUSEMOTION
from newtork_utils import decode_color, receive_message, unpack_cells, receive_exact, unpack_players, unpack_player

pygame.init()

HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = 9999  # The port used by the server

WIDTH = 1280
HEIGHT = 720
FONT = pygame.font.Font("freesansbold.ttf", 32)
BIGFONT = pygame.font.Font("freesansbold.ttf", 72)

# TODO: from config
background_color = (15, 15, 15)
text_color = (255, 255, 255)
spawn_size = 35

cells = {}
cells_lock = Lock()  # OK
players = {}
players_lock = Lock()  # OK
current_player = None
current_client_id = -1


class Cell():
    def __init__(self, cell_id, x, y, color, radius):
        self.cell_id = cell_id  # TODO: is this needed?
        self.radius = radius
        self.color = color
        self.pos_x = x
        self.pos_y = y

    def draw(self, surface, x, y):
        pygame.draw.circle(surface, self.color, (x, y),
                           int(self.radius))  # TODO: why int?


class Player(Cell):
    def __init__(self, username, x, y, color, radius):
        super().__init__(-1, x, y, color, radius)
        self.username = username

    def draw(self, surface, x, y):
        super().draw(surface, x, y)
        # todo if username == curren_username or in different method
        global FONT
        text = FONT.render(str(round(self.radius)), False, text_color)


def parse_cells_data(cell_data):
    for cell in cell_data:
        new_cell = Cell(
            cell[0],
            cell[1],
            cell[2],
            decode_color(cell[3]),
            10  # TODO: send config info in json
        )
        cells[cell[0]] = new_cell


def parse_players_data(players_data, current_player_username):
    for player_data in players_data:
        client_id, username, pos_x, pos_y, color, radius = player_data
        new_player = Player(
            username,
            pos_x,
            pos_y,
            decode_color(color),
            radius
        )

        if username == current_player_username:
            global current_player, current_client_id
            current_player = new_player
            current_client_id = client_id
            print(f"Current client id: {current_client_id}")
        else:
            players[client_id] = new_player


def network_handler(conn):
    """Receive and process cell removal data"""
    while True:
        try:
            event_data = receive_exact(conn, struct.calcsize("I"))
            event = struct.unpack("I", event_data)[0]
            print("Event: ", event)

            if event == 2:  # TODO: enums
                data_format = "Ifff"  # TODO: this should be also in enum
                data = receive_exact(conn, struct.calcsize(data_format))
                client_id, new_pos_x, new_pos_y, new_radius = struct.unpack(data_format, data)

                with players_lock:
                    player = players[client_id]
                    player.pos_x = new_pos_x
                    player.pos_y = new_pos_y
                    player.radius = new_radius

                print(
                    f"New pos: {new_pos_x}, {new_pos_y}, {new_radius}")

            elif event == 5:
                length_data = receive_exact(conn, 4)
                data_length = struct.unpack('I', length_data)[0]
                packed_data = receive_exact(conn, data_length)
                (client_id, username, pos_x, pos_y, color, radius), _ = unpack_player(packed_data=packed_data) 
                print(f"New player has joined: {username}")
                new_player = Player(
                    username,
                    pos_x,
                    pos_y,
                    decode_color(color),
                    radius
                )

                with players_lock:
                    players[client_id] = new_player

            elif event == 7:
                data_format = "I"
                data = receive_exact(conn, struct.calcsize(data_format))
                client_id = struct.unpack(data_format, data)[0]
                with players_lock:
                    players.pop(client_id)

            elif event in (0, 1):
                data_format = "IIII"
                data = receive_exact(conn, struct.calcsize(data_format))
                key, new_pos_x, new_pos_y, new_color = struct.unpack(
                    data_format, data)
                # Remove from local cells dict
                with cells_lock:  # TODO: everywhere or concurrent map
                    cell = cells[key]
                    cell.pos_x = new_pos_x
                    cell.pos_y = new_pos_y
                    cell.color = decode_color(new_color)

                    # cells[key] = cell  # TODO: is this needed?
                    print(f"Removed cell: {key}")
                    print(
                        f"New cell was spawned: {new_pos_x}, {new_pos_y}, {new_color}")
                    
                    print("CELL: ", cells[key].pos_x, cells[key].pos_y, cells[key].color)

                if event == 1:
                    global current_player
                    # TODO no lock, cause only this thread edits -- but other reads!
                    current_player.radius += 0.5

        except Exception as e:
            print(f"Error receiving event or client quitted: {e}")
            break

# TODO: change encoding: ascii to Unicode or UTF? short char


def render_game(conn):
    global WIDTH, HEIGHT
    last_send_time = 0
    SEND_INTERVAL = 1/60  # 60 FPS max
    FPS = 30

    counter = 0
    frame_rate = 30
    start_time = 0
    frame_rate_delay = 0.5

    pygame.display.set_caption("Agar.io")

    CLOCK = pygame.time.Clock()
    SCREEN = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)

    # Start network thread
    network_thread_obj = Thread(
        target=network_handler, args=(conn,))
    network_thread_obj.start()

    global current_player

    while True:
        # start_time_measure = time.time()

        current_time = time.time()

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                data = struct.pack('ff', 999999, 0)
                conn.sendall(data)
                return
            if event.type == MOUSEMOTION:
                mouse_x, mouse_y = event.pos
            else:
                mouse_x = WIDTH / 2
                mouse_y = HEIGHT / 2

        # Throttle sending to avoid spam
        if current_time - last_send_time > SEND_INTERVAL:
            data = struct.pack('ff', (mouse_x - WIDTH / 2), (mouse_y - HEIGHT / 2))
            conn.sendall(data)
            last_send_time = current_time

        current_player.pos_x += ((mouse_x - WIDTH / 2) /
                                 current_player.radius / 2)
        current_player.pos_y += ((mouse_y - HEIGHT / 2) /
                                 current_player.radius / 2)

        # print(player.pos_x)
        with cells_lock:
            for cell in cells.values():
                cell.draw(
                    SCREEN,
                    cell.pos_x - current_player.pos_x + WIDTH / 2,
                    cell.pos_y - current_player.pos_y + HEIGHT / 2
                )

        with players_lock:
            for other_player in players.values():
                # print("other player: ", other_player.username)
                other_player.draw(
                    SCREEN,
                    other_player.pos_x - current_player.pos_x + WIDTH / 2,
                    other_player.pos_y - current_player.pos_y + HEIGHT / 2
                )

        current_player.draw(SCREEN, (WIDTH / 2), (HEIGHT / 2))

        # text = BIGFONT.render("Game over", False, text_color)
        # SCREEN.blit(text, (WIDTH / 2 - 150, HEIGHT / 2 - 40))

        text = FONT.render(
            "Mass: " + str((current_player.radius)), False, text_color)
        SCREEN.blit(text, (20, 20))

        counter += 1
        if delay := (time.time() - start_time) > frame_rate_delay:
            frame_rate = round(counter / delay)
            counter = 0
            start_time = time.time()
        SCREEN.blit(FONT.render(
            f"FPS: {frame_rate}", False, (255, 255, 255)), (20, 50))

        WIDTH, HEIGHT = pygame.display.get_surface().get_size()
        pygame.display.update()
        CLOCK.tick(FPS)
        SCREEN.fill(background_color)

        # print((current_player.pos_x, current_player.pos_y))


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print("Connected")

    username = ""
    response = ""
    request = receive_message(s)
    while request == "GET username":
        print("Type username: ")
        username = input()
        s.sendall(username.encode("ascii"))
        response = receive_message(s)
        print(response)
        if not response.startswith("ERROR"):
            break
        request = receive_message(s)
        print(request)
    else:
        print("An error occurred")
        print(request)
        # sys.exit()

    for i in range(2):  # TODO: take this num from config
        request = receive_message(s)
        print("here!")
        if request == "POST cells":
            received_cells = unpack_cells(s)
            print("Received cells:", received_cells)
            parse_cells_data(received_cells)
        elif request == "POST players":
            print("here2")
            received_players = unpack_players(s)
            print("Received players: ", received_players)
            parse_players_data(received_players, username)
        else:
            print("An error occurred")
            print(request)
            # sys.exit()

    render_game(s)
