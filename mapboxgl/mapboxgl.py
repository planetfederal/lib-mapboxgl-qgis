from qgis.core import *
from qgis.utils import iface
import os
import re
import codecs
from PyQt4.QtCore import *
from PyQt4.QtGui import QColor
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
            print s
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
        d = []
        d["property"] = attribute
        d["stops"] = {}
        for k,v in obj.iteritems():
            if v.symbolLayerCount() > 0:
                d["stops"].append([k, func(v)])
        d["type"] = funcType
        for element in d["stops"]:
            if element[1] is not None:
                paint[property] = d
                break
    else:
        v = func(obj)
        if v is not None:
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
        size = float(qgisLayer.customProperty("labeling/fontSize")) * 2
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
        layer["paint"]["text-halo-color"] = "rgba(%s, %s, %s, 255)" % (rHalo, gHalo, bHalo)
        layer["paint"]["text-halo-width"] =  float(strokeWidth)

    rotation = -1 * float(qgisLayer.customProperty("labeling/angleOffset"))
    layer["layout"]["text-rotate"] = rotation

    offsetX = str(qgisLayer.customProperty("labeling/xOffset"))
    offsetY = str(qgisLayer.customProperty("labeling/yOffset"))

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

def _qcolorFromRGBString(color):
    color = "".join([c for c in color if c in "1234567890,"])
    r, g, b = color.split(",")
    return QColor(int(r), int(g), int(b))


def _markerSymbol(outlineColor, outlineWidth, color, size, opacity):
    symbol = QgsMarkerSymbolV2()
    symbolLayer = QgsSimpleMarkerSymbolLayerV2(size = size, color = _qcolorFromRGBString(color))
    symbolLayer.setOutlineColor(_qcolorFromRGBString(outlineColor))
    symbolLayer.setOutlineWidth(outlineWidth)
    symbol.appendSymbolLayer(symbolLayer)
    symbol.deleteSymbolLayer(0)
    symbol.setAlpha(opacity)
    return symbol

def _fillSymbol(color, outlineColor, translate, opacity):
    symbol = QgsFillSymbolV2()
    symbolLayer = QgsSimpleFillSymbolLayerV2()
    symbolLayer.setBorderColor(_qcolorFromRGBString(outlineColor))
    x,y = translate.split(",")
    symbolLayer.setOffset(QPointF(float(x), float(y)))
    symbolLayer.setFillColor(_qcolorFromRGBString(color))
    symbol.appendSymbolLayer(symbolLayer)
    smymbol.setAlpha(opacity)
    return symbol

def _lineSymbol(color, width, dash, offset, opacity):
    symbol = QgsLineSymbolV2()
    symbolLayer = QgsSimpleLineSymbolLayerV2(_qcolorFromRGBString(color), width)
    symbolLayer.setCustomDashVector(dash)
    symbolLayer.setOffset(offset)
    symbol.appendSymbolLayer(symbolLayer)
    smymbol.setAlpha(opacity)
    return symbol

def setLayerSymbologyFromMapboxStyle(layer, style):
    if style["type"] != layerTypes[layer.geometryType()]:
        return

    if style["type"] == "line":
        if isinstance(style["paint"]["line-color"], list):
            if style["paint"]["circle-radius"]["type"] == "categorical":
                renderer = QgsCategorizedSymbolRendererV2(style["paint"]["line-color"]["property"]
                                                          .replace("{", "").replace("}", ""))
                for i, stop in enumerate(style["paint"]["line-color"]["stops"]):
                    dash = style["paint"]["line-dasharray"]["stops"][i][1]
                    width = style["paint"]["line-width"]["stops"][i][1]
                    offset = style["paint"]["line-offset"]["stops"][i][1]
                    opacity = style["paint"]["circle-opacity"]["stops"][i][1]
                    color = stop[1]
                    symbol = _lineSymbol(color, width, dash, offset, opacity)
                    value = stop[0]
                    category = QgsRendererCategoryV2(value, symbol, value)
                    renderer.addCategory(category)
                layer.setRendererV2(renderer)
            else:
                renderer = QgsGraduatedSymbolRendererV2(style["paint"]["line-color"]["property"]
                                                          .replace("{", "").replace("}", ""))
                for i, stop in enumerate(style["paint"]["line-color"]["stops"]):
                    dash = style["paint"]["line-dasharray"]["stops"][i][1]
                    width = style["paint"]["line-width"]["stops"][i][1]
                    offset = style["paint"]["line-offset"]["stops"][i][1]
                    opacity = style["paint"]["line-opacity"]["stops"][i][1]
                    color = stop[1]
                    symbol = _lineSymbol(color, width, dash, offset, opacity)
                    min = style["paint"]["line-color"]["stops"][i][0]
                    try:
                        min = stop[0]
                    except:
                        max = min
                    range = QgsRendererRangeV2(min, max, symbol, str(min) + "-" + str(max))
                    renderer.addClass(range)
                layer.setRendererV2(renderer)
        else:
            dash = style["paint"]["line-dasharray"]
            width = style["paint"]["line-width"]
            offset = style["paint"]["line-offset"]
            opacity = style["paint"]["line-opacity"]
            color = style["paint"]["line-color"]
            symbol = _lineSymbol(color, width, dash, offset, opacity)
            layer.setRendererV2(QgsSingleSymbolRendererV2(symbol))
    elif style["type"] == "circle":
        if isinstance(style["paint"]["circle-radius"], list):
            if style["paint"]["circle-radius"]["type"] == "categorical":
                renderer = QgsCategorizedSymbolRendererV2(style["paint"]["circle-radius"]["property"]
                                                          .replace("{", "").replace("}", ""))
                for i, stop in enumerate(style["paint"]["circle-radius"]["stops"]):
                    outlineColor = style["paint"]["circle-stroke-color"]["stops"][i][1]
                    outlineWidth = style["paint"]["circle-stroke-width"]["stops"][i][1]
                    color = style["paint"]["circle-color"]["stops"][i][1]
                    opacity = style["paint"]["circle-opacity"]["stops"][i][1]
                    radius = stop[1]
                    symbol = _markerSymbol(outlineColor, outlineWidth, color, radius, opacity)
                    value = stop[0]
                    category = QgsRendererCategoryV2(value, symbol, value)
                    renderer.addCategory(category)
                layer.setRendererV2(renderer)
            else:
                renderer = QgsGraduatedSymbolRendererV2(style["paint"]["circle-radius"]["property"]
                                                          .replace("{", "").replace("}", ""))
                for i, stop in enumerate(style["paint"]["circle-radius"]["stops"]):
                    outlineColor = style["paint"]["circle-stroke-color"]["stops"][i][1]
                    outlineWidth = style["paint"]["circle-stroke-width"]["stops"][i][1]
                    color = style["paint"]["circle-color"]["stops"][i][1]
                    opacity = style["paint"]["circle-opacity"]["stops"][i][1]
                    radius = stop[1]
                    symbol = _markerSymbol(outlineColor, outlineWidth, color, radius, opacity)
                    min = stop[0]
                    try:
                        max = style["paint"]["circle-radius"]["stops"][i+1][0]
                    except:
                        max = min
                    range = QgsRendererRangeV2(min, max, symbol, str(min) + "-" + str(max))
                    renderer.addClass(range)
                layer.setRendererV2(renderer)
        else:
            outlineColor = style["paint"]["circle-stroke-color"]
            outlineWidth = style["paint"]["circle-stroke-width"]
            color = style["paint"]["circle-color"]
            radius = style["paint"]["circle-radius"]
            opacity = style["paint"]["circle-opacity"]
            symbol = _markerSymbol(outlineColor, outlineWidth, color, radius, opacity)
            layer.setRendererV2(QgsSingleSymbolRendererV2(symbol))
    elif style["type"] == "fill":
        if isinstance(style["paint"]["fill-color"], list):
            if style["paint"]["fill-color"]["type"] == "categorical":
                renderer = QgsCategorizedSymbolRendererV2(style["paint"]["fill-color"]["property"]
                                                          .replace("{", "").replace("}", ""))
                for i, stop in enumerate(style["paint"]["fill-color"]["stops"]):
                    outlineColor = style["paint"]["fill-outline-color"]["stops"][i][1]
                    translate = style["paint"]["fill-translate"]["stops"][i][1]
                    opacity = style["paint"]["fill-opacity"]["stops"][i][1]
                    color = stop[1]
                    symbol = _fillSymbol(color, outlineColor, translate, opacity)
                    value = stop[0]
                    category = QgsRendererCategoryV2(value, symbol, value)
                    renderer.addCategory(category)
                layer.setRendererV2(renderer)
            else:
                renderer = QgsGraduatedSymbolRendererV2(style["paint"]["fill-color"]["property"]
                                                          .replace("{", "").replace("}", ""))
                for i, stop in enumerate(style["paint"]["fill-color"]["stops"]):
                    outlineColor = style["paint"]["fill-outline-color"]["stops"][i][1]
                    translate = style["paint"]["fill-translate"]["stops"][i][1]
                    opacity = style["paint"]["fill-opacity"]["stops"][i][1]
                    color = stop[1]
                    symbol = _fillSymbol(color, outlineColor, translate, opacity)
                    min = stop[0]
                    try:
                        min = style["paint"]["fill-color"]["stops"][i+1][0]
                    except:
                        max = min
                    range = QgsRendererRangeV2(min, max, symbol, str(min) + "-" + str(max))
                    renderer.addClass(range)
                layer.setRendererV2(renderer)
        else:
            outlineColor = style["paint"]["fill-outline-color"]["stops"][i][1]
            translate = style["paint"]["fill-translate"]["stops"][i][1]
            opacity = style["paint"]["fill-opacity"]["stops"][i][1]
            color = stop[1]
            symbol = _fillSymbol(color, outlineColor, translate, opacity)
            layer.setRendererV2(QgsSingleSymbolRendererV2(symbol))

def setLayerLabelingFromMapboxStyle(layer, style):
    palyr = QgsPalLayerSettings()
    palyr.readFromLayer(layer)
    palyr.enabled = True
    palyr.fieldName = style["layout"]["text-field"].replace("{", "").replace("}", "")
    palyr.writeToLayer(layer)
    palyr.setDataDefinedProperty(QgsPalLayerSettings.Size,True,True,str(style["layout"]["text-size"]), "")
    palyr.setDataDefinedProperty(QgsPalLayerSettings.Color,True,True,str(style["paint"]["text-color"]), "")
    if "text-halo-color" in style["layout"]:
        palyr.setDataDefinedProperty(QgsPalLayerSettings.BufferColor,True,True,str(style["layout"]["text-halo-color"]), "")
    if "text-halo-width" in style["layout"]:
        palyr.setDataDefinedProperty(QgsPalLayerSettings.BufferSize,True,True,str(style["layout"]["text-halo-width"]), "")
    palyr.writeToLayer(layer)

def _testRoundTrip():
    import processing
    layerA = processing.getObject("a")
    style = layerToMapbox("/Users/volaya/mapboxgl", layerA)
    import json
    print json.dumps(style, indent=4, sort_keys=True)
    layerB = processing.getObject("b")
    setLayerSymbologyFromMapboxStyle(layerB, style["layers"][0])
    setLayerLabelingFromMapboxStyle(layerB, style["layers"][1])
