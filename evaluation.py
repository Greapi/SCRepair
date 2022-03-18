import random
from conbinPatch import Addition, addition_to_source, combine_bytecode, test_equivalence
from utils import Hex, to_opcode
import os
import csv
import opcodes as op
from solcx import compile_files
import json
from creatContract import combine_by_index, deploy, web3, abi_bytecode
import base64

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
                        min_trampoline_length = Hex('5')
                        while True:
                            curr_length = add.funs_impl.blength_by_line(start, jump_num)
                            if add.funs_impl[start][1] == op.jumpdest:  # 碰到基本块代表没有足够的划分空间
                                if _out:
                                    print('{} {}行 {}'.format(_file_path, i + 1, line[2:].strip()))
                                    add.funs_impl.print_by_line(start, jump_num)
                                raise OverflowError('没有足够的空间')
                            if (curr_length >= min_trampoline_length - Hex('1') and add.funs_impl[jump_num][
                                1] == op.jump) or \
                                    (curr_length >= min_trampoline_length - Hex('1') and add.funs_impl[jump_num + 1][
                                        1] == op.jumpdest) or \
                                    curr_length >= min_trampoline_length:
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
        min_trampoline_length = Hex('5')
        while True:
            curr_length = add.funs_impl.blength_by_line(start, jump_num)
            if add.funs_impl[start][1] == op.jumpdest:  # 碰到基本块代表没有足够的划分空间
                add.funs_impl.print_by_line(start, jump_num)
                print('~~~~~~~~~~~~~~~~~~~')
            if (curr_length >= min_trampoline_length - Hex('1') and add.funs_impl[jump_num][
                1] == op.jump) or \
                    (curr_length >= min_trampoline_length - Hex('1') and add.funs_impl[jump_num + 1][
                        1] == op.jumpdest) or \
                    curr_length >= min_trampoline_length:
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

def rand_int(length_uint: list[int, bool]) -> int:
    if length_uint[1]:
        limitation_max = 2**length_uint[0] - 1
        limitation_min = 0
    else:
        limitation_max = 2**(length_uint[0]-1) - 1
        limitation_min = -2**(length_uint[0]-1)
    return random.randint(limitation_min, limitation_max)

def rand_str(length=20) -> str:
    random_str = ''
    base_str = 'ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789'
    base_length = len(base_str) - 1
    for i in range(length):
        random_str += base_str[random.randint(0, base_length)]
    return random_str

def rand_byte(length=20) -> bytes:
    return random.randbytes(length)

def rand_base64(length=10) -> str:
    r_str = rand_str(length)
    bytes_r_str = r_str.encode("utf-8")
    base64_r_str = base64.b64encode(bytes_r_str).decode()
    return base64_r_str

def rand_addr(length=40) -> str:
    return '0xd2a5bC10698FD955D1Fe6cb468a17809A08fd005'

def rand_bytes_array(length=(15, 5)) -> list[bytes]:
    return [rand_byte(length[0]) for _ in range(length[1])]

def rand_int_array(length_uint=(15, 5, True)) -> list[int]:
    # length_uint[0::2] 取第一个和第三个参数
    return [rand_int(length_uint[0::2]) for _ in range(length_uint[1])]

def batch_test(combine_order: list, amount_per_fun=10):
    # 根据 abi 生成分析结果
    def analysis_abi(abi: list) -> list[list]:
        analysis_res = []
        for fun in abi:
            fun_name = fun['name']
            fun_inputs = list(map(lambda x: x['type'], fun['inputs']))
            # 将参数和函数合并
            analysis_res.append([fun_name, fun_inputs])
        return analysis_res

    # 根据函数名字与参数类型生成随机数
    def generate_para(fun: list[str, list]) -> list:
        type_func = {'int': rand_int, 'bytes': rand_byte, 'string': rand_str, 'base64': rand_base64,
                     'address': rand_addr, 'bytes[]': rand_bytes_array, 'int[]': rand_int_array}
        rand_params = []
        default_length = 15
        default_array_length = 5
        name, params_type = fun
        for param_type in params_type:
            if 'int' in param_type:
                # 对有符号与无符号整型的判断
                is_uint = True if 'uint' in param_type else False
                # 基本的对数组的判断
                suffix = param_type.replace('uint', '') if is_uint else param_type.replace('int', '')
                if '[]' in suffix:  # 是数组
                    curr_type = 'int[]'
                    suffix = suffix.replace('[]', '')
                    params = [int(suffix), default_array_length, is_uint]
                else:               # 不是数组
                    curr_type = 'int'
                    params = [int(suffix), is_uint]
                # 特殊函数
                if 'toHexString' in name:
                    params[0] = 10
            elif 'bytes' in param_type:
                suffix = param_type.replace('bytes', '')
                if '[]' in suffix:  # 是数组
                    curr_type = 'bytes[]'
                    suffix = suffix.replace('[]', '')
                    params = [int(suffix), default_array_length] if suffix != '' else [default_length, default_array_length]
                else:               # 不是数组
                    curr_type = 'bytes'
                    params = int(suffix) if suffix != '' else default_length
            elif 'string' in param_type:
                curr_type = param_type
                params = default_length
                if'decode' in name:
                    curr_type = 'base64'
                    params = default_length
            elif 'address' in param_type:
                curr_type = param_type
                params = 40
            else:
                raise TypeError("未知类型 {}".format(param_type))
            rand_params.append(type_func[curr_type].__call__(params))
        return rand_params
    # 部署合约
    lib = read_compiled_contract()
    # abi-字节
    combine_abiBytecode = combine_by_index(combine_order, lib)
    singles_abiBytecode = [[lib[i][1], lib[i][2]] for i in combine_order]
    # 部署地址
    combine_address = deploy(*combine_abiBytecode)
    singles_address = list(map(lambda x: deploy(*x), singles_abiBytecode))
    # 合约类
    combine_contract = web3.eth.contract(address=combine_address, abi=combine_abiBytecode[0])
    singles_addrAbi = list(zip(singles_address, map(lambda x: x[0], singles_abiBytecode)))
    singles_contract = list(map(lambda x: web3.eth.contract(address=x[0], abi=x[1]), singles_addrAbi))

    # ⑴ 遍历每一个单独的合约 ⑵ 构建随机的测试用例 ⑶ 分别对 com 和 single 测试, 并报告不同
    differences = []
    test_log = [['单例文件', '函数数目', '测试用例数目', '通过数目', '未通过数目']]
    for i, single_contract in enumerate(singles_contract):
        # 找出文件中所有函数, 其中每个函数结构 [函数名, [参数类型1, 参数类型2, ...]]
        funs_info = analysis_abi(single_contract.abi)
        file_name = lib[combine_order[i]][0]
        not_pass = 0
        for fun_info in funs_info:
            count = 0
            while count < amount_per_fun:
                paras = generate_para(fun_info)
                try:
                    com_res = getattr(combine_contract.functions, fun_info[0])(*paras).call()
                    sig_res = getattr(singles_contract[i].functions, fun_info[0])(*paras).call()
                    if com_res != sig_res:
                        # 名字-函数名-参数-com值-sig值
                        differences.append([file_name, fun_info[0], paras, com_res, sig_res])
                        not_pass += 1
                except:
                    try:
                        sig_res = getattr(singles_contract[i].functions, fun_info[0])(*paras).call()
                        differences.append([file_name, fun_info[0], paras, '无意义', sig_res])
                        not_pass += 1
                    except:
                        continue
                count += 1
        test_amount = len(funs_info) * amount_per_fun
        test_log.append([file_name, len(funs_info), test_amount, test_amount - not_pass, not_pass])

    test_log.append(['total',
                     sum(map(lambda x: x[1], test_log[1:])),
                     sum(map(lambda x: x[2], test_log[1:])),
                     sum(map(lambda x: x[3], test_log[1:])),
                     sum(map(lambda x: x[4], test_log[1:]))])

    if len(differences) > 0:
        for difference in differences:
            print("文件: {} 测试函数: {} 测试参数: {} 合并结果: {} 单例结果: {}".format(*difference))
        print('-'*100)

    for curr in test_log:
        print("{:<40} {:<20} {:<20} {:<20} {:<20}".format(*curr))

    return test_log


if __name__ == '__main__':
    pass
    # 批量测试划分模块是否正常
    # test_divider('valid_dataset')

    # 批量测试合并模块是否正常
    # test_combine('valid_dataset', False)

    # 测试批量编译模块
    update_compiled_contract()
    # print(*[[i, con] for i, con in enumerate(read_compiled_contract())], sep='\n')

    # 单次测试
    # res = combine_by_index([0, 1, 2, 3, 4, 5, 10, 11], read_compiled_contract())
    # contractAddress = deploy(*res)
    # # bytecode = '608060405234801561001057600080fd5b506103d9806100206000396000f30073000000000000000000000000000000000000000030146080604052600436106100355760003560e01c|68000000000000000356|565b600080fd5b61004d6100483660046101c9565b610063565b60405161005a919061027a565b60405180910390f35b606081516000141561008357505060408051602081019091526000815290565b600060405180606001604052806040815260200161035560409139905060006003845160026100b291906102cf565b6100bc91906102e7565b6100c7906004610309565b905060006100d68260206102cf565b67ffffffffffffffff8111156100ee576100ee61033e565b6040519080825280601f01601f191660200182016040528015610118576020820181803683370190505b509050818152600183018586518101602084015b81831015610184576003830192508251603f8160121c168501518253600182019150603f81600c1c168501518253600182019150603f8160061c168501518253600182019150603f811685015182535060010161012c565b60038951066001811461019e57600281146101af576101bb565b613d3d60f01b6001198301526101bb565b603d60f81b6000198301525b509398975050505050505050565b6000602082840312156101db57600080fd5b813567ffffffffffffffff808211156101f357600080fd5b818401915084601f83011261020757600080fd5b8135818111156102195761021961033e565b604051601f8201601f19908116603f011681019083821181831017156102415761024161033e565b8160405282815287602084870101111561025a57600080fd5b826020860160208301376000928101602001929092525095945050505050565b600060208083528351808285015260005b818110156102a75785810183015185820160400152820161028b565b818111156102b9576000604083870101525b50601f01601f1916929092016040019392505050565b600082198211156102e2576102e2610328565b500190565b60008261030457634e487b7160e01b600052601260045260246000fd5b500490565b600081600019048311821515161561032357610323610328565b500290565b634e487b7160e01b600052601160045260246000fd5b634e487b7160e01b600052604160045260246000fdfe|77|5b806312496a1b1461003a57603556a2646970667358221220f445f141227cd3210f57c2b91a0409e7af9909358857b0f676fa4929ab6fd44b64736f6c63430008070033'.replace('|', '')
    # # contractAddress = deploy(res[0], bytecode)
    # contract = web3.eth.contract(address=contractAddress, abi=res[0])
    # print(contract.functions.min(100, 2).call())
    # print(contract.functions.computeAddress('0x7465737400000000000000000000000000000000000000000000000000000000', '0x7465737400000000000000000000000000000000000000000000000000000000').call())
    # # print(list(map(lambda x: hex(ord(x)), contract.functions.decode('MzM=').call().decode())))
    # # print(contract.functions.encode(b'T*\x05\x0eM#a\xa9&\xc8').call())
    # # print(contract.functions.times(84007913129639935, 3332).call())

    # 批量测试
    test_list = [0, 1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13]
    test_res = batch_test(test_list, 50)
    csvName = 'testResult.csv'
    try:
        with open(csvName, 'a+', newline='', encoding='utf8') as csvFile:
            csvWriter = csv.writer(csvFile)
            csvWriter.writerow(['合并的文件: {}'.format(str(list(map(lambda x:x[0], test_res[1:-1]))))])
            csvWriter.writerows(test_res)
            csvWriter.writerow([])
    except:
        print("文件被占用")

    # 验证base64等价性
    # lib = read_compiled_contract()
    # source_temp = Addition(lib[1][2])
    # source = addition_to_source(source_temp)
    # addition = Addition(lib[2][2])
    # source = combine_bytecode(source, addition)
    # print(test_equivalence(source, addition))

    # 找到所有空间不足的基本块
    # for name, abi, bytecode in read_compiled_contract():
    #     print(name)
    #     find_not_enough_block(bytecode)
    #     print('---------------------')

    # 用于测试某个特定的合约
    # _constructor = '61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f300'
    # Addition(_constructor+'61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3006080604052600436106100435760003560e01c80633ccfd60b1461004f5780638da5cb5b1461006657806391fb54ca14610092578063f2fde38b146100b257600080fd5b3661004a57005b600080fd5b34801561005b57600080fd5b506100646100d2565b005b34801561007257600080fd5b50600054604080516001600160a01b039092168252519081900360200190f35b34801561009e57600080fd5b506100646100ad3660046103ad565b610142565b3480156100be57600080fd5b506100646100cd36600461038b565b610285565b6000546001600160a01b031633146101055760405162461bcd60e51b81526004016100fc90610479565b60405180910390fd5b600080546040516001600160a01b03909116914780156108fc02929091818181858888f1935050505015801561013f573d6000803e3d6000fd5b50565b6000546001600160a01b0316331461016c5760405162461bcd60e51b81526004016100fc90610479565b8051806101b25760405162461bcd60e51b81526020600482015260146024820152731059191c995cdcd95cc81b9bdd081c185cdcd95960621b60448201526064016100fc565b47806102005760405162461bcd60e51b815260206004820152601860248201527f5a65726f2062616c616e636520696e20636f6e7472616374000000000000000060448201526064016100fc565b600061020c83836104ae565b905060005b8381101561027e5784818151811061022b5761022b6104f9565b60200260200101516001600160a01b03166108fc839081150290604051600060405180830381858888f1935050505015801561026b573d6000803e3d6000fd5b5080610276816104d0565b915050610211565b5050505050565b6000546001600160a01b031633146102af5760405162461bcd60e51b81526004016100fc90610479565b6001600160a01b0381166103145760405162461bcd60e51b815260206004820152602660248201527f4f776e61626c653a206e6577206f776e657220697320746865207a65726f206160448201526564647265737360d01b60648201526084016100fc565b600080546040516001600160a01b03808516939216917f8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e091a3600080546001600160a01b0319166001600160a01b0392909216919091179055565b80356001600160a01b038116811461038657600080fd5b919050565b60006020828403121561039d57600080fd5b6103a68261036f565b9392505050565b600060208083850312156103c057600080fd5b823567ffffffffffffffff808211156103d857600080fd5b818501915085601f8301126103ec57600080fd5b8135818111156103fe576103fe61050f565b8060051b604051601f19603f830116810181811085821117156104235761042361050f565b604052828152858101935084860182860187018a101561044257600080fd5b600095505b8386101561046c576104588161036f565b855260019590950194938601938601610447565b5098975050505050505050565b6020808252818101527f4f776e61626c653a2063616c6c6572206973206e6f7420746865206f776e6572604082015260600190565b6000826104cb57634e487b7160e01b600052601260045260246000fd5b500490565b60006000198214156104f257634e487b7160e01b600052601160045260246000fd5b5060010190565b634e487b7160e01b600052603260045260246000fd5b634e487b7160e01b600052604160045260246000fdfea2646970667358221220594ba90ab1a8938f3f895b587b8a56160dd82a85f8823b4a95e1b9aec4a8a17964736f6c63430008070033')

    # 3
    # lib = read_compiled_contract()
    # t_bytecode = addition_to_source(Addition(lib[1][2])).bytecode
    # contractAddress = deploy(lib[1][1], t_bytecode)
    # contract = web3.eth.contract(address=contractAddress, abi=lib[1][1])
    # print(list(map(lambda x: hex(ord(x)), contract.functions.decode('M1Q=').call().decode())))
