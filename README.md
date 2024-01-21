# Simplest Maps

Super simple on-liner maps in python.

# Installation

`pip3 install simplestmaps`

# Usage

This lib aims to be super simple to use. For instance, to draw a markers and an area, you could do something like this:

```python
from simplestmaps import draw_map, area, marker

draw_map(
    marker(-31.2526, -61.4917, popup="my hometown"),
    area([(-31.2741, -61.5105), (-31.2872, -61.5137), (-31.2895, -61.5003), (-31.2764, -61.4973)], color="green", popup="our airfield"),
)
```

![example map](./readme_example1.png)

It can even do more advanced stuff, like plotting the contents of a geojson file (points, areas, lines):

```python
from simplestmaps import draw_map, geojson

draw_map(
    geojson("./demo.geojson"),
)
```

![example map](./readme_example2.png)

And every element plotted into the map is customizable (colors, fonts, sizes, etc).

Here are a good set of examples that showcase (and document) all of the supported features:

# Demo and docs

[See everything that's possible here! (TODO: pending link)](http://example.com)
