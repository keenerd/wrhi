#! /usr/bin/env python2

# PIL seems to clip floating errors when dithering

from PIL import Image
from itertools import *

def dither(img, stego=None):
    "img should be float mode, stego should be half size and pre-dithered"
    pix = img.load()
    if stego is not None:
        stego = stego.load()
    quant_error = 0
    for y in range(img.size[1]):
        x_range = range(img.size[0])
        if y%2 == 1:
            x_range = reversed(x_range)
        for x in x_range:
            old_p = pix[x,y]
            new_p = (old_p >= 128) * 255
            # stego zoom4
            if x%2==0 and y%2==0 and stego is not None:
                try:
                    new_p = stego[x//2,y//2]
                except IndexError:
                    pass
            pix[x,y] = new_p
            quant_error += old_p - new_p
            corrected_error = 0
            kernel = [(1,0,7), (0,1,5), (1,1,1), (-1,1,3)]
            if y%2 == 1:
                kernel = [(-kx,ky,kq) for kx,ky,kq in kernel]
            kernel = [(x+kx, y+ky, kq) for kx,ky,kq in kernel]
            for kx, ky, kq in kernel:
                try:
                    pix[kx,ky] += kq * quant_error / 16.0
                    corrected_error += kq
                except IndexError:
                    pass
            quant_error -= corrected_error * quant_error / 16.0
    return img

def recursive_dither(path):
    img1 = Image.open(path)
    img1 = img1.convert('L')
    gamma = lambda px: (px/255.0) ** 2.2 * 255
    src = img1.point(gamma)

    imgs = [src]
    
    while min(imgs[-1].size) > 8:
        size = imgs[-1].size
        size = size[0]//2, size[1]//2
        imgs.append(imgs[0].resize(size, Image.ANTIALIAS))

    imgs[-1] = imgs[-1].convert('1')
    srcf = img1.point(gamma, 'F')
    # nested floating stego dithers all the way down
    for i in range(len(imgs)-2, -1, -1):
        imgs[i] = dither(srcf.resize(imgs[i].size, Image.ANTIALIAS), imgs[i+1])
        imgs[i] = imgs[i].convert('1', dither=Image.NONE)
    return imgs[0]

def main():
    img1 = Image.open('lena-gray.png')
    img1 = img1.convert('L')
    gamma = lambda px: (px/255.0) ** 2.2 * 255
    src = img1.point(gamma)

    imgs = [src]

    while min(imgs[-1].size) > 8:
        size = imgs[-1].size
        size = size[0]//2, size[1]//2
        imgs.append(imgs[0].resize(size, Image.ANTIALIAS))

    # floating dither is 5x slower, use sparingly
    imgs = [i.convert('1') for i in imgs]
    #imgs = [imgs[0].convert('1')] + [dither(i).convert('1') for i in imgs[1:]]
    #imgs = [dither(i).convert('1') for i in imgs]
    #imgs[-1] = imgs[-1].convert('1')

    srcf = img1.point(gamma, 'F')
    imgs[1] = dither(srcf.resize(imgs[1].size, Image.ANTIALIAS), imgs[2])
    #imgs[1] = imgs[1].convert('1', dither=Image.NONE)

    #imgs[0].show()
    #imgs[1].show()
    imgs[0].save('/tmp/dither.png')

if __name__ == '__main__':
    #main()
    recursive_dither('lena-gray.png').save('/tmp/lena-bw.png')

