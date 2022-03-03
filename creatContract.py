import json
from web3 import Web3
from conbinPatch import Addition, addition_to_source, combine_bytecode

ganache_url = "http://127.0.0.1:7545"
web3 = Web3(Web3.HTTPProvider(ganache_url))
web3.eth.defaultAccount = web3.eth.accounts[0]

def deploy(abi, bytecode):
    Contract = web3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = Contract.constructor().transact()
    address = web3.eth.get_transaction_receipt(tx_hash)['contractAddress']
    return address

def combine_by_index(ls: list) -> tuple:
    global abi_bytecode
    abi = abi_bytecode[ls[0]][0]  # 取出第一个 abi
    source_temp = Addition(abi_bytecode[ls[0]][1])
    source = addition_to_source(source_temp)
    for i in ls[1:]:
        abi += abi_bytecode[i][0]
        addition = Addition(abi_bytecode[i][1])
        source = combine_bytecode(source, addition)
    return abi, source.bytecode


abi_bytecode = [
    # basicMath_v1
    [json.loads('[{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"times","outputs":[{"name":"err","type":"bool"},{"name":"res","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"dividedBy","outputs":[{"name":"err","type":"bool"},{"name":"i","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]'),
     '61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3007300000000000000000000000000000000000000003014606060405260043610610063576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff1680631d3b9edf14610068578063e39bbf68146100a8575b600080fd5b61008760048080359060200190919080359060200190919050506100e8565b60405180831515151581526020018281526020019250505060405180910390f35b6100c76004808035906020019091908035906020019091905050610116565b60405180831515151581526020018281526020019250505060405180910390f35b60008082840290508383820414831517600081146101055761010e565b60019250600091505b509250929050565b6000806000831560008114610132576001935060009250610149565b848604915060405182602082015260208101519350505b505092509290505600a165627a7a72305820ab750985aefc75fe78e2313324cc14fb62fa1023aa5c817fc686feb8f8731d1c0029'],
    # basicMath_v2
    [json.loads('[{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"plus","outputs":[{"name":"err","type":"bool"},{"name":"res","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"minus","outputs":[{"name":"err","type":"bool"},{"name":"res","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]'),
     '61017d610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3007300000000000000000000000000000000000000003014606060405260043610610063576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff16806366098d4f14610068578063f4f3bdc1146100a8575b600080fd5b61008760048080359060200190919080359060200190919050506100e8565b60405180831515151581526020018281526020019250505060405180910390f35b6100c7600480803590602001909190803590602001909190505061011b565b60405180831515151581526020018281526020019250505060405180910390f35b6000808284019050828114838211178484830314166000811461010a57610113565b60019250600091505b509250929050565b6000808284039050600184821485831017858584011416146000811461014057610149565b60019250600091505b5092509290505600a165627a7a7230582033b5d8afbe2a18242836b975fbdc1191288b4cecef20f779e7ab377cc5b61d3b0029']
]

if __name__ == '__main__':
    res = combine_by_index([0, 1])

    contractAddress = deploy(*res)

    contract = web3.eth.contract(address=contractAddress, abi=res[0])  # 创建一个合约
    # test-basicMath
    # print(contract.functions.times(2, 3).call())
    # print(contract.functions.dividedBy(16, 2).call())
    # print(contract.functions.plus(5, 5).call())
    # print(contract.functions.minus(18, 6).call())
