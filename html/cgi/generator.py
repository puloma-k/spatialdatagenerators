#!/usr/local/bin/python3
from abc import ABC, abstractmethod
import math
import os
import random as rand
import sys
from urllib import parse
import bz2
import numpy as np
from math import log
from dataclasses import dataclass

class Generator(ABC):

    def __init__(self, card, geo, dim, dist, output_format, strm, affineMatrix):
        self.card = card
        self.geo = geo
        self.dim = dim
        self.dist = dist
        self.output_format = output_format
        self.strm = strm
        self.compressor = None
        self.affineMatrix = affineMatrix

    def bernoulli(self, p):
        return 1 if rand.random() < p else 0

    def normal(self, mu, sigma):
        return mu + sigma * math.sqrt(-2 * math.log(rand.random())) * math.sin(2 * math.pi * rand.random())

    def is_valid_point(self, point):
        for x in point.coordinates:
            if not (0 <= x <= 1):
                return False
        return True

    @abstractmethod
    def generate(self):
        pass
    
    def write_out(self, data_str):
        data_bytes = bytes(data_str, 'utf-8')
        if(self.compressor):
            data_bytes = self.compressor.compress(data_bytes)
        sys.stdout.buffer.write(data_bytes)
        
    def affineTransformArray(self, coordinates):
        coordinateArr = [];
        for a in coordinates:
            coordinateArr.append([a])
        coordinateArr.append([1])
        dataMatrix = np.array(coordinateArr)
        transformedData = np.matmul(self.affineMatrix, dataMatrix)
         
        newCoordinates = []
        for a in range(2):
            newCoordinates.append(transformedData[a][0])
        return newCoordinates
    

class PointGenerator(Generator):

    def __init__(self, card, geo, dim, dist, output_format, strm, affineMatrix):
        super(PointGenerator, self).__init__(card, geo, dim, dist, output_format, strm, affineMatrix)

    def generate(self):
        pass

    # Used for all generator types, except for parcel generator, which handles output differently
    # See parcel generator for more details
    def generate_and_write(self):        
        prev_point = None
        i = 0
        
        if self.strm == "cfile":
            self.compressor = bz2.BZ2Compressor()
            
        if self.output_format == "gjson":
            self.write_out('{"type": "FeatureCollection", "features": [')
        if self.output_format == "wkt":
            self.write_out('MULTIPOINT (')
            
        while i < self.card:
            point = self.generate_point(i, prev_point)
            
            if(self.affineMatrix is not None):
                point.coordinates = self.affineTransformArray(point.coordinates)
    
            if self.is_valid_point(point):
                prev_point = point
                data = prev_point.to_string(self.output_format) + '\n'
                self.write_out(data)
                i = i + 1
                if self.output_format == "gjson" and i < self.card:
                    self.write_out(',')
                if self.output_format == "wkt" and i < self.card:
                    self.write_out(',')
            
        if self.output_format == "gjson":
            self.write_out(']}') 
        if self.output_format == "wkt":
            self.write_out(')')  
         
        if self.strm == "cfile":       
            data = self.compressor.flush() # Get the last bits of data remaining in the compressor
            sys.stdout.buffer.write(data)
        
    @abstractmethod
    def generate_point(self, i, prev_point):
        pass
    

class UniformGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output_format, strm, affineMatrix):
        super(UniformGenerator, self).__init__(card, geo, dim, dist, output_format, strm, affineMatrix)

    def generate_point(self, i, prev_point):
        coordinates = [rand.random() for d in range(self.dim)]
        return Point(coordinates)


class DiagonalGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output_format, strm, affineMatrix, percentage, buffer):
        super(DiagonalGenerator, self).__init__(card, geo, dim, dist, output_format, strm, affineMatrix)
        self.percentage = percentage
        self.buffer = buffer

    def generate_point(self, i, prev_point):
        if self.bernoulli(self.percentage) == 1:
            coordinates = [rand.random()] * self.dim
        else:
            c = rand.random()
            d = self.normal(0, self.buffer / 5)

            coordinates = [(c + (1 - 2 * (x % 2)) * d / math.sqrt(2)) for x in range(self.dim)]
        return Point(coordinates)


class GaussianGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output_format, strm, affineMatrix):
        super(GaussianGenerator, self).__init__(card, geo, dim, dist, output_format, strm, affineMatrix)

    def generate_point(self, i, prev_point):
        coordinates = [self.normal(0.5, 0.1) for d in range(self.dim)]
        return Point(coordinates)


class SierpinskiGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output_format, strm, affineMatrix):
        super(SierpinskiGenerator, self).__init__(card, geo, dim, dist, output_format, strm, affineMatrix)

    def generate_point(self, i, prev_point):
        if i == 0:
            return Point([0.0, 0.0])
        elif i == 1:
            return Point([1.0, 0.0])
        elif i == 2:
            return Point([0.5, math.sqrt(3) / 2])
        else:
            d = self.dice(5)

            if d == 1 or d == 2:
                return self.get_middle_point(prev_point, Point([0.0, 0.0]))
            elif d == 3 or d == 4:
                return self.get_middle_point(prev_point, Point([1.0, 0.0]))
            else:
                return self.get_middle_point(prev_point, Point([0.5, math.sqrt(3) / 2]))

    def dice(self, n):
        return math.floor(rand.random() * n) + 1

    def get_middle_point(self, point1, point2):
        middle_point_coords = []
        for i in range(len(point1.coordinates)):
            middle_point_coords.append((point1.coordinates[i] + point2.coordinates[i]) / 2)
        return Point(middle_point_coords)


class BitGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output_format, strm, affineMatrix, prob, digits):
        super(BitGenerator, self).__init__(card, geo, dim, dist, output_format, strm, affineMatrix)
        self.prob = prob
        self.digits = digits

    def generate_point(self, i, prev_point):
        coordinates = [self.bit() for d in range(self.dim)]
        return Point(coordinates)

    def bit(self):
        num = 0.0
        for i in range(1, self.digits + 1):
            c = self.bernoulli(self.prob)
            num = num + c / (math.pow(2, i))
        return num
 

class ParcelGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output_format, strm, affineMatrix, split_range, dither):
        super(ParcelGenerator, self).__init__(card, geo, dim, dist, output_format, strm, affineMatrix)
        self.split_range = split_range
        self.dither = dither
        
    def applyTransformation(self, b):
        lowerLeft = [b.box_field.x, b.box_field.y]
        upperRight = [b.box_field.x + b.box_field.w, b.box_field.y + b.box_field.h]
        lowerLeft = self.affineTransformArray(lowerLeft)
        upperRight = self.affineTransformArray(upperRight)
        
        b.box_field.x = lowerLeft[0]
        b.box_field.y = lowerLeft[1]
        b.box_field.w = upperRight[0] - lowerLeft[0]
        b.box_field.h = upperRight[1] - lowerLeft[1]
        

    def generate_and_write(self):
        # Tried gzip and underlying zlib, neither has a bug-free implementation in Python
        # bz2 is the only real option
        if(self.strm == "cfile"):               
            self.compressor = bz2.BZ2Compressor()
            
        # Using dataclass to create BoxWithDepth, which stores depth of each box in the tree
        # Depth is used to determine at which level to stop splitting and start printing    
        box = BoxWithDepth(Box(0.0, 0.0, 1.0, 1.0), 0)
        boxes = [] # Empty stack for depth-first generation of boxes
        boxes.append(box)
        
        max_height = math.ceil(log(self.card, 2))
        
        # We will print some boxes at last level and the remaining at the second to last level 
        # Number of boxes to split on the second to last level
        numToSplit = self.card - pow(2, max(max_height - 1, 0))
        numSplit = 0
        boxes_generated = 0
        
        if self.output_format == "gjson":
            self.write_out('{"type": "FeatureCollection", "features": [{ "type": "Feature", "geometry": { "type": "MultiPolygon", "coordinates": [')
        if self.output_format == "wkt":
            self.write_out('MULTIPOLYGON (')

        while boxes_generated < self.card:
            b = boxes.pop()
            
            if b.depth >= max_height - 1:
                if numSplit < numToSplit: # Split at second to last level and print the new boxes
                    b1, b2 = self.split(b, boxes)
                    numSplit += 1
                    self.dither_and_print(b1)
                    if self.output_format == "gjson" or self.output_format == "wkt":
                        self.write_out(',')
                    self.dither_and_print(b2)
                    boxes_generated += 2
                    if (self.output_format == "gjson" or self.output_format == "wkt") and boxes_generated < self.card:
                        self.write_out(',')
                else: # Print remaining boxes from the second to last level 
                    self.dither_and_print(b)
                    boxes_generated += 1
                    if (self.output_format == "gjson" or self.output_format == "wkt") and boxes_generated < self.card:
                        self.write_out(',')
                    if boxes_generated == 10: # Early flush to ensure immediate download of data
                        sys.stdout.buffer.flush()
  
            else:
                b1, b2 = self.split(b, boxes)
                boxes.append(b2)
                boxes.append(b1)
                
        if self.output_format == "gjson":
            self.write_out(']}, "properties": null }]}')
        if self.output_format == "wkt":
            self.write_out(')')
                
        if self.strm == "cfile":       
            data = bz2_compressor.flush() # Get the last bits of data remaining in the compressor
            sys.stdout.buffer.write(data)
            
    def split(self, b, boxes):
        if b.box_field.w > b.box_field.h:
            # Split vertically if width is bigger than height
            # Tried numpy random number generator, found to be twice as slow as the Python default generator
            split_size = b.box_field.w * rand.uniform(self.split_range, 1 - self.split_range)
            b1 = BoxWithDepth(Box(b.box_field.x, b.box_field.y, split_size, b.box_field.h), b.depth+1)
            b2 = BoxWithDepth(Box(b.box_field.x + split_size, b.box_field.y, b.box_field.w - split_size, b.box_field.h), b.depth+1)
        else:
            # Split horizontally if width is less than height
            split_size = b.box_field.h * rand.uniform(self.split_range, 1 - self.split_range)
            b1 = BoxWithDepth(Box(b.box_field.x, b.box_field.y, b.box_field.w, split_size), b.depth+1)
            b2 = BoxWithDepth(Box(b.box_field.x, b.box_field.y + split_size, b.box_field.w, b.box_field.h - split_size), b.depth+1) 
        return b1, b2
    
    def dither_and_print(self, b):
        b.box_field.w = b.box_field.w * (1.0 - rand.uniform(0.0, self.dither))
        b.box_field.h = b.box_field.h * (1.0 - rand.uniform(0.0, self.dither))
        
        if(self.affineMatrix is not None):
            self.applyTransformation(b)
            
        data = b.box_field.to_string(self.output_format) + '\n'
        self.write_out(data)
        
    def generate_point(self, i, prev_point):
        PointGenerator.generate_point(self, i, prev_point)
            

class Geometry(ABC):

    def to_string(self, output_format):
        if output_format == 'csv':
            return self.to_csv_string()
        elif output_format == 'wkt':
            return self.to_wkt_string()
        elif output_format == 'gjson':
            return self.to_gjson_string()
        else:
            print('Please check the output format.')
            sys.exit()

    @abstractmethod
    def to_csv_string(self):
        pass

    @abstractmethod
    def to_wkt_string(self):
        pass
    
    @abstractmethod
    def to_gjson_string(self):
        pass


class Point(Geometry):

    def __init__(self, coordinates):
        self.coordinates = coordinates

    def to_csv_string(self):
        return ','.join(str(x) for x in self.coordinates)

    def to_wkt_string(self):
        return '({0})'.format(' '.join(str(x) for x in self.coordinates))
#         return 'POINT ({0})'.format(' '.join(str(x) for x in self.coordinates))
    
    def to_gjson_string(self):    
        json_str = '{"type": "Feature", "geometry": { "type": "Point", "coordinates": ['
        i = 1
        num_dim = len(self.coordinates)
        for x in self.coordinates:
            json_str += str(x)
            if i != num_dim:
                json_str += ','
            i += 1
        return json_str + ']}, "properties": null}'
        

class Box(Geometry):

    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def to_csv_string(self):
        return '{},{},{},{}'.format(self.x, self.y, self.x + self.w, self.y + self.h)

    def to_wkt_string(self):
        x1, y1, x2, y2 = self.x, self.y, self.x + self.w, self.y + self.h
        return '(({} {}, {} {}, {} {}, {} {}, {} {}))'.format(x1, y1, x2, y1, x2, y2, x1, y2, x1, y1)
#         return 'POLYGON (({} {}, {} {}, {} {}, {} {}, {} {}))'.format(x1, y1, x2, y1, x2, y2, x1, y2, x1, y1)
    
    def to_gjson_string(self):
        x1, y1, x2, y2 = self.x, self.y, self.x + self.w, self.y + self.h
#         json_str = '{"type": "Feature", "geometry": { "type": "Polygon", "coordinates": ['
        json_str = '[[[{}, {}], [{}, {}], [{}, {}], [{}, {}], [{}, {}]]]'.format(x1, y1, x2, y1, x2, y2, x1, y2, x1, y1)
#         json_str += ']}, "properties": null}'
        return json_str
    
    
@dataclass
class BoxWithDepth:
    box_field: Box
    depth: int
    
def sendErrorToBrowser(message):
    sys.stdout.buffer.write(bytes("Content-type:text/html;charset=utf-8\r\n\r\n", 'utf-8'))
    sys.stdout.buffer.write(bytes('\r\n', 'utf-8'))
    sys.stdout.buffer.write(bytes(message, 'utf-8'))
    sys.stderr.write(message)

def main():
    url = os.environ["REQUEST_URI"]
    # Enable following url to debug without web server
#     url = "http://localhost/cgi/generator.py?dist=uniform&dim=2&card=100&fmt=wkt&per=0.5&buf=0.5&prob=0.5&dig=2&sran=0.5&dith=0.5&geo=point&strm=browser&seed=1596950671543&"

    pDict = dict(parse.parse_qsl(parse.urlparse(url).query, keep_blank_values=True)) # Parse url to get parameter values in pDict
    
    if pDict['seed']:
        rand.seed(int(pDict['seed']))

    try:
        card, geo, dim, dist, output_format, strm = int(pDict['card']), pDict['geo'], int(pDict['dim']), pDict['dist'], pDict['fmt'], pDict['strm']
    except (BaseException, Exception, ArithmeticError, BufferError, LookupError):
        sendErrorToBrowser("Please check your arguments")
        sys.exit(1)
        
    # if one affine transformation parameter exists, then all should exist
    if (pDict.get('a1') or pDict.get('a2') or pDict.get('a3') or pDict.get('a4') or pDict.get('a5') or pDict.get('a6')):
        if (not pDict.get('a1') or not pDict.get('a2') or not pDict.get('a3') or not pDict.get('a4') or not pDict.get('a5') or not pDict.get('a6')):
            sendErrorToBrowser("Enter all parameters for transformation")
            sys.exit(1)
            
    if pDict.get('a1'):
        a1 = float(pDict['a1'])
        a2 = float(pDict['a2'])
        a3 = float(pDict['a3'])
        a4 = float(pDict['a4'])
        a5 = float(pDict['a5'])
        a6 = float(pDict['a6'])
        affineMatrix = np.array([[a1, a2, a3], [a4, a5, a6], [0, 0, 1]])
    else:
        affineMatrix = None

    if dist == 'uniform':
        generator = UniformGenerator(card, geo, dim, dist, output_format, strm, affineMatrix)

    elif dist == 'diagonal':
        percentage, buffer = float(pDict['per']), float(pDict['buf'])
        generator = DiagonalGenerator(card, geo, dim, dist, output_format, strm, affineMatrix, percentage, buffer)

    elif dist == 'gaussian':
        generator = GaussianGenerator(card, geo, dim, dist, output_format, strm, affineMatrix)

    elif dist == 'sierpinski':
        if dim != 2:
            sendErrorToBrowser('Currently we only support 2 dimensions for Sierpinski distribution')
            sys.exit(1)

        generator = SierpinskiGenerator(card, geo, dim, dist, output_format, strm, affineMatrix)

    elif dist == 'bit':
        prob, digits = float(pDict['prob']), int(pDict['dig'])
        generator = BitGenerator(card, geo, dim, dist, output_format, strm, affineMatrix, prob, digits)

    elif dist == 'parcel':
        if dim != 2:
            sendErrorToBrowser('Currently we only support 2 dimensions for Parcel distribution')
            sys.exit(1)

        split_range, dither = float(pDict['sran']), float(pDict['dith'])
        generator = ParcelGenerator(card, geo, dim, dist, output_format, strm, affineMatrix, split_range, dither)

    else:
        sendErrorToBrowser('Please check the distribution type.')
        sys.exit(1)
        
    # Sets default download filename in save file dialog box in browser    
    remote_file_name = "dat" + str(rand.randint(0,1000000)) + "." + output_format + ".bz2"
    
    if strm == "cfile": # Cfile indicates compressed data download
        sys.stdout.buffer.write(bytes("Content-type:application/x-bzip2" + '\r\n', 'utf-8'))
        sys.stdout.buffer.write(bytes("Content-Disposition: attachment; filename=\"" + remote_file_name + "\"" + '\r\n', 'utf-8'))      
    else:
        sys.stdout.buffer.write(bytes("Content-type:text/html;charset=utf-8\r\n\r\n", 'utf-8'))
    sys.stdout.buffer.write(bytes('\r\n', 'utf-8'))
    
#     if strm != "cfile":
#         sys.stdout.buffer.write(bytes("<pre>", 'utf-8'))
    
    generator.generate_and_write()
    
#     if strm != "cfile":
#         sys.stdout.buffer.write(bytes("</pre>", 'utf-8'))

if __name__ == "__main__":
    main()
