from evmdasm import EvmBytecode
import math
import queue


# 用于处理 16 进制
class Hex:
    def __init__(self, num):
        if type(num) == int:
            self.hex_str = hex(num)
            self.num = num
        elif type(num) == str:
            self.hex_str = hex(int(num, 16))
            self.num = int(num, 16)
        else:
            raise TypeError

    def __add__(self, other):
        return Hex(hex(self.num + other.num))

    def __sub__(self, other):
        return Hex(hex(self.num - other.num))

    def __str__(self):
        return self.hex_str

    @property
    def s(self) -> str:
        return self.hex_str.replace('0x', '')


# 将 bytecode 转化为 opcode 并编号
def to_opcode(bytecode: str, base=Hex('0')):
    opcode = ''
    base = base.num
    i = 0
    while i < len(bytecode):
        inc = 2
        start = end = ''  # 用于给 JUMPDEST ,JUMP(I) 做特殊标记
        curr = int(bytecode[i:i + 2], 16)  # 当前指令的 10 进制表示
        if int('60', 16) <= curr <= int('7E', 16):  # 当为 PUSH 时
            inc += (curr - int('60', 16) + 1) * 2
        if curr == int('5b', 16):  # 当为 JUMPDEST 时
            start = '-----------------------\n'
        if curr == int('56', 16) or curr == int('57', 16):  # 当为 JUMP(I)
            end = '<---'
        op = EvmBytecode(bytecode[i:i + inc]).disassemble().as_string
        # opcode += '{}[{}] [{}] {}{}\n'.format(start, hex(i // 2 + base), hex(i // 2), op, end)
        opcode += '{}\n'.format(op)
        i += inc
    return opcode


class BasicPart:
    def __init__(self, start=0, end=0, bytecode='', base=0, create_mode=0):
        if create_mode == 0:
            # 相较于第二个 6080 的偏移
            self.base = Hex(base)
            # 全局起始与终了
            self.start = Hex(start // 2)
            self.end = Hex(end // 2)
            self.length = Hex((end - start) // 2)
            # 源代码与当前代码, 后面相较于第二个 6080 的偏移
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
        if int('60', 16) <= curr <= int('7E', 16):
            inc += (curr - int('60', 16) + 1) * 2
        op = EvmBytecode(self.bytecode[i:i + inc]).disassemble().as_string
        return '[{}] [{}] {}'.format(hex(self.base.num + i // 2), hex(i // 2), op)

    # 以左闭右开的方式十分容易选择
    def __setitem__(self, key, value: str):
        if type(key) == Hex:
            i = int(key.hex_str, 16) * 2
        elif type(key) == str:
            i = int(key, 16) * 2  # 计算下标
        else:
            raise TypeError
        curr = int(self.bytecode[i:i + 2], 16)  # 获得字节码
        inc = 2
        if int('60', 16) <= curr <= int('7E', 16):  # 处理 PUSH 情况
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

    def __getitem__(self, item: int):
        parts = [self.constructor, self.fallback_selector, self.funs_selector, self.fallback_imp, self.funs_imp,
                 self.log]
        return parts[item]

    # 将字节码进行拆分
    def divider(self):
        constructor = fallback_selector = funs_selector = fallback_imp = funs_imp = log = [0, 0]
        bc = self.bytecode
        i, j = 0, 0
        part = 0
        while j < len(self.bytecode):
            inc = 2
            if bc[j:j + 2] == '00' and part == 0:  # STOP
                constructor = [i, j + 2]
                i = j + 2
                part += 1
            elif bc[j - 2:j + 2] == '0416' and part == 1:  # DIV |AND|
                fallback_selector = [i, j + 2]
                i = j + 2
                part += 1
            elif (bc[j:j + 4] == '575b' or bc[j:j + 4] == '565b') and part == 2:  # |JUMPI| JUMPDEST 或者 |JUMP| JUMPDEST
                funs_selector = [i, j + 2]
                i = j + 2
                part += 1
            elif bc[j:j + 2] == 'fd' and part == 3:  # |REVERT| #TODO fallback 函数的终止条件
                fallback_imp = [i, j + 2]
                i = j + 2
                part += 1
            elif bc[j:j + 2] == '00' and part == 4:  # |STOP|
                funs_imp = [i, j + 2]
                i = j + 2
                part += 1
                log = [i, len(bc)]

            op = int(bc[j:j + 2], 16)
            if int('60', 16) <= op <= int('7E', 16):
                inc += (op - int('60', 16) + 1) * 2
            j += inc

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

    def analysis_target(self):
        bytecode = self.middle.bytecode
        i = 0
        pre = None
        while i < len(bytecode):
            inc = 2
            curr = bytecode[i:i + 2]  # 当前指令
            if int('60', 16) <= int(curr, 16) <= int('7E', 16):
                inc += (int(curr, 16) - int('60', 16) + 1) * 2
            pre = bytecode[i:i + inc]  # 上一次指令
            i += inc

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


# 用于生成 push 代码, code 为要写入的内容，length 为 push 的字节长度, 其有两种模式
# 当 length 不为 0 时, 则 length 为 code 的长度
# 当 length 为 0 时, 则使用刚好能容下 code 的 push
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


# 合并字节码 ⑴ 选用第一个合约的回调函数 ⑵ 加上固定的偏置
def combine_bytecode1(codeA: BytecodeAnalysis, codeB: BytecodeAnalysis, targetA: dict, targetB: dict) -> str:
    # 计算偏置
    offset1 = codeB.funs_selector.length
    offset2 = codeA.fallback_imp.length - codeB.fallback_imp.length + codeA.funs_selector.length + codeA.funs_imp.length
    # 修改字节码
    for key, value in targetA.items():
        codeA[Hex(key)] = '60' + (Hex(value) + offset1).s
    for key, value in targetB.items():
        codeB[Hex(key)] = '60' + (Hex(value) + offset2).s
    codeB[Hex('39')] = '80'
    # 合并字节码: 函数选择子 -> 函数实现
    res = codeA[1].bytecode + codeA[2].bytecode + codeB[2].bytecode + \
          codeA[3].bytecode + codeA[4].bytecode + codeB[4].bytecode

    return res

def construct_selector(bytecode: str, offset=Hex('0')) -> str:
    push_queue = queue.Queue()
    i = 0
    while i < len(bytecode):
        inc = 2
        curr = bytecode[i:i + 2]  # 当前指令
        if int('60', 16) <= int(curr, 16) <= int('7E', 16):
            inc += (int(curr, 16) - int('60', 16) + 1) * 2
            push_queue.put(bytecode[i:i+inc])
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

# 蹦床立刻替换, 补丁逐步累计
def combine_bytecode2(codeA: BytecodeAnalysis, codeB: BytecodeAnalysis) -> str:
    patch = ''
    # 第一类补丁, 用于修正函数入口
    # 修正第二个函数的, 利用相对于 funs_imp 的差值不变, - codeB.funs_imp.base 在求差值
    patch_content = codeA[2].bytecode + construct_selector(codeB[2].bytecode, codeA.middle.length - codeB.funs_imp.base)
    # TODO 先不添加 log 部分, 之后补上
    patch_base = codeA.middle.length + codeB.funs_imp.length
    trampoline_t, patch_t = trampoline_patch_generator(patch_base, codeA.funs_selector.length,
                                                       patch_content, codeA[3].base.s)
    # 安装蹦床与记录补丁
    codeA.funs_selector.replace(Hex('0'), codeA.funs_selector.length, trampoline_t)
    patch += patch_t
    patch_target = patch_base + Hex(len(patch)//2)

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
        if int('60', 16) <= curr <= int('7E', 16):  # 当为 PUSH 时
            inc += (curr - int('60', 16) + 1) * 2
        if curr == int('56', 16) or curr == int('57', 16):  # 当为 JUMP(I) 时
            jump_collections.append(counter)
        ops[counter] = (Hex(i//2), bytecode[i:i + inc])  # 记录: 第几行 -> 字节位置, 字节码
        i += inc
        counter += 1

    min_length = math.ceil(len(patch_target.s) / 2) + 3   # 蹦床最小所需直接长度字节长度, 比如跳转位置为 123, 则 min_length=ceil(3/2)+3=5
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
                    patch_content = bytecode[ops[i][0].num * 2:ops[line][0].num * 2] + push_generator(offset.s) + '01'  # 原来的 + 新的
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
                print("无法合并, 没有足够的替换空间")
                return ''

    res = codeA[1].bytecode + codeA[2].bytecode + codeA[3].bytecode + codeA[4].bytecode + \
          codeB[4].bytecode + patch

    return res



add_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663a836572881146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600101905600a165627a7a723058201b5930ac885210ff114b55848f959850c81886c515ec221eb475490f85e319a50029'
double_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663eee9720681146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600202905600a165627a7a72305820f3a6ecd64c261907682d5ce13a40341199a16032194121592a8017e6692158de0029'

add_analysis = BytecodeAnalysis(add_bytecode)
double_analysis = BytecodeAnalysis(double_bytecode)

# JUMP(I) 目标对应 PUSH 地址 -> 跳转的目标
add_target = {'9': '3e', '3b': '43', '47': '4e', '50': '58', '55': '6a'}
double_target = {'9': '3e', '3b': '43', '47': '4e', '50': '58', '55': '6a'}

# combined = combine_bytecode1(add_analysis, double_analysis, add_target, double_target)
# code = to_opcode(combined)

print(combine_bytecode2(add_analysis, double_analysis))
# print(to_opcode('608060405234801561001057600080fd5b50610147806100206000396000f300608060405260043610610041576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff168063771602f714610046575b600080fd5b34801561005257600080fd5b5061007b6004803603810190808035906020019092919080359060200190929190505050610091565b6040518082815260200191505060405180910390f35b6000808284019050838110151515610111576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601b8152602001807f536166654d6174683a206164646974696f6e206f766572666c6f77000000000081525060200191505060405180910390fd5b80915050929150505600a165627a7a72305820c43ba7c72b8d9c1d76ac9137601f4f56bb18008ccbab13afcdd5d56db2da4b6a0029'))