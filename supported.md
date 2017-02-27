This document contains information about unsupported elements in QGIS that, at the moment, cannot be exported into the MapboxGL format.


#General remarks

* All units have to be in *pixels*.

* The only supported renderers are: *Single Symbol*, *Categorized* and *Graduated*

* Data defined properties are not supported for any type of symbology or element.

* Layer transparency is supported, but layer blending is not.

* Layers are reprojected to EPSG:4326, since that's the supported CRS for Mapbox GL

* *Draw effects* functionality is not supported


# Point layers

*Supported symbol layer types:* Ellipse marker, Simple marker, Fill marker, Font marker, SVG marker.

All properties of markers are supported except *Anchor point*. 

Markers of all types are always converted to PNG icons. For this reason, saving and loading a QGIS project into Mapbox GL format and reopening it results in a loss of rendering quality, since simple marker symbols or SVG icons, which are vector symbols and thus scalable, will become raster PNG icons.

Multi-layered markers are supported.

Line layers
============

*Supported symbol layer types:* Simple line. All properties are supported except custom dash pattern


#Polygon layers

Supported symbol layer types: Simple fill and SVGFill.


Outline width is not supported, regardless of the renderer and the symbol type. Dash patterns for the polygon outline are also not supported. If your QGIS layer has a polygon layer styled with an outline wider than a single pixel or that uses a dash pattern, consider creating a separate line layer for rendering the outline.

#Labelling

Only parameters in the Text and Placement sections are supported.

##Text section

*Supported parameters:* Style, Size, Color. Size only supported in points

##Placement section

The only mode supported is *Offset from Point* 

Offset and Rotation are  supported. Quadrant is not, and will always behave as if the central quuadrant is selected
