import socket
import sys
import random
import time
from threading import Thread, Lock
import re
import struct
from newtork_utils import send_cells, send_message, encode_color
from uuid import uuid4

from pygame.locals import QUIT, MOUSEMOTION

cell_count = 2000
map_size = 4000
PLAYER_SPAWN_RADIUS = 35
CELL_RADIUS = 10
respawn_cells = True

WIDTH = 1280
HEIGHT = 720

# ugly, but should work faster
# Cell(pos_x, pos_y, color) + id -- natural number / arr indx
# we can split it into 2 1d array [pos_x, pos_y], [color]
# or everything in one array - colors are just numbers; those can be even encoded ()_255 == 255*255^2 + 255*255 + 255
cells = {}  # TODO: cell can be also another player? -- better split
cells_lock = Lock()
is_alive = True  # TODO: is this needed - if yes - make var; if not - just remove from players

HOST = "127.0.0.1"
PORT = 9999

players = {}  # player_name, player_obj
connections = {}

# @dataclass -- ideally, but I'll convert it to Java anyways
# TODO: arrays + ?id


class CellData():
    def __init__(self, x, y, color):
        self.color = color
        self.pos_x = x
        self.pos_y = y

# EW. TODO: if split then player is represented by many visual cells


def notify_all_clients(format: str, current_client_id: uuid4, *data):
    # TODO: connections lock
    for key, conn in connections.items():
        # TODO: consider ? -> I and use it as a communication
        conn.sendall(struct.pack(
            "?" + format, bool(key == current_client_id), *data))


class Player(CellData):
    def __init__(self, client_id, x, y, color, name, conn):
        super().__init__(x, y, color)
        self.client_id = client_id
        self.radius = PLAYER_SPAWN_RADIUS
        self.name = name
        self.conn = conn

    def collision_check(self):
        cells_to_reuse = []
        # start_time_measure = time.time()
        # TODO: if too slow try changing iteration strategy
        # 1 map batches - only ~1000 closest
        # keys are natural nums, so while loop will be ok also
        # + cell pool or instant respawn for now
        # --> always same num of cells, just change pos (send new pos for id)
        # => acquring lock on one item, not the whole map :)
        with cells_lock:
            for key, cell in cells.items():
                if self._collides_with(cell):
                    new_pos_x, new_pos_y = random.randint(
                        0, map_size * 2), random.randint(0, map_size * 2)

                    new_color = encode_color(
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255)
                    )

                    cells_to_reuse.append(
                        (key, new_pos_x, new_pos_y, new_color))
                    # TODO: this
                    notify_all_clients(
                        "IIII", self.client_id, key, new_pos_x, new_pos_y, new_color)
                    self.radius += 0.5

                    print(f"Player: {self.pos_x}, {self.pos_y}, Cell: ",
                          cell.pos_x, cell.pos_y)

                    print("New cell: ", (key, new_pos_x, new_pos_y, new_color))

            for new_cell_values in cells_to_reuse:
                key, new_pos_x, new_pos_y, new_color = new_cell_values
                cell = cells[key]
                cell.pos_x = new_pos_x
                cell.pos_y = new_pos_y
                cell.color = new_color

                cells[key] = cell

            # delta_time_measure = time.time() - start_time_measure
            # print(f"Removal time elapsed: {delta_time_measure * 100:2f}")

    def _calculate_cell_distance(self, cell):
        '''Returns distance between origins of two cells'''
        return (cell.pos_x - (self.pos_x + WIDTH / 2)) ** 2 + (cell.pos_y - (self.pos_y + HEIGHT / 2)) ** 2

    def _collides_with(self, cell):
        return self._calculate_cell_distance(cell) < (CELL_RADIUS * 0.9 + self.radius) ** 2


# def network_handler(conn):
#     """Receive and process cell removal data"""
#     while True:  # TODO is alive or sth
#         try:
#             data = conn.recv(8)
#             mouse_x, mouse_y = struct.unpack('ff', data)

#             # TODO: handle disconnetion and death
#             # if event.type == QUIT:
#             # sys.exit()
#             # if event.type == MOUSEMOTION and is_alive:
#             #     mouse_x, mouse_y = event.pos

#             # TODO: get quit event
#             # TODO: get mouse pos from player or player pos

#             player.pos_x += ((mouse_x - WIDTH / 2) / player.radius / 2)
#             player.pos_y += ((mouse_y - HEIGHT / 2) / player.radius / 2)

#         except Exception as e:
#             print(f"Network error: {e}")


def main():
    print("Server is running.")
    init_game()
    print("Initialized game.")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()

        while (True):
            # TODO multithreading, multiple users, synchronization
            conn, addr = s.accept()
            print(f"Connected with: {addr}")
            client_id = uuid4()
            connections[client_id] = conn
            # TODO: move to thread
            t = Thread(target=handle_player_gameplay, args=(conn, client_id))
            t.start()
            # handle_player_gameplay(conn)


def init_game():
    # spawn point cells
    for i in range(cell_count):
        new_cell = CellData(
            random.randint(0, map_size * 2),
            random.randint(0, map_size * 2),
            encode_color(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            ),
        )
        cells[i] = new_cell


VALID_USERNAME_CHARACTERS = r"^[a-zA-Z\d _-]+$"
INVALID_USERNAME_MESSAGE = "Invalid username. Valid characters are: letters, digits, ` `, `_`, `-`"
USERNAME_MAX_LENGTH = 50


def validate_username(username):
    if len(username) > 50:
        return "Username is too long."

    if not re.match(VALID_USERNAME_CHARACTERS, username):
        return INVALID_USERNAME_MESSAGE

    if username in players:
        return f"Username: {username} is already taken."

    return "OK"

# GET
# ERROR
# INFO
# POST


def handle_player_gameplay(conn, client_id):
    # TODO: send config

    # username
    with conn:
        while True:
            print("Asking for username...")
            send_message(conn, "GET username")
            username = conn.recv(1024).decode('ascii')
            if (msg := validate_username(username)) != "OK":
                # TODO: is it ok? maybe use enums for this method?
                send_message(conn, "ERROR " + msg)
                continue
            else:
                print(f"Player {username} has joined the game.")
                send_message(conn, "INFO Successfully connected to the game.")
                # players[username] = ...  # TODO: remove player and cleanup
                break

            # TODO: handle no data == null
            # if not data:
            #     break

        # TODO: handle random
        # global player  # TODO: change to field
        # spawn player
        player_color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        )

        player = Player(client_id, map_size / 2, map_size / 2,
                        player_color, "Player1", conn)

        # TODO -1 mouse == disconnect

        # send init game state
        send_message(conn, "POST cells")
        send_cells(conn, cells)

        last_update = time.time()
        TARGET_FPS = 15

        # network_thread_obj = Thread(
        #     target=network_handler, args=(conn,), daemon=True)
        # network_thread_obj.start()

        while True:
            data = conn.recv(8)
            mouse_x, mouse_y = struct.unpack('ff', data)

            if mouse_x == -1:
                print("Player disconnected.")
                connections.pop(client_id)
                break

            player.pos_x += ((mouse_x - WIDTH / 2) / player.radius / 2)
            player.pos_y += ((mouse_y - HEIGHT / 2) / player.radius / 2)

            player.collision_check()

            # print((player.pos_x, player.pos_y))

            # current_time = time.time()
            # if current_time - last_update < 1/TARGET_FPS:
            #     time.sleep(0.001)
            #     continue
            # last_update = current_time

            # delta_time_measure = time.time() - start_time_measure
            # print(f"Time elapsed: {delta_time_measure * 100:2f}")


if __name__ == "__main__":
    main()


# TODO: exception handling
