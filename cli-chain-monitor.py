#!/usr/bin/python3

import curses
import json
import math
from time import time, sleep
from datetime import datetime
import re
import binascii
import hashlib
from argparse import ArgumentParser
import utils.request_helper as rh
import utils.layout_helper as lh
import utils.cosmos_validator as cv

CURRENT_LINE = 0

# necessary because curses is unable to determine width of flags and some other emojis
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0000269B\U0000FE0F"
    "]+"
)

def strip_emoji(text):
    return EMOJI_PATTERN.sub(r'', text)

def request_initial_data(stdscr):
    global CURRENT_LINE

    # Get chain ID
    stdscr.addstr(CURRENT_LINE, 0, 'fetching chain id...')
    CURRENT_LINE += 1
    stdscr.refresh()
    chain_id = rh.get_chain_id()

    # Get provider validators if URL is given
    provider_validators = []
    if rh.PROVIDER_REST_API is not None:
        stdscr.addstr(CURRENT_LINE, 0, 'fetching provider validator info...')
        CURRENT_LINE += 1
        stdscr.refresh()
        provider_validators = rh.get_provider_vals()
    
    # Get consumer validators
    stdscr.addstr(CURRENT_LINE, 0, 'fetching consumer validator info...')
    CURRENT_LINE += 1
    stdscr.refresh()
    validators = rh.get_consumer_vals()
    consumer_validators = sorted(validators, key=lambda x: int(x['voting_power']), reverse=True)

    return chain_id, provider_validators, consumer_validators

def print_init(stdscr):
    global CURRENT_LINE
    stdscr.erase()
    stdscr.addstr(CURRENT_LINE, 0, 'initializing...')
    CURRENT_LINE += 1
    stdscr.refresh()

def only_one_vp_match(validator_list, voting_power_to_find):
    iterator = iter(validator_list)
    has_true = any(int(int(x['voting_power'])) == voting_power_to_find for x in iterator)
    has_another_true = any(int(int(x['voting_power'])) == voting_power_to_find for x in iterator)
    return has_true and not has_another_true

def init_validator_list(provider_validators, consumer_validators):
    validators = []
    token_sum = 0
    for i in range(0, len(consumer_validators)):
        moniker_set = False
        is_diff_pubkey = False
        for k in range(0, len(provider_validators)):
            # try to match on public key
            if (provider_validators[k]['consensus_pubkey']['key'] == consumer_validators[i]['pub_key']['value']):
                moniker = provider_validators[k]['description']['moniker']
                moniker_set = True
                is_diff_pubkey = False
            # try to match on voting power
            if not moniker_set:
                if only_one_vp_match(consumer_validators, int(int(provider_validators[k]['tokens']) / 1000000)):
                    if (int(int(provider_validators[k]['tokens']) / 1000000) == int(consumer_validators[i]['voting_power'])):
                        moniker = provider_validators[k]['description']['moniker']
                        moniker_set = True
                        is_diff_pubkey = True
        if not moniker_set:
            moniker = consumer_validators[i]['address']
            moniker_set = True
            is_diff_pubkey = True
        sanitized_moniker = strip_emoji(moniker)
        hex_pub_addr = hashlib.sha256(binascii.a2b_base64(consumer_validators[i]['pub_key']['value'])).digest()[:20].hex().upper()
        token_sum += int(consumer_validators[i]['voting_power'])
        validators.append(cv.Validator(consumer_validators[i]['pub_key']['value'], hex_pub_addr, is_diff_pubkey,
            int(consumer_validators[i]['voting_power']), sanitized_moniker))
    
    cutoff_5_percent = token_sum * 0.05
    cutoff_sum = 0
    is_still_soft_opt_out = True
    for v in reversed(validators):
        if is_still_soft_opt_out:
            cutoff_sum += int(v.voting_power)
            if cutoff_sum <= cutoff_5_percent:
                v.soft_opt_out = True
            else:
                is_still_soft_opt_out = False
        v.voting_power_percent = float(int(v.voting_power)) / float(token_sum)

    return validators

def main(stdscr):
    global CURRENT_LINE
    lh.init_color_pairs()

    # Init screen and scroll
    curses.curs_set(0)
    curses.halfdelay(1)
    stdscr.clear()
    pad_y_scroll = 0
    pad_height = 100 # only used if empty valset
    search_dialog = None
    paging_y_offset = 0
    pad_begin_x = 1; pad_begin_y = 1
    height = curses.LINES - 3; width = curses.COLS - 3
    block_display_start_x = 2+3+29+2+6+1+40+3

    # Initializing data
    print_init(stdscr)
    chain_id, provider_validators, consumer_validators = request_initial_data(stdscr)

    # Init validator list
    all_validators = init_validator_list(provider_validators, consumer_validators)
    filtered_validators = all_validators

    # Init block and proposer
    last_fetched_time = 0
    block_buffer = dict()
    buffer_init = False
    current_block = 0
    last_block = 0
    processed_block = 0
    last_proposer = None
    current_proposer = None

    # Init timings
    fetch_interval_seconds = 2
    block_time_deltas = []
    last_block_datetime = None
    average_block_time = 1

    # Create buffer for validator <-> signed info
    if not buffer_init:
        for v in all_validators:
            block_buffer[v.hex_key] = []
        buffer_init = True


    # Main loop retrieving new blocks / refresh screen
    while True:
        # Fetch new block
        if (time() - last_fetched_time) > fetch_interval_seconds:
            last_proposer = current_proposer
            block = rh.get_block()
            if current_block:
                if int(block['block']['header']['height']) > current_block:
                    block = rh.get_block_by_height(current_block + 1)
                    if fetch_interval_seconds > average_block_time and fetch_interval_seconds > 1:
                        fetch_interval_seconds -= 0.5
                    block_time = block['block']['header']['time']
                    current_block_datetime = datetime.strptime(block_time[:26], '%Y-%m-%dT%H:%M:%S.%f')
                    if last_block_datetime:
                        block_time_deltas.append((current_block_datetime - last_block_datetime).total_seconds())
                        if len(block_time_deltas) > 10:
                            block_time_deltas.pop(0)
                        average_block_time = sum(block_time_deltas) / len(block_time_deltas)
                    last_block_datetime = current_block_datetime
                else:
                    fetch_interval_seconds += 0.5

            block_last_commits = block['block']['last_commit']['signatures']

            block_no = block['block']['header']['height']
            current_block = int(block_no)
            last_block = current_block - 1

            current_proposer = block['block']['header']['proposer_address']

            last_fetched_time = time()

        # Process (last) block committed signatures
        if current_block - processed_block:
            block_last_commits_json = json.dumps(block_last_commits)
            for v in all_validators:
                if v.hex_key not in block_last_commits_json:
                    block_buffer[v.hex_key].append(0)
                elif v.hex_key == last_proposer:
                    block_buffer[v.hex_key].append(2)
                else:
                    block_buffer[v.hex_key].append(1)

        # UI Stuff
        # Handle inputs/scroll
        c = stdscr.getch()
        curses.update_lines_cols()

        paging_y_offset, pad_height, y_scroll_limit = lh.refresh_y_limits(filtered_validators)
        if c == ord('s'):
            search_dialog = curses.newwin(3, 40, math.floor(curses.LINES/2) - 1, math.floor(curses.COLS/2) - 20)
            search_dialog.border()
        if c == ord('q'):
            exit()
        pad_y_scroll, scroll_indicator_y = lh.y_scroll(c, pad_y_scroll, y_scroll_limit, paging_y_offset)

        height = curses.LINES - 3; width = curses.COLS - 3
        pad_width = 205

        # Update screen
        lh.redraw_base_layout(stdscr, scroll_indicator_y, width, last_block, chain_id)
        stdscr.addstr(0, 20, str(fetch_interval_seconds))
        stdscr.addstr(0, 25, str(average_block_time))

        pad = curses.newpad(pad_height, pad_width)
        pad.erase()

        for i, v in enumerate(filtered_validators):
            if len(v.moniker) > 30:
                moniker = v.moniker[:26] + '...'
            else:
                moniker = v.moniker
            if v.key_assigned:
                pad.addstr(i, 6, moniker, curses.color_pair(4))
            else:
                pad.addstr(i, 6, moniker)
            
            pad.addstr(i, 1, str(i+1))
            pad.addstr(i, 6+30+9, v.hex_key)

            if v.soft_opt_out:
                pad.addstr(i, 38, f"{v.voting_power_percent:.2%}", curses.color_pair(5))
            else:
                pad.addstr(i, 38, f"{v.voting_power_percent:.2%}")
            
            if block_display_start_x + len(block_buffer[v.hex_key]) >= width:
                block_display_offset = (block_display_start_x + len(block_buffer[v.hex_key])) - width
            else:
                block_display_offset = 0
            for k in range(block_display_offset, len(block_buffer[v.hex_key])):
                if block_buffer[v.hex_key][k]:
                    if block_buffer[v.hex_key][k] == 2:
                        pad.addstr(i, block_display_start_x + k - block_display_offset, '■', curses.color_pair(3))
                    else:
                        pad.addstr(i, block_display_start_x + k - block_display_offset, '■', curses.color_pair(2))
                else:
                    pad.addstr(i, block_display_start_x + k - block_display_offset, '■', curses.color_pair(1))

        processed_block = current_block

        stdscr.refresh()
        pad.refresh(pad_y_scroll, 0, pad_begin_y, pad_begin_x, pad_begin_y + height, pad_begin_x + width)

        if (search_dialog is not None):
            curses.curs_set(1)
            search_dialog.refresh()
            curses.cbreak()
            curses.echo()
            s = search_dialog.getstr(1, 2)
            filtered_validators = [val for val in all_validators if s.decode() in val.moniker]
            if len(filtered_validators) < 1:
                filtered_validators = all_validators
            curses.noecho()
            curses.halfdelay(1)
            curses.curs_set(0)
            search_dialog = None


parser = ArgumentParser()
parser.add_argument('consumer_rpc_url', help='consumer chain RPC endpoint URL')
parser.add_argument('provider_rest_url', nargs='?', help='(optional) provider chain REST endpoint URL')
args = parser.parse_args()

rh.set_urls(args.consumer_rpc_url, args.provider_rest_url)

curses.wrapper(main)