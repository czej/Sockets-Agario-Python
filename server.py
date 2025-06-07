import socket
import random
import time
from threading import Thread, Lock
import re
import struct
from newtork_utils import send_cells, send_message, encode_color, send_players, pack_player, notify_client


HOST = "127.0.0.1"
PORT = 9999

CELL_COUNT = 2000
MAP_SIZE = 8000
PLAYER_SPAWN_RADIUS = 35
CELL_RADIUS = 10

cells = {} 
cells_lock = Lock()  # OK

players = {}  # player_name, player_obj
players_lock = Lock()  # OK

connections = {}  # client_id, conn
connections_lock = Lock() # OK

# @dataclass -- ideally, but I'll convert it to Java anyways


class CellData():
    def __init__(self, x, y, color):
        self.color = color
        self.pos_x = x
        self.pos_y = y



def notify_all_clients(*data, event: int, format: str | None = "", current_client_id: int | None = None, packed_data: bytes | None = None):
    with connections_lock:
        for key, conn in connections.items():
            send_event = event

            # cell eaten by current or another player
            if send_event == 0 and key == current_client_id:
                send_event = 1

            elif send_event in (2, 5) and key == current_client_id:
                continue

            notify_client(*data, conn=conn, event=send_event, format=format, packed_data=packed_data)

# 3 == collision with another player (==) -- not needed


# 7 == player has quit
# 5 == new player has joined
# 4 == game over - was eaten by another player
# 3 == other player was eaten
# 2 == another player has moved
# 1 == cell eaten by current_player
# 0 == cell eaten by different player


class Player(CellData):
    def __init__(self, client_id, x, y, color, name, conn):
        super().__init__(x, y, color)
        self.client_id = client_id
        self.radius = PLAYER_SPAWN_RADIUS
        self.username = name
        self.conn = conn

    def collision_check(self):
        cells_to_reuse = []
        
        # TODO: if too slow try changing iteration strategy
        # 1 map batches - only ~1000 closest  // not now
        # keys are natural nums, so while loop will be ok also
        # --> always same num of cells, just change pos (send new pos for id)
        # => acquring lock on one item, not the whole map :)
        with cells_lock:
            for key, cell in cells.items():
                if self._collides_with(cell):
                    new_pos_x, new_pos_y, new_color = self._generate_new_cell_values(cell)
                    cells_to_reuse.append((key, new_pos_x, new_pos_y, new_color))
                    notify_all_clients(
                        key, new_pos_x, new_pos_y, new_color,
                        format="IIII", current_client_id=self.client_id, event=0)
            
                    self.radius += 0.5

            for new_cell_values in cells_to_reuse:
                self._reuse_cell(new_cell_values)
        
        
        with players_lock:
            for username, other_player in players.items():
                if other_player.client_id == self.client_id:
                    continue

                if self._collides_with(other_player):
                    print(f"Player collision: {other_player.username}" )
                    winner, defeated = None, None
                    if self.radius > other_player.radius * 1.15:
                        winner = self
                        defeated = other_player
                    elif other_player.radius > self.radius * 1.15:
                        winner = other_player
                        defeated = self
                    else:
                        continue

                    winner.radius += defeated.radius

                    # TODO: handle game over for defeated - disconnect
                    # remove all data (modify connection out of this scope to avoid deadlock!)

                    # others + winning player:
                    # defeated: get client id to remove
                    # won: get client_id, new radius
                    notify_all_clients(
                        defeated.client_id, winner.client_id, winner.radius,
                        format="III", current_client_id=self.client_id, event=3)

                    # defeated player:
                    # send game over
                    notify_client(conn=defeated.conn, format="", current_client_id=self.client_id, event=4)
        

    def _calculate_distance(self, cell):
        '''Returns distance between origins of two cells'''
        return (cell.pos_x - self.pos_x) ** 2 + (cell.pos_y - self.pos_y) ** 2

    def _collides_with(self, cell):
        return self._calculate_distance(cell) < (CELL_RADIUS * 0.9 + self.radius) ** 2
    
    def _collides_with_player(self, other_player):
        return self._calculate_distance(other_player) < (other_player.radius * 0.5 + self.radius * 0.5) ** 2
    
    def _generate_new_cell_values(self, cell):
            new_pos_x, new_pos_y = random.randint(0, MAP_SIZE), random.randint(0, MAP_SIZE)

            new_color = encode_color(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )
            
            print(f"Player: {self.pos_x}, {self.pos_y}, Cell: ",
                    cell.pos_x, cell.pos_y)

            print("New cell: ", (new_pos_x, new_pos_y, new_color))

            return new_pos_x, new_pos_y, new_color
    
    def _reuse_cell(self, new_values):
        key, new_pos_x, new_pos_y, new_color = new_values
        cell = cells[key]
        cell.pos_x = new_pos_x
        cell.pos_y = new_pos_y
        cell.color = new_color





def main():
    print("Server is running.")
    init_game()
    player_counter = 0
    print("Initialized game.")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()

        while (True):
            # TODO synchronization
            conn, addr = s.accept()
            print(f"Connected with: {addr}")
            player_counter += 1
            client_id = player_counter

            t = Thread(target=handle_player_gameplay, args=(conn, client_id))
            t.start()


def init_game():
    # spawn point cells
    for i in range(CELL_COUNT):
        new_cell = CellData(
            random.randint(0, MAP_SIZE),
            random.randint(0, MAP_SIZE),
            encode_color(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            ),
        )
        # lock not needed
        cells[i] = new_cell


VALID_USERNAME_CHARACTERS = r"^[a-zA-Z\d _-]+$"
INVALID_USERNAME_MESSAGE = "Invalid username. Valid characters are: letters, digits, ` `, `_`, `-`"
USERNAME_MAX_LENGTH = 50


def validate_username(username):
    if username is None or len(username) < 1:
        return "Username is too short. Minimum characters is 1."
    
    if len(username) > 50:
        return "Username is too long. Maximum characters is 50."

    if not re.match(VALID_USERNAME_CHARACTERS, username):
        return INVALID_USERNAME_MESSAGE

    if username in players:
        return f"Username: {username} is already taken."

    return "OK"


def spawn_player(client_id, conn, username) -> Player:
    player_color = encode_color(
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255)
    )

    # TODO: random pos
    # return Player(
    #     client_id, random.randint(
    #         0, MAP_SIZE), random.randint(0, MAP_SIZE),  # TODO: why x2
    #     player_color, username, conn)

    return Player(
        client_id, 0, 0, 
        player_color, username, conn)


# TODO: change this
# GET
# ERROR
# INFO
# POST


def handle_player_gameplay(conn, client_id):
    # TODO: send config
    username = ""

    with conn:
        while True:
            print("Asking for username...")
            send_message(conn, "GET username")
            username = conn.recv(1024).decode('ascii').strip()
            players_lock.acquire()
            try:
                if (msg := validate_username(username)) != "OK":
                    # TODO: is it ok? maybe use enums for this method?
                    players_lock.release()
                    send_message(conn, "ERROR " + msg)
                    continue
                else:
                    # spawn player
                    # TODO: lock on this action - checking and adding username to map
                    # TODO: remove player and cleanup - even if connection was broken
                    # TODO: make this player inactive until renders
                    players[username] = spawn_player(client_id, conn, username)
                    players_lock.release()
                    print(f"Player {username} has joined the game.")
                    send_message(conn, "INFO Successfully connected to the game.")
                    break
            except:
                players_lock.release()
                break

            # TODO: handle no data == null
            # if not data:
            #     break

        # send init game state
        send_message(conn, "POST cells")
        with cells_lock:
            send_cells(conn, cells)

        # send players (containing current player)
        send_message(conn, "POST players")
        with players_lock:
            send_players(conn, players)

            # TODO: notify other players about new player
            player = players[username]

        notify_all_clients(packed_data=pack_player(player, add_length=True), current_client_id=client_id,
                           event=5)

        with connections_lock:
            connections[client_id] = conn

        while True:
            data = conn.recv(8)
            mouse_x, mouse_y = struct.unpack('ff', data)

            # print((mouse_x, mouse_y))

            if mouse_x == 999999:
                print(f"Player {username} disconnected.")
                with connections_lock:
                    connections.pop(client_id)
                
                with players_lock:
                    players.pop(player.username)
                
                notify_all_clients(client_id, format="I", event=7)
                break

            player.pos_x += (mouse_x / player.radius / 2)
            player.pos_y += (mouse_y / player.radius / 2)

            player.collision_check()

            # ? TODO: send only if close position (remember about scale)
            notify_all_clients(client_id, player.pos_x, player.pos_y, player.radius, format="Ifff",
                               current_client_id=client_id, event=2)

            # print((player.pos_x, player.pos_y))



if __name__ == "__main__":
    main()


# TODO: exception handling, handle random disconnect
# TODO: synchorniaztion!!!  -- check locks and add missing
