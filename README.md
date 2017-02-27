# lib-mapboxgl-qgis

A library to export QGIs projects and layer symbology from QGIS into the Mapbox GL style

##Usage

To use the library in your QGIS plugin, just add the `mapboxgl.py` file to your plugin folder, so it can be imported and used.

To export your project to Mapbox GL format, do the following:

```python
import mapboxgl
mapboxgl.projectToMapBox(folder)
```

where `folder` must the destination folder where you want the resulting files to be created. Only layers that are visible will be exported. Disabled layers will  not get exported.

Calling the above method will generate the following content in the specified folder:

* `mapbox.json`. The file which contains the QGIS project info in the Mapbox GL format. It includes references to the layers, a description of their symbology and how they should be rendered, and other elements such as the zoom level or the canvas center point, so as to reproduce as much as possible from the QGIs project from which it was created.

* `sprites.json` and `sprites.png`. File containing sprites to be used as part of the styling. These are generated when the QGIS style of a layer uses SVG icons

* `sprites@2x.json` and `sprites@2x.png`. Same as above, but for HDPI devices.

* `data` folder. File-based layers are are exported to GeoJSON files and stored in this folder. The `mapboxgl.json`references these files instead of the original data sources. Remotes layers are not exported, and they will point to the original sources in the exported `mapboxgl.json` file.


A sample OpenLayers application can be generated as well, so it can be used to quickly test the resulting Mapbox GL file and the rest of the generated file structure. To do it, an additional parameter has to be passed to the `projectToMapbox()` method, as shown below.

```python
import mapboxgl
mapboxgl.projectToMapBox(folder, True)
```

In this case, the output folder will contains the following additional files:

* `index.html`. The sample OpenLayers application
* `olms.js`. The required library to read Mapbox GL styles in OpenLayers.

You will need to have the `sampleapp` folder in your plugin code as well, since in this case, the `mapboxgl.pyp` file is not enough for generating the sample application.

##Supported styles

Not all QGIS styles are supported in the export process. Most of the common styles and features are correctly translated into Mapbox GL format, but some of them are not. When an unsupported style is detected, a message is added to the QGIS log. Make sure to check it in case you see that the resulting Mapbox GL file doesnt match you QGIS symbology.

More details about supported elements can be found in the [Supported elements](./supported.md) page.

##Importing a Mapbox GL file

The library also provides a method to load a project contained in a Mapbox GL file. The example below shows how to use it.

```python
import mapboxgl
openProjectFromMapboxFile(mapboxFile)
```

Although this method is fully functional, it is important to notice that the main goal of this library is to provide a tool to export to Mapbox GL format, so as to have a sound and reliable to method to share QGIS styling with other applications such as GeoServer or OpenLayers. For this reason, you can expect the import functonality to support less elements and to fail in some cases, especially when trying to open Mapbox GL files generated in other software.

Round-tripping from QGIS should work correctly, meaning that a `mapboxgl.json`file generated with this library can be generally saved and then reopened, and the project will be replicated correctly. However, files generated in other applications might cause problems, especially those with multi-layered symbology or labels. The layers might be correctly rendered, but the layer structure in the table of contents might not be optimal.

##Test plugin

A simple test plugin is added, which allows to easily call the methods described above.

To install the plugin, clone or download this repository, open a terminal in the repository folder and run `paver setup` (you will need to have `paver` installed). That will fetch the latest version of the OpenLayers module to support Mapbox GL files. Then run `paver install`. That will copy the plugin files to your QGIS user plugins folder, so the next time you start QGIS you will have it available.

The plugin adds three new menu entries under the *Plugins/Mapbox GL* menu.

* Import Mapbox GL...
* Export Mapbox GL...
* Export Mapbox GL (include test OL app)...


