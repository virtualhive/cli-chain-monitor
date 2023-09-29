import curses
import json
import urllib.request, urllib.parse
import math
from time import time
import re
import binascii
import hashlib


PROVIDER_REST_API = 'https://cosmos-lcd.easy2stake.com'
CONSUMER_RPC_API = 'https://rpc-neutron.cosmos-spaces.cloud/'


# necessary because curses is unable to determine width of flags and some other emojis
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0000269B\U0000FE0F"
    "]+"
)
AGENT_HEADER = 'cli-chain-monitor'

def strip_emoji(text):
    return EMOJI_PATTERN.sub(r'', text)


def get_provider_vals(stdscr):
    stdscr.addstr(2, 0, 'fetching provider validator info...')
    stdscr.refresh()
    request = urllib.request.Request(url=PROVIDER_REST_API + '/cosmos/staking/v1beta1/validators',
                                     headers={'User-Agent': AGENT_HEADER})
    res = urllib.request.urlopen(request)
    res_body = res.read()
    result = json.loads(res_body.decode('utf-8'))
    provider_vals = result['validators']

    page_key = result['pagination']['next_key']
    while (page_key is not None):
        request = urllib.request.Request(url=PROVIDER_REST_API + '/cosmos/staking/v1beta1/validators' + '?pagination.key=%s' % urllib.parse.quote(page_key),
                                     headers={'User-Agent': AGENT_HEADER})
        res = urllib.request.urlopen(request)
        res_body = res.read()
        result = json.loads(res_body.decode('utf-8'))
        provider_vals += result['validators']
        page_key = result['pagination']['next_key']

    return provider_vals

def get_consumer_vals(stdscr):
    stdscr.addstr(3, 0, 'fetching consumer validator info...')
    stdscr.refresh()
    request = urllib.request.Request(url=CONSUMER_RPC_API + '/validators' + '?per_page=100',
                                     headers={'User-Agent': AGENT_HEADER})
    res = urllib.request.urlopen(request)
    res_body = res.read()
    result = json.loads(res_body.decode('utf-8'))
    result_vals = result['result']['validators']

    page_entries_count = int(result['result']['count'])
    total_count = int(result['result']['total'])
    page_no = 1
    while (page_entries_count < total_count):
        page_no += 1
        request = urllib.request.Request(url=CONSUMER_RPC_API + '/validators' + '?per_page=100&page=%s' % page_no,
                                     headers={'User-Agent': AGENT_HEADER})
        res = urllib.request.urlopen(request)
        res_body = res.read()
        result = json.loads(res_body.decode('utf-8'))
        page_entries_count += int(result['result']['count'])
        result_vals += result['result']['validators']

    return result_vals

def get_chain_id(stdscr):
    stdscr.addstr(1, 0, 'fetching chain id...')
    stdscr.refresh()
    request = urllib.request.Request(url=CONSUMER_RPC_API + '/status',
                                     headers={'User-Agent': AGENT_HEADER})
    res = urllib.request.urlopen(request)
    res_body = res.read()
    result = json.loads(res_body.decode('utf-8'))
    network = result['result']['node_info']['network']
    return network

def get_block():
    request = urllib.request.Request(url=CONSUMER_RPC_API + '/block',
                                     headers={'User-Agent': AGENT_HEADER})
    res = urllib.request.urlopen(request)
    res_body = res.read()
    result = json.loads(res_body.decode('utf-8'))

    return result['result']


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


def main(stdscr):

    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    # Init screen and scroll
    curses.curs_set(0)
    curses.halfdelay(1)
    stdscr.clear()
    pad_y_scroll = 0
    pad_height = 100 # only used if empty valset
    scroll_percent = 0
    search_dialog = None
    paging_y_offset = 0

    stdscr.erase()
    stdscr.addstr(0, 0, 'initializing...')
    stdscr.refresh()

    chain_id = get_chain_id(stdscr)

    provider_validators = []
    if PROVIDER_REST_API is not None:
        provider_validators = get_provider_vals(stdscr)
    validators = get_consumer_vals(stdscr)
    buffer_vals = sorted(validators, key=lambda x: int(x['voting_power']), reverse=True)
    filtered_validators = sorted(validators, key=lambda x: int(x['voting_power']), reverse=True)

    # Init block and proposer stuff
    last_fetched_time = 0
    fetched_block = False
    block_buffer = dict()
    buffer_init = False
    current_block = 0
    processed_block = 0
    this_proposer = None
    next_proposer = None

    while True:
        curses.update_lines_cols()
        paging_y_offset, pad_height, y_scroll_limit = refresh_y_limits(filtered_validators)

        # handle inputs/scroll
        c = stdscr.getch()
        pad_y_scroll, scroll_indicator_y = y_scroll(c, pad_y_scroll, y_scroll_limit, paging_y_offset)
        if c == ord('s'):
            search_dialog = curses.newwin(3, 40, math.floor(curses.LINES/2) - 1, math.floor(curses.COLS/2) - 20)
            search_dialog.border()
        if c == ord('q'):
            exit()

        begin_x = 1; begin_y = 1
        height = curses.LINES - 3; width = curses.COLS - 3

        # fetch new block
        if (time() - last_fetched_time) > 4:
            this_proposer = next_proposer
            block = get_block()
            block_last_commits = block['block']['last_commit']['signatures']
            block_no = block['block']['header']['height']
            current_block = int(block_no)
            next_proposer = block['block']['header']['proposer_address']
            fetched_block = True
        if fetched_block:
            last_fetched_time = time()
            fetched_block = False

        if not buffer_init:
            for i in range(0, len(filtered_validators)):
                block_buffer[hashlib.sha256(binascii.a2b_base64(filtered_validators[i]['pub_key']['value'])).digest()[:20].hex().upper()] = []
            buffer_init = True


        stdscr.erase()
        stdscr.border()
        stdscr.addstr(0, int(curses.COLS/2) - 10, f"{scroll_percent:.0%}")
        stdscr.addstr(0, int(curses.COLS/2) + 5, str(scroll_indicator_y))
        stdscr.addstr(scroll_indicator_y, curses.COLS - 2, '█')
        stdscr.addstr(0, 0, block_no)
        stdscr.addstr(0, len(block_no) + 2, f"{chain_id}")
        pad = curses.newpad(pad_height, width)
        pad.erase()


        token_sum = 0
        for i in range(0, len(filtered_validators)):
            moniker_set = False
            is_diff_pubkey = False
            for k in range(0, len(provider_validators)):
                if (provider_validators[k]['consensus_pubkey']['key'] == filtered_validators[i]['pub_key']['value']):
                    if not moniker_set:
                        moniker = provider_validators[k]['description']['moniker']
                        moniker_set = True
                if (int(int(provider_validators[k]['tokens']) / 1000000) == int(filtered_validators[i]['voting_power'])):
                    if not moniker_set:
                        moniker = provider_validators[k]['description']['moniker']
                        moniker_set = True
                        is_diff_pubkey = True
            if not moniker_set:
                moniker = filtered_validators[i]['address']
            filtered_validators[i]['moniker'] = moniker
            if len(moniker) > 30:
                moniker = moniker[:26] + '...'
            if is_diff_pubkey:
                pad.addstr(i, 6, strip_emoji(moniker), curses.color_pair(4))
            else:
                pad.addstr(i, 6, strip_emoji(moniker))
            pad.addstr(i, 1, str(i+1))
            hex_pub_addr = hashlib.sha256(binascii.a2b_base64(filtered_validators[i]['pub_key']['value'])).digest()[:20].hex().upper()
            pad.addstr(i, 6+30+9, hex_pub_addr)
            if current_block - processed_block:
                if hex_pub_addr not in json.dumps(block_last_commits):
                    block_buffer[hex_pub_addr].append(0)
                elif hex_pub_addr == this_proposer:
                    block_buffer[hex_pub_addr].append(2)
                else:
                    block_buffer[hex_pub_addr].append(1)
            token_sum += int(filtered_validators[i]['voting_power'])

        processed_block = current_block


        cutoff_5_percent = token_sum * 0.05
        cutoff_sum = 0
        cutoff_index = 0
        for i in range(0, len(filtered_validators)):
            inverted_index = len(filtered_validators) - i - 1
            cutoff_sum += int(filtered_validators[inverted_index]['voting_power'])
            if cutoff_sum > cutoff_5_percent:
                cutoff_index = inverted_index
                break

        for i in range(0, len(filtered_validators)):
            if i > cutoff_index:
                pad.addstr(i, 38, f"{float(int(filtered_validators[i]['voting_power'])) / float(token_sum):.2%}", curses.color_pair(5))
            else:
                pad.addstr(i, 38, f"{float(int(filtered_validators[i]['voting_power'])) / float(token_sum):.2%}")
            hex_pub_addr = hashlib.sha256(binascii.a2b_base64(filtered_validators[i]['pub_key']['value'])).digest()[:20].hex().upper()
            buffered_block_count = len(block_buffer[hex_pub_addr])
            for k in range(0, buffered_block_count):
                if block_buffer[hex_pub_addr][k]:
                    if block_buffer[hex_pub_addr][k] == 2:
                        pad.addstr(i, 6+30+9+60+k, '■', curses.color_pair(3))
                    else:
                        pad.addstr(i, 6+30+9+60+k, '■', curses.color_pair(2))
                else:
                    pad.addstr(i, 6+30+9+60+k, '■', curses.color_pair(1))

        stdscr.refresh()
        pad.refresh(pad_y_scroll, 0, begin_y, begin_x, begin_y + height, begin_x + width)
        if (search_dialog is not None):
            curses.curs_set(1)
            search_dialog.refresh()
            curses.cbreak()
            curses.echo()
            s = search_dialog.getstr(1, 2)
            filtered_validators = [val for val in buffer_vals if s.decode() in val['moniker']]
            if len(filtered_validators) < 1:
                filtered_validators = buffer_vals
            curses.noecho()
            curses.halfdelay(1)
            curses.curs_set(0)
            search_dialog = None

curses.wrapper(main)