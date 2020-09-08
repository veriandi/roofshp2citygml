# Importing libraries
import shapefile as sf
import rasterio
from lxml import etree
import uuid

# Created by Mirza Veriandi
# Student Number 15116068
# June 2020
# Geodesy and Geomatics Engineering Undergraduate
# Remote Sensing and Geographic Information Sciences Research Group
# Institut Teknologi Bandung (ITB)

# Reading shapefile and extracting features and attribute
shapefile_dir = str(input('Input your roof shapefile data directory (example: C:/Users/.../roof_shapefile):\n'))
fp_features = shapefile_dir
sf_reader = sf.Reader(fp_features)
attributes = sf_reader.records()
features = sf_reader.shapes()

# Reading elevation data (GeoTiff format)
elevation_dir = str(input('Input your DTM data directory (example: C:/Users/.../dtm.tif):\n'))
dataset = rasterio.open(elevation_dir)

# Extracting elevation band (assuming raster data only have one band)
ground_elevation = dataset.read(1)

# Creating output geometry dictionary
out_geometry = {}

# List of all buildings ID
bldg_id = []
for i in range(len(attributes)):
    bldg_id.append(attributes[i][1])
bldg_id_unique = list(set(bldg_id))

# List of all feature indices in the shapefile that forms a certain building
bldg_indices = []
for i in range(len(bldg_id_unique)):
    indices = []
    for n in range(len(bldg_id)):
        if bldg_id[n] == bldg_id_unique[i]:
            indices.append(n)
    bldg_indices.append(indices)

# Concatenated list of buildings features and attributes
# [[building 1 features/attributes], ...., [building n features/attributes]]
bldg_features = []
bldg_attributes = []
for i, ID in enumerate(bldg_id_unique):
    bldg_feat = []
    bldg_att = []
    for index in bldg_indices[i]:
        bldg_feat.append(features[index])
        bldg_att.append(attributes[index])
    bldg_features.append(bldg_feat)
    bldg_attributes.append(bldg_att)

# Defining a function for extracting X, Y, Z data
def adding_z(feature, output, attribute):
    feature_coord = []
    
    # Creating a list of (X, Y, Z) coordinates
    for i in range(len(feature.points)):
        l_coord = list(feature.points[i])
        l_coord.append(feature.z[i])
        t_coord = tuple(l_coord)
        feature_coord.append(t_coord) 
    
    # Surface orientation correction except for WallSurface (2) and ClosureSurface (4)
    # Projected to 2D and evaluated using linear time algorithm (sf.signed_area())
    if attribute[0] != 2 and attribute[0] != 5 and attribute[0] != 4:
        coordXY = []
        for i in range(len(feature_coord)):
            x, y = feature_coord[i][0], feature_coord[i][1]
            coordXY.append((x, y))
        if sf.signed_area(coordXY) < 0:
            feature_coord.reverse()
    
    elif attribute[0] == 4:
        coordXY = []
        for i in range(len(feature_coord)):
            x, y = feature_coord[i][0], feature_coord[i][1]
            coordXY.append((x, y))
        if sf.signed_area(coordXY) >= 0:
            feature_coord.reverse()
    
    output.append(feature_coord)

# Defining a function for extracting XYZ coordinates from multipart features (polygons with holes)
def adding_z_multi(feature, output, attribute):
    
    # Extracting XY coordinates to check for CW/CCW rings
    coordinates_xy = []
    for i in range(len(feature.points)):
        coordinates_xy.append(feature.points[i])
    feature_coord_xy = []
    for i in range(len(feature.parts)):
        if not i == (len(feature.parts)-1):
            part_coord_xy = coordinates_xy[feature.parts[i]:feature.parts[i+1]]
            feature_coord_xy.append(part_coord_xy)
        else:
            part_coord_xy = coordinates_xy[feature.parts[i]:]
            feature_coord_xy.append(part_coord_xy)
        
    # Extracting XYZ coordinates for the end product
    coordinates_xyz = []
    for i in range(len(feature.points)):
        l_coord = list(feature.points[i])
        l_coord.append(feature.z[i])
        t_coord = tuple(l_coord)
        coordinates_xyz.append(t_coord)
    feature_coord_xyz = []
    
    # Dividing coordinates based on polygon parts (outer ring and inner rings)
    for i in range(len(feature.parts)):
        if not i == (len(feature.parts)-1):
            part_coord_xyz = coordinates_xyz[feature.parts[i]:feature.parts[i+1]]
            feature_coord_xyz.append(part_coord_xyz)
        else:
            part_coord_xyz = coordinates_xyz[feature.parts[i]:]
            feature_coord_xyz.append(part_coord_xyz)
            
    if attribute[0] != 2 and attribute[0] != 5 and attribute[0] != 4:
        # Turning CW to CCW and vice versa (CCW for outer ring and CW for inner ring)
        # CW => sf.signed_area < 0, CCW => sf.signed_area >= 0
        for i in range(len(feature_coord_xyz)):
            if (i == 0) and (sf.signed_area(feature_coord_xy[i]) < 0):
                feature_coord_xyz[i].reverse()
            elif (i != 0) and (sf.signed_area(feature_coord_xy[i]) >= 0):
                feature_coord_xyz[i].reverse()
                
    elif attribute[0] == 4:
        # Turning CW to CCW and vice versa (CCW for outer ring and CW for inner ring)
        # CW => sf.signed_area < 0, CCW => sf.signed_area >= 0
        for i in range(len(feature_coord_xyz)):
            if (i == 0) and (sf.signed_area(feature_coord_xy[i]) >= 0):
                feature_coord_xyz[i].reverse()
            elif (i != 0) and (sf.signed_area(feature_coord_xy[i]) < 0):
                feature_coord_xyz[i].reverse()
            
    output.append(feature_coord_xyz)

# Defining a function for creating GroundSurface based on roof base
def ground_surf(roof_base, ground_surface, elevation):
    coordinate = []
    for i in range(len(roof_base.points)):
        l_coord = list(roof_base.points[i])
        l_coord.append(elevation)
        t_coord = tuple(l_coord)
        coordinate.append(t_coord)
    
    # GroundSurface orientation correction, GroundSurface have to be clockwise
    if sf.signed_area(roof_base.points) >= 0:
        coordinate.reverse()
    
    ground_surface.append(coordinate)

# Defining a function for creating WallSurfaces
def wall_surf(roof_base, wall_surfaces, elevation):
	
    # Roof base vertex order correction to give the extruded WallSurface the correct orientation
    if sf.signed_area(roof_base.points) >= 0:
        roof_base.points.reverse()
        roof_base.z.reverse()
    
    for i in range(len(roof_base.points)-1):
        coord1 = list(roof_base.points[i])
        coord1.append(roof_base.z[i])
        coord2 = list(roof_base.points[i+1])
        coord2.append(roof_base.z[i+1])
        coord3 = [coord2[0], coord2[1], elevation]
        coord4 = [coord1[0], coord1[1], elevation]
        surface = [tuple(coord1), tuple(coord2), tuple(coord3), tuple(coord4), tuple(coord1)]
    
        wall_surfaces.append(surface)

# Creating a function for extracting building ground elevation
def calculate_elevation(roof_base, dataset, elevation_band):
    elevations = []

    for i in range(len(roof_base.points)-1):
        x, y = roof_base.points[i]
        row, col = dataset.index(x, y)
        elevations.append(elevation_band[row, col])
    elevation = min(elevations)

    return elevation

# Defining a function for extracting and creating surfaces for a building
def extract_geometry(features, attributes, output):
    
    # Creating surface variables
    ground_surface = []
    wall_surfaces = []
    roof_surfaces = []
    ofloor_surfaces = []
    oceil_surfaces = []
    close_surfaces = []
    
    # Iterating over features
    for i in range(len(features)):
        if attributes[i][0] == 1:
            if len(features[i].parts) > 1:
                adding_z_multi(features[i], roof_surfaces, attributes[i])
            else:
                adding_z(features[i], roof_surfaces, attributes[i])
        elif attributes[i][0] == 2:
            if len(features[i].parts) > 1:
                adding_z_multi(features[i], wall_surfaces, attributes[i])
            else:
                adding_z(features[i], wall_surfaces, attributes[i])
        elif attributes[i][0] == 3:
            if len(features[i].parts) > 1:
                adding_z_multi(features[i], ofloor_surfaces, attributes[i])
            else:
                adding_z(features[i], ofloor_surfaces, attributes[i])
        elif attributes[i][0] == 4:
            if len(features[i].parts) > 1:
                adding_z_multi(features[i], oceil_surfaces, attributes[i])
            else:
                adding_z(features[i], oceil_surfaces, attributes[i])
        elif attributes[i][0] == 5:
            if len(features[i].parts) > 1:
                adding_z_multi(features[i], close_surfaces, attributes[i])
            else:
                adding_z(features[i], close_surfaces, attributes[i])
        elif attributes[i][0] == 10:
            elevation = calculate_elevation(features[i], dataset, ground_elevation)
            wall_surf(features[i], wall_surfaces, elevation)
            ground_surf(features[i], ground_surface, elevation)
        elif attributes[i][0] == 11:
            elevation = calculate_elevation(features[i], dataset, ground_elevation)
            wall_surf(features[i], close_surfaces, elevation)
            ground_surf(features[i], ground_surface, elevation)
        else:
            pass
        
    # Defining a function for adding surfaces to the building geometry dictionary
    surfaces_dict = {}
    def add_surfaces(surfaces, dictionary, surface_name):
        if len(surfaces) > 0:
            dictionary[surface_name] = surfaces
        else:
            pass
    
    # Adding surfaces to the building geometry dictionary
    add_surfaces(ground_surface, surfaces_dict, 'Ground')
    add_surfaces(wall_surfaces, surfaces_dict, 'Wall')
    add_surfaces(roof_surfaces, surfaces_dict, 'Roof')
    add_surfaces(ofloor_surfaces, surfaces_dict, 'OuterFloor')
    add_surfaces(oceil_surfaces, surfaces_dict, 'OuterCeiling')
    add_surfaces(close_surfaces, surfaces_dict, 'Closure')
       
    # Adding building geometry dictionary to the output geometry dictionary
    output[attributes[0][1]] = surfaces_dict

# Extracting and creating buildings surfaces and save it to the output geometry dictionary
for i in range(len(bldg_id_unique)):
    extract_geometry(bldg_features[i], bldg_attributes[i], out_geometry)

# Changing dictionary to list for easier fetching and iterating through data
building_geometry = list(out_geometry.items())

# Defining CityGML namespaces
ns_base = "http://www.citygml.org/citygml/profiles/base/2.0"
ns_core = "http://www.opengis.net/citygml/2.0"
ns_bldg = "http://www.opengis.net/citygml/building/2.0"
ns_gen = "http://www.opengis.net/citygml/generics/2.0"
ns_gml = "http://www.opengis.net/gml"
ns_xAL = "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0"
ns_xlink = "http://www.w3.org/1999/xlink"
ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"
ns_schemaLocation = "http://www.citygml.org/citygml/profiles/base/2.0 http://schemas.opengis.net/citygml/profiles/base/2.0/CityGML.xsd"

nsmap = {None : ns_base, 'core': ns_core, 'bldg': ns_bldg, 'gen': ns_gen, 'gml': ns_gml, 'xAL': ns_xAL, 'xlink': ns_xlink, 'xsi': ns_xsi}

# Creating CityGML root element (CityModel)
CityModel = etree.Element("{%s}CityModel" % ns_core, nsmap=nsmap)
CityModel.set('{%s}schemaLocation' % ns_xsi, ns_schemaLocation)

# Writing a description
description = etree.SubElement(CityModel, '{%s}description' % ns_gml)
description.text = 'ITB Ganesha LOD 2 Buildings'

# Defining a function to extract bounding box for a building
def bounding_box(bldg_feat_dict):
    coorX = []
    coorY = []
    coorZ = []
    for key in bldg_feat_dict.keys():
        for i in range(len(bldg_feat_dict[key])):
            for n in range(len(bldg_feat_dict[key][i])):
                coordinate = bldg_feat_dict[key][i][n]
                if type(coordinate) == tuple:
                    coorX.append(coordinate[0])
                    coorY.append(coordinate[1])
                    coorZ.append(coordinate[2])
                elif type(coordinate) == list:
                    for m in range(len(coordinate)):
                        coorX.append(coordinate[m][0])
                        coorY.append(coordinate[m][1])
                        coorZ.append(coordinate[m][2])
    lowerCorner = [min(coorX), min(coorY), min(coorZ)]
    upperCorner = [max(coorX), max(coorY), max(coorZ)]
    return lowerCorner, upperCorner

def writing_surface(surface_geometry, surface_element_name):
    for n in range(len(surface_geometry)):
        
        # if feature is not multipart
        if type(surface_geometry[n][0]) == tuple:
            surf_uuid = 'UUID_' + str(uuid.uuid4()) + '_2'
            boundedBy = etree.SubElement(Building, '{%s}boundedBy' % ns_bldg)
            Surface = etree.SubElement(boundedBy, surface_element_name % ns_bldg)
            Surface.set('{%s}id' % ns_gml, surf_uuid)
            lod2MultiSurface = etree.SubElement(Surface, '{%s}lod2MultiSurface' % ns_bldg)
            MultiSurface = etree.SubElement(lod2MultiSurface, '{%s}MultiSurface' % ns_gml)
            surfaceMember = etree.SubElement(MultiSurface, '{%s}surfaceMember' % ns_gml)
            Polygon = etree.SubElement(surfaceMember, '{%s}Polygon' % ns_gml)
            Polygon.set('{%s}id' % ns_gml, surf_uuid + '_poly')
            exterior = etree.SubElement(Polygon, '{%s}exterior' % ns_gml)
            LinearRing = etree.SubElement(exterior, '{%s}LinearRing' % ns_gml)
            posList = etree.SubElement(LinearRing, '{%s}posList' % ns_gml, srsDimension='3')
            coordinates = ''
            copy = ''

            for m in range(len(surface_geometry[n])):
                coordinates = copy + str(surface_geometry[n][m][0]) + ' ' + str(surface_geometry[n][m][1]) + ' ' + str(surface_geometry[n][m][2]) + ' '
                copy = coordinates
            posList.text = coordinates[:-1]
            solid_link = etree.SubElement(CompositeSurface, '{%s}surfaceMember' % ns_gml)
            solid_link.set('{%s}href' % ns_xlink, '#' + surf_uuid + '_poly')
                    
        # if feature is multipart
        elif type(surface_geometry[n][0]) == list:
            surf_uuid = 'UUID_' + str(uuid.uuid4()) + '_2'
            boundedBy = etree.SubElement(Building, '{%s}boundedBy' % ns_bldg)
            Surface = etree.SubElement(boundedBy, surface_element_name % ns_bldg)
            Surface.set('{%s}id' % ns_gml, surf_uuid)
            lod2MultiSurface = etree.SubElement(Surface, '{%s}lod2MultiSurface' % ns_bldg)
            MultiSurface = etree.SubElement(lod2MultiSurface, '{%s}MultiSurface' % ns_gml)
            surfaceMember = etree.SubElement(MultiSurface, '{%s}surfaceMember' % ns_gml)
            Polygon = etree.SubElement(surfaceMember, '{%s}Polygon' % ns_gml)
            Polygon.set('{%s}id' % ns_gml, surf_uuid + '_poly')

            for m in range(len(surface_geometry[n])):
                if m == 0:
                    exterior = etree.SubElement(Polygon, '{%s}exterior' % ns_gml)
                    LinearRing = etree.SubElement(exterior, '{%s}LinearRing' % ns_gml)
                    posList = etree.SubElement(LinearRing, '{%s}posList' % ns_gml, srsDimension='3')
                    coordinates = ''
                    copy = ''

                    for l in range(len(surface_geometry[n][m])):
                        coordinates = copy + str(surface_geometry[n][m][l][0]) + ' ' + str(surface_geometry[n][m][l][1]) + ' ' + str(surface_geometry[n][m][l][2]) + ' '
                        copy = coordinates
                    posList.text = coordinates[:-1]

                else:
                    interior = etree.SubElement(Polygon, '{%s}interior' % ns_gml)
                    LinearRing = etree.SubElement(interior, '{%s}LinearRing' % ns_gml)
                    posList = etree.SubElement(LinearRing, '{%s}posList' % ns_gml, srsDimension='3')
                    coordinates = ''
                    copy = ''

                    for l in range(len(surface_geometry[n][m])):
                        coordinates = copy + str(surface_geometry[n][m][l][0]) + ' ' + str(surface_geometry[n][m][l][1]) + ' ' + str(surface_geometry[n][m][l][2]) + ' '
                        copy = coordinates
                    posList.text = coordinates[:-1]

            solid_link = etree.SubElement(CompositeSurface, '{%s}surfaceMember' % ns_gml)
            solid_link.set('{%s}href' % ns_xlink, '#' + surf_uuid + '_poly')

# Iterating writing to CityGML for every building
for bldg_id in out_geometry.keys():
    crs = 'EPSG:25833'
    cityObjectMember = etree.SubElement(CityModel, '{%s}cityObjectMember' % ns_core)
    
    Building = etree.SubElement(cityObjectMember, '{%s}Building' % ns_bldg)
    Building.set('{%s}id' % ns_gml, 'ID_' + str(bldg_id))
    
    BoundingBox = etree.SubElement(Building, '{%s}boundedBy' % ns_gml)
    Envelope = etree.SubElement(BoundingBox, '{%s}Envelope' % ns_gml, srsDimension='3')
    Envelope.set('srsName', crs)
    
    lower, upper = bounding_box(out_geometry[bldg_id])
    lowCorner = etree.SubElement(Envelope, '{%s}lowerCorner' % ns_gml)
    lowCorner.text = str(lower[0]) + ' ' + str(lower[1]) + ' ' + str(lower[2])
    uppCorner = etree.SubElement(Envelope, '{%s}upperCorner' % ns_gml)
    uppCorner.text = str(upper[0]) + ' ' + str(upper[1]) + ' ' + str(upper[2])
    
    lod2Solid = etree.SubElement(Building, '{%s}lod2Solid' % ns_bldg)
    Solid = etree.SubElement(lod2Solid, '{%s}Solid' % ns_gml)
    exterior = etree.SubElement(Solid, '{%s}exterior' % ns_gml)
    CompositeSurface = etree.SubElement(exterior, '{%s}CompositeSurface' % ns_gml)
    
    building_geometry = list(out_geometry[bldg_id].items())
    
    Ground = '{%s}GroundSurface'
    Wall = '{%s}WallSurface'
    Roof = '{%s}RoofSurface'
    OuterFloor = '{%s}OuterFloorSurface'
    OuterCeiling = '{%s}OuterCeilingSurface'
    Closure = '{%s}ClosureSurface'
    
    for i in range(len(building_geometry)):
        if building_geometry[i][0] == 'Ground':
            writing_surface(building_geometry[i][1], Ground)

        elif building_geometry[i][0] == 'Wall':
            writing_surface(building_geometry[i][1], Wall)
            
        elif building_geometry[i][0] == 'Roof':
            writing_surface(building_geometry[i][1], Roof)

        elif building_geometry[i][0] == 'OuterFloor':
            writing_surface(building_geometry[i][1], OuterFloor)
            
        elif building_geometry[i][0] == 'OuterCeiling':
            writing_surface(building_geometry[i][1], OuterCeiling)
                    
        elif building_geometry[i][0] == 'Closure':
            writing_surface(building_geometry[i][1], Closure)

output_dir = str(input('Input your output directory and file name (example: C:/Users/.../LoD2Building.gml):\n'))
etree.ElementTree(CityModel).write(output_dir, xml_declaration=True, encoding='utf-8', pretty_print= True)