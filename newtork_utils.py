import struct


def _pack_cells(cells):
    """
    Pack cell data into binary format for efficient transmission
    cells: list of tuples [(key, pos_x, pos_y, color), ...]
    """
    # Format: 'I' = unsigned int (4 bytes each)
    # We'll send count first, then all cell data
    packed_data = struct.pack('I', len(cells))  # Number of cells

    for key, cell in cells.items():
        # Pack each cell as 4 unsigned integers
        # TODO: consider shorts
        packed_data += struct.pack('IIII', key, cell.pos_x,
                                   cell.pos_y, cell.color)

    return packed_data


def send_cells(sock, cells):
    """Send cell data over socket"""
    try:
        packed_data = _pack_cells(cells)
        # Send data length first (for reliable receiving)
        data_length = len(packed_data)
        sock.send(struct.pack('I', data_length))
        # Send the actual data
        sock.send(packed_data)
        return True
    except Exception as e:
        print(f"Error sending cells: {e}")
        return False


def _pack_players(players):
    """
    Pack cell data into binary format for efficient transmission
    cells: list of tuples [(key, pos_x, pos_y, color), ...]
    """
    packed_data = struct.pack('I', len(players))  # Number of players

    for username, player in players.items():
        # Pack each cell as 4 unsigned integers
        # TODO: consider shorts
        encoded_username = username.encode("ascii")

        packed_data += struct.pack('I', len(encoded_username))
        packed_data += encoded_username
        packed_data += struct.pack('ffIf', player.pos_x,
                                   player.pos_y, player.color, player.radius)

    return packed_data


def send_players(sock, players):
    """Send cell data over socket"""
    try:
        packed_data = _pack_players(players)
        # Send data length first (for reliable receiving)
        data_length = len(packed_data)
        sock.send(struct.pack('I', data_length))
        # Send the actual data
        sock.send(packed_data)
        return True
    except Exception as e:
        print(f"Error sending players: {e}")
        return False


def encode_color(r, g, b):
    return r * 255*255 + g * 255 + b


def send_message(conn, msg):
    data = msg.encode("ascii")
    length = struct.pack('I', len(data))
    conn.sendall(length + data)


# client

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
            # TODO: floats
            cell_data = struct.unpack('IIII', packed_data[offset:offset+16])
            cells.append(cell_data)  # (key, pos_x, pos_y, color)
            offset += 16

        return cells
    except Exception as e:
        print(f"Error receiving cells: {e}")
        return []


def unpack_players(sock):
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

        # Unpack number of players
        count = struct.unpack('I', packed_data[:4])[0]

        players = []
        offset = 4  # Skip the cell count

        for _ in range(count):
            # Unpack each cell (4 integers)
            username_length = struct.unpack(
                'I', packed_data[offset:offset + 4])[0]
            offset += 4
            username = packed_data[offset:offset +
                                   username_length].decode('ascii')
            offset += username_length
            player_data = struct.unpack(
                'ffIf', packed_data[offset:offset + 16])
            # (username, pos_x, pos_y, color, radius)
            players.append((username, *player_data))
            offset += 16

        return players
    except Exception as e:
        print(f"Error receiving players: {e}")
        return []
