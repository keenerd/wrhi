# Makefile
#

WRDK_SHARE := $(shell wrdk-config --share)
include $(WRDK_SHARE)/definitions.mk

# list of modules
SRC = $(wildcard *.c)

include $(WRDK_SHARE)/rules.mk
