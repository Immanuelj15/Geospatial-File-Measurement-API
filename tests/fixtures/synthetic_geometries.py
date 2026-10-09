from pathlib import Path
from typing import List


def create_synthetic_kml(
    file_path: Path,
    include_point: bool = True,
    include_line: bool = True,
    include_polygon: bool = True,
) -> Path:
    """Generate a valid synthetic OGC KML 2.2 file for testing."""
    placemarks: List[str] = []

    if include_point:
        placemarks.append(
            """    <Placemark>
      <name>Survey Marker 1</name>
      <description>Ground control point</description>
      <Point>
        <coordinates>77.5946,12.9716,0</coordinates>
      </Point>
    </Placemark>"""
        )

    if include_line:
        placemarks.append(
            """    <Placemark>
      <name>Survey Transect Line</name>
      <description>Linear flight path</description>
      <LineString>
        <coordinates>
          77.5946,12.9716,0
          77.5956,12.9726,0
          77.5966,12.9736,0
        </coordinates>
      </LineString>
    </Placemark>"""
        )

    if include_polygon:
        placemarks.append(
            """    <Placemark>
      <name>Survey Boundary Polygon</name>
      <description>Monitored field area</description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0
              77.5950,12.9700,0
              77.5950,12.9750,0
              77.5900,12.9750,0
              77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>"""
        )

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Synthetic Survey Dataset</name>
{chr(10).join(placemarks)}
  </Document>
</kml>"""

    file_path.write_text(content, encoding="utf-8")
    return file_path


def create_multi_folder_kml(file_path: Path) -> Path:
    """Generate a KML file containing features in multiple folders."""
    content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder>
      <name>Markers</name>
      <Placemark>
        <name>Marker Alpha</name>
        <Point>
          <coordinates>77.5946,12.9716,0</coordinates>
        </Point>
      </Placemark>
    </Folder>
    <Folder>
      <name>Boundaries</name>
      <Placemark>
        <name>Field Beta</name>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                77.5900,12.9700,0
                77.5950,12.9700,0
                77.5950,12.9750,0
                77.5900,12.9750,0
                77.5900,12.9700,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>
  </Document>
</kml>"""
    file_path.write_text(content, encoding="utf-8")
    return file_path


def create_malformed_kml(file_path: Path) -> Path:
    """Generate an unparseable KML file with corrupt XML syntax."""
    file_path.write_text("<?xml version='1.0'?><kml><unclosed_tag>", encoding="utf-8")
    return file_path


def create_empty_kml(file_path: Path) -> Path:
    """Generate a valid KML structure with zero features."""
    content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Empty Dataset</name>
  </Document>
</kml>"""
    file_path.write_text(content, encoding="utf-8")
    return file_path
