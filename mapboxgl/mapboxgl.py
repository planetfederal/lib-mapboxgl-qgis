from qgis.core import * 
from qgis.utils import iface
import os
import re
import codecs
from PyQt4.QtCore import *

def qgisLayers():
    skipType = [2]
    return [lay for lay in iface.mapCanvas().layers() if lay.type() not in skipType]

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

def _property(s):
    return (lambda x: x.symbolLayer(0).properties()[s])

def _colorProperty(s):
    return  (lambda x: _getRGBAColor(x.symbolLayer(0).properties()[s], x.alpha()))

def _getRGBAColor(color, alpha):
    try:
        r,g,b,a = color.split(",")
    except:
        color = color.lstrip('#')
        lv = len(color)
        r,g,b = tuple(str(int(color[i:i + lv // 3], 16)) for i in range(0, lv, lv // 3))
        a = 255.0
    a = float(a) / 255.0
    return 'rgba(%s)' % ",".join([r, g, b, str(alpha * a)])

def _convertSymbologyForLayerType(symbols, functionType, layerType, attribute):
    d = {}
    print layerType
    if layerType == "circle":
        d["circle-radius"] = _paintProperty(symbols, _property("size"), functionType, attribute)
        d["circle-color"] = _paintProperty(symbols, _colorProperty("outline_color"), functionType, attribute)
    elif layerType == "line":
        d["line-width"] = _paintProperty(symbols, _property("line_width"), functionType, attribute)
        d["line-color"] = _paintProperty(symbols, _colorProperty("line_color"), functionType, attribute)
        #TODO:line dash pattern
    elif layerType == "fill":
        d["fill-color"] = _paintProperty(symbols, _colorProperty("color"), functionType, attribute)
        d["fill-outline-color"] = _paintProperty(symbols, _colorProperty("outline_color"), functionType, attribute)

    return d

def _paintProperty(obj, func, funcType, attribute):
    if isinstance(obj, dict):
        d = {}
        d["property"] = attribute
        d["stops"] = {k:func(v) for k,v in obj.iteritems()}
        d["type"] = funcType
        return d
    else:
        return func(obj)

layerTypes = {QGis.Point: "circle", QGis.Line: "line", QGis.Polygon: "fill"}

def processLayer(qgisLayer):
    layers = []
    try:
        layer = {}
        layer["id"] = "lyr_" + safeName(qgisLayer.name())
        layer["source"] = "src_" + safeName(qgisLayer.name())
        layer["type"] = layerTypes[qgisLayer.geometryType()]
        renderer = qgisLayer.rendererV2()
        if isinstance(renderer, QgsSingleSymbolRendererV2):
            symbols = renderer.symbol()
            functionType = None
            prop = None
        elif isinstance(renderer, QgsCategorizedSymbolRendererV2):
            symbols = {}
            for cat in renderer.categories():
                symbols[cat.value()] = cat.symbol()
            functionType = "categorical"
            prop = renderer.classAttribute()
        elif isinstance(renderer, QgsGraduatedSymbolRendererV2):
            symbols = {}
            for ran in renderer.ranges():
                symbols[ran.lowerValue()] = ran.symbol()
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

def processLabeling(layer):
    pass

def safeName(name):
    #TODO: we are assuming that at least one character is valid...
    validChars = '123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
    return ''.join(c for c in name if c in validChars).lower()

