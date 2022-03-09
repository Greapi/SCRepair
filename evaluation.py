from conbinPatch import Addition
from utils import Hex, to_opcode
import os
import csv
import opcodes as op
from solcx import compile_files
import json
from creatContract import combine_by_index, deploy, web3, abi_bytecode

def is_push(opcode: str) -> bool:
    opcode_dec = int(opcode, 16)
    return int('60', 16) <= opcode_dec <= int('7F', 16)

def save_valid_file(path: str, out_path: str):
    def is_valid(bytecode: str) -> bool:
        try:
            int(bytecode[-4::], 16)
        except ValueError:
            return False
        cbor_ending_length = int(bytecode[-4::], 16) * 2 + 4
        start = bytecode[len(bytecode) - cbor_ending_length:len(bytecode) - cbor_ending_length + 2]
        if (bytecode[-4::] == '0033' or bytecode[-4::] == '0029') and \
                (start == 'a1' or start == 'a2' or start == 'a3' or start == 'a4'):
            return True
        return False

    def csv_writer(csv_name: str, content: list):
        try:
            with open(csv_name, 'w', newline='', encoding='utf8') as csvFile:
                csvWriter = csv.writer(csvFile)
                csvWriter.writerows(content)
        except:
            print("文件被占用")

    if os.path.isfile(path):
        is_file = True
    elif os.path.isdir(path):
        is_file = False
    else:
        raise FileNotFoundError("文件/文件夹不存在")

    if is_file:
        valid_list = list()
        file = open(path, 'r', encoding='utf8')
        for line in file.readlines():
            if is_valid(line.strip()):
                valid_list.append([line.strip()])
        file_name = os.path.split(path)[-1]
        name = os.path.join(out_path, "valid_" + file_name)
        csv_writer(name, valid_list)
    else:
        for root, dirs, files in os.walk(path):
            for file_name in files:
                file = open(os.path.join(root, file_name), 'r', encoding='utf8')
                valid_list = list()
                for line in file.readlines():
                    if is_valid(line.strip()):
                        valid_list.append([line.strip()])
                name = os.path.join(out_path, "valid_" + file_name)
                csv_writer(name, valid_list)


def test_divider(file_folder: str):
    if os.path.isfile(file_folder):
        is_file = True
    elif os.path.isdir(file_folder):
        is_file = False
    else:
        raise FileNotFoundError("文件/文件夹不存在")

    def _test(_file_path: str):
        counter_true = counter_false = 0
        constructor = '61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f300'
        file = open(_file_path, 'r', encoding='utf8')
        for i, line in enumerate(file.readlines()):
            if line.startswith('0x'):
                try:
                    Addition(constructor + line[2:].strip())
                    counter_true += 1
                except:
                    print('{} {}行 {}'.format(_file_path, i + 1, line[2:].strip()))
                    counter_false += 1
        print('---------------------------------')
        return counter_true, counter_false

    counter_t = counter_f = 0
    if is_file:
        counter_t, counter_f = _test(file_folder)
    else:
        for root, dirs, files in os.walk(file_folder):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                temp = _test(file_path)
                counter_t += temp[0]
                counter_f += temp[1]
    print("总计: {} 成功: {} 失败: {}".format(counter_t + counter_f, counter_t, counter_f))


def test_combine(file_folder: str, out=True):
    if os.path.isfile(file_folder):
        is_file = True
    elif os.path.isdir(file_folder):
        is_file = False
    else:
        raise FileNotFoundError("文件/文件夹不存在")

    def _test(_file_path: str, _out):
        counter_true = counter_false = 0
        constructor = '61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f300'
        file = open(_file_path, 'r', encoding='utf8')
        for i, line in enumerate(file.readlines()):
            if line.startswith('0x'):
                try:
                    add = Addition(constructor + line[2:].strip())
                    # 找到新合约 funs_impl 中所有 jump(i) 的行号
                    jump_nums = list()
                    for _i, opcode in enumerate(add.funs_impl):
                        if opcode[1] == op.jump or opcode[1] == op.jumpi:
                            jump_nums.append(_i)
                    for jump_num in jump_nums:
                        start = jump_num
                        # 采用 CGF 的方案, 对 jump(i) 的上一行判断
                        opcode = add.funs_impl[jump_num - 1][1]
                        operand = add.funs_impl[jump_num - 1][2]
                        if is_push(opcode) and Hex(len(operand) // 2) >= Hex('2'):  # 大于两个字节
                            continue
                        # 找到填充蹦床的起始位置 start
                        min_trampoline_length = Hex('4')
                        while True:
                            curr_length = add.funs_impl.blength_by_line(start, jump_num)
                            if add.funs_impl[start][1] == op.jumpdest:  # 碰到基本块代表没有足够的划分空间
                                if _out:
                                    print('{} {}行 {}'.format(_file_path, i + 1, line[2:].strip()))
                                    add.funs_impl.print_by_line(start, jump_num)
                                raise OverflowError('没有足够的空间')
                            if curr_length >= min_trampoline_length:
                                break
                            start -= 1
                    counter_true += 1
                except OverflowError:
                    counter_false += 1
                except IndexError:
                    pass

        return counter_true, counter_false

    counter_t = counter_f = 0
    if is_file:
        counter_t, counter_f = _test(file_folder, out)
    else:
        for root, dirs, files in os.walk(file_folder):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                temp = _test(file_path, out)
                counter_t += temp[0]
                counter_f += temp[1]

    print("总计: {} 成功: {} 失败: {}".format(counter_t + counter_f, counter_t, counter_f))

def find_not_enough_block(_contract: str):
    add = Addition(_contract)
    # 找到新合约 funs_impl 中所有 jump(i) 的行号
    jump_nums = list()
    for _i, opcode in enumerate(add.funs_impl):
        if opcode[1] == op.jump or opcode[1] == op.jumpi:
            jump_nums.append(_i)
    for jump_num in jump_nums:
        start = jump_num
        # 采用 CGF 的方案, 对 jump(i) 的上一行判断
        opcode = add.funs_impl[jump_num - 1][1]
        operand = add.funs_impl[jump_num - 1][2]
        if is_push(opcode) and Hex(len(operand) // 2) >= Hex('2'):  # 大于两个字节
            continue
        # 找到填充蹦床的起始位置 start
        min_trampoline_length = Hex('4')
        while True:
            curr_length = add.funs_impl.blength_by_line(start, jump_num)
            if add.funs_impl[start][1] == op.jumpdest:  # 碰到基本块代表没有足够的划分空间
                add.funs_impl.print_by_line(start, jump_num+1)
                print('~~~~~~~~~~~~~~~~~')
            if curr_length >= min_trampoline_length:
                break
            start -= 1

def compile_contract(folder: str) -> list:
    os.path.isdir(folder)
    match = {'0425': '0.4.25', '087': '0.8.7', '0810': '0.8.10'}
    out_list = []
    for root, dirs, files in os.walk(folder):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            pre = os.path.splitext(file_name)[0]
            version = match[pre.split('_')[-1]]
            compiled = compile_files([file_path], output_values=["abi", "bin"], solc_version=version,
                                     optimize=True, optimize_runs=200)
            items = compiled.popitem()[1]
            out_list.append([file_name, items['abi'], items['bin']])

    out_list.sort(key=lambda x: x[0])

    return out_list

def update_compiled_contract():
    compiled_contract = compile_contract('test_contract')
    with open('compileContract.txt', 'w', encoding='utf8') as f:
        f.write(json.dumps(compiled_contract))

def read_compiled_contract() -> list:
    with open('compileContract.txt', 'r', encoding='utf8') as f:
        return json.loads(f.read())


if __name__ == '__main__':
    pass
    # 批量测试划分模块是否正常
    # test_divider('valid_dataset')

    # 批量测试合并模块是否正常
    # test_combine('valid_dataset', False)

    # 测试批量编译模块
    update_compiled_contract()
    # print(*read_compiled_contract(), sep='\n')

    # 测试实际存在的库合约
    # res = combine_by_index([13, 14], read_compiled_contract())
    # contractAddress = deploy(*res)
    # contract = web3.eth.contract(address=contractAddress, abi=res[0])
    # print(contract.functions.tryAdd(2, 3).call())
    # print(contract.functions.average(5, 7).call())

    # 找到所有空间不足的基本块
    for name, abi, bytecode in read_compiled_contract():
        print(name)
        find_not_enough_block(bytecode)
        print('---------------------')

    # 用于测试某个特定的合约
    # _constructor = '61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f300'
    # Addition(_constructor+'61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3006080604052600436106100435760003560e01c80633ccfd60b1461004f5780638da5cb5b1461006657806391fb54ca14610092578063f2fde38b146100b257600080fd5b3661004a57005b600080fd5b34801561005b57600080fd5b506100646100d2565b005b34801561007257600080fd5b50600054604080516001600160a01b039092168252519081900360200190f35b34801561009e57600080fd5b506100646100ad3660046103ad565b610142565b3480156100be57600080fd5b506100646100cd36600461038b565b610285565b6000546001600160a01b031633146101055760405162461bcd60e51b81526004016100fc90610479565b60405180910390fd5b600080546040516001600160a01b03909116914780156108fc02929091818181858888f1935050505015801561013f573d6000803e3d6000fd5b50565b6000546001600160a01b0316331461016c5760405162461bcd60e51b81526004016100fc90610479565b8051806101b25760405162461bcd60e51b81526020600482015260146024820152731059191c995cdcd95cc81b9bdd081c185cdcd95960621b60448201526064016100fc565b47806102005760405162461bcd60e51b815260206004820152601860248201527f5a65726f2062616c616e636520696e20636f6e7472616374000000000000000060448201526064016100fc565b600061020c83836104ae565b905060005b8381101561027e5784818151811061022b5761022b6104f9565b60200260200101516001600160a01b03166108fc839081150290604051600060405180830381858888f1935050505015801561026b573d6000803e3d6000fd5b5080610276816104d0565b915050610211565b5050505050565b6000546001600160a01b031633146102af5760405162461bcd60e51b81526004016100fc90610479565b6001600160a01b0381166103145760405162461bcd60e51b815260206004820152602660248201527f4f776e61626c653a206e6577206f776e657220697320746865207a65726f206160448201526564647265737360d01b60648201526084016100fc565b600080546040516001600160a01b03808516939216917f8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e091a3600080546001600160a01b0319166001600160a01b0392909216919091179055565b80356001600160a01b038116811461038657600080fd5b919050565b60006020828403121561039d57600080fd5b6103a68261036f565b9392505050565b600060208083850312156103c057600080fd5b823567ffffffffffffffff808211156103d857600080fd5b818501915085601f8301126103ec57600080fd5b8135818111156103fe576103fe61050f565b8060051b604051601f19603f830116810181811085821117156104235761042361050f565b604052828152858101935084860182860187018a101561044257600080fd5b600095505b8386101561046c576104588161036f565b855260019590950194938601938601610447565b5098975050505050505050565b6020808252818101527f4f776e61626c653a2063616c6c6572206973206e6f7420746865206f776e6572604082015260600190565b6000826104cb57634e487b7160e01b600052601260045260246000fd5b500490565b60006000198214156104f257634e487b7160e01b600052601160045260246000fd5b5060010190565b634e487b7160e01b600052603260045260246000fd5b634e487b7160e01b600052604160045260246000fdfea2646970667358221220594ba90ab1a8938f3f895b587b8a56160dd82a85f8823b4a95e1b9aec4a8a17964736f6c63430008070033')
