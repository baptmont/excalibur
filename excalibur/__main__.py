# -*- coding: utf-8 -*-

from __future__ import absolute_import


__all__ = ("main",)


def main():
    from excalibur.cli import webserver

    webserver()


if __name__ == "__main__":
    main()
