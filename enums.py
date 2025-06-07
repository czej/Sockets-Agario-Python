import enum
class Events(enum.Enum):
    def __new__(cls, *args, **kwds):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj
    
    def __init__(self, code: int, format: str | None = None):
        self.code = code
        self.format = format

    CELL_EATEN = 0, "IIII"
    CELL_EATEN_BY_CURRENT_PLAYER = 1, "IIII"
    PLAYER_MOVED = 2, "Ifff"
    PLAYER_EATEN = 3, "IIf"
    GAME_OVER = 4, ""
    NEW_PLAYER = 5, None
    PLAYER_EATEN_BY_CURRENT_PLAYER = 6, "IIf"
    PLAYER_QUIT = 7, "I"

