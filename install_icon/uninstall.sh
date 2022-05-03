#!/bin/bash

if [ -f "~/.local/bin/wfdlogger" ]; then
    rm ~/.local/bin/wfdlogger
fi

xdg-icon-resource uninstall --size 64 k6gte-wfdlogger

xdg-desktop-icon uninstall k6gte-wfdlogger.desktop

xdg-desktop-menu uninstall k6gte-wfdlogger.desktop

