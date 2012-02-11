// QUAd Fractal Format
// for viewing WikiReader Huge Images

#include <stdlib.h>
#include <stdarg.h>
#include <inttypes.h>
#include <ctype.h>
#include <stdio.h>
#include <string.h>

#include <grifo.h>

#define STACKDEPTH 20
#define IMAGECACHE 2000000

/*
quad tree with 8 bytes nodes/leaves

Node:
    height/dither (8 bit)
    type 0,1,2,3 (16 bit)
        exists, leaf, bounds, color
    child[0] pointer (32 bit)
    crop (2x3 bit)  # not implemented in this decoder

Leaf:
    8x8 1 bit block (64 bits)
*/

struct point
{
    int x;
    int y;
};

struct range
{
    int r1;
    int r2;
};

struct area
{
    struct range xr;
    struct range yr;
};

struct todo_element
{
    int address;
    int quad;
};

struct recursive_element
{
    int address;
    int height;
    struct area box;
    int branches[4];
};

static void run (void);

// main() must be first?  check this
int main (void)
{
    run();
    return 0;
}

// globals galore
int zoom;
struct point center;
struct area viewport;

void blinker()
// debugging tool :-(
{
    for (;;)
    {
        delay_us(500000);
        lcd_set_pixel(100, 100, 1);
        delay_us(500000);
        lcd_set_pixel(100, 100, 0);
    }
}

int parse_type (uint8_t n)
// returns 0:outside, 1:white, 2:black, -1:leaf, -2:node
{
    // 8:exists, 4:leaf, 2:bounds, 1:color
    if (n & 2)
        {return 0;}
    if ((n & 8) && (n & 4))
        {return -1;}
    if (n & 8)
        {return -2;}
    return ((n & 1) + 1);
}

int combine32 (uint8_t b0, uint8_t b1, uint8_t b2, uint8_t b3)
// sign error on 16GB images with 2 billion nodes
{
    return (((int)b0 & 0xFF)<<24) + (((int)b1 & 0xFF)<<16) +
           (((int)b2 & 0xFF)<<8)  +  ((int)b3 & 0xFF);
}

void build_branches (int* branches, int zero_p, uint8_t tb1, uint8_t tb2)
{
    int i;
    branches[0] = parse_type(tb1 / 16);
    branches[1] = parse_type(tb1 % 16);
    branches[2] = parse_type(tb2 / 16);
    branches[3] = parse_type(tb2 % 16);
    for (i=0; i<4; i++)
    {
        if (branches[i] == -2)
            {branches[i] =  zero_p; zero_p++;}
        if (branches[i] == -1)
            {branches[i] = -zero_p; zero_p++;}
    }
}

int overlap (struct range a, struct range b)
{
    if (a.r1 < b.r1)
        {return (a.r2 > b.r1);}
    else
        {return (b.r2 > a.r1);}
}

void refresh_viewport ()
// run after center or zoom is updated
// so pretty much on every input event
// or once per frame
{
    viewport.xr.r1 = center.x - LCD_WIDTH  * zoom / 2;
    viewport.xr.r2 = center.x + LCD_WIDTH  * zoom / 2;
    viewport.yr.r1 = center.y - LCD_HEIGHT * zoom / 2;
    viewport.yr.r2 = center.y + LCD_HEIGHT * zoom / 2;
}

int in_view (struct range xr, struct range yr)
{
    return (overlap(viewport.xr, xr) && overlap(viewport.yr, yr));
}

struct point screen_map (int xq, int yq)
// convert from quad space to screen space
{
    struct point s_pixel;
    // precompute some of this in refresh_viewport?
    s_pixel.x = (xq - center.x) / zoom + LCD_WIDTH  / 2;
    s_pixel.y = (yq - center.y) / zoom + LCD_HEIGHT / 2;
    return s_pixel;
}

struct area quad_chop (struct area a, int quad)
{
    int xm = (a.xr.r1 + a.xr.r2) / 2;
    int ym = (a.yr.r1 + a.yr.r2) / 2;
    struct area b;
    if (quad == 0)
        {b.xr.r1 = a.xr.r1; b.xr.r2 = xm; b.yr.r1 = a.yr.r1; b.yr.r2 = ym;}
    if (quad == 1)
        {b.xr.r1 = xm; b.xr.r2 = a.xr.r2; b.yr.r1 = a.yr.r1; b.yr.r2 = ym;}
    if (quad == 2)
        {b.xr.r1 = xm; b.xr.r2 = a.xr.r2; b.yr.r1 = ym; b.yr.r2 = a.yr.r2;}
    if (quad == 3)
        {b.xr.r1 = a.xr.r1; b.xr.r2 = xm; b.yr.r1 = ym; b.yr.r2 = a.yr.r2;}
    return b;
}

int branch_of (struct recursive_element parent, int address)
{
    int i;
    for (i=0; i<4; i++)
    {
        if (abs(parent.branches[i]) == address)
            {return 1;}
    }
    return 0;
}

void blit_box (struct area leaf)
{
    int x, y, x1, x2, y1, y2;
    struct point p;
    p = screen_map(leaf.xr.r1, leaf.yr.r1);
    x1 = p.x;
    y1 = p.y;
    p = screen_map(leaf.xr.r2, leaf.yr.r2);
    x2 = p.x;
    y2 = p.y;
    for (x=x1; x<x2; x++) { for (y=y1; y<y2; y++)
        {lcd_set_pixel(x, y, 1);}
    }
}

void blit_leaf (struct area leaf, uint8_t* raw)
// raw should be 8 characters long
{
    struct point p;
    int x, y;
    p = screen_map(leaf.xr.r1, leaf.yr.r1);
    // could this be replaced with write-byte-to-buffer?
    // would need to snap viewport to 8 and only helps zoom 1
    for (x=0; x<8; x+=zoom) { for (y=0; y<8; y+=zoom) {
        if (raw[x] & (1<<(7-y)))
            {continue;}
        lcd_set_pixel(p.x + x/zoom, p.y + y/zoom, 1);
    }}
}

void lcd_set_point (struct point p)
// convenient wrapper because this gets annoying
// could probably macro this
{
    lcd_set_pixel(p.x, p.y, 1);
}

void blit_dither (struct area leaf, uint8_t raw)
{
    int xm = (leaf.xr.r1 + leaf.xr.r2) / 2;
    int ym = (leaf.yr.r1 + leaf.yr.r2) / 2;
    if (raw & 8)
        {lcd_set_point(screen_map(leaf.xr.r1, leaf.yr.r1));}
    if (raw & 4)
        {lcd_set_point(screen_map(xm, leaf.yr.r1));}
    if (raw & 2)
        {lcd_set_point(screen_map(xm, ym));}
    if (raw & 1)
        {lcd_set_point(screen_map(leaf.xr.r1, ym));}
}

void render (uint8_t* nodes)
{
    int target_height = 3;
    struct todo_element todo[STACKDEPTH * 4];
    struct recursive_element stack[STACKDEPTH];
    struct recursive_element now;
    int todo_p=0, stack_p=0;
    int addr, quad, interesting, q;
    uint8_t* raw;
    int branch0;
    struct area box2;
    if (zoom == 16)
        {target_height = 4;}
    if (zoom == 32)
        {target_height = 5;}
    if (zoom == 64)
        {target_height = 6;}
    todo[0].address = 2;  // seed root
    todo_p = 1;
    while (todo_p > 0)
    {
        //lcd_printf("%i %i\n", stack_p, todo_p);
        addr = todo[(todo_p - 1)].address;
        quad = todo[(todo_p - 1)].quad;
        todo_p--;
        while (stack_p > 0 && ! branch_of(stack[stack_p-1], addr))
            {stack_p--;}
        now = stack[stack_p];
        now.address = addr;
        raw = &(nodes[addr*8]);
        // unpack data and store in struct on stack
        branch0 = combine32(raw[3], raw[4], raw[5], raw[6]);
        build_branches(now.branches, branch0, raw[1], raw[2]);
        if (stack_p > 0)
        {
            now.height = stack[stack_p-1].height - 1;
            now.box = quad_chop(stack[stack_p-1].box, quad);
        }
        else
        {
            now.height = raw[0];
            now.box.xr.r1 = 0; now.box.xr.r2 = 1<<now.height;
            now.box.yr.r1 = 0; now.box.yr.r2 = 1<<now.height;
        }
        // ignore, render or recurse the node & branches
        if (! in_view(now.box.xr, now.box.yr))
            {continue;}
        interesting = 0;
        for (q=0; q<4; q++)
        {
            box2 = quad_chop(now.box, q);
            if (now.branches[q] == 2)
                {blit_box(box2); continue;}
            if (now.height == target_height)
                {blit_dither(box2, raw[0]); continue;}
            if (now.branches[q] < 0)
                {blit_leaf(box2, &(nodes[-8*now.branches[q]])); continue;}
            if (now.branches[q] <= 2)
                {continue;}
            todo[todo_p].address = now.branches[q];
            todo[todo_p].quad = q;
            todo_p++;
            interesting++;
        }
        if (interesting)
        {
            stack[stack_p] = now;
            stack_p++;
        }
    }
}

void load_wrhi (char* path, char* nodes)
// put entire thing in ram, max IMAGECACHE
// this only does 8.3 filenames
{
    int fd, fs, fp;
    fd = file_open(path, FILE_OPEN_READ);
    // check fd >= 0 ?
    fs = file_read(fd, nodes, 512);
    fp = fs;
    while (fs > 0)
    {
        fs = file_read(fd, &nodes[fp], 512);
        fp += fs;
    }
    file_close(fd);
}

void run ()
{
    uint8_t nodes[IMAGECACHE];
    lcd_clear(0);
    // initialize globals
    zoom = 1;
    center.x = 256; center.y = 256;
    refresh_viewport();
    load_wrhi("lena.wri", nodes);
    render(nodes);
    blinker();
    for (;;)
    {
        // page flipping?
        // wait for input
        delay_us(1000000);
    }
}

