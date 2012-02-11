#! /usr/bin/env python2

# a simpler all in one version that will be ported to C

import random
import Tkinter as tk

"""
Node:
    height/dither (8 bit)
    type 0,1,2,3 (16 bit)
        exists, leaf, bounds, color
    child[0] pointer (32 bit)
    crop (8 bit)  # not implemented in decoder

Leaf:
    8x8 1 bit block (64 bits)
"""

canvas = None

def pixel(x, y):
    box(x, y, x, y)

def box(x1, y1, x2, y2):
    canvas.create_rectangle(x1,y1,x2,y2, fill='black', outline='')

def load(path):
    "returns a list of 8x8 bit ints"
    nodes = []
    string = open(path).read()
    for i in range(0, len(string), 8):
        nodes.append(map(ord, string[i:i+8]))
    return nodes

class Struct(object):
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            self.__setattr__(k, v)

def parse_type(nibble):
    "0:outside, 1:white, 2:black, -1:leaf, -2:node"
    n = nibble  # 8:exists, 4:leaf, 2:bounds, 1:color
    if n & 2:
        return 0
    if n & 8 and n & 4:
        return -1
    if n & 8:
        return -2
    return (n & 1) + 1

def combine32(bs):
    assert len(bs) == 4
    return (bs[0]<<24) + (bs[1]<<16) + (bs[2]<<8) + bs[3]

def build_branches(zero, tb1, tb2):
    branches = [0,0,0,0]
    branches[0] = parse_type(tb1 // 16)
    branches[1] = parse_type(tb1 % 16)
    branches[2] = parse_type(tb2 // 16)
    branches[3] = parse_type(tb2 % 16)
    for i in range(4):
        if branches[i] == -1:
            branches[i] = -zero
            zero += 1
        if branches[i] == -2:
            branches[i] = zero
            zero += 1
    return branches

def overlap(rangeA, rangeB):
    a1,a2 = rangeA
    b1,b2 = rangeB
    return a2>b1 if a1<b1 else b2>a1

def in_view_fn(bbox, center, zoom):
    "returns function(xr, yr) -> bool"
    xb,yb = bbox
    xc,yc = center
    xrv = xc - xb*zoom//2, xc + xb*zoom//2
    yrv = yc - yb*zoom//2, yc + yb*zoom//2
    return lambda xr,yr: overlap(xrv, xr) and overlap(yrv, yr)

def screen_map_fn(bbox, center, zoom):
    "returns function(x_quad, y_quad) -> x_screen, y_screen"
    xm,ym = bbox[0]//2, bbox[1]//2
    xc,yc = center
    return lambda xq,yq: ((xq-xc)/zoom + xm, (yq-yc)/zoom + ym)

def quad_chop(xr, yr, quad): 
    x1,x3 = xr
    x2 = (x1+x3) // 2
    y1,y3 = yr
    y2 = (y1+y3) // 2
    xr_new = [(x1,x2), (x2,x3), (x2,x3), (x1,x2)][quad]
    yr_new = [(y1,y2), (y1,y2), (y2,y3), (y2,y3)][quad]
    return xr_new, yr_new

def branch_of(struct, address):
    return any(address in (n, -n) for n in struct.branches)

def blit_box(screen_map, xr, yr):
    xy0 = screen_map(xr[0], yr[0])
    xy1 = screen_map(xr[1], yr[1])
    box(*(xy0 + xy1))
    #box(xr[0], yr[0], xr[1], yr[1])

def blit_leaf(screen_map, xr, yr, zoom, raw):
    # I don't think I meant to make this column major....
    for x in range(0, 8, zoom):
        for y in range(0, 8, zoom):
            p = bool(raw[x] & 2**(7-y))
            if p:
                continue
            x2,y2 = screen_map(xr[0], yr[0])
            pixel(x2+x//zoom, y2+y//zoom)
            #pixel(xr[0] + x, yr[0] + y)

def blit_dither(screen_map, xr, yr, raw):
    xm = sum(xr)//2
    ym = sum(yr)//2
    if raw & 8:
        pixel(*screen_map(xr[0], yr[0]))
    if raw & 4:
        pixel(*screen_map(xm, yr[0]))
    if raw & 2:
        pixel(*screen_map(xm, ym))
    if raw & 1:
        pixel(*screen_map(xr[0], ym))

def viewport(nodes, bbox, center, zoom):
    "simple one shot renderer"
    target_height = {1:3, 2:3, 4:3, 8:3, 16:4, 32:5, 64:6}[zoom]
    in_view = in_view_fn(bbox, center, zoom)
    screen_map = screen_map_fn(bbox, center, zoom)
    # set up the root
    todo = [(2, None)]  # assert length < 80
    stack = []  # assert length < 20
    # todo <= 4x stack
    maxtodo = 0
    maxstack = 0
    while todo:
        maxtodo = max(maxtodo, len(todo))
        maxstack = max(maxstack, len(stack))
        adr,quad = todo.pop(-1)  # DFS
        while stack and not branch_of(stack[-1], adr):
            stack.pop(-1)
        raw = nodes[adr]
        # unpack data and store in struct on stack
        branch0 = combine32(raw[3:7])
        branches = build_branches(branch0, raw[1], raw[2])
        if stack:
            height = stack[-1].height - 1
            xr, yr = quad_chop(stack[-1].xr, stack[-1].yr, quad)
        else:
            height = raw[0]
            xr,yr = (0, 2**height), (0, 2**height)
        if not in_view(xr, yr):
            continue
        #print 'stack', len(stack), 'todo', len(todo)
        #print 'now', adr, height, xr, yr
        #print branches, '\n'
        interesting = False
        for q in range(4):
            xrq,yrq = quad_chop(xr, yr, q)
            if branches[q] == 2:
                blit_box(screen_map, xrq, yrq)
                continue
            if height == target_height:
                blit_dither(screen_map, xrq, yrq, raw[0]) 
                continue
            if branches[q] < 0:
                blit_leaf(screen_map, xrq, yrq, zoom, nodes[-branches[q]]) 
                continue
            if branches[q] <= 2:
                # not recursable
                continue
            todo.append((branches[q], q))
            interesting = True
        if interesting:
            struct = Struct(address=adr, height=height,
                            xr=xr, yr=yr, branches=branches)
            stack.append(struct)
    print maxstack, maxtodo


def main(path):
    global canvas
    nodes = load(path)
    root = tk.Tk()
    canvas = tk.Canvas(root, bg='white')
    canvas.pack(expand=1, fill=tk.BOTH)
    canvas.tk_focusFollowsMouse()
    center = random.randint(0,500), random.randint(0,500)
    zoom = random.choice((1,1,1,1,2,2,4,8,16,32))
    #center = (256, 256)
    #zoom = 4
    print center, zoom
    viewport(nodes, (240,208), center, zoom)
    root.mainloop()

main('lena.wrhi')


