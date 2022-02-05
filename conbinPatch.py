from evmdasm import EvmBytecode
import math
from utils import Hex, to_opcode
import opcodes as op
import copy


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
            res.append((Hex(i // 2), curr_hex, ''))
        i += inc
    return res


# 格式化字节码
class FBytecode:
    def __init__(self, bytecode=''):
        self.bytecode = bytecode
        self.formatted_bytecode = format_bytecode(self.bytecode)

    @property
    def length(self):
        return Hex(len(self.bytecode) // 2)

    def __iter__(self):
        return iter(self.formatted_bytecode)

    def update(self, bytecode):
        self.bytecode = bytecode
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
        return self.formatted_bytecode[item]

    def __str__(self):
        s = ''
        for i, line in enumerate(self.formatted_bytecode):
            # 行号 - 字节位置 - 操作数 - 操作码
            s += '{} {} {}\n'.format(i, line[0], EvmBytecode(line[1] + line[2]).disassemble().as_string)
        return s

    def print_by_line(self, start: int, end: int):
        s = ''
        for i in range(start, end + 1):
            line = self.formatted_bytecode[i]
            s += '{} {} {}\n'.format(i, line[0],
                                     EvmBytecode(line[1] + line[2]).disassemble().as_string)  # 行号 - 字节位置 - 操作数 - 操作码
        print(s)

    def replace_by_line(self, start_end_trampoline: list):
        for start, end, trampoline in start_end_trampoline:
            start_h = self.formatted_bytecode[start][0]
            end_h = self.formatted_bytecode[end][0] + self._blength_of_line(end)
            self.bytecode = self.bytecode[0:start_h.num * 2] + trampoline.bytecode + self.bytecode[end_h.num * 2::]
        self.update(self.bytecode)

    def get_by_line(self, start: int, end: int):
        start_h = self.formatted_bytecode[start][0]
        end_h = self.formatted_bytecode[end][0] + self._blength_of_line(end)
        bytecode = self.bytecode[start_h.num * 2:end_h.num * 2]
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
        self.base = copy.deepcopy(base)  # 深拷贝

    def update_funBlock(self, bytecode: str, base: Hex):
        super(FunBlock, self).update(bytecode)
        self.base = copy.deepcopy(base)


class Constructor(FBytecode):
    pass


class SelectorGenerator(FunBlock):
    pass


class SelectorTrampoline(FunBlock):
    def __init__(self, bytecode='', base=Hex('0'), target=Hex('0')):
        super().__init__(bytecode, base)
        if target != Hex('0') and self.length > Hex('0'):
            bytecode = push_generator(target, self.length - Hex('2')) + op.jump
            self.update_funBlock(bytecode, self.base)

    def update_target(self, target: Hex):
        new_push = push_generator(target, self.length - Hex('2'))
        new_bytecode = new_push + op.jump
        self.update_funBlock(new_bytecode, self.base)


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
                    temp = [Hex(self.bytecode[i + 2:i + inc])]
                    count += 1
                else:  # 单数
                    temp.append(Hex(self.bytecode[i + 2:i + inc]))
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
        self.formatted_selector = self._format_selector()  # [[签名, 跳转目标]]

    def update_selector_offset(self, offset: Hex):
        bytecode = ''
        for i in range(len(self.formatted_selector)):
            sign = self.formatted_selector[i][0]
            target = self.formatted_selector[i][1]
            # 给加上移动的偏移
            new_target_push = push_generator(target + offset)
            bytecode += op.dup1 + op.push4 + sign.s + op.eq + new_target_push + op.jumpi
        return Selector(bytecode)


class FallbackImpl(FunBlock):
    pass


class FunsImpl(FunBlock):
    pass


class SelectorRevise(FunBlock):
    def __init__(self, bytecode='', base=Hex('0'), back_target=Hex('0')):
        super().__init__(bytecode, base)
        if back_target != Hex('0') and self.length > Hex('0'):
            self.sign_bytecode = op.jumpdest + self.bytecode
            self.push_bytecode = push_generator(back_target) + op.jump
            bytecode = self.sign_bytecode + self.push_bytecode
            self.update_funBlock(bytecode, base)
        else:
            self.sign_bytecode = ''
            self.push_bytecode = ''

    def add_selector(self, new_selector_bytecode: str):
        self.sign_bytecode += new_selector_bytecode
        bytecode = self.sign_bytecode + self.push_bytecode
        self.update_funBlock(bytecode, self.base)


class CBOR:
    def __init__(self, bytecode='', base=Hex('0')):
        self.bytecode = bytecode
        self.base = base

    @property
    def length(self) -> Hex:
        return Hex(len(self.bytecode) // 2)


class Middle(FBytecode):
    def __init__(self, blocks: list):
        self.blocks = blocks
        super(Middle, self).__init__(self._get_bytecode_from_blocks())

    def _get_bytecode_from_blocks(self) -> str:
        s = ''
        for block in self.blocks:
            s += block.bytecode
        return s

    def __str__(self):
        output = ''
        counter = 0
        for i, block in enumerate(self.blocks):
            output += '--------第{}部分--------\n'.format(i)
            for line in block.formatted_bytecode:
                # 行号 - 字节位置 - 操作数 - 操作码
                output += '{} {} {}'.format(counter, line[0] + block.base,
                                            EvmBytecode(line[1] + line[2]).disassemble().as_string)
                if line[1] == op.jump or line[1] == op.jumpi:
                    output += ' <---\n'
                else:
                    output += '\n'
                counter += 1
        return output


class Patch:
    def __init__(self, base: Hex):
        self.fBytecode_list = []
        self.base = copy.deepcopy(base)

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
            output += '--------第{}次补丁--------\n'.format(i)
            for line in fBytecode.formatted_bytecode:
                output += '{} {} {}\n'.format(counter, line[0], EvmBytecode(
                    line[1] + line[2]).disassemble().as_string)  # 行号 - 字节位置 - 操作数 - 操作码
                counter += 1
        return output


class Source(FBytecode):
    def __init__(self):
        self.constructor = Constructor()
        self.selector_generator = SelectorGenerator()
        self.selector_trampoline = SelectorTrampoline()
        self.fallback_impl = FallbackImpl()
        self.funs_impl = FunsImpl()
        self.selector_revise = SelectorRevise()
        self.cbor = CBOR()

    @property
    def formatted_bytecode(self):
        fun_blocks = [self.constructor, self.selector_generator, self.selector_trampoline,
                      self.fallback_impl, self.funs_impl, self.selector_revise]  # 不包含 cbor
        bytecode = ''
        for fun_block in fun_blocks:
            bytecode += fun_block.bytecode
        return format_bytecode(bytecode)

    # 动态生成, 因为会不断变化
    @property
    def bytecode(self) -> str:
        all_blocks = [self.constructor, self.selector_generator, self.selector_trampoline,
                      self.fallback_impl, self.funs_impl, self.selector_revise, self.cbor]
        bytecode = ''
        for all_block in all_blocks:
            bytecode += all_block.bytecode
        return bytecode

    @property
    def middle(self) -> Middle:
        middle_blocks = [self.selector_generator, self.selector_trampoline, self.fallback_impl, self.funs_impl]
        bytecode = ''
        for middle_block in middle_blocks:
            bytecode += middle_block.bytecode
        return Middle(middle_blocks)

    @property
    def middle_test(self) -> Middle:
        middle_blocks = [self.selector_generator, self.selector_trampoline, self.fallback_impl, self.funs_impl,
                         self.selector_revise]
        bytecode = ''
        for middle_block in middle_blocks:
            bytecode += middle_block.bytecode
        return Middle(middle_blocks)

    def append_funs_impl(self, new_funs_impl: FunsImpl, patch: Patch):
        def combine_funsImpl_patch(_funs_impl: FunsImpl, _patch: Patch) -> FBytecode:
            return FBytecode(_funs_impl.bytecode + _patch.bytecode)

        self.funs_impl += combine_funsImpl_patch(new_funs_impl, patch)  # 在 FBytecode 层面上的更新
        self.selector_revise.base += (new_funs_impl + patch).length

    def selector_revise_update(self, selector: Selector):
        self.selector_revise.add_selector(selector.bytecode)
        self.cbor.base += selector.length

    def cbor_update(self, other: CBOR):
        self.cbor.bytecode += other.bytecode

    def constructor_update(self):
        template = ['608060405234801561001057600080fd5b50', '8061', '6000396000f300']  # constructor 的模板
        # codecopy 的 length 参数的 push 操作码以及操作数
        push_length = push_generator(self.middle.length + self.selector_revise.length + self.cbor.length)
        # codecopy 的 offset 参数的 push 操作数
        offset = Hex('1d') + Hex(len(push_length) // 2)
        bytecode = template[0] + push_length + template[1] + '00' + offset.s + template[2]
        self.constructor = Constructor(bytecode)

    def __str__(self):
        s = super(Source, self).__str__()
        s += "CBOR共 {} 字节".format(self.cbor.length)
        return s


class Addition(FBytecode):
    def __init__(self, contract: str):
        self.constructor = Constructor()
        self.selector_generator = SelectorGenerator()
        self.selector = Selector()
        self.fallback_impl = FallbackImpl()
        self.funs_impl = FunsImpl()
        self.cbor = CBOR()

        self._divider(contract)

    def _divider(self, contract):
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
        bc = contract
        i, j = 0, 0
        part = 0
        while j < len(contract):
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
        self.cbor = CBOR(bc[cbor[0]:cbor[1]], base)

    @property
    def bytecode(self) -> str:
        all_blocks = [self.constructor, self.selector_generator, self.selector,
                      self.fallback_impl, self.funs_impl, self.cbor]
        bytecode = ''
        for all_block in all_blocks:
            bytecode += all_block.bytecode
        return bytecode

    @property
    def formatted_bytecode(self):
        fun_blocks = [self.constructor, self.selector_generator, self.selector, self.fallback_impl, self.funs_impl]
        bytecode = ''
        for fun_block in fun_blocks:
            bytecode += fun_block.bytecode
        return format_bytecode(bytecode)

    @property
    def middle(self):
        middle_blocks = [self.selector_generator, self.selector, self.fallback_impl, self.funs_impl]
        bytecode = ''
        for middle_block in middle_blocks:
            bytecode += middle_block.bytecode
        return Middle(middle_blocks)


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
    patch = op.jumpdest + replaced_code.bytecode + push_generator(offset) + op.add + push_generator(
        back_target) + op.jump
    return FBytecode(patch)

# 判断是否为 push, 一个过度函数
def is_push(opcode: str) -> bool:
    opcode_dec = int(opcode, 16)
    return int('60', 16) <= opcode_dec <= int('7F', 16)

# 合并字节码
def combine_bytecode(src: Source, add: Addition):
    # 找到新合约 funs_impl 中所有 jump(i) 的行号
    jump_nums = list()
    for i, opcode in enumerate(add.funs_impl):
        if opcode[1] == op.jump or opcode[1] == op.jumpi:
            jump_nums.append(i)
    patch_target = src.middle.length + add.funs_impl.length

    # 修正新合约 funs_impl 中所有 jump(i)
    patch = Patch(patch_target)  # patch 类
    start_end_trampolines = []  # 蹦床的开始+结尾+蹦床本身
    for jump_num in jump_nums:
        start = jump_num - 1  # 不替换 jump(i) 本身, 从上一行开始
        # 采用修正 CGF 的方案
        if start == jump_num - 1 and is_push(add.funs_impl[start][1]):
            limited_length = Hex(len(add.funs_impl[start][2])//2)  # 新的target不能超过此字节数
            # 以下所有类为 Hex 类
            old_target = Hex(add.funs_impl[start][2])
            offset = src.middle.length - add.funs_impl.base
            new_target = old_target + offset
            # 判断新的跳转目标可否在不影响直接偏置的情况加入
            if new_target.blength <= limited_length:
                push_bytecode = push_generator(new_target, limited_length)
                start_end_trampolines.append((start, start, Trampoline(push_bytecode)))
                continue
        # 找到填充蹦床的起始位置 start
        min_trampoline_length = patch_target.blength + Hex('3')
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
        # ⑴ 生成当前补丁
        replaced_code = add.funs_impl.get_by_line(start, jump_num - 1)
        offset = src.middle.length - add.funs_impl.base
        # 跳转回来的位置为 -> jump(i)位置的上一字节, 这里会预设 jumpdest
        # src.middle.length 是未来合并后 add.funs_impl 的新基址
        back_target = (add.funs_impl[jump_num][0] - Hex('1')) + src.middle.length
        patch_curr = jump_patch_generator(replaced_code, offset, back_target)
        # ⑵ 生成蹦床
        start_end_trampolines.append((start, jump_num - 1, trampoline_generator(patch_target, curr_length)))
        # ⑶ 生成补丁
        patch_target += patch_curr.length
        patch += patch_curr

    # 更新选择器与蹦床
    # 更新选择器
    offset = src.middle.length - add.funs_impl.base
    revised_selector = add.selector.update_selector_offset(offset)
    src.selector_revise_update(revised_selector)
    # 更新选择器蹦床蹦床
    src.selector_trampoline.update_target(patch_target)

    # 修复 funs_impl 和 安装 jump_patch
    add.funs_impl.replace_by_line(start_end_trampolines)
    src.append_funs_impl(add.funs_impl, patch)

    # 更新 CBOR
    src.cbor_update(add.cbor)

    # 更新 constructor
    src.constructor_update()

    return src


def addition_to_source(add: Addition) -> Source:
    src = Source()
    src.selector_generator = copy.deepcopy(add.selector_generator)
    # 创建蹦床
    src.selector_trampoline = SelectorTrampoline(add.selector.bytecode, add.selector.base, add.middle.length)
    src.fallback_impl = copy.deepcopy(add.fallback_impl)
    src.funs_impl = copy.deepcopy(add.funs_impl)
    # 创建选择器修正
    src.selector_revise = SelectorRevise(add.selector.bytecode, add.middle.length, add.fallback_impl.base)
    src.cbor = copy.deepcopy(add.cbor)
    # constructor 修正
    src.constructor_update()

    return copy.deepcopy(src)


add1_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663a836572881146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600101905600a165627a7a723058201b5930ac885210ff114b55848f959850c81886c515ec221eb475490f85e319a50029'
double_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663eee9720681146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600202905600a165627a7a72305820f3a6ecd64c261907682d5ce13a40341199a16032194121592a8017e6692158de0029'
sign_bytecode = '608060405234801561001057600080fd5b506103c4806100206000396000f3fe608060405234801561001057600080fd5b506004361061002b5760003560e01c806379d6348d14610030575b600080fd5b61004a60048036038101906100459190610168565b610060565b60405161005791906101f9565b60405180910390f35b60606002604051602401610074919061021b565b6040516020818303038152906040527febc78ceb000000000000000000000000000000000000000000000000000000007bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19166020820180517bffffffffffffffffffffffffffffffffffffffffffffffffffffffff83818316178352505050509050919050565b600061010b6101068461025b565b610236565b9050828152602081018484840111156101275761012661036e565b5b6101328482856102c7565b509392505050565b600082601f83011261014f5761014e610369565b5b813561015f8482602086016100f8565b91505092915050565b60006020828403121561017e5761017d610378565b5b600082013567ffffffffffffffff81111561019c5761019b610373565b5b6101a88482850161013a565b91505092915050565b60006101bc8261028c565b6101c68185610297565b93506101d68185602086016102d6565b6101df8161037d565b840191505092915050565b6101f3816102b5565b82525050565b6000602082019050818103600083015261021381846101b1565b905092915050565b600060208201905061023060008301846101ea565b92915050565b6000610240610251565b905061024c8282610309565b919050565b6000604051905090565b600067ffffffffffffffff8211156102765761027561033a565b5b61027f8261037d565b9050602081019050919050565b600081519050919050565b600082825260208201905092915050565b600060ff82169050919050565b60006102c0826102a8565b9050919050565b82818337600083830152505050565b60005b838110156102f45780820151818401526020810190506102d9565b83811115610303576000848401525b50505050565b6103128261037d565b810181811067ffffffffffffffff821117156103315761033061033a565b5b80604052505050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052604160045260246000fd5b600080fd5b600080fd5b600080fd5b600080fd5b6000601f19601f830116905091905056fea264697066735822122076f424f75f2b522810fb433195931bbf5e25eb21b8d68b46814674772360557864736f6c63430008070033'
addition_add1 = Addition(add1_bytecode)
source_add1 = addition_to_source(addition_add1)
addition_double = Addition(double_bytecode)
addition_sign = Addition(sign_bytecode)

com1 = combine_bytecode(source_add1, addition_double)
com2 = combine_bytecode(com1, addition_sign)

print(com2.bytecode)
