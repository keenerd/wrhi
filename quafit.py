#! /usr/bin/env python2

import Tkinter as tk
from itertools import *

# quad format interpreter for wrhi files

"""
Node:
    ratio/height (8 bit)
    type 0,1,2,3 (16 bit)
        exists, leaf, bounds, color
    child[0] pointer (32 bit)
    null (8 bit)  # todo - store the edge crop here for not % 8 sizes

Leaf:
    8x8 1 bit block (64 bits)
"""

def fixed_bin(n, width):
    bs = []
    for i in reversed(range(width)):
        j = 2**i
        bs.append(n >= j)
        if n >= j:
            n -= j
    assert n == 0
    return bs

class Node(object):
    "un-serialized file"
    def __init__(self, chars):
        "takes 8 bytes of char"
        self.literal = map(ord, chars)
        assert len(self.literal) == 8
        lit = self.literal
        self.bits = []
        [self.bits.extend(fixed_bin(n, 8)) for n in lit]
        self.ratio = lit[0]
        self.height = lit[0]
        self.types = [lit[1]//16, lit[1]%16, lit[2]//16, lit[2]%16]
        self.pointer = (lit[3]<<24) + (lit[4]<<16) + (lit[5]<<8) + lit[6]
        self.x_clip = lit[7] // 16
        self.y_clip = lit[7] % 16

class Block(object):
    "hold state while walking tree"
    def __init__(self, node, parent=None, quad=None):
        self.node = node
        if parent is None:
            self.xr = (0, 2**node.height)
            self.yr = (0, 2**node.height)
            self.height = node.height
        else:
            self.xr, self.yr = quad_chop(parent.xr, parent.yr, quad)
            self.height = parent.height - 1
        # normally we'd check the bounding box before continuing
        self.children = [None, None, None, None]
        self.types    = [None, None, None, None]
        assert self.height >= 3
        self.find_children()
    def find_children(self):
        j = 0
        for i,t in enumerate(self.node.types):
            exists,leaf,bounds,color = fixed_bin(t, 4)
            if bounds:
                self.children[i] = 'outside'
                self.types[i] = 'outside'
                continue
            if exists:
                self.children[i] = self.node.pointer + j
                j += 1
                self.types[i] = 'node'
            if leaf:
                self.types[i] = 'leaf'
            if exists:
                continue
            self.types[i] = 'solid'
            self.children[i] = ('white', 'black')[color]

def quad_chop(xr, yr, quad): 
    x1,x3 = xr
    x2 = (x1+x3) // 2
    y1,y3 = yr
    y2 = (y1+y3) // 2
    xr_new = [(x1,x2), (x2,x3), (x2,x3), (x1,x2)][quad]
    yr_new = [(y1,y2), (y1,y2), (y2,y3), (y2,y3)][quad]
    return xr_new, yr_new

def draw(canvas, xr, yr, fill=None, bits=None):
    if fill == 'black':
        canvas.create_rectangle(xr[0], yr[0], xr[1], yr[1],
               fill='black', outline='')
    if bits:
        points = product(range(xr[0], xr[1]), range(yr[0], yr[1]))
        for xy,b in zip(points, bits):
            if b:  # bug?  black should be 1
                continue
            canvas.create_rectangle(xy[0], xy[1], xy[0], xy[1],
                   fill='black', outline='')

error = 0
def draw2(canvas, xr, yr, fill=None, bits=None):
    "zoom 2:1, passable hack"
    global error
    if fill == 'black':
        xr = xr[0]//2, xr[1]//2
        yr = yr[0]//2, yr[1]//2
        canvas.create_rectangle(xr[0], yr[0], xr[1], yr[1],
               fill='black', outline='')
    if bits:
        points = list(product(range(xr[0], xr[1]), range(yr[0], yr[1])))
        p2 = dict(zip(points, bits))
        order = [1, 0, 4, 5, 9, 8, 12, 13, 14, 15, 11, 10, 6, 7, 3, 2]
        subpoints = list(product(range(xr[0], xr[1], 2), range(yr[0], yr[1], 2)))
        for x,y in [subpoints[i] for i in order]:
            tally = p2[(x,y)] + p2[(x+1,y)] + p2[(x,y+1)] + p2[(x+1,y+1)]
            b = (tally + error) >= 3
            error -= (-tally, 4-tally)[b]
            #b = tally >= 2
            if b:
                continue
            canvas.create_rectangle(x//2, y//2, x//2, y//2,
                   fill='black', outline='')

def draw4(canvas, xr, yr, fill=None, bits=None):
    "zoom 4:1, ugly"
    global error
    if fill == 'black':
        xr = xr[0]//4, xr[1]//4
        yr = yr[0]//4, yr[1]//4
        canvas.create_rectangle(xr[0], yr[0], xr[1], yr[1],
               fill='black', outline='')
    if bits:
        points = list(product(range(xr[0], xr[1]), range(yr[0], yr[1])))
        p2 = dict(zip(points, bits))
        order = [0, 1, 2, 3]
        subpoints = list(product(range(xr[0], xr[1], 4), range(yr[0], yr[1], 4)))
        for x,y in [subpoints[i] for i in order]:
            tally = sum(p2[xy] for xy in product(range(x,x+4), range(y,y+4)))
            b = (tally + error) >= 9
            error -= (-tally, 16-tally)[b]
            #b = tally >= 8
            if b:
                continue
            canvas.create_rectangle(x//4, y//4, x//4, y//4,
                   fill='black', outline='')

def load(path):
    nodes = []
    string = open(path).read()
    string = string
    for i in range(0, len(string), 8):
        chars = string[i:i+8]
        nodes.append(Node(chars))
    print len(nodes)
    return nodes

def walk(canvas, nodes, draw_fn):
    stack = [Block(nodes[2])]
    while stack:
        now = stack.pop(0)
        for q,child in enumerate(now.children):
            assert child is not None
            if now.types[q] == 'node':
                stack.append(Block(nodes[child], now, q))
                continue
            if now.types[q] == 'outside':
                continue
            xr,yr = quad_chop(now.xr, now.yr, q)
            if now.types[q] == 'leaf':
                draw_fn(canvas, xr, yr, bits=nodes[child].bits)
            if now.types[q] == 'solid':
                draw_fn(canvas, xr, yr, fill=now.children[q])

def main(path):
    nodes = load(path)
    root = tk.Tk()
    canvas = tk.Canvas(root, bg='white')
    canvas.pack(expand=1, fill=tk.BOTH)
    canvas.tk_focusFollowsMouse()
    #walk(canvas, nodes, draw)
    #walk(canvas, nodes, draw2)
    walk(canvas, nodes, draw4)
    root.mainloop()

main('lena.wrhi')

