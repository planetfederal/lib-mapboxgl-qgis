# -*- coding: utf-8 -*-

import mapboxgl
from PyQt4 import QtGui

class MapboxGLPlugin:

    def __init__(self, iface):
        self.iface = iface

    def unload(self):
        self.menuImport.deleteLater()

    def initGui(self):
        self.actionImport = QtGui.QAction("Import Mapbox GL...", self.iface.mainWindow())
        self.actionImport.triggered.connect(self.importMapbox)
        self.iface.addPluginToMenu(u"Mapbox GL", self.actionImport)
        self.actionExport = QtGui.QAction("Export Mapbox GL...", self.iface.mainWindow())
        self.actionExport.triggered.connect(lambda: self.exportMapbox(False))
        self.iface.addPluginToMenu(u"Mapbox GL", self.actionExport)
        self.actionExportWithApp = QtGui.QAction("Export Mapbox GL (include test OL app)...", self.iface.mainWindow())
        self.actionExportWithApp.triggered.connect(lambda: self.exportMapbox(True))
        self.iface.addPluginToMenu(u"Mapbox GL", self.actionExportWithApp)        


    def importMapbox(self):
        filename = QtGui.QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Open Mapbox File')
        if filename:
            mapboxgl.openProjectFromMapboxFile(filename)
        
    def exportMapbox(self, includeApp):
        folder =  QtGui.QFileDialog.getExistingDirectory(self.iface.mainWindow(), "Select folder to store project", 
                                                        "", QtGui.QFileDialog.ShowDirsOnly)
        if folder:
            mapboxgl.projectToMapbox(folder, includeApp)
    