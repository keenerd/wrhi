#! /usr/bin/env python2

from PIL import Image
from itertools import *

img1 = Image.open('lena-gray.png')
gamma = lambda px: int(((px/255.0) ** 2.2) * 255 + 0.5)
src = img1.point(gamma)

imgs = [src]

while max(imgs[-1].size) > 8:
    size = imgs[-1].size
    size = size[0]//2, size[1]//2
    imgs.append(imgs[0].resize(size, Image.ANTIALIAS))

imgs = [i.convert("1") for i in imgs]
pixs = [i.load() for i in imgs]


# manually dither zoom2, embed zoom4 inside it
img2 = src.resize(imgs[1].size, Image.ANTIALIAS)
pix2 = img2.load()
pix4 = pixs[2]
this_line = [pix2[x2,0] for x2 in range(img2.size[0])]
next_line = [pix2[x2,1] for x2 in range(img2.size[0])]
for y,x in product(range(img2.size[1]), range(img2.size[0])):
    if x == 0 and y != 0:
        this_line = next_line
    if x == 0 and y != img2.size[1]-1:
        next_line = [pix2[x2,y+1] for x2 in range(img2.size[0])]
    old_p = this_line[x]
    new_p = (old_p >= 128) * 255
    # stego zoom4
    if x%2==0 and y%2==0:
        new_p = pix4[x//2,y//2]
    pix2[x,y] = new_p
    quant_error = old_p - new_p
    if x+1 < img2.size[0]:
        this_line[x+1] += 7 * quant_error / 16.0
        next_line[x+1] += 1 * quant_error / 16.0
    next_line[x] += 5 * quant_error / 16.0
    if x-1 >= 0:
        next_line[x-1] += 3 * quant_error / 16.0
for x2 in range(img2.size[0]):
    pix2[x2,img2.size[1]-1] = next_line[x2]

img2 = img2.convert('1', dither=Image.NONE)
imgs[1] = img2
img2.show()

