import socket
import struct
import pygame
import time
import sys
from threading import Thread, Lock
from pygame.locals import QUIT, MOUSEMOTION

pygame.init()

WIDTH = 1280
HEIGHT = 720
cells = {}  # TODO: cell can be also another player
is_alive = True
FONT = pygame.font.Font("freesansbold.ttf", 32)
BIGFONT = pygame.font.Font("freesansbold.ttf", 72)


HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = 9999  # The port used by the server

# TODO: from config
player_color = (255, 0, 0)
background_color = (0, 0, 0)
text_color = (255, 255, 255)
spawn_size = 35


class Cell():
    def __init__(self, cell_id, x, y, color, radius):
        self.cell_id = cell_id
        self.radius = radius
        self.color = color
        self.pos_x = x
        self.pos_y = y

    def draw(self, surface, x, y):
        pygame.draw.circle(surface, self.color, (x, y), int(self.radius))


class Player(Cell):
    def __init__(self, x, y, color, radius, name):
        super().__init__(-1, x, y, color, radius)

    def draw(self, surface, x, y):
        super().draw(surface, x, y)
        global FONT
        text = FONT.render(str(round(self.radius)), False, text_color)

    def collision_check(self):
        for cell in cells:
            if self._collides_with(cell) and cell.radius <= self.radius:
                cells.remove(cell)  # TODO: linkedlist or map
                self.radius += 0.5

                print(f"Player: {self.pos_x}, {self.pos_y}, Cell: ",
                      cell.pos_x, cell.pos_y)

    def _calculate_cell_distance(self, cell):
        '''Returns distance between origins of two cells'''
        return (cell.pos_x - (self.pos_x + WIDTH / 2)) ** 2 + (cell.pos_y - (self.pos_y + HEIGHT / 2)) ** 2

    def _collides_with(self, cell):
        return self._calculate_cell_distance(cell) < (cell.radius*0.9 + self.radius) ** 2


def receive_exact(sock, n_bytes):
    """Receive exactly n bytes from socket"""
    data = b''
    while len(data) < n_bytes:
        chunk = sock.recv(n_bytes - len(data))
        if not chunk:
            raise ConnectionError("Socket connection broken")
        data += chunk
    return data


def receive_message(conn):
    # Read 4 bytes for length
    length_data = conn.recv(4)
    if not length_data:
        return None
    length = struct.unpack('I', length_data)[0]

    # Read exact message length
    message = conn.recv(length).decode('ascii')
    return message


def decode_color(color):
    r = color % 255
    color //= 255
    g = color % 255
    color //= 255
    b = color % 255

    return (r, g, b)


def parse_cell_data(cell_data):
    for cell in cell_data:
        new_cell = Cell(
            cell[0],
            cell[1] - 32768,
            cell[2] - 32768,
            decode_color(cell[3]),
            10  # TODO: send config info in json
        )
        cells[cell[0]] = new_cell


def unpack_cells(sock):
    """
    Receive and unpack cell data from socket
    Returns: list of tuples [(key, pos_x, pos_y, color), ...]
    """
    try:
        # First receive the data length
        length_data = receive_exact(sock, 4)
        data_length = struct.unpack('I', length_data)[0]

        # Then receive the actual data
        packed_data = receive_exact(sock, data_length)

        # Unpack number of cells
        cell_count = struct.unpack('I', packed_data[:4])[0]

        cells = []
        offset = 4  # Skip the cell count

        for i in range(cell_count):
            # Unpack each cell (4 integers)
            cell_data = struct.unpack('IIII', packed_data[offset:offset+16])
            cells.append(cell_data)  # (key, pos_x, pos_y, color)
            offset += 16

        return cells
    except Exception as e:
        print(f"Error receiving cells: {e}")
        return []


data_lock = Lock()


def network_handler(conn):
    """Receive and process cell removal data"""
    while True:  # TODO is alive or sth
        try:
            data = receive_message(conn)
            if data.startswith("DELETE cells"):
                # Read count
                count_data = conn.recv(4)
                count = struct.unpack('I', count_data)[0]

                # Read cell keys
                keys_to_remove = []
                for _ in range(count):
                    key_data = conn.recv(4)
                    key = struct.unpack('I', key_data)[0]
                    keys_to_remove.append(key)

                # Remove from local cells dict
                with data_lock:  # TODO: everywhere or concurrent map
                    for key in keys_to_remove:
                        cells.pop(key)
                        print(f"removed cell: {key}")

            else:
                print("wrong cells data " + data)

        except Exception as e:
            print(f"Error receiving removals: {e}")


def render_game(conn):
    global WIDTH, HEIGHT
    last_send_time = 0
    SEND_INTERVAL = 1/120  # 60 FPS max
    FPS = 30

    counter = 0
    frame_rate = 30
    start_time = 0
    frame_rate_delay = 0.5

    pygame.display.set_caption("Agar.io")

    CLOCK = pygame.time.Clock()
    SCREEN = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)

    # spawn player
    player = Player(2000, 2000, player_color, spawn_size, "Player")

    # Start network thread
    network_thread_obj = Thread(
        target=network_handler, args=(conn,), daemon=True)
    network_thread_obj.start()

    while True:
        current_time = time.time()

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            if event.type == MOUSEMOTION and is_alive:
                mouse_x, mouse_y = event.pos
            else:
                mouse_x = WIDTH / 2
                mouse_y = HEIGHT / 2

        # Throttle sending to avoid spam
        if current_time - last_send_time > SEND_INTERVAL:
            data = struct.pack('ff', mouse_x, mouse_y)  # 'ff' = 2 floats
            conn.sendall(data)
            last_send_time = current_time

        player.pos_x += ((mouse_x - WIDTH / 2) / player.radius / 2)
        player.pos_y += ((mouse_y - HEIGHT / 2) / player.radius / 2)

        # print(player.pos_x)
        # with data_lock: TODO
        for cell in cells.values():
            cell.draw(
                SCREEN,
                cell.pos_x - player.pos_x,
                cell.pos_y - player.pos_y
            )

        if is_alive:
            player.draw(SCREEN, (WIDTH / 2), (HEIGHT / 2))
            # player.collision_check()
        else:
            text = BIGFONT.render("Game over", False, text_color)
            SCREEN.blit(text, (WIDTH / 2 - 150, HEIGHT / 2 - 40))

        text = FONT.render(
            "Mass: " + str((player.radius)), False, text_color)
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


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print("Connected")

    response = ''
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

    request = receive_message(s)
    print("here!")
    if request.startswith("POST"):
        received_cells = unpack_cells(s)
        print("Received cells:", received_cells)
        parse_cell_data(received_cells)
    else:
        print("An error occurred")
        print(request)
        # sys.exit()

    render_game(s)
