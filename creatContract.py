import json
from web3 import Web3

ganache_url = "http://127.0.0.1:7545"
web3 = Web3(Web3.HTTPProvider(ganache_url))
web3.eth.defaultAccount = web3.eth.accounts[0]

def deploy(abi, bytecode):
    Contract = web3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = Contract.constructor().transact()
    print(type(Contract))

abi = json.loads('[{"constant":true,"inputs":[{"name":"a","type":"uint256"}],"name":"add1","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"num","type":"uint256"}],"name":"double","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]')
bytecode = '608060405234801561001057600080fd5b506100d9806100206000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041667000000000000009f565b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b6001019056005b3460b7565b57600080fd5b5060586100c2565b565b60408051918252519081900360200190f35b60ce565b56005b63a836572881146043578063eee9720614607157603e565b8015604e602e016076565b600435606a602e016084565b60020290602e01609c56'
# deploy(abi, bytecode)

contractAddress = '0xc770A7c6c15309B8fd5a0Bb0C0c58990E30363c5'
contract = web3.eth.contract(address=contractAddress, abi=abi)  # 创建一个合约
a = contract.functions.double(2).call()      # 当无需 gas 时直接使用 call 即可读取
print(a)

