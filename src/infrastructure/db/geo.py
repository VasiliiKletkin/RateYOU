"""PostGIS <-> domain geometry conversion.

Not an entity mapper — repositories build entities inline. This is the
narrow translation between `Location` and the WKT/WKB representations
geoalchemy2 speaks, which is pure geometry plumbing.
"""

from geoalchemy2 import WKBElement, WKTElement
from geoalchemy2.shape import to_shape

from src.domain.profile.value_objects import Location


def location_to_wkt(loc: Location) -> WKTElement:
    # PostGIS POINT order is (lon, lat) — (x, y) in cartesian terms.
    return WKTElement(f"POINT({loc.lon} {loc.lat})", srid=4326)


def wkb_to_location(wkb: WKBElement) -> Location:
    point = to_shape(wkb)  # shapely.Point; .x = lon, .y = lat
    return Location(lat=float(point.y), lon=float(point.x))
