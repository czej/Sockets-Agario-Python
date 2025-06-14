import struct
import socket

def notify_client(*data, conn: socket, event: int, format: str | None = "", packed_data: bytes | None = None):
    send_format = "I" + format
    if packed_data == None:
        conn.sendall(struct.pack(
            send_format, event, *data))
    else:
        conn.sendall(struct.pack(
            send_format, event) + packed_data)


# CELLS
def _pack_cells(cells):
    packed_data = struct.pack('I', len(cells))  # Number of cells

    for key, cell in cells.items():
        packed_data += struct.pack('IffI', key, cell.pos_x,
                                   cell.pos_y, cell.color)

    return packed_data


def send_cells(sock, cells):
    try:
        packed_data = _pack_cells(cells)

        # Send data length first
        data_length = len(packed_data)
        sock.send(struct.pack('I', data_length))

        sock.send(packed_data)
        return True
    except Exception as e:
        print(f"Error sending cells: {e}")
        return False
    

def unpack_cells(sock):
    try:
        # data length
        length_data = receive_exact(sock, 4)
        data_length = struct.unpack('I', length_data)[0]

        # actual data
        packed_data = receive_exact(sock, data_length)

        # number of cells
        cell_count = struct.unpack('I', packed_data[:4])[0]

        cells = []
        offset = 4  # Skip the cell count

        for _ in range(cell_count):
            cell_data = struct.unpack('IffI', packed_data[offset:offset+16])
            cells.append(cell_data)  # (key, pos_x, pos_y, color)
            offset += 16

        return cells
    except Exception as e:
        print(f"Error receiving cells: {e}")
        return []


# PLAYERS
def pack_player(player, add_length: bool | None = False):
    packed_player = struct.pack("I", player.client_id)
    encoded_username = player.username.encode("ascii")

    packed_player += struct.pack('I', len(encoded_username))
    packed_player += encoded_username
    packed_player += struct.pack('ffIf', player.pos_x,
                                 player.pos_y, player.color, player.radius)
    
    if add_length:
        packed_player = struct.pack("I", len(packed_player)) + packed_player

    return packed_player


def _pack_players(players):
    packed_data = struct.pack('I', len(players))  # Number of players

    for player in players.values():
        packed_data += pack_player(player)

    return packed_data


def send_players(sock, players):
    try:
        packed_data = _pack_players(players)

        # Send data length first
        data_length = len(packed_data)
        sock.send(struct.pack('I', data_length))
        
        sock.send(packed_data)
        return True
    except Exception as e:
        print(f"Error sending players: {e}")
        return False
    


def unpack_player(packed_data: bytes, start_offset: int | None = 0):
    offset = start_offset
    client_id = struct.unpack(
        'I', packed_data[offset:offset + struct.calcsize('I')])[0]
    offset += struct.calcsize('I')

    username_length = struct.unpack(
        'I', packed_data[offset:offset + struct.calcsize('I')])[0]
    offset += struct.calcsize('I')

    username = packed_data[offset:offset +
                           username_length].decode('ascii')
    offset += username_length

    player_data = struct.unpack(
        'ffIf', packed_data[offset:offset + struct.calcsize('ffIf')])
    offset += struct.calcsize('ffIf')

    return (client_id, username, *player_data), offset


def unpack_players(sock):
    try:
        # data length
        length_data = receive_exact(sock, 4)
        data_length = struct.unpack('I', length_data)[0]

        # actual data
        packed_data = receive_exact(sock, data_length)

        # number of players
        count = struct.unpack('I', packed_data[:4])[0]

        players = []
        offset = 4  # Skip the cell count

        for _ in range(count):
            # (client_id, username, pos_x, pos_y, color, radius)
            data, new_offset = unpack_player(
                packed_data=packed_data, start_offset=offset)
            offset = new_offset
            players.append(data)

        return players
    except Exception as e:
        print(f"Error receiving players: {e}")
        return []


# MESSAGES
def send_message(conn, msg):
    data = msg.encode("ascii")
    length = struct.pack('I', len(data))
    conn.sendall(length + data)


def receive_exact(sock, n_bytes):
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


# OTHER
def decode_color(color):
    r = color % 256
    color //= 256
    g = color % 256
    color //= 256
    b = color % 256

    return (r, g, b)

def encode_color(r, g, b):
    return r * 256*256 + g * 256 + b