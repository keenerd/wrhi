#! /usr/bin/env python2

# PIL seems to clip floating errors when dithering

from PIL import Image
from itertools import *

def dither(img, stego=None):
    "img should be float mode, stego should be half size and pre-dithered"
    pix = img.load()
    if stego is not None:
        stego = stego.load()
    for y,x in product(range(img.size[1]), range(img.size[0])):
        old_p = pix[x,y]
        new_p = (old_p >= 128) * 255
        # stego zoom4
        if x%2==0 and y%2==0 and stego is not None:
            new_p = stego[x//2,y//2]
        pix[x,y] = new_p
        quant_error = old_p - new_p
        if x+1 < img.size[0]:
            pix[x+1,y] += 7 * quant_error / 16.0
        if y+1 < img.size[1]:
            pix[x,y+1] += 5 * quant_error / 16.0
            if x+1 < img.size[0]:
                pix[x+1,y+1] += 1 * quant_error / 16.0
            if x-1 >= 0:
                pix[x-1,y+1] += 3 * quant_error / 16.0
    return img

def main():
    img1 = Image.open('lena-gray.png')
    gamma = lambda px: (px/255.0) ** 2.2 * 255
    src = img1.point(gamma)

    imgs = [src]

    while max(imgs[-1].size) > 8:
        size = imgs[-1].size
        size = size[0]//2, size[1]//2
        imgs.append(imgs[0].resize(size, Image.ANTIALIAS))

    # floating dither is 5x slower, use sparingly
    imgs = [i.convert('1') for i in imgs]
    #imgs = [imgs[0].convert('1')] + [dither(i).convert('1') for i in imgs[1:]]
    #imgs = [dither(i).convert('1') for i in imgs]

    srcf = img1.point(gamma, 'F')
    imgs[1] = dither(srcf.resize(imgs[1].size, Image.ANTIALIAS), imgs[2])
    imgs[1] = imgs[1].convert('1', dither=Image.NONE)
    imgs[1].show()

if __name__ == '__main__':
    main()

