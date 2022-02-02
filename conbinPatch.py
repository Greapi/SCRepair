from evmdasm import EvmBytecode
import math
from utils import Hex, to_opcode
import opcodes as op


def format_bytecode(bytecode) -> list:
    i = 0
    res = list()  # (行号) - 字节位置 - 操作码 - 操作数
    while i < len(bytecode):
        inc = 2
        curr_hex = bytecode[i:i + 2]
        curr = int(curr_hex, 16)  # 当前指令的 10 进制表示
        if int('60', 16) <= curr <= int('7F', 16):  # 当为 PUSH 时
            inc += (curr - int('60', 16) + 1) * 2
            res.append((Hex(i // 2), curr_hex, bytecode[i + 2:i + inc]))
        else:
            res.append((Hex(i // 2), curr_hex))
        i += inc
    return res


# 格式化字节码
class FBytecode:
    def __init__(self, bytecode=''):
        self.bytecode = bytecode
        self.length = Hex(len(bytecode) // 2)
        self.formatted_bytecode = format_bytecode(self.bytecode)

    def __iter__(self):
        return iter(self.formatted_bytecode)

    def update(self, bytecode):
        self.bytecode = bytecode
        self.length = Hex(len(bytecode) // 2)
        self.formatted_bytecode = format_bytecode(self.bytecode)

    def _blength_of_line(self, line_num: int) -> Hex:
        default = 1
        curr = int(self.formatted_bytecode[line_num][1], 16)
        if int('60', 16) <= curr <= int('7F', 16):
            default += curr - int('60', 16) + 1
        return Hex(default)

    def blength_by_line(self, start: int, end: int) -> Hex:
        before_end = self.formatted_bytecode[end][0] - self.formatted_bytecode[start][0]
        return before_end + self._blength_of_line(end)

    def __getitem__(self, item: int):
        return self.formatted_bytecode

    def __str__(self):
        s = ''
        for i, line in enumerate(self.formatted_bytecode):
            s += '{} {} {}\n'.format(i, line[0],
                                     EvmBytecode(line[1] + line[2]).disassemble().as_string)  # 行号 - 字节位置 - 操作数 - 操作码
        return s

    def print_by_line(self, start: int, end: int):
        s = ''
        for i in range(start, end + 1):
            line = self.formatted_bytecode[i]
            s += '{} {} {}\n'.format(i, line[0],
                                     EvmBytecode(line[1] + line[2]).disassemble().as_string)  # 行号 - 字节位置 - 操作数 - 操作码
        print(s)

    def replace_by_line(self, start: int, end: int, value):
        start_h = self.formatted_bytecode[start][0]
        end_h = self.formatted_bytecode[end][0] + self._blength_of_line(end)
        new_bytecode = self.bytecode[0:start_h.num * 2] + value.bytecode + self.bytecode[end_h.num * 2::]
        self.update(new_bytecode)

    def get_by_line(self, start: int, end: int):
        start_h = self.formatted_bytecode[start][0]
        end_h = self.formatted_bytecode[end][0] + self._blength_of_line(end)
        bytecode = self.bytecode[start_h.num:end_h.num]
        return FBytecode(bytecode)

    def __iadd__(self, other):
        bytecode = self.bytecode + other.bytecode
        self.update(bytecode)
        return self

    def __add__(self, other):
        bytecode = self.bytecode + other.bytecode
        return FBytecode(bytecode)


# 功能块
class FunBlock(FBytecode):
    def __init__(self, bytecode='', base=Hex('0')):
        super().__init__(bytecode)
        self.base = base

    def update_funBlock(self, bytecode: str, base: Hex):
        super(FunBlock, self).update(bytecode)
        self.base = base


class Constructor(FBytecode):
    pass


class SelectorGenerator(FunBlock):
    pass


class SelectorTrampoline(FunBlock):
    def update_target(self, target: Hex):
        new_push = push_generator(target, self.length - Hex('2'))
        new_bytecode = new_push + op.jump
        self.update_funBlock(new_bytecode, Hex('0'))


class Selector(FunBlock):
    # 提取出签名
    def _format_selector(self) -> list:
        formatted_selector = []
        temp = []
        i = 0
        count = 0
        while i < len(self.bytecode):
            inc = 2
            curr_hex = self.bytecode[i:i + 2]
            curr = int(curr_hex, 16)  # 当前指令的 10 进制表示
            if int('60', 16) <= curr <= int('7F', 16):  # 当为 PUSH 时
                inc += (curr - int('60', 16) + 1) * 2
                if count % 2 == 0:  # 双数
                    if curr_hex != op.push4:
                        print("Selector无效签名")
                        raise TypeError
                    temp = [curr_hex]
                    count += 1
                else:  # 单数
                    temp.append(curr_hex)
                    formatted_selector.append(temp)
                    temp = []
                    count += 1
            i += inc
        if count % 2 != 0:  # 签名和目标必须成对存在
            print("Selector跳转缺失目标")
            raise TypeError
        return formatted_selector

    def __init__(self, bytecode='', base=Hex('0')):
        super().__init__(bytecode, base)
        self.formatted_selector = self._format_selector()

    # 会引起原来的 bytecode 发生内容与长度的改变
    def update_offset(self, offset: Hex):
        bytecode = ''
        for i in range(len(self.formatted_selector)):
            sign = self.formatted_selector[i][0]
            target = self.formatted_selector[i][1]
            # 给加上移动的偏移
            new_target_push = push_generator(target + offset)
            bytecode += op.dup1 + op.push4 + sign + op.eq + \
                        new_target_push + op.jumpi
            self.formatted_selector[i][1] = new_target_push[2::]
        self.update(bytecode)


class FallbackImpl(FunBlock):
    pass


class FunsImpl(FunBlock):
    pass


class SelectorRevise(FunBlock):
    pass


class CBOR:
    def __init__(self, bytecode='', base=Hex('0')):
        self.bytecode = bytecode
        self.base = base

    @property
    def length(self) -> Hex:
        return Hex(len(self.bytecode)//2)


class Middle(FBytecode):
    pass


class Patch:
    def __init__(self):
        self.fBytecode_list = []

    @property
    def length(self) -> Hex:
        length = Hex('0')
        for fBytecode in self.fBytecode_list:
            length += fBytecode.length
        return length

    @property
    def bytecode(self) -> str:
        s = ''
        for fBytecode in self.fBytecode_list:
            s += fBytecode.bytecode
        return s

    @property
    def formatted_bytecode(self) -> list:
        ls = list()
        for fBytecode in self.fBytecode_list:
            ls += fBytecode.formatted_bytecode
        return ls

    def __iadd__(self, other: FBytecode):
        self.fBytecode_list.append(other)
        return self

    def __str__(self):
        output = ''
        counter = 0
        for i, fBytecode in enumerate(self.fBytecode_list):
            output += '--------第{}次补丁--------'.format(i)
            for line in fBytecode.formatted_bytecode:
                output += '{} {} {}\n'.format(counter, line[0], EvmBytecode(
                    line[1] + line[2]).disassemble().as_string)  # 行号 - 字节位置 - 操作数 - 操作码
                counter += 1
        return output


class Source:
    def __init__(self, contract: str):
        self.constructor = Constructor()
        self.selector_generator = SelectorGenerator()
        self.selector_trampoline = SelectorTrampoline()
        self.fallback_impl = FallbackImpl()
        self.funs_impl = FunsImpl()
        self.selector_revise = SelectorRevise()
        self.cbor = CBOR()

    # 动态生成, 因为会不断变化
    @property
    def bytecode(self) -> str:
        fun_blocks = [self.constructor, self.selector_generator, self.selector_trampoline,
                      self.fallback_impl, self.funs_impl, self.selector_revise, self.cbor]
        bytecode = ''
        for fun_block in fun_blocks:
            bytecode += fun_block.bytecode
        return bytecode

    @property
    def middle(self) -> Middle:
        middle_blocks = [self.selector_generator, self.selector_trampoline, self.fallback_impl, self.funs_impl]
        bytecode = ''
        for middle_block in middle_blocks:
            bytecode += middle_block.bytecode
        return Middle(bytecode)

    def append_funs_impl(self, new_funs_impl: FunsImpl, patch: Patch):
        def combine_funsImpl_patch(_funs_impl: FunsImpl, _patch: Patch) -> FBytecode:
            return FBytecode(_funs_impl.bytecode + _patch.bytecode)

        self.funs_impl += combine_funsImpl_patch(new_funs_impl, patch)  # 在 FBytecode 层面上的更新
        self.selector_revise.base += (new_funs_impl + patch).length

    def selector_revise_update(self, selector: Selector):
        bytecode = self.selector_revise.bytecode + selector.bytecode
        self.selector_revise.update(bytecode)
        self.cbor.base += selector.length

    def cbor_update(self, other: CBOR):
        self.cbor.bytecode += other.bytecode

    def constructor_update(self):
        template = ['608060405234801561001057600080fd5b50', '8061001f6000396000f300']  # constructor 的模板
        # codecopy 的 length 参数的 push 操作码
        push_length = push_generator(self.middle.length + self.cbor.length)
        return template[0] + push_length + template[1] + self.middle.bytecode + self.cbor.bytecode


class Addition:
    def __init__(self, contract: str):
        self.bytecode = contract
        self.constructor = Constructor()
        self.selector_generator = SelectorGenerator()
        self.selector = Selector()
        self.fallback_impl = FallbackImpl()
        self.funs_impl = FunsImpl()
        self.cbor = CBOR()

        self._divider()

    def _divider(self):
        def match(bytecode: str) -> bool:
            _j = 0
            ops = []
            while _j < len(bytecode):
                _inc = 2
                ops.append(bytecode[_j:_j + 2])
                _op = int(bytecode[_j:_j + 2], 16)
                if int('60', 16) <= _op <= int('7F', 16):
                    _inc += (_op - int('60', 16) + 1) * 2
                _j += _inc
            if len(ops) >= 2 and not (int('60', 16) <= int(ops[-2], 16) <= int('7F', 16)):  # 倒数第二个必须是 PUSH
                return False
            ops = ops[0:-2] + ops[-1::]  # 去除倒数第二个
            return ops == ['63', '14', '57'] or ops == ['63', '81', '14', '57']

        constructor = selector_generator = selector = fallback_impl = funs_impl = cbor = [0, 0]
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
                if match(bc[j + 2:j + 22]) or match(
                        bc[j + 2:j + 24]):  # |PUSH4 EQ PUSH? JUMPI| 或者 |PUSH4 DUP2 EQ PUSH? JUMPI|
                    selector_generator = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分出 fun selector
            if part == 2:
                if bc[j:j + 4] == '575b' or bc[j:j + 4] == '565b':  # |JUMPI| JUMPDEST 或者 |JUMP| JUMPDEST
                    selector = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分出 fallback impl
            if part == 3:
                if bc[j:j + 2] == 'fd':  # |REVERT|
                    fallback_impl = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分出 funs impl 和 log
            if part == 4:
                if bc[j:j + 2] == '00' or bc[j:j + 2] == 'fe':  # |STOP(0x00)| 或者 |0xfe|
                    funs_impl = [i, j + 2]
                    i = j + 2
                    part += 1
                    cbor = [i, len(bc)]

            opcode = int(bc[j:j + 2], 16)
            if int('60', 16) <= opcode <= int('7F', 16):
                inc += (opcode - int('60', 16) + 1) * 2
            j += inc

        if constructor == [0, 0] or selector_generator == [0, 0] or selector == [0, 0] or \
                fallback_impl == [0, 0] or funs_impl == [0, 0]:
            raise TypeError

        self.constructor = Constructor(bc[constructor[0]:constructor[1]])
        base = Hex('0')
        self.selector_generator = SelectorGenerator(bc[selector_generator[0]:selector_generator[1]], base)
        base += self.selector_generator.length
        self.selector = Selector(bc[selector[0]:selector[1]], base)
        base += self.selector.length
        self.fallback_impl = FallbackImpl(bc[fallback_impl[0]:fallback_impl[1]], base)
        base += self.fallback_impl.length
        self.funs_impl = FunsImpl(bc[funs_impl[0]:funs_impl[1]], base)
        base += self.funs_impl.length
        self.cbor = CBOR(bc[cbor[0]:cbor[1]], Hex('0'))

    @property
    def middle(self):
        middle_blocks = [self.selector_generator, self.selector, self.fallback_impl, self.funs_impl]
        bytecode = ''
        for middle_block in middle_blocks:
            bytecode += middle_block.bytecode
        return Middle(bytecode)


class Trampoline(FBytecode):
    pass


# 以操作数(code)为输入, 生成合乎长度(length)的操作码与操作数
# 当 length 不为 0 时, 则操作数为 length 字节长度, 多余的补零
# 当 length 为 0 时, 则操作数为刚好能容下 code 的字节长度, 奇数长度补一个零
def push_generator(code: Hex, length=Hex('0')) -> str:
    code = code.s
    code_length = len(code)
    if length.num == 0:
        length = Hex(math.ceil(code_length / 2))
    push_x = (Hex('60') + length - Hex('1')).s
    push_code = push_x + '0' * (length.num * 2 - code_length) + code
    return push_code

# 生成蹦床, trampoline_length 为蹦床的总长度
def trampoline_generator(patch_target: Hex, trampoline_length: Hex):
    if trampoline_length < Hex('4'):
        print("蹦床长度过短")
        raise OverflowError
    trampoline_bytecode = push_generator(patch_target, trampoline_length - Hex('3')) + '56' + '5b'
    return Trampoline(trampoline_bytecode)

# 生成 jump 修正补丁
def jump_patch_generator(replaced_code: FBytecode, offset: Hex, back_target: Hex) -> FBytecode:
    patch = op.jumpdest + replaced_code.bytecode + push_generator(offset) + op.add + push_generator(back_target) + op.jump
    return FBytecode(patch)

# 合并字节码
def combine_bytecode(src: Source, add: Addition):
    # 找到新合约 funs_impl 中所有 jump(i) 的行号
    jump_nums = list()
    for i, opcode in enumerate(add.funs_impl):
        if opcode[1] == op.jump or opcode[1] == op.jumpi:
            jump_nums.append(i)
    patch_target = src.middle.length + add.funs_impl.length

    # 修正新合约 funs_impl 中所有 jump(i)
    patch = Patch()  # patch 类
    for jump_num in jump_nums:
        # 找到填充蹦床的起始位置 start
        min_trampoline_length = patch_target.blength + Hex('3')
        start = jump_num - 1  # 不替换 jump(i) 本身, 从上一行开始
        while True:
            curr_length = add.funs_impl.blength_by_line(start, jump_num - 1)
            if add.funs_impl[start][1] == op.jumpdest:  # 不能碰到基本块
                add.funs_impl.print_by_line(start, jump_num)
                print("没有足够的空间")
                raise OverflowError
            if curr_length >= min_trampoline_length:
                break
            start -= 1
        # 修正当前 jump(i)
        # 生成与安装蹦床
        trampoline = trampoline_generator(patch_target, curr_length)
        add.funs_impl.replace_by_line(start, jump_num - 1, trampoline)
        # 生成安装补丁
        replaced_code = add.funs_impl.get_by_line(start, jump_num - 1)
        offset = src.middle.length - add.funs_impl.base
        back_target = add.funs_impl[start][0] + src.middle.length  # 实际要跳转的位置, 将 source 之前偏移量
        patch_code = jump_patch_generator(replaced_code, offset, back_target)
        patch_target += patch_code.length
        patch += patch_code
    src.append_funs_impl(add.funs_impl, patch)

    # 更新选择器与蹦床
    # 更新选择器
    offset = src.middle.length - add.funs_impl.base
    add.selector.update_offset(offset)
    src.selector_revise_update(add.selector)
    # 更新蹦床
    selector_target = patch_target + src.selector_revise.length
    src.selector_trampoline.update_target(selector_target)

    # 更新 CBOR
    src.cbor_update(add.cbor)

    # 更新 constructor
    src.constructor_update()

    return src


print(to_opcode('608060405234801561001057600080fd5b50336000806101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555060008054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16600073ffffffffffffffffffffffffffffffffffffffff167f342827c97908e5e2f71151c08502a66d44b6f758e3ac2f1de95f02eb95f0a73560405160405180910390a3610356806100db6000396000f3fe608060405234801561001057600080fd5b50600436106100365760003560e01c8063893d20e81461003b578063a6f9dae114610059575b600080fd5b610043610075565b604051610050919061025d565b60405180910390f35b610073600480360381019061006e91906101fe565b61009e565b005b60008060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff16905090565b60008054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff161461012c576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040161012390610278565b60405180910390fd5b8073ffffffffffffffffffffffffffffffffffffffff1660008054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff167f342827c97908e5e2f71151c08502a66d44b6f758e3ac2f1de95f02eb95f0a73560405160405180910390a3806000806101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555050565b6000813590506101f881610309565b92915050565b600060208284031215610214576102136102db565b5b6000610222848285016101e9565b91505092915050565b610234816102a9565b82525050565b6000610247601383610298565b9150610252826102e0565b602082019050919050565b6000602082019050610272600083018461022b565b92915050565b600060208201905081810360008301526102918161023a565b9050919050565b600082825260208201905092915050565b60006102b4826102bb565b9050919050565b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b600080fd5b7f43616c6c6572206973206e6f74206f776e657200000000000000000000000000600082015250565b610312816102a9565b811461031d57600080fd5b5056fea26469706673582212208f65d9c920a5e7c951f66594688d8b1bb886420d647e05d3e5c9ec7eeab019cd64736f6c63430008070033'))
add_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663a836572881146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600101905600a165627a7a723058201b5930ac885210ff114b55848f959850c81886c515ec221eb475490f85e319a50029'
double_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663eee9720681146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600202905600a165627a7a72305820f3a6ecd64c261907682d5ce13a40341199a16032194121592a8017e6692158de0029'
hello_bytecode = '608060405234801561001057600080fd5b5061017c806100206000396000f3fe608060405234801561001057600080fd5b506004361061002b5760003560e01c806319ff1d2114610030575b600080fd5b61003861004e565b6040516100459190610124565b60405180910390f35b60606040518060400160405280600b81526020017f68656c6c6f20776f726c64000000000000000000000000000000000000000000815250905090565b600081519050919050565b600082825260208201905092915050565b60005b838110156100c55780820151818401526020810190506100aa565b838111156100d4576000848401525b50505050565b6000601f19601f8301169050919050565b60006100f68261008b565b6101008185610096565b93506101108185602086016100a7565b610119816100da565b840191505092915050565b6000602082019050818103600083015261013e81846100eb565b90509291505056fea2646970667358221220dac56691e4e7399d1cd082465dc09cff423a7ed5f52c84162e8ff8859bc6764e64736f6c634300080b0033'

add_analysis = Addition(add_bytecode)
double_analysis = Addition(double_bytecode)
hello_analysis = Addition(hello_bytecode)

# for part in hello_analysis:  # 检验划分问题
#     print(part.bytecode)

# print(combine_bytecode(add_analysis, double_analysis).bytecode)
# print(to_opcode('608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041667000000000000009f565b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b6001019056005b3460b7565b57600080fd5b5060586100c2565b565b60408051918252519081900360200190f35b60ce565b56005b63a836572881146043578063eee9720614607157603e565b8015604e602e016076565b600435606a602e016084565b60020290602e01609c56'))
