from evmdasm import EvmBytecode
import math
import queue
from utils import Hex, to_opcode

# 处理划分出的功能块
class BasicPart:
    def __init__(self, start=0, end=0, bytecode='', base=0, create_mode=0):
        if create_mode == 0:
            # 该功能块的绝对偏移的基址
            self.base = Hex(base)
            # 该功能块相较于合约字节码的偏移
            self.start = Hex(start // 2)
            self.end = Hex(end // 2)
            self.length = Hex((end - start) // 2)
            # 源代码与当前功能块的代码
            self.source_bytecode = bytecode
            self.bytecode = bytecode[start:end]
        elif create_mode == 1:
            self.base = Hex('0')
            self.start = Hex('0')
            self.end = Hex('0')
            self.length = Hex(len(bytecode) // 2)
            self.source_bytecode = bytecode
            self.bytecode = bytecode
        else:
            raise TypeError

    # 以绝对字节位置索引操作码以及操作数
    def __getitem__(self, item):
        # 获得字符串对应下标
        if type(item) == str:
            i = int(item, 16) * 2
        elif type(item) == Hex:
            i = item.num * 2
        else:
            raise TypeError
        # 获得当前操作字节码十进制表示
        curr = int(self.bytecode[i:i + 2], 16)
        # 处理当为 PUSH 时的情况
        inc = 2
        if int('60', 16) <= curr <= int('7F', 16):
            inc += (curr - int('60', 16) + 1) * 2
        op = EvmBytecode(self.bytecode[i:i + inc]).disassemble().as_string
        return '[{}] [{}] {}'.format(hex(self.base.num + i // 2), hex(i // 2), op)

    # 以相对字节位置替换一句操作码
    def __setitem__(self, key, value: str):
        if type(key) == Hex:
            i = int(key.hex_str, 16) * 2
        elif type(key) == str:
            i = int(key, 16) * 2  # 计算下标
        else:
            raise TypeError
        curr = int(self.bytecode[i:i + 2], 16)  # 获得字节码
        inc = 2
        if int('60', 16) <= curr <= int('7F', 16):  # 处理 PUSH 情况
            inc += (curr - int('60', 16) + 1) * 2
        op = EvmBytecode(self.bytecode[i:i + inc]).disassemble().as_string
        self.bytecode = self.bytecode[0:i] + value + self.bytecode[i + inc::]
        op_c = EvmBytecode(value).disassemble().as_string
        print('[{}] [{}] {} --> {}\n'.format(hex(self.base.num + i // 2), hex(i // 2), op, op_c))

    def __len__(self):
        return self.length.num

    @property
    def opcode(self):
        return to_opcode(self.bytecode, self.base)

    # 以相对字节位置替换一段操作码
    def replace(self, start: Hex, length: Hex, content: str):
        end = start + length
        self.bytecode = self.bytecode[0:start.num * 2] + content + self.bytecode[end.num * 2::]


# 用于处理字节码
class BytecodeAnalysis:
    def __init__(self, bytecode: str):
        self.bytecode = bytecode
        self.constructor = BasicPart()  # 构造函数
        self.fallback_selector = BasicPart()  # 回调函数选择子
        self.funs_selector = BasicPart()  # 函数选择子
        self.fallback_imp = BasicPart()  # 回调函数实现
        self.funs_imp = BasicPart()  # 函数实现
        self.log = BasicPart()  # 日志
        self.middle = BasicPart()  # 中间部分

        # 初始化
        self.divider()

    # 迭代划分后的结果
    def __iter__(self):
        return iter([self.constructor, self.fallback_selector, self.funs_selector, self.fallback_imp, self.funs_imp,
                     self.log])

    # 将功能块按顺序从0开始排序，使用排序下标索引功能块
    def __getitem__(self, item: int):
        parts = [self.constructor, self.fallback_selector, self.funs_selector, self.fallback_imp, self.funs_imp,
                 self.log]
        return parts[item]

    # 将字节码拆分为功能块
    def divider(self):
        def match(bytecode: str) -> bool:
            j = 0
            ops = []
            while j < len(bytecode):
                _inc = 2
                ops.append(bytecode[j:j + 2])
                _op = int(bytecode[j:j + 2], 16)
                if int('60', 16) <= _op <= int('7F', 16):
                    _inc += (_op - int('60', 16) + 1) * 2
                j += _inc
            if len(ops) >= 2 and not (int('60', 16) <= int(ops[-2], 16) <= int('7F', 16)):  # 倒数第二个必须是 PUSH
                return False
            ops = ops[0:-2] + ops[-1::]  # 去除倒数第二个
            return ops == ['63', '14', '57'] or ops == ['63', '81', '14', '57']

        constructor = fallback_selector = funs_selector = fallback_imp = funs_imp = log = [0, 0]
        bc = self.bytecode
        i, j = 0, 0
        part = 0
        while j < len(self.bytecode):
            inc = 2
            # 拆分出 constructor
            if part == 0:
                if bc[j:j + 2] == '00' or bc[j:j + 2] == 'fe':  # |STOP(0x00)| 或者 |0xfe|
                    constructor = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分出 fallback selector
            if part == 1:
                if match(bc[j + 2:j + 22]) or match(bc[j + 2:j + 24]):  # |PUSH4 EQ PUSH? JUMPI| 或者 |PUSH4 DUP2 EQ PUSH? JUMPI|
                    fallback_selector = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分出 fun selector
            if part == 2:
                if bc[j:j + 4] == '575b' or bc[j:j + 4] == '565b':  # |JUMPI| JUMPDEST 或者 |JUMP| JUMPDEST
                    funs_selector = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分出 fallback impl
            if part == 3:
                if bc[j:j + 2] == 'fd':  # |REVERT|
                    fallback_imp = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分出 funs impl 和 log
            if part == 4:
                if bc[j:j + 2] == '00' or bc[j:j + 2] == 'fe':  # |STOP(0x00)| 或者 |0xfe|
                    funs_imp = [i, j + 2]
                    i = j + 2
                    part += 1
                    log = [i, len(bc)]

            op = int(bc[j:j + 2], 16)
            if int('60', 16) <= op <= int('7F', 16):
                inc += (op - int('60', 16) + 1) * 2
            j += inc

        if constructor == [0, 0] or fallback_selector == [0, 0] or funs_selector == [0, 0] or \
                fallback_imp == [0, 0] or funs_imp == [0, 0]:
            raise TypeError

        self.constructor = BasicPart(constructor[0], constructor[1], self.bytecode, 0)
        base = 0
        self.fallback_selector = BasicPart(fallback_selector[0], fallback_selector[1], bc, base)
        base += len(self.fallback_selector)
        self.funs_selector = BasicPart(funs_selector[0], funs_selector[1], bc, base)
        base += len(self.funs_selector)
        self.fallback_imp = BasicPart(fallback_imp[0], fallback_imp[1], bc, base)
        base += len(self.fallback_imp)
        self.funs_imp = BasicPart(funs_imp[0], funs_imp[1], bc, base)
        base += len(self.funs_imp)
        self.log = BasicPart(log[0], log[1], bc, base)
        self.middle = BasicPart(fallback_selector[0], funs_imp[1], bc, 0)

    # 以绝对字节位置替换一句操作码
    def __setitem__(self, key: Hex, value):
        base_all = [self.fallback_selector.base, self.funs_selector.base, self.fallback_imp.base, self.funs_imp.base,
                    self.log.base]
        parts = [self.log, self.funs_imp, self.fallback_imp, self.funs_selector, self.fallback_selector,
                 self.constructor]
        for i, base in enumerate(reversed(base_all)):
            if key.num >= base.num:
                curr = parts[i]
                curr[key - curr.base] = value
                break

    # TODO：等会弃用
    def analysis_target(self):
        bytecode = self.middle.bytecode
        i = 0
        pre = None
        while i < len(bytecode):
            inc = 2
            curr = bytecode[i:i + 2]  # 当前指令
            if int('60', 16) <= int(curr, 16) <= int('7F', 16):
                inc += (int(curr, 16) - int('60', 16) + 1) * 2
            pre = bytecode[i:i + inc]  # 上一次指令
            i += inc

    # 打印划分好的功能块
    def __str__(self):
        return "constructor: {}-{} {}\n".format(self.constructor.start, self.constructor.end,
                                                self.constructor.bytecode) + \
               "fallback_selector: {}-{} {}\n".format(self.fallback_selector.start, self.fallback_selector.end,
                                                      self.fallback_selector.bytecode) + \
               "funs_selector: {}-{} {}\n".format(self.funs_selector.start, self.funs_selector.end,
                                                  self.funs_selector.bytecode) + \
               "fallback_imp: {}-{} {}\n".format(self.fallback_imp.start, self.fallback_imp.end,
                                                 self.fallback_imp.bytecode) + \
               "funs_imp: {}-{} {}\n".format(self.funs_imp.start, self.funs_imp.end, self.funs_imp.bytecode) + \
               "log: {}-{} {}\n".format(self.log.start, self.log.end, self.log.bytecode)


# 以操作数(code)为输入, 生成合乎长度(length)的操作码与操作数
# 当 length 不为 0 时, 则操作数为 length 字节长度, 多余的补零
# 当 length 为 0 时, 则操作数为刚好能容下 code 的字节长度, 奇数长度补一个零
def push_generator(code: str, length=Hex('0')) -> str:
    code_length = len(code)
    if length.num == 0:
        length = Hex(math.ceil(code_length / 2))
    push_x = (Hex('60') + length - Hex('1')).s
    push_code = push_x + '0' * (length.num * 2 - code_length) + code
    return push_code


def trampoline_patch_generator(patch_target: Hex, trampoline_length: Hex, patch_content: str, back_target: str,
                               has_jumpdest=False) -> tuple[str, str]:
    if not has_jumpdest:
        trampoline = push_generator(patch_target.s, trampoline_length - Hex('2')) + '56'
    else:
        trampoline = push_generator(patch_target.s, trampoline_length - Hex('3')) + '56' + '5b'
    patch = '5b' + patch_content + push_generator(back_target) + '56'
    return trampoline, patch


def selector_generator(bytecode: str, offset=Hex('0')) -> str:
    push_queue = queue.Queue()
    i = 0
    while i < len(bytecode):
        inc = 2
        curr = bytecode[i:i + 2]  # 当前指令
        if int('60', 16) <= int(curr, 16) <= int('7F', 16):
            inc += (int(curr, 16) - int('60', 16) + 1) * 2
            push_queue.put(bytecode[i:i + inc])
        i += inc
    if push_queue.qsize() % 2 != 0:
        print("队列非双数")
        raise Exception
    res = ''
    while not push_queue.empty():
        a = push_queue.get()
        b = push_queue.get()
        # 给加上移动的偏移
        b = push_generator((Hex(b[2::]) + offset).s)
        res += '80' + a + '14' + b + '57'

    return res


# 给合约加上初始化代码
def add_constructor(bytecode: str) -> str:
    template = ['608060405234801561001057600080fd5b50', '8061001f6000396000f300']  # constructor 的模板
    # codecopy 的 length 参数的 push 操作码
    length = push_generator(hex(len(bytecode) // 2).replace('0x', ''))
    return template[0] + length + template[1] + bytecode


# 合并两个合约
def combine_bytecode(codeA: BytecodeAnalysis, codeB: BytecodeAnalysis) -> BytecodeAnalysis:
    patch = ''
    # 第一类补丁, 用于修正函数入口
    # 修正第二个函数的, 利用相对于 funs_imp 的差值不变, - codeB.funs_imp.base 在求差值
    # TODO：将 offset 分出为一个单独变量，因为这样更方便理解
    patch_content = codeA[2].bytecode + selector_generator(codeB[2].bytecode, codeA.middle.length - codeB.funs_imp.base)
    patch_base = codeA.middle.length + codeB.funs_imp.length
    trampoline_t, patch_t = trampoline_patch_generator(patch_base, codeA.funs_selector.length,
                                                       patch_content, codeA[3].base.s)
    # 安装蹦床与记录补丁
    codeA.funs_selector.replace(Hex('0'), codeA.funs_selector.length, trampoline_t)
    patch += patch_t
    patch_target = patch_base + Hex(len(patch) // 2)

    # 第二类补丁, 用于修正 codeB.funs_imp 中所有的 JUMP ⑴ 找到 JUMP(I) 记录位置, 构建所有指令位置 ⑵ 比较指令位置, 选择合适的替换指令 ⑶ length 可得, content 可得需要加上原来被替换的地方, 回来位置可得 JUMP
    bytecode = codeB.funs_imp.bytecode
    jump_collections = []  # 记录所有 JUMP(I) 的位置
    ops = dict()  # 以行的方式构建指令
    counter = 0  # 行的计数器
    i = 0
    # 找到 JUMP(I) 位置
    while i < len(bytecode):
        inc = 2
        curr = int(bytecode[i:i + 2], 16)  # 当前指令的 10 进制表示
        if int('60', 16) <= curr <= int('7F', 16):  # 当为 PUSH 时
            inc += (curr - int('60', 16) + 1) * 2
        if curr == int('56', 16) or curr == int('57', 16):  # 当为 JUMP(I) 时
            jump_collections.append(counter)
        ops[counter] = (Hex(i // 2), bytecode[i:i + inc])  # 记录: 第几行 -> 字节位置, 字节码
        i += inc
        counter += 1

    min_length = math.ceil(len(patch_target.s) / 2) + 3  # 蹦床最小所需直接长度字节长度, 比如跳转位置为 123, 则 min_length=ceil(3/2)+3=5
    for line in jump_collections:
        i = line - 1  # JUMP 从上一行开始检测合适的插入位置
        while True:
            if ops[i][1] != '5b':  # 碰到了 JUMPDEST, 表示没有足够的位置合并
                curr_length = ops[line][0] - ops[i][0]
                if curr_length.num >= min_length:  # 空间足够
                    # 跳转位置计算
                    patch_target = patch_base + Hex(len(patch) // 2)
                    # 跳转内容计算
                    offset = codeA.middle.length - codeB.funs_imp.base
                    patch_content = bytecode[ops[i][0].num * 2:ops[line][0].num * 2] + push_generator(
                        offset.s) + '01'  # 原来的 + 新的
                    # 回来目标计算
                    back_target = (ops[line][0] - Hex('1') + codeA.middle.length).s  # 向上移动到 JUMPDEST
                    trampoline_t, patch_t = trampoline_patch_generator(patch_target, curr_length,
                                                                       patch_content, back_target, True)
                    codeB.funs_imp.replace(ops[i][0], curr_length, trampoline_t)
                    patch += patch_t
                    min_length = math.ceil(len(patch_target.s) / 2) + 3
                    break
                else:
                    i -= 1
            else:
                # TODO 把空间不够的那一部份字节码提出来并转为操作码
                print("无法合并, 没有足够的替换空间")
                return BytecodeAnalysis('')

    res = codeA[1].bytecode + codeA[2].bytecode + codeA[3].bytecode + codeA[4].bytecode + \
          codeB[4].bytecode + patch

    res = add_constructor(res)
    # TODO 更新一个 codeA 的 BytecodeAnalysis，而不是创建一个新的
    return BytecodeAnalysis(res)


add_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663a836572881146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600101905600a165627a7a723058201b5930ac885210ff114b55848f959850c81886c515ec221eb475490f85e319a50029'
double_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663eee9720681146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600202905600a165627a7a72305820f3a6ecd64c261907682d5ce13a40341199a16032194121592a8017e6692158de0029'
hello_bytecode = '608060405234801561001057600080fd5b5061017c806100206000396000f3fe608060405234801561001057600080fd5b506004361061002b5760003560e01c806319ff1d2114610030575b600080fd5b61003861004e565b6040516100459190610124565b60405180910390f35b60606040518060400160405280600b81526020017f68656c6c6f20776f726c64000000000000000000000000000000000000000000815250905090565b600081519050919050565b600082825260208201905092915050565b60005b838110156100c55780820151818401526020810190506100aa565b838111156100d4576000848401525b50505050565b6000601f19601f8301169050919050565b60006100f68261008b565b6101008185610096565b93506101108185602086016100a7565b610119816100da565b840191505092915050565b6000602082019050818103600083015261013e81846100eb565b90509291505056fea2646970667358221220dac56691e4e7399d1cd082465dc09cff423a7ed5f52c84162e8ff8859bc6764e64736f6c634300080b0033'

add_analysis = BytecodeAnalysis(add_bytecode)
double_analysis = BytecodeAnalysis(double_bytecode)
hello_analysis = BytecodeAnalysis(hello_bytecode)

# for part in hello_analysis:  # 检验划分问题
#     print(part.bytecode)

# print(combine_bytecode(add_analysis, double_analysis).bytecode)
print(to_opcode('608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041667000000000000009f565b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b6001019056005b3460b7565b57600080fd5b5060586100c2565b565b60408051918252519081900360200190f35b60ce565b56005b63a836572881146043578063eee9720614607157603e565b8015604e602e016076565b600435606a602e016084565b60020290602e01609c56'))