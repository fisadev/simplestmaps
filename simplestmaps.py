from collections import namedtuple
from functools import partial, wraps
from pathlib import Path
from types import GeneratorType
import json

import folium


class Coords:
    """
    A container of lat lon coordinates, which is also able to extract those values from any other
    type of coordinates containing objects.
    """
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon

    def __repr__(self):
        return f"Coords({self.lat}, {self.lon})"

    @classmethod
    def extract(cls, coords_source):
        """
        Extract lat lon coordinates from any possible known thing.
        """
        if hasattr(coords_source, "lat") and hasattr(coords_source, "lon"):
            # a few known classes that have lat long attributes
            lat, lon = coords_source.lat, coords_source.lon
        elif hasattr(coords_source, "latitude") and hasattr(coords_source, "longitude"):
            # a few known classes that have latitude longitude attributes, like some common geo
            # libs
            lat, lon = coords_source.latitude, coords_source.longitude
        elif hasattr(coords_source, "latitude_deg") and hasattr(coords_source, "longitude_deg"):
            # a few known classes that have latitude_deg longitude_deg attributes, like the
            # locations from the orbit-predictor lib
            lat, lon = coords_source.latitude_deg, coords_source.longitude_deg
        elif isinstance(coords_source, (tuple, list)) and len(coords_source) == 1:
            return Coords.extract(coords_source[0])
        elif isinstance(coords_source, (tuple, list)) and len(coords_source) in (2, 3):
                lat, lon = coords_source[:2]
        else:
            raise ValueError(
                f"Can't guess the latitude and longitude from this object: {repr(coords_source)}"
            )

        return cls(lat, lon)


# types of things we can display on a map, with their attributes
Marker = namedtuple("Marker", "coords popup")
Dot = namedtuple("Dot", "coords color radius opacity border_color border_width popup")
Label = namedtuple("Label", "coords text color size font opacity popup")
Html = namedtuple("Html", "coords code popup")
Line = namedtuple("Line", "coords_sequence color width opacity popup")
Area = namedtuple("Area", "coords_sequence color opacity border_color border_width popup")
Geojson = namedtuple("Geojson", "path points_as lines_as areas_as")


def marker(*coords, popup=None):
    """
    Helper to easily build a Marker instance.
    """
    if not coords:
        return partial(marker, popup=popup)

    return Marker(Coords.extract(coords), popup)


def dot(*coords, color="blue", radius=3, opacity=1, border_color=None, border_width=0, popup=None):
    """
    Helper to easily build a Dot instance.
    """
    if not coords:
        return partial(dot, color=color, radius=radius, opacity=opacity, border_color=border_color,
                       border_width=border_width, popup=popup)

    if border_color is None:
        border_color = color
    elif border_width == 0:
        border_width = 2

    return Dot(Coords.extract(coords), color, radius, opacity, border_color, border_width, popup)


def label(*coords, text, color="blue", size=12, font="arial", opacity=1, popup=None):
    """
    Helper to easily build a Label instance.
    """
    if not coords:
        return partial(label, text=text, color=color, size=size, font=font, opacity=opacity,
                       popup=popup)

    return Label(Coords.extract(coords), text, color, size, font, opacity, popup)


def html(*coords, code, popup=None):
    """
    Helper to easily build a Html instance.
    """
    if not coords:
        return partial(html, code=code, popup=popup)

    return Html(Coords.extract(coords), code, popup)


def line(coords_sequence=None, color="blue", width=2, opacity=1, popup=None):
    """
    Helper to easily build a Line instance.
    """
    if not coords_sequence:
        return partial(line, color=color, width=width, opacity=opacity, popup=popup)

    coords_sequence = [Coords.extract(coords) for coords in coords_sequence]
    return Line(coords_sequence, color, width, opacity, popup)


def area(coords_sequence=None, color="blue", opacity=0.5, border_color=None, border_width=0,
         popup=None):
    """
    Helper to easily build an Area instance.
    """
    if not coords_sequence:
        return partial(area, color=color, opacity=opacity, border_color=border_color,
                       border_width=border_width, popup=popup)

    if border_color is None:
        border_color = color
    elif border_width == 0:
        border_width = 2

    coords_sequence = [Coords.extract(coords) for coords in coords_sequence]
    return Area(coords_sequence, color, opacity, border_color, border_width, popup)


def geojson(path_or_data, points_as=marker, lines_as=line, areas_as=area):
    """
    Helper to easily read the contents of a geojson, and extract all the things it contains.
    """
    if isinstance(path_or_data, (str, Path)):
        # a path to a geojson file, read it and extract its contents
        with open(path_or_data, "r") as geojson_f:
            geojson_data = json.load(geojson_f)
    else:
        geojson_data = path_or_data

    if isinstance(geojson_data, list):
        # a list of geo items, extract them individually
        for item_data in geojson_data:
            yield from geojson(item_data, points_as, lines_as, areas_as)

    elif isinstance(geojson_data, dict):
        # a single geo object, try to identify its type
        geojson_type = geojson_data.get("type")

        if geojson_type is None:
            raise ValueError(
                "The provided geojson seems to contain invalid data (no 'type' key present):\n\n"
                f"{repr(geojson_data)}"
            )

        elif geojson_type == "FeatureCollection":
            # a collection of features, extract them individually
            for feature in geojson_data["features"]:
                yield from geojson(feature["geometry"], points_as, lines_as, areas_as)

        elif geojson_type == "Point":
            # geojson uses lon,lat instead of lat,lon
            raw_coords = geojson_data["coordinates"]
            yield points_as(raw_coords[1], raw_coords[0])

        elif geojson_type == "LineString":
            # geojson uses lon,lat instead of lat,lon
            raw_coords_sequence = geojson_data["coordinates"]
            yield lines_as(
                (raw_coords[1], raw_coords[0])
                for raw_coords in raw_coords_sequence
            )

        elif geojson_type == "Polygon":
            # geojson uses lon,lat instead of lat,lon. And polygons have lists of lists of coords
            for raw_coords_sequence in geojson_data["coordinates"]:
                yield areas_as(
                    (raw_coords[1], raw_coords[0])
                    for raw_coords in raw_coords_sequence
                )


def pluralize(helper):
    """
    Make a helper able to work with multiple sources instead of just one.
    Example: use the 'label' helper to create a new 'labels' helper, that works with multiple
    points coordinates instead of just one point.
    """
    @wraps(helper)
    def plural_helper(sources, **kwargs):
        for source in sources:
            yield helper(source, **kwargs)

    return plural_helper


marker_set = pluralize(marker)
dot_set = pluralize(dot)
label_set = pluralize(label)
html_set = pluralize(html)
line_set = pluralize(line)
area_set = pluralize(area)
geojson_set = pluralize(geojson)


def draw_map(*things, center=(0, 0), zoom=1.5, tiles="cartodbpositron"):
    """
    Draw a simple map with elements on it. Good known working tiles with folium 0.14:
    - "cartodbpositron": white
    - "Stamen Terrain": terrain colors
    """
    center = Coords.extract(center)

    map_ = folium.Map(location=(center.lat, center.lon), zoom_start=zoom, attr=".", tiles=tiles)

    # consume all the things to display, and use inverted order so the user can easily understand
    # what's o top of what
    things = list(reversed(things))

    while things:
        thing = things.pop()

        if isinstance(thing, (list, tuple, GeneratorType)):
            # a collection of things, probably created using the geojson() helper. Feed those
            # things into the pending list
            things.extend(thing)

        if isinstance(thing, Marker):
            folium.Marker(
                location=[thing.coords.lat, thing.coords.lon],
                popup=thing.popup,
            ).add_to(map_)

        elif isinstance(thing, Dot):
            folium.CircleMarker(
                location=[thing.coords.lat, thing.coords.lon],
                radius=thing.radius,
                color=thing.border_color,
                weight=thing.border_width,
                fillColor=thing.color,
                fillOpacity=thing.opacity,
                popup=thing.popup,
            ).add_to(map_)

        elif isinstance(thing, Label):
            folium.Marker(
                location=[thing.coords.lat, thing.coords.lon],
                icon=folium.DivIcon(html=f"""
                    <div style="font-family: {thing.font};
                                font-size: {thing.size}px;
                                color: {thing.color};
                                opacity: {thing.opacity}">
                        {thing.text}
                    </div>
                """),
                popup=thing.popup,
            ).add_to(map_)

        elif isinstance(thing, Html):
            folium.Marker(
                location=[thing.coords.lat, thing.coords.lon],
                icon=folium.DivIcon(html=thing.code),
                popup=thing.popup,
            ).add_to(map_)

        elif isinstance(thing, Line):
            folium.PolyLine(
                locations=[(coords.lat, coords.lon)
                           for coords in thing.coords_sequence],
                color=thing.color,
                weight=thing.width,
                opacity=thing.opacity,
                popup=thing.popup,
            ).add_to(map_)

        elif isinstance(thing, Area):
            folium.Polygon(
                locations=[(coords.lat, coords.lon)
                           for coords in thing.coords_sequence],
                color=thing.border_color,
                weight=thing.border_width,
                fill_color=thing.color,
                fill_opacity=thing.opacity,
                popup=thing.popup,
            ).add_to(map_)

    return map_
