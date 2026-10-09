from pathlib import Path
import tempfile
from typing import List
import zipfile

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon


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


def create_synthetic_shapefile_zip(
    zip_path: Path,
    geometry_type: str = "Polygon",
    crs: str = "EPSG:4326",
    include_prj: bool = True,
) -> Path:
    """Generate a valid synthetic Shapefile ZIP archive containing specified geometry type."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        shp_stem = "parcels"
        shp_file = temp_dir_path / f"{shp_stem}.shp"

        # Generate sample geometries and attributes
        if geometry_type == "Polygon":
            geoms = [
                Polygon(
                    [
                        (77.590, 12.970),
                        (77.595, 12.970),
                        (77.595, 12.975),
                        (77.590, 12.975),
                        (77.590, 12.970),
                    ]
                ),
                Polygon(
                    [
                        (77.600, 12.980),
                        (77.605, 12.980),
                        (77.605, 12.985),
                        (77.600, 12.985),
                        (77.600, 12.980),
                    ]
                ),
            ]
            data = {
                "name": ["Zone A", "Zone B"],
                "area_class": ["Industrial", "Commercial"],
            }
        elif geometry_type == "LineString":
            geoms = [
                LineString([(77.590, 12.970), (77.595, 12.975), (77.600, 12.980)]),
                LineString([(77.610, 12.990), (77.615, 12.995)]),
            ]
            data = {
                "name": ["Pipeline 1", "Pipeline 2"],
                "status": ["Active", "Planned"],
            }
        elif geometry_type == "Point":
            geoms = [
                Point(77.5946, 12.9716),
                Point(77.6000, 12.9800),
            ]
            data = {"name": ["Sensor 1", "Sensor 2"], "elevation": [920.5, 915.2]}
        else:
            raise ValueError(f"Unsupported synthetic geometry type: {geometry_type}")

        gdf = gpd.GeoDataFrame(data, geometry=geoms, crs=crs if include_prj else None)
        gdf.to_file(shp_file, driver="ESRI Shapefile")

        # If include_prj is False, remove .prj file if generated
        prj_file = temp_dir_path / f"{shp_stem}.prj"
        if not include_prj and prj_file.exists():
            prj_file.unlink()

        # Pack component files into ZIP
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in temp_dir_path.iterdir():
                if item.is_file() and item.stem.lower() == shp_stem.lower():
                    zf.write(item, arcname=item.name)

    return zip_path
