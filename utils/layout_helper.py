import curses
import math

def init_color_pairs():
    curses.init_color(2, 0, 500, 0)
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)

def refresh_y_limits(validator_list):
    paging_y_offset = curses.LINES - 2
    pad_height = len(validator_list)
    y_scroll_limit = pad_height - curses.LINES + 2
    if y_scroll_limit < 0:
        y_scroll_limit = 0

    return paging_y_offset, pad_height, y_scroll_limit

def y_scroll(c, pad_y_scroll, y_scroll_limit, paging_y_offset):
    if c == curses.KEY_DOWN:
            if (pad_y_scroll + 1 <= y_scroll_limit):
                pad_y_scroll += 1
            else:
                pad_y_scroll = y_scroll_limit
    if c == curses.KEY_UP:
        if (pad_y_scroll >= 1):
            pad_y_scroll -= 1
        else:
            pad_y_scroll = 0
    if c == curses.KEY_NPAGE:
        if (pad_y_scroll + paging_y_offset <= y_scroll_limit):
            pad_y_scroll += paging_y_offset
        else:
            pad_y_scroll = y_scroll_limit
    if c == curses.KEY_PPAGE:
        if (pad_y_scroll >= paging_y_offset):
            pad_y_scroll -= paging_y_offset
        else:
            pad_y_scroll = 0

    if (pad_y_scroll > y_scroll_limit):
        pad_y_scroll = y_scroll_limit
    if y_scroll_limit > 0:
        scroll_percent = pad_y_scroll / y_scroll_limit
    else:
        scroll_percent = 1

    scroll_indicator_y = math.floor(scroll_percent * (curses.LINES - 3)) + 1

    return pad_y_scroll, scroll_indicator_y

def redraw_base_layout(stdscr, scroll_indicator_y, width, block_no, chain_id):
    stdscr.erase()
    stdscr.border()
    stdscr.addstr(scroll_indicator_y, width + 2, '█')
    stdscr.addstr(0, 0, str(block_no))
    stdscr.addstr(0, len(str(block_no)) + 2, f"{chain_id}")
