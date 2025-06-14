import socket
import struct
import pygame
import time
from threading import Thread, Lock
from pygame.locals import QUIT, MOUSEMOTION
from newtork_utils import decode_color, receive_message, unpack_cells, receive_exact, unpack_players, unpack_player
from enums import Events

pygame.init()

HOST = "127.0.0.1"  
PORT = 9999  

WIDTH = 1280
HEIGHT = 720
SMALLFONT = pygame.font.Font("freesansbold.ttf", 16)
FONT = pygame.font.Font("freesansbold.ttf", 32)
BIGFONT = pygame.font.Font("freesansbold.ttf", 72)

BACKGROUND_COLOR = (15, 15, 15)
TEXT_COLOR = (255, 255, 255)
SPAWN_SIZE = 35
CELL_RADIUS = 10

cells = {}
cells_lock = Lock()  
players = {}
players_lock = Lock()  
current_player = None
current_client_id = -1


class Cell():
    def __init__(self, x, y, color, radius):
        self.radius = radius
        self.color = color
        self.pos_x = x
        self.pos_y = y

    def draw(self, surface, x, y):
        pygame.draw.circle(surface, self.color, (x, y), self.radius)


class Player(Cell):
    def __init__(self, username, x, y, color, radius):
        super().__init__(x, y, color, radius)
        self.username = username
        self.is_alive = True

    def draw(self, surface, x, y):
        super().draw(surface, x, y)
        display_text = self.username
        
        # Render and draw text
        text_surface = SMALLFONT.render(display_text, True, TEXT_COLOR)
        text_rect = text_surface.get_rect(center=(x, y))
        surface.blit(text_surface, text_rect)


def parse_cells_data(cell_data):
    for cell in cell_data:
        new_cell = Cell(
            cell[1],
            cell[2],
            decode_color(cell[3]),
            CELL_RADIUS 
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
    """Receive and process network data"""
    while True:
        try:
            event_data = receive_exact(conn, struct.calcsize("I"))
            event = struct.unpack("I", event_data)[0]
            if event != 2:
                print("Event: ", event)

            match event:
                case Events.PLAYER_MOVED.code:
                    data_format = Events.PLAYER_MOVED.format
                    data = receive_exact(conn, struct.calcsize(data_format))
                    client_id, new_pos_x, new_pos_y, new_radius = struct.unpack(data_format, data)

                    with players_lock:
                        player = players[client_id]
                        player.pos_x = new_pos_x
                        player.pos_y = new_pos_y
                        player.radius = new_radius

                case Events.NEW_PLAYER.code:
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
                    

                case Events.PLAYER_QUIT.code:
                    data_format = Events.PLAYER_QUIT.format
                    data = receive_exact(conn, struct.calcsize(data_format))
                    client_id = struct.unpack(data_format, data)[0]
                    with players_lock:
                        players.pop(client_id)

                case Events.PLAYER_EATEN.code:
                    data_format = Events.PLAYER_EATEN.format
                    data = receive_exact(conn, struct.calcsize(data_format))
                    defeated_client_id, winner_client_id, new_winner_radius = struct.unpack(
                        data_format, data)
                    
                    with players_lock:
                        players.pop(defeated_client_id, None)
                        try:
                            winner = players[winner_client_id]
                            winner.radius = new_winner_radius
                        except Exception as e:
                            print(e)
                    
                case Events.PLAYER_EATEN_BY_CURRENT_PLAYER.code:
                    data_format = Events.PLAYER_EATEN_BY_CURRENT_PLAYER.format
                    data = receive_exact(conn, struct.calcsize(data_format))
                    defeated_client_id, winner_client_id, new_winner_radius = struct.unpack(
                        data_format, data)
                    
                    with players_lock:
                        players.pop(defeated_client_id, None)
                        current_player.radius = new_winner_radius

                case Events.GAME_OVER.code:
                    print("Game over.")
                    current_player.is_alive = False
                    break

                case Events.CELL_EATEN.code | Events.CELL_EATEN_BY_CURRENT_PLAYER.code:
                    data_format = Events.CELL_EATEN.format
                    data = receive_exact(conn, struct.calcsize(data_format))
                    key, new_pos_x, new_pos_y, new_color = struct.unpack(
                        data_format, data)

                    with cells_lock:  
                        cell = cells[key]
                        cell.pos_x = new_pos_x
                        cell.pos_y = new_pos_y
                        cell.color = decode_color(new_color)

                        print(f"Removed cell: {key}")
                        print(f"New cell was spawned: {new_pos_x}, {new_pos_y}, {new_color}")
                        

                    if event == Events.CELL_EATEN_BY_CURRENT_PLAYER.code:
                        current_player.radius += 0.5
            
        except Exception as e:
            print(f"Game ended.")
            break




def render_game(conn):
    global WIDTH, HEIGHT
    last_send_time = 0
    SEND_INTERVAL = 1/60 
    FPS = 30

    pygame.display.set_caption("Agar.io")

    CLOCK = pygame.time.Clock()
    SCREEN = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)

    # Start network thread
    network_thread_obj = Thread(
        target=network_handler, args=(conn,))
    network_thread_obj.start()

    global current_player

    while True:
        current_time = time.time()

        if not current_player.is_alive:
            return

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

        if current_time - last_send_time > SEND_INTERVAL:
            data = struct.pack('ff', (mouse_x - WIDTH / 2), (mouse_y - HEIGHT / 2))
            conn.sendall(data)
            last_send_time = current_time

        current_player.pos_x += ((mouse_x - WIDTH / 2) /
                                 current_player.radius / 2)
        current_player.pos_y += ((mouse_y - HEIGHT / 2) /
                                 current_player.radius / 2)


        with cells_lock:
            for cell in cells.values():
                cell.draw(
                    SCREEN,
                    cell.pos_x - current_player.pos_x + WIDTH / 2,
                    cell.pos_y - current_player.pos_y + HEIGHT / 2
                )

        with players_lock:
            for other_player in players.values():
                other_player.draw(
                    SCREEN,
                    other_player.pos_x - current_player.pos_x + WIDTH / 2,
                    other_player.pos_y - current_player.pos_y + HEIGHT / 2
                )

        current_player.draw(SCREEN, (WIDTH / 2), (HEIGHT / 2))

   
        text = FONT.render(
            "Mass: " + str((current_player.radius)), False, TEXT_COLOR)
        SCREEN.blit(text, (20, 20))

    

        WIDTH, HEIGHT = pygame.display.get_surface().get_size()
        pygame.display.update()
        CLOCK.tick(FPS)
        SCREEN.fill(BACKGROUND_COLOR)

        


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

    for i in range(2):  
        request = receive_message(s)
        if request == "POST cells":
            received_cells = unpack_cells(s)
            print("Received cells:", received_cells)
            parse_cells_data(received_cells)
        elif request == "POST players":
            received_players = unpack_players(s)
            print("Received players: ", received_players)
            parse_players_data(received_players, username)
        else:
            print("An error occurred")
            print(request)

    render_game(s)
