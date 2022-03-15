import json
from web3 import Web3
from conbinPatch import Addition, addition_to_source, combine_bytecode
from utils import to_opcode

ganache_url = "http://127.0.0.1:7545"
web3 = Web3(Web3.HTTPProvider(ganache_url))
web3.eth.defaultAccount = web3.eth.accounts[0]

def deploy(abi, bytecode):
    Contract = web3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = Contract.constructor().transact()
    address = web3.eth.get_transaction_receipt(tx_hash)['contractAddress']
    return address

def combine_by_index(ls: list, _abi_bytecode) -> tuple:
    abi = _abi_bytecode[ls[0]][1]  # 取出第一个 abi
    source_temp = Addition(_abi_bytecode[ls[0]][2])
    source = addition_to_source(source_temp)
    for i in ls[1:]:
        abi += _abi_bytecode[i][1]
        addition = Addition(_abi_bytecode[i][2])
        source = combine_bytecode(source, addition)
    return abi, source.bytecode


abi_bytecode = [
    ['basicMath_v1',
     json.loads('[{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"times","outputs":[{"name":"err","type":"bool"},{"name":"res","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"dividedBy","outputs":[{"name":"err","type":"bool"},{"name":"i","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]'),
     '61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3007300000000000000000000000000000000000000003014606060405260043610610063576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff1680631d3b9edf14610068578063e39bbf68146100a8575b600080fd5b61008760048080359060200190919080359060200190919050506100e8565b60405180831515151581526020018281526020019250505060405180910390f35b6100c76004808035906020019091908035906020019091905050610116565b60405180831515151581526020018281526020019250505060405180910390f35b60008082840290508383820414831517600081146101055761010e565b60019250600091505b509250929050565b6000806000831560008114610132576001935060009250610149565b848604915060405182602082015260208101519350505b505092509290505600a165627a7a72305820ab750985aefc75fe78e2313324cc14fb62fa1023aa5c817fc686feb8f8731d1c0029'],
    ['basicMath_v2',
     json.loads('[{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"plus","outputs":[{"name":"err","type":"bool"},{"name":"res","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"minus","outputs":[{"name":"err","type":"bool"},{"name":"res","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]'),
     '61017d610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3007300000000000000000000000000000000000000003014606060405260043610610063576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff16806366098d4f14610068578063f4f3bdc1146100a8575b600080fd5b61008760048080359060200190919080359060200190919050506100e8565b60405180831515151581526020018281526020019250505060405180910390f35b6100c7600480803590602001909190803590602001909190505061011b565b60405180831515151581526020018281526020019250505060405180910390f35b6000808284019050828114838211178484830314166000811461010a57610113565b60019250600091505b509250929050565b6000808284039050600184821485831017858584011416146000811461014057610149565b60019250600091505b5092509290505600a165627a7a7230582033b5d8afbe2a18242836b975fbdc1191288b4cecef20f779e7ab377cc5b61d3b0029'],
    ["Address_087.sol",
     [{"inputs": [{"internalType": "address", "name": "target", "type": "address"}, {"internalType": "bytes", "name": "data", "type": "bytes"}], "name": "functionCall", "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}], "stateMutability": "nonpayable", "type": "function"}, {"inputs": [{"internalType": "address", "name": "target", "type": "address"}, {"internalType": "bytes", "name": "data", "type": "bytes"}, {"internalType": "uint256", "name": "value", "type": "uint256"}], "name": "functionCallWithValue", "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}], "stateMutability": "nonpayable", "type": "function"}, {"inputs": [{"internalType": "address", "name": "target", "type": "address"}, {"internalType": "bytes", "name": "data", "type": "bytes"}, {"internalType": "uint256", "name": "value", "type": "uint256"}, {"internalType": "string", "name": "errorMessage", "type": "string"}], "name": "functionCallWithValue", "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}], "stateMutability": "nonpayable", "type": "function"}, {"inputs": [{"internalType": "address", "name": "target", "type": "address"}, {"internalType": "bytes", "name": "data", "type": "bytes"}, {"internalType": "string", "name": "errorMessage", "type": "string"}], "name": "functionDelegateCall", "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}], "stateMutability": "nonpayable", "type": "function"}, {"inputs": [{"internalType": "address", "name": "target", "type": "address"}, {"internalType": "bytes", "name": "data", "type": "bytes"}], "name": "functionDelegateCall", "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}], "stateMutability": "nonpayable", "type": "function"}, {"inputs": [{"internalType": "address", "name": "target", "type": "address"}, {"internalType": "bytes", "name": "data", "type": "bytes"}], "name": "functionStaticCall", "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}], "stateMutability": "view", "type": "function"}, {"inputs": [{"internalType": "address", "name": "target", "type": "address"}, {"internalType": "bytes", "name": "data", "type": "bytes"}, {"internalType": "string", "name": "errorMessage", "type": "string"}], "name": "functionStaticCall", "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}], "stateMutability": "view", "type": "function"}, {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "isContract", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"}, {"inputs": [{"internalType": "bool", "name": "success", "type": "bool"}, {"internalType": "bytes", "name": "returndata", "type": "bytes"}, {"internalType": "string", "name": "errorMessage", "type": "string"}], "name": "verifyCallResult", "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}], "stateMutability": "pure", "type": "function"}],
     "608060405234801561001057600080fd5b5061090d806100206000396000f3fe608060405234801561001057600080fd5b50600436106100935760003560e01c8063a0b5ffb011610066578063a0b5ffb014610110578063c21d36f314610123578063d525ab8a14610136578063dbc40fb914610149578063ee33b7e21461015c57600080fd5b806316279055146100985780632a011594146100ca57806357387df0146100ea578063946b5793146100fd575b600080fd5b6100b56100a63660046105ea565b6001600160a01b03163b151590565b60405190151581526020015b60405180910390f35b6100dd6100d83660046106c7565b61016f565b6040516100c19190610809565b6100dd6100f8366004610653565b61019f565b6100dd61010b36600461079c565b610281565b6100dd61011e366004610605565b6102ba565b6100dd610131366004610605565b6102fc565b6100dd61014436600461071e565b610321565b6100dd610157366004610653565b610452565b6100dd61016a366004610605565b61050d565b606061019584848460405180606001604052806029815260200161086360299139610321565b90505b9392505050565b60606001600160a01b0384163b61020c5760405162461bcd60e51b815260206004820152602660248201527f416464726573733a2064656c65676174652063616c6c20746f206e6f6e2d636f6044820152651b9d1c9858dd60d21b60648201526084015b60405180910390fd5b600080856001600160a01b03168560405161022791906107ed565b600060405180830381855af49150503d8060008114610262576040519150601f19603f3d011682016040523d82523d6000602084013e610267565b606091505b5091509150610277828286610281565b9695505050505050565b60608315610290575081610198565b8251156102a05782518084602001fd5b8160405162461bcd60e51b81526004016102039190610809565b606061019883836040518060400160405280601e81526020017f416464726573733a206c6f772d6c6576656c2063616c6c206661696c65640000815250610532565b6060610198838360405180606001604052806025815260200161088c60259139610452565b6060824710156103825760405162461bcd60e51b815260206004820152602660248201527f416464726573733a20696e73756666696369656e742062616c616e636520666f6044820152651c8818d85b1b60d21b6064820152608401610203565b6001600160a01b0385163b6103d95760405162461bcd60e51b815260206004820152601d60248201527f416464726573733a2063616c6c20746f206e6f6e2d636f6e74726163740000006044820152606401610203565b600080866001600160a01b031685876040516103f591906107ed565b60006040518083038185875af1925050503d8060008114610432576040519150601f19603f3d011682016040523d82523d6000602084013e610437565b606091505b5091509150610447828286610281565b979650505050505050565b60606001600160a01b0384163b6104b75760405162461bcd60e51b8152602060048201526024808201527f416464726573733a207374617469632063616c6c20746f206e6f6e2d636f6e746044820152631c9858dd60e21b6064820152608401610203565b600080856001600160a01b0316856040516104d291906107ed565b600060405180830381855afa9150503d8060008114610262576040519150601f19603f3d011682016040523d82523d6000602084013e610267565b606061019883836040518060600160405280602781526020016108b16027913961019f565b60606101958484600085610321565b80356001600160a01b038116811461055857600080fd5b919050565b600082601f83011261056e57600080fd5b813567ffffffffffffffff808211156105895761058961084c565b604051601f8301601f19908116603f011681019082821181831017156105b1576105b161084c565b816040528381528660208588010111156105ca57600080fd5b836020870160208301376000602085830101528094505050505092915050565b6000602082840312156105fc57600080fd5b61019882610541565b6000806040838503121561061857600080fd5b61062183610541565b9150602083013567ffffffffffffffff81111561063d57600080fd5b6106498582860161055d565b9150509250929050565b60008060006060848603121561066857600080fd5b61067184610541565b9250602084013567ffffffffffffffff8082111561068e57600080fd5b61069a8783880161055d565b935060408601359150808211156106b057600080fd5b506106bd8682870161055d565b9150509250925092565b6000806000606084860312156106dc57600080fd5b6106e584610541565b9250602084013567ffffffffffffffff81111561070157600080fd5b61070d8682870161055d565b925050604084013590509250925092565b6000806000806080858703121561073457600080fd5b61073d85610541565b9350602085013567ffffffffffffffff8082111561075a57600080fd5b6107668883890161055d565b945060408701359350606087013591508082111561078357600080fd5b506107908782880161055d565b91505092959194509250565b6000806000606084860312156107b157600080fd5b8335801515811461067157600080fd5b600081518084526107d981602086016020860161081c565b601f01601f19169290920160200192915050565b600082516107ff81846020870161081c565b9190910192915050565b60208152600061019860208301846107c1565b60005b8381101561083757818101518382015260200161081f565b83811115610846576000848401525b50505050565b634e487b7160e01b600052604160045260246000fdfe416464726573733a206c6f772d6c6576656c2063616c6c20776974682076616c7565206661696c6564416464726573733a206c6f772d6c6576656c207374617469632063616c6c206661696c6564416464726573733a206c6f772d6c6576656c2064656c65676174652063616c6c206661696c6564a264697066735822122030acf2da5f17a465fccc5c7e6475a29f8db9ea48bb3b90d3d50d2d262b830c3964736f6c63430008070033"]
]

if __name__ == '__main__':
    res = combine_by_index([2], abi_bytecode)

    contractAddress = deploy(*res)

    contract = web3.eth.contract(address=contractAddress, abi=res[0])  # 创建一个合约
    # test-basicMath
    # print(contract.functions.times(2, 3).call())
    # print(contract.functions.dividedBy(16, 2).call())
    # print(contract.functions.plus(5, 5).call())
    # print(contract.functions.minus(18, 6).call())
