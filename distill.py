#! /usr/bin/env python2

# pil on py3 is buggy, won't open png

from PIL import Image
from dither import recursive_dither
from itertools import *
from collections import defaultdict

# wikireader huge image distill
# turns an image into a wrhi file

"""
Convert 1 bit png to a quad tree
Specifically for the Wikireader
(Later, make app for panning/zooming these)

Tree should be heap-ish, for easy parsing
Nodes should have color ratio, for future easy dithering

since the tree is BF, all quads are sequential
only store pointer to quad[0]!

Node:
    height/dither (8 bit)
        height only in root
        dither only uses 4 bits, one per child
    type 0,1,2,3 (16 bit)
        exists, leaf, bounds, color
    child[0] pointer (32 bit)
    crop (8 bit)
        only used in root, 2x3 bit

Leaf:
    8x8 1 bit block (64 bits)

Load tree DFS with a stack
Discard branches that are outside viewport
If you are clever, panning viewport is only new pixels on edge

generating zoom{2,4,8} dynamically is dumb
embed it somewhere
make a stego-dither algo and embed it inside the picture

"""

class Node(object):
    def __init__(self, parent, xr, yr):
        "size is log2"
        self.root = False
        self.parent = parent
        try:
            self._pix = parent._pix
        except AttributeError:
            self._pix = parent  # root node
            self.parent = None
        self.xr = xr
        self.yr = yr
        self.children = [None] * 4
        self.out_of_bounds = xr[0]>xr[1] or yr[0]>yr[1]
        if self.out_of_bounds:
            return
        self.b_count, self.w_count = tally[self.xr + self.yr]
        self.size = int_log2(max(xr[1]-xr[0], yr[1]-yr[0]))
    def __repr__(self):
        return str((self.xr, self.yr, self.children))
    def pix(self, x, y):
        try:
            return self._pix[x,y]
        except IndexError:
            return True
    def bitwise(self, blocks):
        binary = []
        if self.root:
            binary.append(self.size)
        else:
            xm = sum(self.xr) // 2
            ym = sum(self.yr) // 2
            dither =            (not bool(self.pix(self.xr[0], self.yr[0])))
            dither = dither*2 + (not bool(self.pix(xm, self.yr[0])))
            dither = dither*2 + (not bool(self.pix(xm, ym)))
            dither = dither*2 + (not bool(self.pix(self.xr[0], ym)))
            binary.append(dither)
        t0 = block_type(blocks, self.children[0])
        t1 = block_type(blocks, self.children[1])
        t2 = block_type(blocks, self.children[2])
        t3 = block_type(blocks, self.children[3])
        binary.append((t0<<4) + t1)
        binary.append((t2<<4) + t3)
        try:
            pointer = min(c for c in self.children if type(c) == int)
        except TypeError:   # no child pointers
            pointer = 0
        except ValueError:  # no child pointers
            pointer = 0
        assert pointer < len(blocks)
        binary.extend(bitwise(pointer, 32))
        if self.root:
            binary.append((self.xr[1]%8)*16 + self.yr[1]%8)
        else:
            binary.append(0)
        return binary

def block_type(blocks, child):
    # exists, leaf, bounds, color
    exists = type(child) in (int, long)
    leaf   = exists and type(blocks[child]) in (int, long)
    bounds = child == 'outside'
    color  = child == 'black'
    return exists*8 + leaf*4 + bounds*2 + color

def bitwise(n, bits):
    for sub in range(0, bits, 8):
        out = 0
        for i in list(reversed(range(bits)))[sub:sub+8]:
            j = 1<<i
            out *= 2
            if n >= j:
                n -= j
                out += 1
        yield out

def print_bin(blocks, block):
    if type(block) == str:
        return map(ord, block)
    binary = []
    if type(block) in (int, long):
        for b in bitwise(block, 64):
            binary.append(b)
        assert len(binary) == 8
        return binary
    binary = block.bitwise(blocks)
    if len(binary) != 8:
        print block
        print binary
    assert len(binary) == 8
    return binary

def int_log2(n):
    return [i for i in range(16) if (1<<i) >= n][0]

def chop_by_quad(node):
    x1 = node.xr[0]
    x2 = x1 + (1<<(node.size-1))
    x3 = node.xr[1]
    y1 = node.yr[0]
    y2 = y1 + (1<<(node.size-1))
    y3 = node.yr[1]
    return [Node(node, (x1,x2), (y1,y2)),
            Node(node, (x2,x3), (y1,y2)),
            Node(node, (x2,x3), (y2,y3)),
            Node(node, (x1,x2), (y2,y3))]

def literal(node):
    "return 64 bit int, black is 1"
    if node.size != 3:
        raise
    n = 0
    for y,x in product(range(*node.yr), range(*node.xr)):
        n *= 2
        try:
            if not pix[x,y]:
                n += 1
        except IndexError:
            pass
    return n

def fast_count(pix, size):
    tally = defaultdict(lambda: [0,0])  # (x, x, y, y) : (black, white)
    for x,y in product(range(0, size[0], 8), range(0, size[1], 8)):
        b,w = 0,0
        for xsub,ysub in product(range(8), range(8)):
            if x+xsub >= size[0]:
                continue
            if y+ysub >= size[1]:
                continue
            if pix[x+xsub,y+ysub]:
                w += 1
            else:
                b += 1
        tally[(x,x+8,y,y+8)] = (b,w)
        tally[(x, min(x+8, size[0]), y, min(y+8, size[1]))] = (b,w)
    added = len(tally)
    ival = 8
    while added > 1:
        added = 0
        ival *= 2
        for x,y in product(range(0, size[0], ival), range(0, size[1], ival)):
            added += 1
            branches = [tally[(x,         x+ival//2, y,         y+ival//2)], 
                        tally[(x+ival//2, x+ival,    y,         y+ival//2)],
                        tally[(x+ival//2, x+ival,    y+ival//2, y+ival)],
                        tally[(x,         x+ival//2, y+ival//2, y+ival)]]
            tally[(x,x+ival,y,y+ival)] = map(sum, zip(*branches))
            tally[(x, min(x+ival, size[0]), y, min(y+ival, size[1]))] = map(sum, zip(*branches))
    return tally

#img = Image.open('lena.png')
img = recursive_dither('lena-gray.png')
print "dithering complete"
img.save('/tmp/dither.png')
pix = img.load()
tally = fast_count(pix, img.size)
root_height = int_log2(max(img.size))
#print root_height

blocks = ['#!quafit\n', '#v0000\n']
root = Node(pix, (0,img.size[0]), (0,img.size[1]))
root.root = True
blocks.append(root)
#print blocks

todo = [2]  # blocks to quadify

while todo:
    now = todo.pop(0)
    new_quads = chop_by_quad(blocks[now])
    pre_length = len(blocks)
    added_blocks = []
    for i,node in enumerate(new_quads):
        if node.out_of_bounds:
            blocks[now].children[i] = 'outside'
            continue
        if node.b_count == 0:
            blocks[now].children[i] = 'white'
            continue
        if node.w_count == 0:
            blocks[now].children[i] = 'black'
            continue
        blocks.append(None)
        address = len(blocks) - 1
        if node.size > 3:
            blocks[address] = node
            todo.append(address)
            added_blocks.append(address)
        if node.size == 3:
            blocks[address] = literal(node)
        blocks[now].children[i] = address
   # print blocks[now]
   # for i in added_blocks:
   #     print "   ", blocks[i].xr, blocks[i].yr

#print
#print 'block count', len(blocks)

binary = []
[binary.extend(print_bin(blocks, b)) for b in blocks]
assert all(0<=b<=255 for b in binary)

#print len(binary)
f = open('/tmp/image.wri', 'wb')
f.write(''.join(map(chr, binary)))
f.close()


