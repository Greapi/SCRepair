import copy
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
    # add1
    [json.loads('[{"inputs":[{"internalType":"uint256","name":"a","type":"uint256"}],"name":"add1","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"pure","type":"function"}]'),
     '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663a836572881146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600101905600a165627a7a723058201b5930ac885210ff114b55848f959850c81886c515ec221eb475490f85e319a50029'],
    # double
    [json.loads('[{"constant":true,"inputs":[{"name":"num","type":"uint256"}],"name":"double","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]'),
     '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663eee9720681146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600202905600a165627a7a72305820f3a6ecd64c261907682d5ce13a40341199a16032194121592a8017e6692158de0029'],
    # fibonacci
    [json.loads('[{"constant":false,"inputs":[{"name":"start","type":"uint256"},{"name":"n","type":"uint256"}],"name":"fibonacci","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"nonpayable","type":"function"}]'),
     '608060405234801561001057600080fd5b5060fa8061001f6000396000f300608060405260043610603f576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff168063421ec765146044575b600080fd5b348015604f57600080fd5b5060766004803603810190808035906020019092919080359060200190929190505050608c565b6040518082815260200191505060405180910390f35b600080821415609c5782905060c8565b600182141560ae5760018301905060c8565b60b98360028403608c565b60c48460018503608c565b0190505b929150505600a165627a7a7230582081833e4b1d50f6135747f882ff694aa69db1bebe74d2f47eee08eaa7debf9c850029']
]

abi = json.loads('[{"constant":false,"inputs":[{"name":"start","type":"uint256"},{"name":"n","type":"uint256"}],"name":"fibonacci","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"name":"a","type":"uint256"}],"name":"add1","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"num","type":"uint256"}],"name":"double","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]')
bytecode = '608060405234801561001057600080fd5b506101dd806100206000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041667000000000000013a565b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b6001019056005b348015607c57600080fd5b5060586004356098565b60408051918252519081900360200190f35b61009f565b005b60020290602e0156609d565b34801560b657600080fd5b50605b60043560243560d5565b60408051918252519081900360200190f35b600081151560e357610115565b5b816001141560f457506001610121565b5b6097836002840360d5565b60a2846001850360d5565b0190505b61012d565b005b508160a66068015660e2565b820160a66068015660f3565b9291505060680156610113565b63a836572881146043578063eee97206146071578063421ec7651460ab57603e56a165627a7a723058201b5930ac885210ff114b55848f959850c81886c515ec221eb475490f85e319a50029a165627a7a72305820f3a6ecd64c261907682d5ce13a40341199a16032194121592a8017e6692158de0029a165627a7a72305820924e3776cadabeb78157c4953a03fef645eca8938de0cd5d40b5cdb2b23c24410029'

# res = combine_by_index([0, 1, 2])

contractAddress = deploy(abi, bytecode)

contract = web3.eth.contract(address=contractAddress, abi=abi)  # 创建一个合约
a = contract.functions.double(2).call()      # 当无需 gas 时直接使用 call 即可读取
b = contract.functions.add1(2).call()
c = contract.functions.fibonacci(0, 7).call()
print(a, b, c)

