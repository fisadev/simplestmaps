from collections import namedtuple
from functools import partial, wraps
from pathlib import Path
from types import GeneratorType
import json

import folium


Point = namedtuple("Point", "lat lon")

# type -> converter function that receives instance of type and returns either a single (lat,lon)
# tuple, or a sequence of (lat,lon) tuples
converters = {}


def all_numbers(sequence):
    """
    Is a sequence composed of just numbers?
    """
    return all(
        isinstance(x, (int, float)) and not isinstance(x, bool)
        for x in sequence
    )


def to_points(source, inverted_tuples=False):
    """
    Convert any possible thing to lat lon points and/or sequences of points.
    Optionally reverse lat,lon values (used when converting points from lists of coordinates in
    geojsons).
    """
    while source.__class__ in converters:
        # a custom type for which we have a converter registered, use it before trying to extract
        # points from it
        source = converters[source.__class__](source)

    if isinstance(source, Point):
        # don't re-convert things that are already points
        return source
    elif isinstance(source, GeneratorType):
        # traverse the generator and build a tuple with its components, that we can inspect and
        # parse (so we can do things like decide how to parse it based on its length and the types
        # of its items)
        return to_points(tuple(source), inverted_tuples=inverted_tuples)
    elif hasattr(source, "lat") and hasattr(source, "lon"):
        # a few known classes that have lat long attributes
        lat, lon = source.lat, source.lon
    elif hasattr(source, "latitude") and hasattr(source, "longitude"):
        # a few known classes that have latitude longitude attributes, like some common geo
        # libs
        lat, lon = source.latitude, source.longitude
    elif hasattr(source, "latitude_deg") and hasattr(source, "longitude_deg"):
        # a few known classes that have latitude_deg longitude_deg attributes, like the
        # locations from the orbit-predictor lib
        lat, lon = source.latitude_deg, source.longitude_deg
    elif source.__class__.__name__ == "Position" and hasattr(source, "position_llh"):
        # a known class from the orbit-predictor lib, which has ECEF coordinates but can easily
        # produce lat, lon, height coords
        lat, lon, _ = source.position_llh
    elif isinstance(source, (tuple, list)):
        if len(source) == 1:
            # a sequence with a single object inside, so extract a point from it as if we just got
            # that object alone
            return to_points(source[0], inverted_tuples=inverted_tuples)
        elif len(source) in (2, 3) and all_numbers(source):
            # a sequence of 2 or 3 numbers, these must be coordinates, finally!
            if inverted_tuples:
                lon, lat = source[:2]
            else:
                lat, lon = source[:2]
        else:
            # a sequence that doesn't look like coordinates but maybe a collection of points, try
            # to extract all of them into a list
            return [to_points(item, inverted_tuples=inverted_tuples) for item in source]
    else:
        raise ValueError(
            f"Can't guess the latitude and longitude from this object: {repr(source)}"
        )

    return Point(lat, lon)


def auto_convert(custom_type, converter_function):
    """
    Register a custom type to be automatically converted to single coordinates or sequences of
    coordinates, to be able to use them in the helper functions for map elements.
    """
    converters[custom_type] = converter_function


# types of things we can display on a map, with their attributes
Marker = namedtuple("Marker", "point popup")
Dot = namedtuple("Dot", "point color radius opacity border_color border_width popup")
Label = namedtuple("Label", "point text color size font opacity popup")
Html = namedtuple("Html", "point code popup")
Line = namedtuple("Line", "points_sequence color width opacity popup")
Area = namedtuple("Area", "points_sequence color opacity border_color border_width popup")
Geojson = namedtuple("Geojson", "path points_as lines_as areas_as")


def extract_single_points(points_source):
    """
    Extract and iterate over single points that might be part of point sequences, or even trees of
    points.

    This function assumes that points_source can contain only two types of things: Point instances,
    or sequences (lists/tuples/generators) containing any of both.

    Something like [[point_a], [point_b, point_c, point_d], [[[point_e]], point_f]]
    Will yield all of the Point instances, one by one, in order.
    """
    pending = [points_source]
    while pending:
        current = pending.pop(0)

        if isinstance(current, Point):
            yield current
        elif isinstance(current, (list, tuple, GeneratorType)):
            pending.extend(current)


def extract_points_sequences(points_source):
    """
    Extract and iterate over point sequences that might be themselves part of higher order
    sequences, or even trees of sequences.

    This function assumes that points_source can contain only two types of things: Point instances,
    or sequences (lists/tuples/generators) containing any of both.

    The only condition is that any sequence (list/tuple/generator) contains either all Point
    instances, or all sequences. No mixing of the two element types inside the same sequence.

    Something like [[point_a], [point_b, point_c, point_d], [[[point_e]]]]
    Will yield three sequences:
    [point_a]
    [point_b, point_c, point_d]
    [point_e]

    While something like [point_a, [point_b, point_c]]
    Will yield an error, as there's a sequence (the top level one) mixing types inside it.
    """
    pending = [points_source]
    while pending:
        current = pending.pop(0)

        if isinstance(current, Point):
            # we received a single point, not even in a sequence, just yield it as a sequence of
            # one element
            yield [current]
        elif isinstance(current, (list, tuple, GeneratorType)):
            # we have a sequence, but is it a sequence of points? or a sequence of other sequences?
            if all(isinstance(item, Point) for item in current):
                # current is a sequence of coords!
                yield current
            elif any(isinstance(item, Point) for item in current):
                raise ValueError(
                    f"There's a sequence mixing points and other kinds of objects: {repr(current)}"
                )
            else:
                # a sequence of sequences, or a sequence of broken things. Add each item to the
                # pending queue and deal with them when popped
                pending.extend(current)
        else:
            raise ValueError(
                f"Can't guess a sequence of coordinates from this object: {repr(current)}"
            )


def marker(*points_sources, popup=None):
    """
    Helper to easily build a Marker instance.
    """
    if not points_sources:
        return partial(marker, popup=popup)

    return [
        Marker(point, popup)
        for point in extract_single_points(to_points(points_sources))
    ]


def dot(*points_sources, color="blue", radius=3, opacity=1, border_color=None, border_width=0,
        popup=None):
    """
    Helper to easily build a Dot instance.
    """
    if not points_sources:
        return partial(dot, color=color, radius=radius, opacity=opacity, border_color=border_color,
                       border_width=border_width, popup=popup)

    if border_color is None:
        border_color = color
    elif border_width == 0:
        border_width = 2

    return [
        Dot(point, color, radius, opacity, border_color, border_width, popup)
        for point in extract_single_points(to_points(points_sources))
    ]


def label(*points_sources, text, color="blue", size=12, font="arial", opacity=1, popup=None):
    """
    Helper to easily build a Label instance.
    """
    if not points_sources:
        return partial(label, text=text, color=color, size=size, font=font, opacity=opacity,
                       popup=popup)

    return [
        Label(point, text, color, size, font, opacity, popup)
        for point in extract_single_points(to_points(points_sources))
    ]


def html(*points_sources, code, popup=None):
    """
    Helper to easily build a Html instance.
    """
    if not points_sources:
        return partial(html, code=code, popup=popup)

    return [
        Html(point, code, popup)
        for point in extract_single_points(to_points(points_sources))
    ]


def line(*points_sequences_sources, color="blue", width=2, opacity=1, popup=None):
    """
    Helper to easily build a Line instance.
    """
    if not points_sequences_sources:
        return partial(line, color=color, width=width, opacity=opacity, popup=popup)

    return [
        Line(points_sequence, color, width, opacity, popup)
        for points_sequence in extract_points_sequences(to_points(points_sequences_sources))
    ]


def area(*points_sequences_sources, color="blue", opacity=0.5, border_color=None, border_width=0,
         popup=None):
    """
    Helper to easily build an Area instance.
    """
    if not points_sequences_sources:
        return partial(area, color=color, opacity=opacity, border_color=border_color,
                       border_width=border_width, popup=popup)

    if border_color is None:
        border_color = color
    elif border_width == 0:
        border_width = 2

    return [
        Area(points_sequence, color, opacity, border_color, border_width, popup)
        for points_sequence in extract_points_sequences(to_points(points_sequences_sources))
    ]


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
            yield points_as(
                extract_single_points(to_points(geojson_data["coordinates"],
                                                inverted_tuples=True))
            )
        elif geojson_type == "LineString":
            yield lines_as(
                extract_points_sequences(to_points(geojson_data["coordinates"],
                                                   inverted_tuples=True))
            )
        elif geojson_type in ("Polygon", "MultiPolygon"):
            yield areas_as(
                extract_points_sequences(to_points(geojson_data["coordinates"],
                                                   inverted_tuples=True))
            )


def draw_map(*things, center=(0, 0), zoom=1.5, tiles="cartodbpositron"):
    """
    Draw a simple map with elements on it. Good known working tiles with folium 0.14:
    - "cartodbpositron" (white maps)
    - "OpenStreetMap"

    More info on tiles:
    https://python-visualization.github.io/folium/latest/user_guide/raster_layers/tiles.html
    """
    center = to_points(center)

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
                location=[thing.point.lat, thing.point.lon],
                popup=thing.popup,
            ).add_to(map_)

        elif isinstance(thing, Dot):
            folium.CircleMarker(
                location=[thing.point.lat, thing.point.lon],
                radius=thing.radius,
                color=thing.border_color,
                weight=thing.border_width,
                fillColor=thing.color,
                fillOpacity=thing.opacity,
                popup=thing.popup,
            ).add_to(map_)

        elif isinstance(thing, Label):
            folium.Marker(
                location=[thing.point.lat, thing.point.lon],
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
                location=[thing.point.lat, thing.point.lon],
                icon=folium.DivIcon(html=thing.code),
                popup=thing.popup,
            ).add_to(map_)

        elif isinstance(thing, Line):
            folium.PolyLine(
                locations=[(point.lat, point.lon)
                           for point in thing.points_sequence],
                color=thing.color,
                weight=thing.width,
                opacity=thing.opacity,
                popup=thing.popup,
            ).add_to(map_)

        elif isinstance(thing, Area):
            folium.Polygon(
                locations=[(point.lat, point.lon)
                           for point in thing.points_sequence],
                color=thing.border_color,
                weight=thing.border_width,
                fill_color=thing.color,
                fill_opacity=thing.opacity,
                popup=thing.popup,
            ).add_to(map_)

    return map_


try:
    # add shapely support if present
    from shapely.geometry import (
        Point as ShpPoint,
        LineString as ShpLineString,
        LinearRing as ShpLinearRing,
        Polygon as ShpPolygon,
        MultiPoint as ShpMultiPoint,
        MultiPolygon as ShpMultiPolygon,
        MultiLineString as ShpMultiLineString
    )

    auto_convert(ShpPoint, lambda p: (p.y, p.x))
    auto_convert(ShpLineString, lambda ls: [(c[1], c[0]) for c in ls.coords])
    auto_convert(ShpLinearRing, lambda ls: [(c[1], c[0]) for c in ls.coords])
    auto_convert(ShpPolygon, lambda p: [(c[1], c[0]) for c in p.exterior.coords])
    auto_convert(ShpMultiPoint, lambda mp: list(mp.geoms))
    auto_convert(ShpMultiLineString, lambda mp: list(mp.geoms))
    auto_convert(ShpMultiPolygon, lambda mp: list(mp.geoms))
except ImportError:
    # shapely not present, do nothing
    pass


try:
    # add shapely support if present
    # (https://telluric.readthedocs.io/en/latest/index.html)
    from telluric import GeoVector, FeatureCollection, GeoFeature

    auto_convert(GeoVector, lambda gv: gv.get_shape(gv.crs))
    auto_convert(GeoFeature, lambda gf: gf.geometry)
    auto_convert(FeatureCollection, lambda fc: fc.geometries)
except ImportError:
    # telluric not present, do nothing
    pass
