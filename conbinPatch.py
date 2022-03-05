import os
import json
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

    def replace_by_line_generator(self, start_end_trampoline: list):
        bytecode = self.bytecode
        for start, end, trampoline in start_end_trampoline:
            start_h = self.formatted_bytecode[start][0]
            end_h = self.formatted_bytecode[end][0] + self._blength_of_line(end)
            bytecode = bytecode[0:start_h.num * 2] + trampoline.bytecode + bytecode[end_h.num * 2::]
        return FBytecode(bytecode)

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

    def replace_by_line_generator(self, start_end_trampoline: list):
        fBytecode = super(FunBlock, self).replace_by_line_generator(start_end_trampoline)
        return FunBlock(fBytecode.bytecode, self.base)


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
        selector = []
        target = []
        i = 0
        flag = False
        while i < len(self.bytecode):
            inc = 2
            curr_hex = self.bytecode[i:i + 2]
            curr = int(curr_hex, 16)  # 当前指令的 10 进制表示
            if int('60', 16) <= curr <= int('7F', 16):  # 当为 PUSH 时
                inc += (curr - int('60', 16) + 1) * 2
                if curr_hex == op.push4 and not flag:  # 找到签名
                    flag = True
                    curr_selector = Hex(self.bytecode[i + 2:i + inc])
                    if curr_selector in selector:  # 后面的签名替换前面的签名，因为前面的签名可能是用于划分的
                        index = selector.index(curr_selector)
                        selector.pop(index)
                        target.pop(index)
                    selector.append(curr_selector)
                elif flag:  # 将签名下一个地址获得
                    flag = False
                    target.append(Hex(self.bytecode[i + 2:i + inc]))
            i += inc
        if len(selector) != len(target):
            raise BaseException("Selector 筛选出错")
        formatted_selector = [[selector[i], target[i]] for i in range(len(selector))]
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
        s += "Metadata 共 {} 字节: {}".format(self.cbor.length, self.cbor.bytecode)
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
        def find_min_target(bytecode: str) -> Hex:
            _selector = []
            target = []
            _i = 0
            flag = False
            while _i < len(bytecode):
                _inc = 2
                curr_hex = bytecode[_i:_i + 2]
                curr = int(curr_hex, 16)  # 当前指令的 10 进制表示
                if int('60', 16) <= curr <= int('7F', 16):  # 当为 PUSH 时
                    _inc += (curr - int('60', 16) + 1) * 2
                    if curr_hex == op.push4 and not flag:  # 找到签名
                        flag = True
                        curr_selector = Hex(bytecode[_i + 2:_i + _inc])
                        if curr_selector in _selector:  # 后面的签名替换前面的签名，因为前面的签名可能是用于划分的
                            index = _selector.index(curr_selector)
                            _selector.pop(index)
                            target.pop(index)
                        _selector.append(curr_selector)
                    elif flag:  # 将签名下一个地址获得
                        flag = False
                        target.append(Hex(bytecode[_i + 2:_i + _inc]))
                _i += _inc
            if len(_selector) != len(target):
                raise BaseException("Selector 筛选出错")
            return min(target)

        def is_last_jumpi(bytecode: str) -> bool:
            op_order = [op.push4, op.eq, op.jumpi]  # 只要依次出现以下操作码, 哪便一定不是最后一个 jumpi
            _i = 0
            while _i < len(bytecode):
                _inc = 2
                curr_hex = bytecode[_i:_i + 2]
                curr = int(curr_hex, 16)  # 当前指令的 10 进制表示
                if int('60', 16) <= curr <= int('7F', 16):  # 当为 PUSH 时
                    _inc += (curr - int('60', 16) + 1) * 2
                if curr_hex == op_order[0]:
                    op_order.pop(0)
                    if len(op_order) <= 0:
                        break  # 当 op_order 为空, 则无须继续判定
                _i += _inc  # 此处的 _i 可能会越界, 因为 bytecode 可能会少截取一部分
            return len(op_order) > 0

        constructor = selector_generator = selector = fallback_impl = funs_impl = cbor = [0, 0]
        had_calldataload = False
        bc = contract
        i, j = 0, 0
        part = 0
        while j < len(contract):
            inc = 2
            # 拆分出 constructor
            if part == 0:
                if bc[j:j + 4] == 'f300' or bc[j:j + 4] == 'f3fe':  # |STOP(0x00)| 或者 |0xfe|
                    constructor = [i, j + 4]
                    i = j + 4
                    part += 1
            # 拆分出 generator
            if part == 1:
                if bc[j:j+2] == op.calldataload:
                    had_calldataload = True
                if (bc[j:j + 4] == '8063' and bc[j + 2:j + 12] != '63ffffffff') or \
                        (bc[j + 2:j + 4] == '63' and bc[j + 2:j + 12] != '63ffffffff') and had_calldataload:
                    selector_generator = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分出 selector
            if part == 2:
                if bc[j:j + 2] == '57' and is_last_jumpi(bc[j+2:j+34]):  # 判断是否是最后一个 JUMPI
                    selector = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分 fallback impl, funs impl, CBOR,
            if part == 3:
                # 拆分 fallback impl, 利用 selector 的跳转地址
                min_target = find_min_target(bc[selector[0]:selector[1]])
                min_target_index = min_target.num * 2 + constructor[1]
                fallback_impl = [i, min_target_index]
                i = min_target_index
                # 拆分 funs impl 和 CBOR, 利用 CBOR 的长度
                cbor_ending_length = int(bc[-4::], 16) * 2 + 4  # 最后两个直接记录了CBOR的长度
                funs_impl = [i, len(bc)-cbor_ending_length]
                i = len(bc)-cbor_ending_length
                cbor = [i, len(bc)]
                break

            opcode = int(bc[j:j + 2], 16)
            if int('60', 16) <= opcode <= int('7F', 16):
                inc += (opcode - int('60', 16) + 1) * 2
            j += inc

        if constructor == [0, 0] or selector_generator == [0, 0] or selector == [0, 0] or \
                fallback_impl == [0, 0] or funs_impl == [0, 0]:
            raise IndexError("划分失败")

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

    def __str__(self):
        s = super(Addition, self).__str__()
        s += "Metadata 共 {} 字节: {}".format(self.cbor.length, self.cbor.bytecode)
        return s


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
def jump_patch_generator(replaced_code: FBytecode, offset: Hex, back_target: Hex, jump_type: str) -> FBytecode:
    patch = op.jumpdest + replaced_code.bytecode + push_generator(offset) + op.add + jump_type + push_generator(
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
        start = jump_num  # 替换 jump(i) 本身, 从当前行开始
        # 采用 CGF 的方案, 对 jump(i) 的上一行判断
        opcode = add.funs_impl[jump_num - 1][1]
        operand = add.funs_impl[jump_num - 1][2]
        if is_push(opcode):
            limited_length = Hex(len(operand) // 2)  # 新的target不能超过此字节数
            # 以下所有类为 Hex 类
            old_target = Hex(operand)
            offset = src.middle.length - add.funs_impl.base
            new_target = old_target + offset
            # 判断新的跳转目标可否在不影响直接偏置的情况加入
            if new_target.blength <= limited_length:
                push_bytecode = push_generator(new_target, limited_length)
                start_end_trampolines.append((jump_num - 1, jump_num - 1, Trampoline(push_bytecode)))
                continue
        # 找到填充蹦床的起始位置 start
        min_trampoline_length = patch_target.blength + Hex('3')
        while True:
            curr_length = add.funs_impl.blength_by_line(start, jump_num)
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
        # 跳转回来的位置为 -> jump(i)位置的当前字节, 这里会预设 jumpdest
        # src.middle.length 是未来合并后 add.funs_impl 的新基址
        back_target = add.funs_impl[jump_num][0] + src.middle.length
        patch_curr = jump_patch_generator(replaced_code, offset, back_target, op.jump)
        # ⑵ 生成蹦床
        start_end_trampolines.append((start, jump_num, trampoline_generator(patch_target, curr_length)))
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
    revised_funs_impl = add.funs_impl.replace_by_line_generator(start_end_trampolines)
    src.append_funs_impl(revised_funs_impl, patch)

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


if __name__ == '__main__':
    def get_unit_test(contract: str) -> list:
        add = Addition(contract)
        part = [add.constructor, add.selector_generator, add.selector, add.fallback_impl, add.funs_impl, add.cbor]
        return [contract, list(map(lambda x: x.bytecode, part))]

    def add_unit_test(contract: str):
        unit_test = get_unit_test(contract)
        try:
            with open('dividerUnitTest.txt', 'r', encoding='utf8') as f:
                unit_tests = json.loads(f.read())
            unit_tests.append(unit_test)
            with open('dividerUnitTest.txt', 'w', encoding='utf8') as f:
                f.write(json.dumps(unit_tests))
        except:
            with open('dividerUnitTest.txt', 'w', encoding='utf8') as f:
                f.write(json.dumps([unit_test]))

    def test_divider() -> bool:
        cons = True
        try:
            with open('dividerUnitTest.txt', 'r', encoding='utf8') as f:
                unit_tests = json.loads(f.read())
        except:
            print("单元测试文件不存在或者单元测试数据出错")
        for contract, test_res in unit_tests:
            curr = Addition(contract)
            part = [curr.constructor, curr.selector_generator, curr.selector, curr.fallback_impl, curr.funs_impl, curr.cbor]
            curr_res = list(map(lambda x: x.bytecode, part))
            cons = cons and curr_res == test_res
        return cons

    unknown_bytecode = '608060405234801561001057600080fd5b5060d48061001f6000396000f3fe608060405260043610601c5760003560e01c806312065fe014607f575b7f909c57d5c6ac08245cf2a6de3900e2b868513fa59099b92b27d8db823d92df9c5a60405190815260200160405180910390a160405162461bcd60e51b81526020600482015260016024820152606b60f81b604482015260640160405180910390fd5b348015608a57600080fd5b504760405190815260200160405180910390f3fea2646970667358221220145395ac7890445828b59945e9593ab8919952bb83ad366fc498e807b422da9864736f6c634300080b0033'
    add1_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663a836572881146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600101905600a165627a7a723058201b5930ac885210ff114b55848f959850c81886c515ec221eb475490f85e319a50029'
    double_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663eee9720681146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600202905600a165627a7a72305820f3a6ecd64c261907682d5ce13a40341199a16032194121592a8017e6692158de0029'
    fibonacci_bytecode = '608060405234801561001057600080fd5b5060d88061001f6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663421ec76581146043575b600080fd5b348015604e57600080fd5b50605b600435602435606d565b60408051918252519081900360200190f35b6000811515607b57508160a6565b8160011415608c57506001820160a6565b60978360028403606d565b60a28460018503606d565b0190505b929150505600a165627a7a72305820924e3776cadabeb78157c4953a03fef645eca8938de0cd5d40b5cdb2b23c24410029'
    receive_bytecode = '61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3006080604052600436106100435760003560e01c80633ccfd60b1461004f5780638da5cb5b1461006657806391fb54ca14610092578063f2fde38b146100b257600080fd5b3661004a57005b600080fd5b34801561005b57600080fd5b506100646100d2565b005b34801561007257600080fd5b50600054604080516001600160a01b039092168252519081900360200190f35b34801561009e57600080fd5b506100646100ad3660046103ad565b610142565b3480156100be57600080fd5b506100646100cd36600461038b565b610285565b6000546001600160a01b031633146101055760405162461bcd60e51b81526004016100fc90610479565b60405180910390fd5b600080546040516001600160a01b03909116914780156108fc02929091818181858888f1935050505015801561013f573d6000803e3d6000fd5b50565b6000546001600160a01b0316331461016c5760405162461bcd60e51b81526004016100fc90610479565b8051806101b25760405162461bcd60e51b81526020600482015260146024820152731059191c995cdcd95cc81b9bdd081c185cdcd95960621b60448201526064016100fc565b47806102005760405162461bcd60e51b815260206004820152601860248201527f5a65726f2062616c616e636520696e20636f6e7472616374000000000000000060448201526064016100fc565b600061020c83836104ae565b905060005b8381101561027e5784818151811061022b5761022b6104f9565b60200260200101516001600160a01b03166108fc839081150290604051600060405180830381858888f1935050505015801561026b573d6000803e3d6000fd5b5080610276816104d0565b915050610211565b5050505050565b6000546001600160a01b031633146102af5760405162461bcd60e51b81526004016100fc90610479565b6001600160a01b0381166103145760405162461bcd60e51b815260206004820152602660248201527f4f776e61626c653a206e6577206f776e657220697320746865207a65726f206160448201526564647265737360d01b60648201526084016100fc565b600080546040516001600160a01b03808516939216917f8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e091a3600080546001600160a01b0319166001600160a01b0392909216919091179055565b80356001600160a01b038116811461038657600080fd5b919050565b60006020828403121561039d57600080fd5b6103a68261036f565b9392505050565b600060208083850312156103c057600080fd5b823567ffffffffffffffff808211156103d857600080fd5b818501915085601f8301126103ec57600080fd5b8135818111156103fe576103fe61050f565b8060051b604051601f19603f830116810181811085821117156104235761042361050f565b604052828152858101935084860182860187018a101561044257600080fd5b600095505b8386101561046c576104588161036f565b855260019590950194938601938601610447565b5098975050505050505050565b6020808252818101527f4f776e61626c653a2063616c6c6572206973206e6f7420746865206f776e6572604082015260600190565b6000826104cb57634e487b7160e01b600052601260045260246000fd5b500490565b60006000198214156104f257634e487b7160e01b600052601160045260246000fd5b5060010190565b634e487b7160e01b600052603260045260246000fd5b634e487b7160e01b600052604160045260246000fdfea2646970667358221220594ba90ab1a8938f3f895b587b8a56160dd82a85f8823b4a95e1b9aec4a8a17964736f6c63430008070033'

    print(test_divider())