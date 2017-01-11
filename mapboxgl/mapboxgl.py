from qgis.core import *
from qgis.utils import iface
import os
import re
import codecs
from PyQt4.QtCore import *
import math

def qgisLayers():
    return [lay for lay in iface.mapCanvas().layers() if lay.type() == lay.VectorLayer]

def projectToMapbox(folder = None):
    if folder is None:
        folder = "~/mapbox"
    return toMapbox(folder, qgisLayers())

def layerToMapbox(folder, layer):
    return toMapbox(folder, [layer])

def toMapbox(folder, layers):
    return {
        "version": 8,
        "name": "QGIS project",
        "sprite": "mapbox://sprites/mapbox/streets-v8",
        "glyphs": "mapbox://fonts/mapbox/{fontstack}/{range}.pbf",
        "sources": createSources(folder, layers),
        "layers": createLayers(layers)
    }

def createLayers(_layers):
    layers = []
    for layer in _layers:
        layers.extend(processLayer(layer))
    return layers

def createSources(folder, layers, precision = 2):
    sources = {}
    layersFolder = os.path.join(folder, "data")
    QDir().mkpath(layersFolder)
    reducePrecision = re.compile(r"([0-9]+\.[0-9]{%s})([0-9]+)" % precision)
    removeSpaces = lambda txt:'"'.join( it if i%2 else ''.join(it.split())
                         for i,it in enumerate(txt.split('"')))
    regexp = re.compile(r'"geometry":.*?null\}')
    for layer in layers:
        if layer.type() == layer.VectorLayer:
            layerName =  safeName(layer.name())
            path = os.path.join(layersFolder, "%s.geojson" % layerName)
            '''
            QgsVectorFileWriter.writeAsVectorFormat(layer, path, "utf-8", layer.crs(), 'GeoJson')
            with codecs.open(path, encoding="utf-8") as f:
                lines = f.readlines()
            with codecs.open(path, "w", encoding="utf-8") as f:
                for line in lines:
                    line = reducePrecision.sub(r"\1", line)
                    line = line.strip("\n\t ")
                    line = removeSpaces(line)
                    if layer.wkbType()==QGis.WKBMultiPoint:
                        line = line.replace("MultiPoint", "Point")
                        line = line.replace("[ [", "[")
                        line = line.replace("] ]", "]")
                        line = line.replace("[[", "[")
                        line = line.replace("]]", "]")
                    line = regexp.sub(r'"geometry":null', line)
                    f.write(line)
            '''
            sources[layerName] = {"type": "geojson",
                                "data": "./data/lyr_%s.geojson" % layerName
                                }

    return sources

def _toZoomLevel(lev):
    #TODO
    return lev

def _property(s, default=None):
    def _f(x):
        try:
            return float(x.symbolLayer(0).properties()[s])
        except KeyError:
            return default
    return _f

def _colorProperty(s):
    def _f(x):
        try:
            return _getRGBColor(x.symbolLayer(0).properties()[s])
        except KeyError:
            return "rgb(0,0,0)"
    return _f


def _getRGBColor(color):
    try:
        r,g,b,a = color.split(",")
    except:
        color = color.lstrip('#')
        lv = len(color)
        r,g,b = tuple(str(int(color[i:i + lv // 3], 16)) for i in range(0, lv, lv // 3))
    return 'rgb(%s)' % ",".join([r, g, b])


def _fillPatternIcon(x):
    try:
        return x.svgFilePath()

    except:
        return None

def _alpha(x):
    try:
        return x.alpha()
    except:
        return 1

def _lineDash(x):
    #TODO: improve this
    try:
        if x.symbolLayer(0).properties()["line_style"] == "solid":
            return [1]
        else:
            return [3, 3]
    except KeyError:
        return [1]

def _convertSymbologyForLayerType(symbols, functionType, layerType, attribute):
    d = {}
    if layerType == "circle":
        _setPaintProperty(d, "circle-radius", symbols, _property("size", 1), functionType, attribute)
        _setPaintProperty(d, "circle-color", symbols, _colorProperty("color"), functionType, attribute)
        _setPaintProperty(d, "circle-opacity", symbols, _alpha, functionType, attribute)
        _setPaintProperty(d, "circle-stroke-width", symbols, _property("outline_width", 1), functionType, attribute)
        _setPaintProperty(d, "circle-stroke-color", symbols, _colorProperty("outline_color"), functionType, attribute)
    elif layerType == "line":
        _setPaintProperty(d, "line-width", symbols, _property("line_width", 1), functionType, attribute)
        _setPaintProperty(d, "line-opacity", symbols, _alpha, functionType, attribute)
        _setPaintProperty(d, "line-color", symbols, _colorProperty("line_color"), functionType, attribute)
        _setPaintProperty(d, "line-offset", symbols, _property("offset"), functionType, attribute)
        _setPaintProperty(d, "line-dasharray", symbols, _lineDash, functionType, attribute)
    elif layerType == "fill":
        _setPaintProperty(d, "fill-color", symbols, _colorProperty("color"), functionType, attribute)
        _setPaintProperty(d, "fill-outline-color", symbols, _colorProperty("outline_color"), functionType, attribute)
        _setPaintProperty(d, "fill-pattern", symbols, _fillPatternIcon, functionType, attribute)
        _setPaintProperty(d, "fill-opacity", symbols, _alpha, functionType, attribute)
        _setPaintProperty(d, "fill-translate", symbols, _property("offset"), functionType, attribute)

    return d

def _setPaintProperty(paint, property, obj, func, funcType, attribute):
    if isinstance(obj, dict):
        d = {}
        d["property"] = attribute
        d["stops"] = {}
        for k,v in obj.iteritems():
            if v.symbolLayerCount() > 0:
                d["stops"][k] = func(v)
        d["type"] = funcType
        for element in d["stops"].values():
            if element is not None:
                paint[property] = d
                break
    else:
        v = func(obj)
        if v:
           paint[property] = v

layerTypes = {QGis.Point: "circle", QGis.Line: "line", QGis.Polygon: "fill"}

def processLayer(qgisLayer):
    layers = []
    try:
        layer = {}
        layer["id"] = "lyr_" + safeName(qgisLayer.name())
        layer["source"] = "src_" + safeName(qgisLayer.name())
        layer["type"] = layerTypes[qgisLayer.geometryType()]
        if str(qgisLayer.customProperty("labeling/scaleVisibility")).lower() == "true":
            layer["minzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMin")))
            layer["maxzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMax")))

        renderer = qgisLayer.rendererV2()
        if isinstance(renderer, QgsSingleSymbolRendererV2):
            symbols = renderer.symbol().clone()
            functionType = None
            prop = None
        elif isinstance(renderer, QgsCategorizedSymbolRendererV2):
            symbols = {}
            for cat in renderer.categories():
                symbols[cat.value()] = cat.symbol().clone()
            functionType = "categorical"
            prop = renderer.classAttribute()
        elif isinstance(renderer, QgsGraduatedSymbolRendererV2):
            symbols = {}
            for ran in renderer.ranges():
                symbols[ran.lowerValue()] = ran.symbol().clone()
            functionType = "interval"
            prop = renderer.classAttribute()
        else:
            return []

        layer["paint"] = _convertSymbologyForLayerType(symbols, functionType, layer["type"], prop)

    except Exception, e:
        import traceback
        print traceback.format_exc()
        return []

    layers.append(layer)
    if str(qgisLayer.customProperty("labeling/enabled")).lower() == "true":
        layers.append(processLabeling(qgisLayer))
    return layers

def processLabeling(qgisLayer):
    layer = {}
    layer["id"] = "txt_" + safeName(qgisLayer.name())
    layer["source"] = "src_" + safeName(qgisLayer.name())
    layer["type"] = "symbol"

    layer["layout"] = {}
    labelField = qgisLayer.customProperty("labeling/fieldName")
    layer["layout"]["text-field"] = "{%s}" % labelField
    try:
        size = str(float(qgisLayer.customProperty("labeling/fontSize")) * 2)
    except:
        size = 1
    layer["layout"]["text-size"] = size

    layer["paint"] = {}
    r = qgisLayer.customProperty("labeling/textColorR")
    g = qgisLayer.customProperty("labeling/textColorG")
    b = qgisLayer.customProperty("labeling/textColorB")
    color = "rgba(%s, %s, %s, 255)" % (r,g,b)
    layer["paint"]["text-color"] = color

    if str(qgisLayer.customProperty("labeling/bufferDraw")).lower() == "true":
        rHalo = str(qgisLayer.customProperty("labeling/bufferColorR"))
        gHalo = str(qgisLayer.customProperty("labeling/bufferColorG"))
        bHalo = str(qgisLayer.customProperty("labeling/bufferColorB"))
        strokeWidth = str(float(qgisLayer.customProperty("labeling/bufferSize")))
        layer["paint"]["text-halo-color"] = "rgba(%s, %s, %s, 255)" % (rHalo, gHalo, bHalo),
        layer["paint"]["text-halo-width"] =  strokeWidth

    rotation = -1 * float(qgisLayer.customProperty("labeling/angleOffset"))
    layer["layout"]["text-rotate"] = rotation

    offsetX = qgisLayer.customProperty("labeling/xOffset")
    offsetY = qgisLayer.customProperty("labeling/yOffset")

    layer["layout"]["text-offset"] = offsetX + "," + offsetY
    layer["layout"]["text-opacity"] = (255 - int(qgisLayer.layerTransparency())) / 255.0

    # textBaselines = ["bottom", "middle", "top"]
    # textAligns = ["end", "center", "start"]
    # quad = int(layer.customProperty("labeling/quadOffset"))
    # textBaseline = textBaselines[quad / 3]
    # textAlign = textAligns[quad % 3]
    #===========================================================================

    if str(qgisLayer.customProperty("labeling/scaleVisibility")).lower() == "true":
        layer["minzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMin")))
        layer["maxzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMax")))

    return layer


def safeName(name):
    #TODO: we are assuming that at least one character is valid...
    validChars = '123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
    return ''.join(c for c in name if c in validChars).lower()


def setLayerSymbologyFromMapboxStyle(layer, style):
    if style["type"] != layerTypes[qgisLayer.geometryType()]:
        return

