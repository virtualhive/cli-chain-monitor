import urllib.request, urllib.parse
import json

AGENT_HEADER = 'cli-chain-monitor'
CONSUMER_RPC_API = None
PROVIDER_REST_API = None

def set_urls(consumer_rpc_url, provider_rest_url):
    global CONSUMER_RPC_API
    global PROVIDER_REST_API
    if CONSUMER_RPC_API is None:
        CONSUMER_RPC_API = consumer_rpc_url
    if PROVIDER_REST_API is None:
        PROVIDER_REST_API = provider_rest_url

def get_provider_vals():
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

    provider_validators = [v for v in provider_vals if v['status'] == 'BOND_STATUS_BONDED']

    return provider_validators

def get_consumer_vals():
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

def get_chain_id():
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

def get_block_by_height(height: int):
    request = urllib.request.Request(url=CONSUMER_RPC_API + f"/block?height={height}",
                                     headers={'User-Agent': AGENT_HEADER})
    res = urllib.request.urlopen(request)
    res_body = res.read()
    result = json.loads(res_body.decode('utf-8'))

    return result['result']