import socket
import sys
import random
import time
from threading import Thread
import re
import logging
import struct

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
is_alive = True  # TODO: is this needed - if yes - make var; if not - just remove from players

HOST = "127.0.0.1"
PORT = 9999

players = {}  # player_name, player_obj

# @dataclass -- ideally, but I'll convert it to Java anyways
# TODO: arrays + ?id


class CellData():
    def __init__(self, x, y, color):
        self.color = color
        self.pos_x = x
        self.pos_y = y

# EW. TODO: if split then player is represented by many visual cells


class Player(CellData):
    def __init__(self, x, y, color, name, conn):
        super().__init__(x, y, color)
        self.radius = PLAYER_SPAWN_RADIUS
        self.name = name
        self.conn = conn

    def collision_check(self):
        cells_to_remove = []
        for key, cell in cells.items():
            if self._collides_with(cell) and CELL_RADIUS <= self.radius:
                cells_to_remove.append(key)
                self.radius += 0.5

                print(f"Player: {self.pos_x}, {self.pos_y}, Cell: ",
                      cell.pos_x, cell.pos_y)

                # TODO: move somewhere else, check <= cells...
                # if respawn_cells:
                #     new_cell = Cell(
                #         random.randint(-map_size, map_size),
                #         random.randint(-map_size, map_size),
                #         (
                #             random.randint(0, 255),
                #             random.randint(0, 255),
                #             random.randint(0, 255)
                #         ),
                #         5,
                #     )
                #     cells.append(new_cell)

        for cell_key in cells_to_remove:
            cells.pop(cell_key)

        if cells_to_remove:
            send_cell_keys(self.conn, cells_to_remove, remove=True)

    def _calculate_cell_distance(self, cell):
        '''Returns distance between origins of two cells'''
        return (cell.pos_x - (self.pos_x + WIDTH / 2)) ** 2 + (cell.pos_y - (self.pos_y + HEIGHT / 2)) ** 2

    def _collides_with(self, cell):
        return self._calculate_cell_distance(cell) < (CELL_RADIUS * 0.9 + self.radius) ** 2


def send_cell_keys(conn, cell_keys, remove=False):
    """Send list of cell keys to remove"""
    try:
        # Pack: count + cell keys
        data = struct.pack('I', len(cell_keys))
        for key in cell_keys:
            data += struct.pack('I', key)

        # Send with message type prefix
        send_message(conn, "DELETE cells")
        conn.sendall(data)
    except Exception as e:
        print(f"Error sending removals: {e}")


def pack_cells(cells):
    """
    Pack cell data into binary format for efficient transmission
    cells: list of tuples [(key, pos_x, pos_y, color), ...]
    """
    # Format: 'I' = unsigned int (4 bytes each)
    # We'll send count first, then all cell data
    packed_data = struct.pack('I', len(cells))  # Number of cells

    for key, cell in cells.items():
        # Pack each cell as 4 unsigned integers
        # TODO: change to non negative
        # TODO: consider shorts
        packed_data += struct.pack('IIII', key, cell.pos_x +
                                   32768, cell.pos_y + 32768, encode_color(cell.color))

    return packed_data


def send_cells(sock, cells):
    """Send cell data over socket"""
    try:
        packed_data = pack_cells(cells)
        # Send data length first (for reliable receiving)
        data_length = len(packed_data)
        sock.send(struct.pack('I', data_length))
        # Send the actual data
        sock.send(packed_data)
        return True
    except Exception as e:
        print(f"Error sending cells: {e}")
        return False


def encode_color(color):
    r, g, b = color
    return r * 255*255 + g * 255 + b


def main():
    print("Server is running.")
    init_game()
    print("Initialized game.")

    # packed_data = pack_cells(cells)
    # cell_count = struct.unpack('I', packed_data[:4])[0]
    # print(cell_count)

    # unpacked_cells = []
    # offset = 4  # Skip the cell count

    # for i in range(cell_count):
    #     # Unpack each cell (4 integers)
    #     cell_data = struct.unpack('IIII', packed_data[offset:offset+16])
    #     unpacked_cells.append(cell_data)  # (key, pos_x, pos_y, color)
    #     offset += 16

    # print(unpacked_cells)
    # return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()

        while (True):
            # TODO multithreading, multiple users, synchronization
            conn, addr = s.accept()
            print(f"Connected with: {addr}")
            # TODO: move to thread
            # Thread(target=handle_player_gameplay, args=(conn, ))
            handle_player_gameplay(conn)


def init_game():
    # spawn point cells
    for i in range(cell_count):
        new_cell = CellData(
            random.randint(0, map_size * 2),
            random.randint(0, map_size * 2),
            (
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


def send_message(conn, msg):
    data = msg.encode("ascii")
    length = struct.pack('I', len(data))
    conn.sendall(length + data)


def handle_player_gameplay(conn):
    # TODO: send current game state
    # TODO: ideally we want only send once all cells
    # and then updates only

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
        global player  # TODO: change to field
        # spawn player
        player_color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        )

        player = Player(map_size / 2, map_size / 2,
                        player_color, "Player1", conn)

        # TODO -1 mouse == disconnect

        # send init game state
        send_message(conn, "POST cells")
        send_cells(conn, cells)

        last_update = time.time()
        TARGET_FPS = 30

        while True:
            data = conn.recv(8)
            mouse_x, mouse_y = struct.unpack('ff', data)

            # TODO: handle disconnetion and death
            # if event.type == QUIT:
            # sys.exit()
            # if event.type == MOUSEMOTION and is_alive:
            #     mouse_x, mouse_y = event.pos

            # TODO: get quit event
            # TODO: get mouse pos from player or player pos

            player.pos_x += ((mouse_x - WIDTH / 2) / player.radius / 2)
            player.pos_y += ((mouse_y - HEIGHT / 2) / player.radius / 2)

            # print(player.pos_x)

            if is_alive:
                player.collision_check()

            current_time = time.time()
            if current_time - last_update < 1/TARGET_FPS:
                time.sleep(0.001)
                continue
            last_update = current_time


if __name__ == "__main__":
    main()

#  while (true) {
#                     out.println("name?");
#                     name = in.readLine();
#                     if (name == null) {
#                         return;
#                     }
#                     synchronized (names) {
#                         if (!names.contains(name)) {
#                             names.add(name);
#                             break;
#                         }
#                     }
#                 }

#                 out.println("accepted");
#                 writers.add(out);

#                 while (true) {
#                     String input = in.readLine();
#                     if (input == null) {
#                         return;
#                     }
#                     for (PrintWriter writer : writers) {
#                         writer.println("message " + name + ": " + input);
#                     }
#                 }


# TODO: exception handling
