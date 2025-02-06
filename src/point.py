from dataclasses import dataclass

@dataclass
class Point:
    x: int = 0
    y: int = 0

    def __add__(self, other: 'Point') -> 'Point':
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: 'Point') -> 'Point':
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, k: int) -> 'Point':
        return Point(self.x * k, self.y * k)

    def __repr__(self) -> str:
        return f'({self.x}; {self.y})'
