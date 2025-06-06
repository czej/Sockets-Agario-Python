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
        # TODO: change to non negative
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
            cell_data = struct.unpack('IIII', packed_data[offset:offset+16])
            cells.append(cell_data)  # (key, pos_x, pos_y, color)
            offset += 16

        return cells
    except Exception as e:
        print(f"Error receiving cells: {e}")
        return []
