from qgis.core import *
from qgis.utils import iface
import os
import re
import codecs
import json
from PyQt4.QtCore import *
from PyQt4.QtGui import QColor, QImage, QPixmap, QPainter
import math
from collections import OrderedDict
from processing import dataobjects
from distutils.dir_util import copy_tree

def qgisLayers():
    return [lay for lay in iface.mapCanvas().layers() if lay.type() == lay.VectorLayer]

def projectToMapbox(folder, includeApp = False):
    return toMapbox(qgisLayers(), folder, includeApp)

def layerToMapbox(layer, folder, includeApp = False):
    return toMapbox(folder, [layer], includeApp)   

def toMapbox(qgislayers, folder, includeApp = False):
    layers, sprites = createLayers(folder, qgislayers)
    extent = iface.mapCanvas().extent()
    center = [(extent.xMinimum() + extent.xMaximum() ) / 2, (extent.yMinimum() + extent.yMaximum() ) / 2]
    zoom = _toZoomLevel(iface.mapCanvas().scale())
    obj = {
        "version": 8,
        "name": "QGIS project",
        "glyphs": "mapbox://fonts/mapbox/{fontstack}/{range}.pbf",
        "sources": createSources(folder, qgislayers),
        "layers": layers,
        "center": center,
        "zoom": zoom
    }
    if sprites:
        obj["sprite"] = "./sprites"
    with open(os.path.join(folder, "mapbox.json"), 'w') as f:
        json.dump(obj, f)

    if includeApp:
        sampleAppFolder = os.path.join(os.path.dirname(__file__), "sampleapp")
        copy_tree(sampleAppFolder, folder)
    
    return obj

def createLayers(folder, _layers):
    layers = []
    allSprites = {}
    for layer in _layers:
        sprites, style = processLayer(layer)
        layers.extend(style)
        allSprites.update(sprites)
    saveSprites(folder, allSprites)
    
    return layers, allSprites

NO_ICON = "no_icon"

def saveSprites(folder, sprites):
    if sprites:
        height = max([s.height() for s,s2x in sprites.values()])
        width = sum([s.width() for s,s2x in sprites.values()])
        img = QImage(width, height, QImage.Format_ARGB32)
        img.fill(QColor(Qt.transparent))
        img2x = QImage(width * 2, height * 2, QImage.Format_ARGB32)
        img2x.fill(QColor(Qt.transparent))
        painter = QPainter(img)  
        painter.begin(img)
        painter2x = QPainter(img2x)  
        painter2x.begin(img2x)
        spritesheet = {NO_ICON:{"width": 0,
                             "height": 0,
                             "x": 0,
                             "y": 0,
                             "pixelRatio": 1}}
        spritesheet2x = {NO_ICON:{"width": 0,
                             "height": 0,
                             "x": 0,
                             "y": 0,
                             "pixelRatio": 1}}
        x = 0
        for name, sprites in sprites.iteritems():
            s, s2x = sprites
            painter.drawImage(x, 0, s)
            painter2x.drawImage(x * 2, 0, s2x)
            spritesheet[name] = {"width": s.width(),
                                 "height": s.height(),
                                 "x": x,
                                 "y": 0,
                                 "pixelRatio": 1}
            spritesheet2x[name] = {"width": s2x.width(),
                                 "height": s2x.height(),
                                 "x": x * 2,
                                 "y": 0,
                                 "pixelRatio": 2}
            x += s.width()
        painter.end()
        painter2x.end()
        img.save(os.path.join(folder, "sprites.png"))
        img2x.save(os.path.join(folder, "sprites@2x.png"))
        with open(os.path.join(folder, "sprites.json"), 'w') as f:
            json.dump(spritesheet, f)
        with open(os.path.join(folder, "sprites@2x.json"), 'w') as f:
            json.dump(spritesheet2x, f)

def createSources(folder, layers, precision = 6):
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
            if folder is not None:
                path = os.path.join(layersFolder, "%s.geojson" % layerName)
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
            sources[layerName] = {"type": "geojson",
                                "data": "data/%s.geojson" % layerName
                                }

    return sources

def _toZoomLevel(scale):
    return int(math.log(1000000000 / scale, 2))

def _toScale(level):
    return 1000000000 / (math.pow(2, level))

def _property(s, iSymbolLayer, default=None):
    def _f(x):
        if iSymbolLayer >= x.symbolLayerCount():
            return default
        try:
            return float(x.symbolLayer(iSymbolLayer).properties()[s])
        except KeyError:
            QgsMessageLog.logMessage("Unknown property '%s' in symbol of type '%s'. That type of symbol might not be supported for export"
                 % (s, x.symbolLayer(iSymbolLayer).__class__.__name__), level=QgsMessageLog.WARNING)
            return default
        except ValueError:
            return str(x.symbolLayer(iSymbolLayer).properties()[s])
    return _f

def _fillOutlineColor(iSymbolLayer):
    def _f(x):
        if iSymbolLayer >= x.symbolLayerCount():
            return "rgb(0,0,0)"
        symbolLayer = x.symbolLayer(iSymbolLayer)
        if isinstance(symbolLayer, QgsSVGFillSymbolLayer):
            return _getRGBColor(x.symbolLayer(iSymbolLayer).subSymbol().symbolLayer(0).properties()["line_color"])
        try:
            return _getRGBColor(x.symbolLayer(iSymbolLayer).properties()["outline_color"])
        except:
            return "rgb(0,0,0)"
    return _f

def _fillColor(iSymbolLayer):
    def _f(x):
        if iSymbolLayer >= x.symbolLayerCount():
            return  "rgb(0,0,0)"
        symbolLayer = x.symbolLayer(iSymbolLayer)
        if isinstance(symbolLayer, QgsSVGFillSymbolLayer):
            return "rgb(0,0,0)"
        try:
            return _getRGBColor(x.symbolLayer(iSymbolLayer).properties()["color"])
        except:
            return "rgb(0,0,0)"
    return _f    

def _colorProperty(s, iSymbolLayer):
    def _f(x):
        if iSymbolLayer >= x.symbolLayerCount():
            return "rgb(0,0,0)"
        try:
            return _getRGBColor(x.symbolLayer(iSymbolLayer).properties()[s])
        except KeyError:
            return  "rgb(0,0,0)"
    return _f


def _getRGBColor(color):
    try:
        r,g,b,a = color.split(",")
    except:
        color = color.lstrip('#')
        lv = len(color)
        r,g,b = tuple(str(int(color[i:i + lv // 3], 16)) for i in range(0, lv, lv // 3))
    return 'rgb(%s)' % ",".join([r, g, b])


def _fillPatternIcon(iSymbolLayer):
    def _f(x):
        if iSymbolLayer >= x.symbolLayerCount():
            return NO_ICON
        symbolLayer = x.symbolLayer(iSymbolLayer)
        try:
            filename, ext = os.path.splitext(os.path.basename(symbolLayer.svgFilePath()))
            return filename
        except:
            return NO_ICON
    return _f

def _alpha(iSymbolLayer):
    def _f(x):
        if iSymbolLayer >= x.symbolLayerCount():
            return 0
        try:
            return x.alpha()
        except:
            return 1
    return _f

def _lineDash(iSymbolLayer):
    def _f(x):
        if iSymbolLayer >= x.symbolLayerCount():
            return [0]
        #TODO: improve this
        try:
            if x.symbolLayer(iSymbolLayer).properties()["line_style"] == "solid":
                return [0]
            else:
                return [3, 3]
        except KeyError:
            return [0]
    return _f

_nonSvgIcons = {}
def _iconName(iSymbolLayer):
    def _f(x):
        global _nonSvgIcons
        if iSymbolLayer >= x.symbolLayerCount():
            return NO_ICON
        symbolLayer = x.symbolLayer(iSymbolLayer)
        if isinstance(symbolLayer, QgsSvgMarkerSymbolLayerV2):
            filename, ext = os.path.splitext(os.path.basename(symbolLayer.path()))
            return filename
        elif isinstance(symbolLayer, QgsSVGFillSymbolLayer):
            filename, ext = os.path.splitext(os.path.basename(symbolLayer.svgFilePath()))
            return filename
        else:
            if symbolLayer not in _nonSvgIcons:
                _nonSvgIcons[symbolLayer] = "nonsvg_%i" % len(_nonSvgIcons)
            return _nonSvgIcons[symbolLayer]
    return _f
        
def _saveSymbolLayerSprite(symbol, iSymbolLayer):
    sl = symbol.symbolLayer(iSymbolLayer).clone()
    if isinstance(sl, QgsSVGFillSymbolLayer):
        patternWidth = sl.patternWidth()
        color = sl.svgFillColor()
        outlineColor = sl.svgOutlineColor()
        sl = QgsSvgMarkerSymbolLayerV2(sl.svgFilePath())
        sl.setFillColor(color)
        sl.setOutlineColor(outlineColor)
        sl.setSize(patternWidth)
        sl.setOutputUnit(QgsSymbolV2.Pixel)  
    sl2x = sl.clone()
    try:
        sl2x.setSize(sl2x.size() * 2)
    except AttributeError:
        return None, None
    newSymbol = QgsMarkerSymbolV2()
    newSymbol.appendSymbolLayer(sl)
    newSymbol.deleteSymbolLayer(0)
    newSymbol2x = QgsMarkerSymbolV2()
    newSymbol2x.appendSymbolLayer(sl2x)
    newSymbol2x.deleteSymbolLayer(0)
    img = newSymbol.asImage(QSize(sl.size(), sl.size()))
    img2x = newSymbol2x.asImage(QSize(sl2x.size(), sl2x.size()))
    return img, img2x

def _checkUnitsProperty(qgisLayer, symbols, iSymbolLayer, prop):
    if not isinstance(symbols, dict):
        symbols = {"singlesymbol": symbols}
    for k,v in symbols.iteritems():
        try:
            value = v.symbolLayer(iSymbolLayer).properties()[prop]
        except:
            continue
        if value != "Pixel":
            QgsMessageLog.logMessage("Warning: marker symbol in layer '%s' (class '%s', symbol layer number %i) "
                "uses units other than pixels. Only pixels are supported"
                 % (qgisLayer.name(), k, iSymbolLayer + 1), level=QgsMessageLog.WARNING)

def _convertSymbologyForLayer(qgisLayer, symbols, functionType, attribute):
    layers = []
    sprites = {}
    if not isinstance(symbols, OrderedDict):
        symbolLayerCount = symbols.symbolLayerCount()
    else:
        symbolLayerCount = max([s.symbolLayerCount() for s in symbols.values()])
    for iSymbolLayer in xrange(symbolLayerCount):
        paint = {}
        layer = {}
        layerType = _getLayerType(qgisLayer)
        if layerType == "symbol":
            _symbols = symbols
            if not isinstance(symbols, OrderedDict):
                _symbols = {"singlesymbol": symbols}
            for k, symbol in _symbols.iteritems():                
                if iSymbolLayer < symbol.symbolLayerCount():
                    sl = symbol.symbolLayer(iSymbolLayer)
                    if sl.outputUnit() != QgsSymbolV2.Pixel:
                        QgsMessageLog.logMessage("Warning: marker symbol in layer '%s' (class '%s', symbol layer number %i) "
                            "uses units other than pixels. Only pixels are supported" 
                            % (qgisLayer.name(), k, iSymbolLayer + 1), level=QgsMessageLog.WARNING)
                    img, img2x = _saveSymbolLayerSprite(symbol, iSymbolLayer)
                    if img is not None:
                        sprites[_iconName(iSymbolLayer)(symbol)] = (img, img2x)
            _setPaintProperty(paint, "icon-image", symbols, _iconName(iSymbolLayer), functionType, attribute)
        elif layerType == "line":
            _checkUnitsProperty(qgisLayer, symbols, iSymbolLayer, "line_width_unit")
            _setPaintProperty(paint, "line-width", symbols, _property("line_width", iSymbolLayer, 1), functionType, attribute)
            _setPaintProperty(paint, "line-opacity", symbols, _alpha(iSymbolLayer), functionType, attribute)
            _setPaintProperty(paint, "line-color", symbols, _colorProperty("line_color", iSymbolLayer), functionType, attribute)
            _setPaintProperty(paint, "line-offset", symbols, _property("offset", iSymbolLayer, 0), functionType, attribute)
            _setPaintProperty(paint, "line-dasharray", symbols, _lineDash(iSymbolLayer), functionType, attribute)
        elif layerType == "fill":
            _setPaintProperty(paint, "fill-color", symbols, _fillColor(iSymbolLayer), functionType, attribute)
            _setPaintProperty(paint, "fill-outline-color", symbols, _fillOutlineColor(iSymbolLayer), functionType, attribute)
            _symbols = symbols
            if not isinstance(symbols, OrderedDict):
                _symbols = {"singlesymbol": symbols}
            for symbol in _symbols.values():
                if iSymbolLayer < symbol.symbolLayerCount():
                    img, img2x = _saveSymbolLayerSprite(symbol, iSymbolLayer)
                    if img:
                        sprites[_iconName(iSymbolLayer)(symbol)] = (img, img2x)
            _setPaintProperty(paint, "fill-pattern", symbols, _fillPatternIcon(iSymbolLayer), functionType, attribute)
            _setPaintProperty(paint, "fill-opacity", symbols, _alpha(iSymbolLayer), functionType, attribute)
            _setPaintProperty(paint, "fill-translate", symbols, _property("offset", iSymbolLayer, 0), functionType, attribute)
        layer["paint"] = paint
        layer["type"] = layerType
        layers.append(layer)

    return sprites, layers

def _setPaintProperty(paint, property, obj, func, funcType, attribute):
    if isinstance(obj, OrderedDict):
        d = {}
        d["property"] = attribute
        d["stops"] = []
        for k,v in obj.iteritems():
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

def _getLayerType(qgisLayer):
    if qgisLayer.geometryType() == QGis.Line:
        return "line"
    if qgisLayer.geometryType() == QGis.Polygon:
        return "fill"
    else:
        return "symbol"


def processLayer(qgisLayer):
    allLayers = []
    allSprites = {}
    try:
        renderer = qgisLayer.rendererV2()
        if isinstance(renderer, QgsSingleSymbolRendererV2):
            symbols = renderer.symbol().clone()
            functionType = None
            prop = None
        elif isinstance(renderer, QgsCategorizedSymbolRendererV2):
            symbols = OrderedDict()
            for cat in renderer.categories():
                symbols[cat.value()] = cat.symbol().clone()
            functionType = "categorical"
            prop = renderer.classAttribute()
        elif isinstance(renderer, QgsGraduatedSymbolRendererV2):
            symbols = OrderedDict()
            for ran in renderer.ranges():
                symbols[ran.lowerValue()] = ran.symbol().clone()
            functionType = "interval"
            prop = renderer.classAttribute()
        else:
            QgsMessageLog.logMessage("Warning: unsupported renderer:" + renderer.__class__.__name__, level=QgsMessageLog.WARNING)
            return {}, []

        sprites, layers = _convertSymbologyForLayer(qgisLayer, symbols, functionType, prop)
        for i, layer in enumerate(layers):
            layer["id"] = "%s:%i" % (safeName(qgisLayer.name()), i)
            layer["source"] = safeName(qgisLayer.name())
            if str(qgisLayer.customProperty("labeling/scaleVisibility")).lower() == "true":
                mapboxLayer["minzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMin")))
                mapboxLayer["maxzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMax")))
            allLayers.append(layer)

        allSprites.update(sprites)
        
    except Exception, e:
        import traceback
        QgsMessageLog.logMessage("ERROR: " + traceback.format_exc(), level=QgsMessageLog.CRITICAL)
        return {}, []

    if str(qgisLayer.customProperty("labeling/enabled")).lower() == "true":
        allLayers.append(processLabeling(qgisLayer))
    return allSprites, allLayers

def processLabeling(qgisLayer):
    layer = {}
    layer["id"] = "txt_" + safeName(qgisLayer.name())
    layer["source"] =  safeName(qgisLayer.name())
    layer["type"] = "symbol"

    layer["layout"] = {}
    labelField = qgisLayer.customProperty("labeling/fieldName")
    layer["layout"]["text-field"] = "{%s}" % labelField
    try:
        size = float(qgisLayer.customProperty("labeling/fontSize"))
    except:
        size = 1
    layer["layout"]["text-size"] = size
    layer["layout"]["text-font"] =  ["Arial Normal"]

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

    offsetX = float(qgisLayer.customProperty("labeling/xOffset"))
    offsetY = float(qgisLayer.customProperty("labeling/yOffset"))

    layer["layout"]["text-offset"] = [offsetX, offsetY]
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

def _fillSymbolLayer(color, outlineColor, translate):
    symbolLayer = QgsSimpleFillSymbolLayerV2()
    symbolLayer.setBorderColor(_qcolorFromRGBString(outlineColor))
    x,y = translate.split(",")
    symbolLayer.setOffset(QPointF(float(x), float(y)))
    symbolLayer.setFillColor(_qcolorFromRGBString(color))    
    return symbolLayer

def _fillSymbol(color, outlineColor, translate, opacity):
    symbol = QgsFillSymbolV2()  
    symbol.appendSymbolLayer(_fillSymbolLayer(color, outlineColor, translate))
    symbol.deleteSymbolLayer(0)
    symbol.setAlpha(opacity)
    return symbol

def _svgFillSymbolLayer(outlineColor, fillPattern, sprites):
    symbolLayer = QgsSVGFillSymbolLayer()
    svgPath, size = _getSvgPath(fillPattern, sprites)
    symbolLayer.setSvgFilePath(svgPath)
    symbolLayer.setPatternWidth(size)
    symbolLayer.setOutputUnit(QgsSymbolV2.Pixel) 
    subSymbol = QgsLineSymbolV2()
    subSymbol.appendSymbolLayer(QgsSimpleLineSymbolLayerV2(_qcolorFromRGBString(outlineColor)))
    subSymbol.deleteSymbolLayer(0)
    symbolLayer.setSubSymbol(subSymbol)
    return symbolLayer

def _svgFillSymbol(outlineColor, opacity, fillPattern, sprites):
    symbol = QgsFillSymbolV2()
    symbol.appendSymbolLayer(_svgFillSymbolLayer(outlineColor, fillPattern, sprites))
    symbol.deleteSymbolLayer(0)
    symbol.setAlpha(opacity)
    return symbol

def _lineSymbolLayer(color, width, dash, offset):    
    symbolLayer.setCustomDashVector(dash)
    symbolLayer.setOffset(offset)
    return symbol

def _lineSymbol(color, width, dash, offset, opacity):
    symbol = QgsLineSymbolV2()
    symbol.appendSymbolLayer(_lineSymbolLayer(color, width, dash, offset))
    symbol.deleteSymbolLayer(0)
    symbol.setAlpha(opacity)

def _getSvgPath(name, sprites):
    #TODO: see if there is a built-in sprite with that name    
    if name is None:
        return None, None
    with open(sprites + ".json") as f:
        spritesDict = json.load(f)
    rect = QRect(spritesDict[name]["x"], spritesDict[name]["y"], 
                spritesDict[name]["width"], spritesDict[name]["height"])
    width = spritesDict[name]["width"]
    height = spritesDict[name]["height"]
    image = QImage()
    image.load(sprites + ".png")
    sprite = image.copy(rect)
    pngPath = os.path.join(os.path.dirname(sprites), name + ".png")
    sprite.save(pngPath)
    with open(pngPath, "rb") as f:
        data = f.read()
    base64 = data.encode("base64")
    svgPath = os.path.join(os.path.dirname(sprites), name + ".svg")
    with open(svgPath, "w") as f:
        f.write(_svgTemplate % {"w": width, "h": height, "b64": base64 })
    return svgPath, max([width, height])

_svgTemplate =  """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"
    "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
    <svg version="1.1"
    xmlns="http://www.w3.org/2000/svg"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    width="%(w)ipx" height="%(h)ipx" viewBox="0 0 %(w)i %(h)i">
    <image xlink:href="data:image/png;base64,%(b64)s" width="%(w)i" height="%(h)i" x="0" y="0" />
    </svg>"""

def _svgMarkerSymbolLayer(name, sprites):
    if name is None:
        return None
    svgPath, size = _getSvgPath(name, sprites)
    symbolLayer = QgsSvgMarkerSymbolLayerV2(svgPath)
    symbolLayer.setSize(size)
    symbolLayer.setOutputUnit(QgsSymbolV2.Pixel)  
    return symbolLayer  

def _svgMarkerSymbol(name, sprites):
    symbol = QgsMarkerSymbolV2()
    symbol.appendSymbolLayer(_svgMarkerSymbolLayer(name, sprites))
    symbol.deleteSymbolLayer(0)
    return symbol

def _getCategoryOrRange(layer, name):
    renderer = layer.rendererV2()
    if isinstance(renderer, QgsCategorizedSymbolRendererV2):        
        cats = renderer.categories()
        for i, cat in enumerate(cats):
            if cat.label() == name:
                return i, cat
        return -1, None
    else:
        ranges = renderer.ranges()
        for i, rang in enumerate(ranges):
            if rang.label() == name:
                return i, rang
        return -1, None

layerTypes = {QGis.Point: ["circle", "symbol"], QGis.Line: ["line"], QGis.Polygon: ["fill"]}

def setLayerSymbologyFromMapboxStyle(layer, style, sprites, add):
    if style["type"] not in layerTypes[layer.geometryType()]:
        return

    if style["type"] == "line":
        if isinstance(style["paint"]["line-color"], dict):
            if style["paint"]["line-color"]["type"] == "categorical":
                categories = []
                for i, stop in enumerate(style["paint"]["line-color"]["stops"]):
                    dash = style["paint"]["line-dasharray"]["stops"][i][1]
                    width = style["paint"]["line-width"]["stops"][i][1]
                    offset = style["paint"]["line-offset"]["stops"][i][1]
                    opacity = style["paint"]["line-opacity"]["stops"][i][1]
                    color = stop[1]
                    value = stop[0]
                    if add:
                        idx, cat = _getCategoryOrRange(layer, str(value))
                        if idx != 1:                            
                            symbol = cat.symbol().clone()
                            symbolLayer = _lineSymbolLayer(color, width, dash, offset)
                            if symbolLayer is not None:
                                symbol.appendSymbolLayer(symbolLayer)
                                layer.rendererV2().updateCategorySymbol(idx, symbol)
                    else:
                        symbol = _lineSymbol(color, width, dash, offset, opacity)
                        categories.append(QgsRendererCategoryV2(value, symbol, str(value)))                    
                if not add:
                    renderer = QgsCategorizedSymbolRendererV2(style["paint"]["line-color"]["property"], categories)
                    layer.setRendererV2(renderer)
            else:
                ranges = []
                for i, stop in enumerate(style["paint"]["line-color"]["stops"]):
                    dash = style["paint"]["line-dasharray"]["stops"][i][1]
                    width = style["paint"]["line-width"]["stops"][i][1]
                    offset = style["paint"]["line-offset"]["stops"][i][1]
                    opacity = style["paint"]["line-opacity"]["stops"][i][1]
                    color = stop[1]
                    minValue = stop[0]
                    try:
                        maxValue = style["paint"]["line-color"]["stops"][i+1][0]
                    except:
                        maxValue = 100000000000
                    rangeName = str(minValue) + "-" + str(maxValue)
                    if add:
                        idx, rang = _getCategoryOrRange(layer, str(value))
                        if idx != 1:                            
                            symbol = rang.symbol().clone()
                            symbolLayer = _lineSymbolLayer(color, width, dash, offset)
                            if symbolLayer is not None:
                                symbol.appendSymbolLayer(symbolLayer)
                                layer.rendererV2().updateRangeSymbol(idx, symbol)
                    else:
                        symbol = _lineSymbol(color, width, dash, offset, opacity)
                        ranges.append(QgsRendererRangeV2(minValue, maxValue, symbol, rangeName))
                if not add:
                    renderer = QgsGraduatedSymbolRendererV2(style["paint"]["line-color"]["property"], ranges)
                    layer.setRendererV2(renderer)
        else:
            dash = style["paint"]["line-dasharray"]
            width = style["paint"]["line-width"]
            offset = style["paint"]["line-offset"]
            opacity = style["paint"]["line-opacity"]
            color = style["paint"]["line-color"]
            if add:
                symbol = layer.rendererV2().symbol().clone()
                symbolLayer = _lineSymbolLayer(color, width, dash, offset)
                if symbolLayer is not None:
                    symbol.appendSymbolLayer(symbolLayer)
                    layer.rendererV2().setSymbol(symbol)
            else:
                symbol = _lineSymbol(color, width, dash, offset, opacity)
                layer.setRendererV2(QgsSingleSymbolRendererV2(symbol))
    elif style["type"] == "fill":
        var = style["paint"]["fill-color"] if "fill-color" in style["paint"] else style["paint"]["fill-pattern"]
        if isinstance(var, dict):            
            if var["type"] == "categorical":
                categories = []
                for i, stop in enumerate(var["stops"]):
                    outlineColor = style["paint"]["fill-outline-color"]["stops"][i][1]
                    try:
                        translate = style["paint"]["fill-translate"]["stops"][i][1]
                    except:
                        translate = 0
                    opacity = style["paint"]["fill-opacity"]["stops"][i][1]
                    try:
                        fillPattern = style["paint"]["fill-pattern"]["stops"][i][1]
                    except KeyError:
                        fillPattern = None
                        color = stop[1]
                    value = stop[0]
                    if add:
                        idx, cat = _getCategoryOrRange(layer, str(value))
                        if idx != 1:                            
                            symbol = cat.symbol().clone()
                            if fillPattern is None:
                                symbolLayer = _fillSymbolLayer(color, outlineColor, translate)
                            else:
                                symbolLayer = _svgFillSymbolLayer(outlineColor, fillPattern, sprites)
                            if symbolLayer is not None:                                
                                symbol.appendSymbolLayer(symbolLayer)
                                layer.rendererV2().updateCategorySymbol(idx, symbol)
                    else:
                        if fillPattern is None:
                            symbolLayer = _fillSymbol(color, outlineColor, translate, opacity)
                        else:
                            symbolLayer = _svgFillSymbol(outlineColor, fillPattern, sprites, opacity)
                        categories.append(QgsRendererCategoryV2(value, symbol, str(value)))
                if not add:
                    renderer = QgsCategorizedSymbolRendererV2(style["paint"]["fill-color"]["property"], categories)
                    layer.setRendererV2(renderer)
            else:
                ranges = []
                for i, stop in enumerate(var["stops"]):
                    outlineColor = style["paint"]["fill-outline-color"]["stops"][i][1]
                    try:
                        translate = style["paint"]["fill-translate"]["stops"][i][1]
                    except:
                        translate = 0
                    opacity = style["paint"]["fill-opacity"]["stops"][i][1]
                    try:
                        fillPattern = style["paint"]["fill-pattern"]["stops"][i][1]
                    except KeyError:
                        fillPattern = None
                        color = stop[1]
                    minValue = stop[0]
                    try:
                        maxValue = style["paint"]["fill-color"]["stops"][i+1][0]
                    except:
                        maxValue = 100000000000
                    rangeName = str(minValue) + "-" + str(maxValue)
                    if add:
                        idx, rang = _getCategoryOrRange(layer, str(value))
                        if idx != 1:                            
                            symbol = rang.symbol().clone()
                            if fillPattern is None:
                                symbolLayer = _fillSymbolLayer(color, outlineColor, translate)
                            else:
                                symbolLayer = _svgFillSymbolLayer(outlineColor, fillPattern, sprites)                            
                            if symbolLayer is not None:
                                symbol.appendSymbolLayer(symbolLayer)
                                layer.rendererV2().updateRangeSymbol(idx, symbol)
                    else:
                        if fillPattern is None:
                            symbolLayer = _fillSymbol(color, outlineColor, translate, opacity)
                        else:
                            symbolLayer = _svgFillSymbol(outlineColor, fillPattern, sprites, opacity)
                        ranges.append(QgsRendererRangeV2(minValue, maxValue, symbol, rangeName))
                if not add:
                    renderer = QgsGraduatedSymbolRendererV2(style["paint"]["fill-color"]["property"], ranges)
                    layer.setRendererV2(renderer)
        else:
            outlineColor = style["paint"]["fill-outline-color"]
            try:
                translate = style["paint"]["fill-translate"]
            except:
                translate = 0
            opacity = style["paint"]["fill-opacity"]
            try:
                fillPattern = style["paint"]["fill-pattern"]
            except KeyError:
                fillPattern = None
                color = style["paint"]["fill-color"]
            if add:
                symbol = layer.rendererV2().symbol().clone()
                if fillPattern is None:
                    symbolLayer = _fillSymbolLayer(color, outlineColor, translate)
                else:
                    symbolLayer = _svgFillSymbolLayer(outlineColor, fillPattern, sprites)
                if symbolLayer is not None:
                    symbol.appendSymbolLayer(symbolLayer)
                    layer.rendererV2().setSymbol(symbol)
            else:
                symbol = _fillSymbol(color, outlineColor, translate, opacity)
                layer.setRendererV2(QgsSingleSymbolRendererV2(symbol))
    elif style["type"] == "symbol":
        if isinstance(style["paint"]["icon-image"], dict):            
            if style["paint"]["icon-image"]["type"] == "categorical":
                categories = []
                for i, stop in enumerate(style["paint"]["icon-image"]["stops"]):
                    value = stop[0]
                    if add:
                        idx, cat = _getCategoryOrRange(layer, str(value))
                        if idx != 1:                            
                            symbol = cat.symbol().clone()
                            symbolLayer = _svgMarkerSymbolLayer(stop[1], sprites)
                            if symbolLayer is not None:
                                symbol.appendSymbolLayer(symbolLayer)
                                layer.rendererV2().updateCategorySymbol(idx, symbol)
                    else:
                        symbol = _svgMarkerSymbol(stop[1], sprites)
                        categories.append(QgsRendererCategoryV2(value, symbol, str(value)))
                if not add:
                    renderer = QgsCategorizedSymbolRendererV2(style["paint"]["icon-image"]["property"], categories)
                    layer.setRendererV2(renderer)
            else:
                ranges = []
                for i, stop in enumerate(style["paint"]["icon-image"]["stops"]):
                    minValue = stop[0]
                    try:
                        maxValue = style["paint"]["icon-image"]["stops"][i+1][0]
                    except:
                        maxValue = 100000000000
                    rangeName = str(minValue) + "-" + str(maxValue)
                    if add:
                        idx, rang = _getCategoryOrRange(layer, str(value))
                        if idx != 1:                            
                            symbol = rang.symbol().clone()
                            symbolLayer = _svgMarkerSymbolLayer(stop[1], sprites)
                            if symbolLayer is not None:
                                symbol.appendSymbolLayer(symbolLayer)
                                layer.rendererV2().updateRangeSymbol(idx, symbol)
                    else:
                        symbol = _svgMarkerSymbol(stop[1], sprites)
                        ranges.append(QgsRendererRangeV2(minValue, maxValue, symbol, rangeName))
                if not add:
                    renderer = QgsGraduatedSymbolRendererV2(style["paint"]["icon-image"]["property"], ranges)
                    layer.setRendererV2(renderer)
        else:
            if add:
                symbol = layer.rendererV2().symbol().clone()
                symbolLayer = _svgMarkerSymbolLayer(style["paint"]["icon-image"], sprites)
                if symbolLayer is not None:
                    symbol.appendSymbolLayer(symbolLayer)
                    layer.rendererV2().setSymbol(symbol)
            else:
                symbol = _svgMarkerSymbol(style["paint"]["icon-image"], sprites)
                layer.setRendererV2(QgsSingleSymbolRendererV2(symbol))

    iface.legendInterface().refreshLayerSymbology(layer)
    layer.triggerRepaint()

def setLayerLabelingFromMapboxStyle(layer, style):
    palyr = QgsPalLayerSettings()
    palyr.readFromLayer(layer)
    palyr.enabled = True
    palyr.fieldName = style["layout"]["text-field"].replace("{", "").replace("}", "")
    offsets = style["layout"]["text-offset"].split(",")
    palyr.xOffset = float(offsets[0])
    palyr.yOffset = float(offsets[0])
    if "minzoom" in style:
        palyr.scaleMin = _toScale(float(style["minzoom"]))
        palyr.scaleMax = _toScale(float(style["maxzoom"]))
        palyr.scaleVisibility = True
        palyr.placement = QgsPalLayerSettings.OverPoint

    #palyr.setDataDefinedProperty(QgsPalLayerSettings.OffsetXY,True,True,str(offsets), "")
    palyr.setDataDefinedProperty(QgsPalLayerSettings.Size,True,True,str(style["layout"]["text-size"]), "")
    palyr.setDataDefinedProperty(QgsPalLayerSettings.Color,True,True,str(style["paint"]["text-color"]), "")

    if "text-halo-color" in style["layout"]:
        palyr.setDataDefinedProperty(QgsPalLayerSettings.BufferColor,True,True,str(style["layout"]["text-halo-color"]), "")
    if "text-halo-width" in style["layout"]:
        palyr.setDataDefinedProperty(QgsPalLayerSettings.BufferSize,True,True,str(style["layout"]["text-halo-width"]), "")
    palyr.writeToLayer(layer)

def openProjectFromMapboxFile(mapboxFile):
    iface.newProject()
    layers = {}
    labels = []
    with open(mapboxFile) as f:
        project = json.load(f)
    if "sprite" in project:
        sprites = os.path.join(os.path.dirname(mapboxFile), project["sprite"])
    else:
        sprites = None
    for layer in project["layers"]:
        source = project["sources"][layer["source"]]["data"]
        path = os.path.join(os.path.dirname(mapboxFile), source)
        if layer["id"].startswith("txt"):
            labels.append(layer)
        else:
            add = True
            if layer["source"] not in layers:
                add = False
                layers[layer["source"]] = dataobjects.load(path, layer["id"])
            setLayerSymbologyFromMapboxStyle(layers[layer["source"]], layer, sprites, add)
    for labelLayer in labels:
        setLayerLabelingFromMapboxStyle(layers[labelLayer["source"]], labelLayer)
        
        
            