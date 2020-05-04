#!/usr/local/bin/python3
from abc import ABC, abstractmethod
import math
from optparse import OptionParser
import os
import queue
import random as rand
import sys
from urllib import parse
import bz2
from math import log
from dataclasses import dataclass

class Generator(ABC):

    def __init__(self, card, geo, dim, dist, output_format, strm):
        self.card = card
        self.geo = geo
        self.dim = dim
        self.dist = dist
        self.output_format = output_format
        self.strm = strm

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


class PointGenerator(Generator):

    def __init__(self, card, geo, dim, dist, output_format, strm):
        super(PointGenerator, self).__init__(card, geo, dim, dist, output_format, strm)

    def generate(self):
        pass

    def generate_and_write(self):         
        prev_point = None
        i = 0
        
        if self.strm == "cfile":
            bz2_file = bz2.BZ2Compressor()
            
        while i < self.card:
            point = self.generate_point(i, prev_point)
            if self.is_valid_point(point):
                prev_point = point
                data = bytes(prev_point.to_string(self.output_format) + '\n', 'utf-8')
                if self.strm == "cfile":
                    data = bz2_file.compress(data)
                sys.stdout.buffer.write(data)
                i = i + 1
        if self.strm == "cfile":       
            data = bz2_file.flush()
            sys.stdout.buffer.write(data)

        
    @abstractmethod
    def generate_point(self, i, prev_point):
        pass


class UniformGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output_format, strm):
        super(UniformGenerator, self).__init__(card, geo, dim, dist, output_format, strm)

    def generate_point(self, i, prev_point):
        coordinates = [rand.random() for d in range(self.dim)]
        return Point(coordinates)


class DiagonalGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output_format, strm, percentage, buffer):
        super(DiagonalGenerator, self).__init__(card, geo, dim, dist, output_format, strm)
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

    def __init__(self, card, geo, dim, dist, output_format, strm):
        super(GaussianGenerator, self).__init__(card, geo, dim, dist, output_format, strm)

    def generate_point(self, i, prev_point):
        coordinates = [self.normal(0.5, 0.1) for d in range(self.dim)]
        return Point(coordinates)


class SierpinskiGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output_format, strm):
        super(SierpinskiGenerator, self).__init__(card, geo, dim, dist, output_format, strm)

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

    def __init__(self, card, geo, dim, dist, output_format, strm, prob, digits):
        super(BitGenerator, self).__init__(card, geo, dim, dist, output_format, strm)
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

    def __init__(self, card, geo, dim, dist, output_format, strm, split_range, dither):
        super(ParcelGenerator, self).__init__(card, geo, dim, dist, output_format, strm)
        self.split_range = split_range
        self.dither = dither

    def generate_and_write(self):               
        if self.strm == "cfile":
            bz2_file = bz2.BZ2Compressor()
            
        box = BoxWithDepth(Box(0.0, 0.0, 1.0, 1.0), 0)
        boxes = []
        boxes.append(box)
        
        max_height = math.ceil(log(self.card, 2))
        numToSplit = self.card - pow(2, max(max_height - 1, 0))
        numSplit = 0
        boxes_generated = 0

        while boxes_generated < self.card:
            # Pop from the stack to get a box
            b = boxes.pop()
            
            if b.depth >= max_height - 1:
                if numSplit < numToSplit:
                    self.split(b, boxes)
                    numSplit += 1
                else:
                    self.dither_and_print(b, bz2_file)
                    boxes_generated += 1
            else:
                self.split(b, boxes)
                
        if self.strm == "cfile":       
            data = bz2_file.flush()
            sys.stdout.buffer.write(data)

    def split(self, b, boxes):
        if b.box_field.w > b.box_field.h:
            # Split vertically if width is bigger than height
            split_size = b.box_field.w * rand.uniform(self.split_range, 1 - self.split_range)
            b1 = BoxWithDepth(Box(b.box_field.x, b.box_field.y, split_size, b.box_field.h), b.depth+1)
            b2 = BoxWithDepth(Box(b.box_field.x + split_size, b.box_field.y, b.box_field.w - split_size, b.box_field.h), b.depth+1)
        else:
            # Split horizontally if width is less than height
            split_size = b.box_field.h * rand.uniform(self.split_range, 1 - self.split_range)
            b1 = BoxWithDepth(Box(b.box_field.x, b.box_field.y, b.box_field.w, split_size), b.depth+1)
            b2 = BoxWithDepth(Box(b.box_field.x, b.box_field.y + split_size, b.box_field.w, b.box_field.h - split_size), b.depth+1) 
        boxes.append(b2)
        boxes.append(b1)
    
    def dither_and_print(self, b, bz2_file):
        b.box_field.w = b.box_field.w * (1.0 - rand.uniform(0.0, self.dither))
        b.box_field.h = b.box_field.h * (1.0 - rand.uniform(0.0, self.dither))
        
        data = bytes(b.box_field.to_string(self.output_format) + '\n', 'utf-8')
        if self.strm == "cfile":
            data = bz2_file.compress(data)
        
        sys.stdout.buffer.write(data)

        
    def generate_point(self, i, prev_point):
        PointGenerator.generate_point(self, i, prev_point)
            

class Geometry(ABC):

    def to_string(self, output_format):
        if output_format == 'csv':
            return self.to_csv_string()
        elif output_format == 'wkt':
            return self.to_wkt_string()
        else:
            print('Please check the output format.')
            sys.exit()

    @abstractmethod
    def to_csv_string(self):
        pass

    @abstractmethod
    def to_wkt_string(self):
        pass


class Point(Geometry):

    def __init__(self, coordinates):
        self.coordinates = coordinates

    def to_csv_string(self):
        return ','.join(str(x) for x in self.coordinates)

    def to_wkt_string(self):
        return 'POINT ({0})'.format(' '.join(str(x) for x in self.coordinates))


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
        return 'POLYGON (({} {}, {} {}, {} {}, {} {}, {} {}))'.format(x1, y1, x2, y1, x2, y2, x1, y2, x1, y1)
    
@dataclass
class BoxWithDepth:
    box_field: Box
    depth: int

def main():
    """
    Generate a list of geometries and write the list to file
    :return:
    """
    
    url = os.environ["REQUEST_URI"]
#     url = "http://localhost/cgi/generator.py?dist=parcel&card=10&geo=box&dim=2&fmt=wkt&dith=0&sran=0.5&strm=cfile"

    pDict = dict(parse.parse_qsl(parse.urlparse(url).query))

    try:
        card, geo, dim, dist, output_format, strm = int(pDict['card']), pDict['geo'], int(pDict['dim']), pDict['dist'], pDict['fmt'], pDict['strm']
    except RuntimeError:
        print('Please check your arguments')

    if dist == 'uniform':
        generator = UniformGenerator(card, geo, dim, dist, output_format, strm)

    elif dist == 'diagonal':
        percentage, buffer = float(pDict['per']), float(pDict['buf'])
        generator = DiagonalGenerator(card, geo, dim, dist, output_format, strm, percentage, buffer)

    elif dist == 'gaussian':
        generator = GaussianGenerator(card, geo, dim, dist, output_format, strm)

    elif dist == 'sierpinski':
        if dim != 2:
            print('Currently we only support 2 dimensions for Sierpinski distribution')
            sys.exit()

        generator = SierpinskiGenerator(card, geo, dim, dist, output_format, strm)

    elif dist == 'bit':
        prob, digits = float(pDict['prob']), int(pDict['dig'])
        generator = BitGenerator(card, geo, dim, dist, output_format, strm, prob, digits)

    elif dist == 'parcel':
        if dim != 2:
            print('Currently we only support 2 dimensions for Parcel distribution')
            sys.exit()

        split_range, dither = float(pDict['sran']), float(pDict['dith'])
        generator = ParcelGenerator(card, geo, dim, dist, output_format, strm, split_range, dither)

    else:
        print('Please check the distribution type.')
        sys.exit()
        
    remote_file_name = "dat" + str(rand.randint(0,1000000)) + "." + output_format + ".gz"
    if strm == "cfile":
        sys.stdout.buffer.write(bytes("Content-type:application/x-gzip" + '\r\n', 'utf-8'))
        sys.stdout.buffer.write(bytes("Content-Disposition: attachment; filename=\"" + remote_file_name + "\"" + '\r\n', 'utf-8'))      
    else:
        sys.stdout.buffer.write(bytes("Content-type:text/html;charset=utf-8\r\n\r\n", 'utf-8'))
    sys.stdout.buffer.write(bytes('\r\n', 'utf-8'))
    
    if strm != "cfile":
        sys.stdout.buffer.write(bytes("<pre>", 'utf-8'))
    
    generator.generate_and_write()
    
    if strm != "cfile":
        sys.stdout.buffer.write(bytes("</pre>", 'utf-8'))

if __name__ == "__main__":
    main()
