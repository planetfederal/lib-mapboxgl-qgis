import unittest
import sys
from processing.mapboxgl import mapboxgl
from qgis.utils import iface
import os
from qgis.core import QgsMapLayerRegistry
import shutil
import processing
from processing import dataobjects
import tempfile

def testRoundTripPoints():
    projectFile = os.path.join(os.path.dirname(__file__), "data", "testpoints.qgs")
    iface.addProject(projectFile)
    layerA = processing.getObject("points")
    folder = tempfile.mkdtemp()
    styles = mapboxgl.projectToMapbox(folder)
    layerA2 =dataobjects.load(layerA.source(), "points2")
    mapboxgl.setLayerSymbologyFromMapboxStyle(layerA2, styles["layers"][0])
    mapboxgl.setLayerLabelingFromMapboxStyle(layerA2, styles["layers"][1])
    layerB2 =dataobjects.load(layerA.source(), "pointsb2")
    mapboxgl.setLayerSymbologyFromMapboxStyle(layerB2, styles["layers"][2])
    shutil.rmtree(folder, ignore_errors=True)
    '''
    QgsMapLayerRegistry.instance().removeMapLayer(layerA)
    layerB = processing.getObject("pointsb")
    QgsMapLayerRegistry.instance().removeMapLayer(layerB)
    stylesB = mapboxgl.projectToMapbox("d:\\mapbox")
    self.assertEqual(styles, stylesB)
    '''

def testRoundTripPolygons():
    projectFile = os.path.join(os.path.dirname(__file__), "data", "testpolygons.qgs")
    iface.addProject(projectFile)
    layerA = processing.getObject("polygons")
    folder = tempfile.mkdtemp()
    styles = mapboxgl.projectToMapbox(folder)
    layerA2 =dataobjects.load(layerA.source(), "polygons2")
    mapboxgl.setLayerSymbologyFromMapboxStyle(layerA2, styles["layers"][0])
    layerB2 =dataobjects.load(layerA.source(), "polygonsb2")
    mapboxgl.setLayerSymbologyFromMapboxStyle(layerB2, styles["layers"][1])
    layerC2 =dataobjects.load(layerA.source(), "polygonsc2")
    mapboxgl.setLayerSymbologyFromMapboxStyle(layerC2, styles["layers"][2])
    shutil.rmtree(folder, ignore_errors=True)
