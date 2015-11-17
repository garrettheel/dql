""" Utilities for monitoring the consumed capacity of tables """
import time

import curses
import six
from datetime import datetime


class Monitor(object):
    """ Tool for monitoring the consumed capacity of many tables """

    def __init__(self, engine, tables):
        self.engine = engine
        self.win = None
        self._tables = tables
        self._refresh_rate = 30
        self._max_width = 80

    def start(self):
        """ Start the monitor """
        curses.wrapper(self.run)

    def run(self, stdscr):
        """ Initialize curses and refresh in a loop """
        self.win = stdscr
        curses.curs_set(0)
        stdscr.timeout(0)
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
        while True:
            self.refresh()
            time.sleep(self._refresh_rate)

    def _progress_bar(self, width, percent, left='', right='', fill='|'):
        """ Get the green/yellow/red pieces of a text + bar display """
        text = left + (width - len(left) - len(right)) * ' ' + right
        cutoff = int(round(percent * width))
        text = text[:cutoff].replace(' ', fill) + text[cutoff:]
        low_cutoff = int(round(0.7 * width))
        med_cutoff = int(round(0.9 * width))
        if percent < 0.7:
            yield 2, text[:cutoff]
            yield 0, text[cutoff:]
        elif percent < 0.9:
            yield 2, text[:low_cutoff]
            yield 3, text[low_cutoff:cutoff]
            yield 0, text[cutoff:]
        else:
            yield 2, text[:low_cutoff]
            yield 3, text[low_cutoff:med_cutoff]
            yield 4, text[med_cutoff:cutoff]
            yield 0, text[cutoff:]

    def _add_throughput(self, y, x, width, op, title, available, used):
        """ Write a single throughput measure to a row """
        percent = float(used) / available
        self.win.addstr(y, x, '[')
        self.win.addstr(y, x + width - 1, ']')
        x += 1
        right = "%.1f/%d:%s" % (used, available, op)
        pieces = self._progress_bar(width - 2, percent, title, right)
        for color, text in pieces:
            self.win.addstr(y, x, text, curses.color_pair(color))
            x += len(text)
        return y + 1

    def refresh(self):
        """ Redraw the display """
        height, width = self.win.getmaxyx()
        self.win.addstr(0, 0, datetime.now().strftime('%H:%M:%S'))
        y = 1
        x = 0
        for table in self._tables:
            desc = self.engine.describe(table, True, True)
            cap = desc.consumed_capacity['__table__']
            col_width = min(width - x, self._max_width)
            rows = 2 * len(desc.consumed_capacity) + 1
            if y + rows > height:
                if x + 1 + 2 * col_width < width:
                    x = col_width + 1
                    y = 1
                    col_width = min(width - x, self._max_width)
                else:
                    break
            self.win.addstr(y, x, table, curses.color_pair(1))
            y += 1
            y = self._add_throughput(y, x, col_width, 'R', '',
                                     desc.read_throughput, cap['read'])
            y = self._add_throughput(y, x, col_width, 'W', '',
                                     desc.write_throughput, cap['write'])
            for index, cap in six.iteritems(desc.consumed_capacity):
                if index == '__table__':
                    continue
                y = self._add_throughput(y, x, col_width, 'R', index,
                                         desc.read_throughput, cap['read'])
                y = self._add_throughput(y, x, col_width, 'W', index,
                                         desc.write_throughput, cap['write'])
        self.win.refresh()
