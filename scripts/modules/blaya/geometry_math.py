"""Array operations shared by mesh tools; independent of Blender UI state."""
import numpy as np


def coordinates(points, minimum=1):
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3 or len(array) < minimum:
        raise ValueError(f'Select at least {minimum} valid vertices')
    if not np.isfinite(array).all():
        raise ValueError('Geometry contains non-finite coordinates')
    return array


def transform_points(matrix, points):
    points = coordinates(points, minimum=0)
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise ValueError('Object transform is not finite')
    return points @ matrix[:3, :3].T + matrix[:3, 3]


def inverse_transform(matrix):
    matrix = np.asarray(matrix, dtype=np.float64)
    if not np.isfinite(matrix).all():
        raise ValueError('Object transform is not finite')
    try:
        inverse = np.linalg.inv(matrix)
    except np.linalg.LinAlgError as error:
        raise ValueError('An edited object has zero scale; restore its scale first') from error
    if not np.isfinite(inverse).all():
        raise ValueError('Object transform cannot be inverted')
    return inverse


def pack_tiles(sizes, start_tile=1001, padding=0.0, occupied_tiles=()):
    """Deterministic shelf packing without changing UV scale or orientation."""
    if not 1001 <= start_tile <= 2000 or not 0 <= padding < .5:
        raise ValueError('Choose a valid UDIM tile and padding smaller than half a tile')
    occupied_tiles = set(occupied_tiles)
    placements = [None] * len(sizes)
    tile, x, y, row_height = start_tile, padding, padding, 0.0
    ordered = sorted(enumerate(sizes), key=lambda item: (-item[1][1], -item[1][0], item[0]))
    for index, (width, height) in ordered:
        while tile in occupied_tiles:
            tile += 1
            x, y, row_height = padding, padding, 0.0
        if not np.isfinite((width, height)).all() or min(width, height) < 0:
            raise ValueError('UV island bounds are invalid')
        if max(width, height) > 1 - 2 * padding + 1e-9:
            raise ValueError('An island is larger than a tile; reduce its density or scale first')
        if x + width > 1 - padding + 1e-9:
            x, y, row_height = padding, y + row_height + padding, 0.0
        if y + height > 1 - padding + 1e-9:
            tile += 1
            x, y, row_height = padding, padding, 0.0
        while tile in occupied_tiles:
            tile += 1
        if tile > 2000:
            raise ValueError('The layout exceeds the supported UDIM range (1001–2000)')
        placements[index] = ((tile - 1001) % 10 + x, (tile - 1001) // 10 + y)
        x += width + padding
        row_height = max(row_height, height)
    return placements
