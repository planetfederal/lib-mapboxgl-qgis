# -*- coding: utf-8 -*-

def classFactory(iface):
    from plugin import MapboxGLPlugin
    return MapboxGLPlugin(iface)
