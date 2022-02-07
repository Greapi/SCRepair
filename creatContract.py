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
    # fibonacci 0.4.25 0.5.0 0.6.0 0.7.0 开优化200
    [json.loads('[{"constant":false,"inputs":[{"name":"start","type":"uint256"},{"name":"n","type":"uint256"}],"name":"fibonacci","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"nonpayable","type":"function"}]'),
     '608060405234801561001057600080fd5b5060d28061001f6000396000f3fe6080604052348015600f57600080fd5b506004361060285760003560e01c8063421ec76514602d575b600080fd5b604d60048036036040811015604157600080fd5b5080359060200135605f565b60408051918252519081900360200190f35b600081606b5750816096565b8160011415607c5750600182016096565b60878360028403605f565b60928460018503605f565b0190505b9291505056fea2646970667358221220483dea6b833aff37591a132d1f07d64351a7443c3e5352291700acad7bcf926a64736f6c63430007000033'],
    # sqrt
    [json.loads('[{"inputs":[{"internalType":"uint256","name":"y","type":"uint256"}],"name":"sqrt","outputs":[{"internalType":"uint256","name":"z","type":"uint256"}],"stateMutability":"pure","type":"function"}]'),
     '608060405234801561001057600080fd5b5060e98061001f6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663677342ce81146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600080600383111560ad5750819050600160028204015b8181101560a9578091506002818285811515609857fe5b040181151560a257fe5b0490506081565b60b7565b821560b757600191505b509190505600a165627a7a723058202e71fd1835416cee731e478d74eaca6168d776ab062d936c747d0f7a6b07c7a40029']
]

res = combine_by_index([3, 2])

contractAddress = deploy(*res)

contract = web3.eth.contract(address=contractAddress, abi=res[0])  # 创建一个合约
# print(contract.functions.add1(2).call())
# print(contract.functions.double(2).call())      # 当无需 gas 时直接使用 call 即可读取
print(contract.functions.fibonacci(0, 7).call())
print(contract.functions.sqrt(5).call())

