import os
import json
from evmdasm import EvmBytecode
import math
from utils import Hex, to_opcode, print_formatted
import opcodes as op
import copy


def format_bytecode(bytecode, is_temp=False) -> list:
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
    if not is_temp:
        assert (i == len(bytecode))
    return res

# 找到 codecopy 并分析 offset 与
def find_codecopy(bytecode: str, base: Hex) -> list[list[Hex, int]]:
    off_len_line = list()  # 表示没有.byte部分
    # 尝试通过 codecopy 找出 .byte
    fb = format_bytecode(bytecode, True)
    for i, line in enumerate(fb):
        _, opcode, _ = line
        if opcode == op.codecopy:
            para1 = fb[i - 3]  # offset
            para2 = fb[i - 2]  # length
            if is_push(para1[1]) and is_push(para2[1]) and para1[2] != '' and para2[2] != '':  # 表示均为 push 且取值有意义
                off_len_line.append([Hex(para1[2]), Hex(para2[2]), i])

    off_len_line.sort(key=lambda x: x[0])  # 以 offset 进行排序

    return off_len_line

# 验证 codecopy 的有效性
# @bytecode 与data块相接的块字节码 + data块
# @base 与data块相接的块字节码的基址
def assert_codecopy_valid(off_len_line: list, bytecode: str, base: Hex):
    if len(off_len_line) > 0:
        # 找出最后一个字节
        last_code_index = (off_len_line[0][0] - base).num * 2 - 2
        last_bytecode = bytecode[last_code_index:last_code_index + 2]
        # 确认是否找到 .byte 部分的开头, 确认是否找到.byte末尾
        assert last_bytecode == op.invalid_fe or last_bytecode == op.stop, "没有找到.byte开头"
        assert off_len_line[-1][0] + off_len_line[-1][1] == base + Hex(len(bytecode)//2), "没有找到.byte末尾"
        # 验证找到的.byte链接的合法性
        i = 1
        while i < len(off_len_line):
            assert off_len_line[i - 1][0] + off_len_line[i - 1][1] == off_len_line[i][0], ".byte链接不合法"
            i += 1

# 格式化的字节码
class FBytecode:
    def __init__(self, bytecode=''):
        self.bytecode = bytecode

    @property
    def formatted_bytecode(self):
        return format_bytecode(self.bytecode)

    @property
    def length(self):
        return Hex(len(self.bytecode) // 2)

    def __iter__(self):
        return iter(self.formatted_bytecode)

    def update(self, bytecode):
        self.bytecode = bytecode

    # 获得当前行所占字节数
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
        print(s, end='')

    def replace_by_line_generator(self, start_end_trampoline: list):
        bytecode = self.bytecode
        for start, end, trampoline in start_end_trampoline:
            start_h = self.formatted_bytecode[start][0]
            end_h = self.formatted_bytecode[end][0] + self._blength_of_line(end)
            assert (end_h - start_h == trampoline.length)
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

    def insert(self, index_line: int, bytecode: str):
        hex_pos: Hex = self.formatted_bytecode[index_line][0]
        new_bytecode = self.bytecode[0:hex_pos.num * 2] + bytecode + self.bytecode[hex_pos.num * 2:]
        self.update(new_bytecode)

    # 以行进行替换
    def __setitem__(self, key: int, value: str):
        start_num = self.formatted_bytecode[key][0].num * 2
        end_num = self.formatted_bytecode[key + 1][0].num * 2
        self.bytecode = self.bytecode[:start_num] + value + self.bytecode[end_num:]


# 功能块
class FunBlock(FBytecode):
    def __init__(self, bytecode='', base=Hex('0')):
        super().__init__(bytecode)
        self.base = copy.deepcopy(base)  # 深拷贝, 不算 constructor

    def update_funBlock(self, bytecode: str, base: Hex):
        super(FunBlock, self).update(bytecode)
        self.base = copy.deepcopy(base)

    def replace_by_line_generator(self, start_end_trampoline: list):
        fBytecode = super(FunBlock, self).replace_by_line_generator(start_end_trampoline)
        return FunBlock(fBytecode.bytecode, self.base)

    # 以行进行替换
    def replace_by_line(self, key: int, value: str):
        start_num = self.formatted_bytecode[key][0].num * 2
        end_num = self.formatted_bytecode[key + 1][0].num * 2
        self.bytecode = self.bytecode[:start_num] + value + self.bytecode[end_num:]

    # 返回一个: 地址 -> 行号: int
    @property
    def address_lineNum(self) -> dict:
        res_dict = dict()
        for i, line in enumerate(self.formatted_bytecode):
            target, _, _ = line
            res_dict[target] = i
        return res_dict


class Data:
    def __init__(self, bytecode='', base=Hex('0')):
        self.bytecode = bytecode
        self.base = base

    @property
    def length(self) -> Hex:
        return Hex(len(self.bytecode) // 2)


class Constructor(FunBlock):
    pass


class SelectorGenerator(FunBlock):
    pass


class SelectorTrampoline(FunBlock):
    # 这里 bytecode 只起到计算长度的作用
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

    # 固定将 selector 以dup1 push4 eq push jumpi 输出
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
    def have_jumpdest(self, start: int, end: int) -> bool:
        for _, opcode, _ in self.formatted_bytecode[start:end + 1]:
            if opcode == op.jumpdest:
                return True
        return False

    # def __str__(self):
    #     s = self.code.__str__()
    #     s += "\t.byte\n{}".format(self.data)
    #     return s

    # # 以行进行替换
    # def replace_by_line(self, key: int, value: str):
    #     start_num = self.code.formatted_bytecode[key][0].num * 2
    #     end_num = self.code.formatted_bytecode[key + 1][0].num * 2
    #     self.bytecode = self.bytecode[:start_num] + value + self.bytecode[end_num:]
    #
    # def print_by_line(self, start: int, end: int):
    #     s = ''
    #     for i in range(start, end + 1):
    #         line = self.code.formatted_bytecode[i]
    #         s += '{} {} {}\n'.format(i, line[0],
    #                                  EvmBytecode(line[1] + line[2]).disassemble().as_string)  # 行号 - 字节位置 - 操作数 - 操作码
    #     print(s, end='')


class SelectorRevise(FunBlock):
    # sign_bytecode 选择器部分, push_bytecode 回位部分
    def __init__(self, bytecode='', base=Hex('0'), back_target=Hex('0')):
        super().__init__(bytecode, base)
        if back_target != Hex('0') and self.length > Hex('0'):
            self.sign_bytecode = op.jumpdest + self.bytecode
            self.push_bytecode = push_generator(back_target) + op.jump + op.invalid_fe
            bytecode = self.sign_bytecode + self.push_bytecode
            self.update_funBlock(bytecode, base)
        else:
            self.sign_bytecode = ''
            self.push_bytecode = ''

    # 因为在 SelectorRevise 末尾有回位代码, 因此添加时是在合并代码以前
    def add_selector(self, new_selector_bytecode: str):
        self.sign_bytecode += new_selector_bytecode
        bytecode = self.sign_bytecode + self.push_bytecode
        self.update_funBlock(bytecode, self.base)


class Middle:
    def __init__(self, blocks: list, addition_target=None):
        assert (len(blocks) >= 4)
        self.blocks = blocks
        self.bytecode = self._get_bytecode_from_blocks()
        self.addition_target = addition_target

    def _get_bytecode_from_blocks(self) -> str:
        s = ''
        for block in self.blocks:
            s += block.bytecode
        return s

    @property
    def length(self) -> Hex:
        return Hex(len(self.bytecode) // 2)

    def __str__(self):
        output = ''
        counter = 0
        for i, block in enumerate(self.blocks):
            output += '--------第{}部分--------\n'.format(i)
            for line in block.formatted_bytecode:
                if type(block) == FunsImpl and self.addition_target is not None and line[0] == self.addition_target:
                    output += '--------补丁---------\n'
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


class Source:
    def __init__(self):
        self.constructor = Constructor()
        self.selector_generator = SelectorGenerator()
        self.selector_trampoline = SelectorTrampoline()
        self.fallback_impl = FallbackImpl()
        self.funs_impl = FunsImpl()
        self.selector_revise = SelectorRevise()
        self.extra_data = Data()
        self.cbor = Data()

        self.addition_target = None  # 为了方便后续的等价性测试

    # 动态生成, 因为会不断变化
    @property
    def bytecode(self) -> str:
        all_blocks = [self.constructor, self.selector_generator, self.selector_trampoline,
                      self.fallback_impl, self.funs_impl, self.selector_revise, self.extra_data, self.cbor]
        bytecode = ''
        for all_block in all_blocks:
            bytecode += all_block.bytecode
        return bytecode

    @property
    def formatted_bytecode(self):
        blocks = [self.constructor, self.selector_generator, self.selector_trampoline,
                  self.fallback_impl, self.funs_impl, self.selector_revise]  # 不包含 cbor
        fb = []
        for block in blocks:
            for line in block:
                target, opcode, operand = line
                fb.append([target + block.base, opcode, operand])
        return fb

    @property
    def middle(self) -> Middle:
        middle_blocks = [self.selector_generator, self.selector_trampoline, self.fallback_impl, self.funs_impl]
        return Middle(middle_blocks, self.addition_target)

    @property
    def middle_test(self) -> Middle:
        middle_blocks = [self.selector_generator, self.selector_trampoline, self.fallback_impl, self.funs_impl,
                         self.selector_revise]
        return Middle(middle_blocks, self.addition_target)

    # 对 codecopy 修正
    def codecopy_revise(self, data_target: Hex) -> Hex:
        # 找到所有的 codecopy
        codecopy_info = find_codecopy(self.funs_impl.bytecode, self.funs_impl.base)
        for _, length, line in codecopy_info:
            push_length = Hex(self.funs_impl[line - 3][1]) - Hex(op.push1) + Hex('1')  # 获得 push 所能承载的字节
            assert data_target.blength <= push_length, "codecopy替换空间不足"
            self.funs_impl.replace_by_line(line - 3, push_generator(data_target, push_length))
            data_target += length
        codecopy_info = find_codecopy(self.funs_impl.bytecode, self.funs_impl.base)
        assert_codecopy_valid(codecopy_info, self.selector_revise.bytecode+self.extra_data.bytecode, self.selector_revise.base)
        return data_target

    # ⑴ 进行对 fun_impl 的合并 ⑵ 更新 codecopy ⑶ 更新selector_revise的base
    def append_funs_impl(self, code: FunBlock, data: Data, patch: Patch):
        # 新bytecode = 代码 + 数据 + 补丁
        self.funs_impl.bytecode = self.funs_impl.code.bytecode + code.bytecode + patch.bytecode + \
                                  self.funs_impl.data.bytecode + data.bytecode
        # 更新 codecopy
        self.funs_impl.data_info = self.funs_impl.codecopy_analysis()

        # 更新selector_revise的base
        self.selector_revise.base += code.length + patch.length + data.length

    def selector_revise_update(self, selector: Selector):
        self.selector_revise.add_selector(selector.bytecode)  # 会更新 selector_revise 本身
        self.cbor.base += selector.length

    def cbor_update(self, other: Data):
        self.cbor.bytecode += other.bytecode

    def constructor_update(self):
        template = ['608060405234801561001057600080fd5b50', '8061', '6000396000f300']  # constructor 的模板
        # codecopy 的 length 参数的 push 操作码以及操作数
        push_length = push_generator(self.middle.length + self.selector_revise.length + self.extra_data.length +
                                     self.cbor.length)
        # codecopy 的 offset 参数的 push 操作数
        offset = Hex('1d') + Hex(len(push_length) // 2)
        bytecode = template[0] + push_length + template[1] + '00' + offset.s + template[2]
        self.constructor = Constructor(bytecode)

    # FunBlock 的 base 需相对于 source, 这才能保证跳转的正确性
    def get_curr_add(self) -> FunBlock:
        assert (self.addition_target is not None)
        fun_impl_bytecode = self.funs_impl.code.bytecode
        add_bytecode = fun_impl_bytecode[self.addition_target.num * 2:]
        return FunBlock(add_bytecode, self.funs_impl.base)

    def __str__(self):
        blocks = [self.constructor, self.selector_generator, self.selector_trampoline, self.fallback_impl,
                  self.funs_impl, self.selector_revise]
        output = ''
        counter = 0
        for i, block in enumerate(blocks):
            output += '--------第{}部分--------\n'.format(i)
            for line in block.formatted_bytecode:
                if type(block) == FunsImpl and self.addition_target is not None and line[0] == self.addition_target:
                    output += '--------补丁---------\n'
                # 行号 - 字节位置 - 操作数 - 操作码
                output += '{} {} {}'.format(counter, line[0] + block.base,
                                            EvmBytecode(line[1] + line[2]).disassemble().as_string)
                if line[1] == op.jump or line[1] == op.jumpi:
                    output += ' <---\n'
                else:
                    output += '\n'
                counter += 1
        output += ".byte 偏移 {}, 共 {} 字节\n{}\n".format(self.extra_data.base, self.extra_data.length, self.extra_data.bytecode)
        output += ".Metadata 偏移 {}, 共 {} 字节\n{}".format(self.cbor.base, self.cbor.length, self.cbor.bytecode)
        return output


class Addition:
    def __init__(self, contract: str):
        self.constructor = Constructor()
        self.selector_generator = SelectorGenerator()
        self.selector = Selector()
        self.fallback_impl = FallbackImpl()
        self.funs_impl = FunsImpl()
        self.extra_data = Data()
        self.cbor = Data()

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
                if bc[j:j + 2] == op.calldataload:
                    had_calldataload = True
                if (bc[j + 2:j + 6] == '8063' and bc[j + 2:j + 12] != '63ffffffff') or \
                        (bc[j + 2:j + 4] == '63' and bc[j + 2:j + 12] != '63ffffffff') and had_calldataload:
                    selector_generator = [i, j + 2]
                    i = j + 2
                    part += 1
            # 拆分出 selector
            if part == 2:
                if bc[j:j + 2] == '57' and is_last_jumpi(bc[j + 2:j + 34]):  # 判断是否是最后一个 JUMPI
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
                cbor_ending_length = int(bc[-4::], 16) * 2 + 4  # 最后两个字节记录了CBOR的长度
                funs_impl = [i, len(bc) - cbor_ending_length]
                i = len(bc) - cbor_ending_length
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
        funs_impl_data = bc[funs_impl[0]:funs_impl[1]]
        codecopy_info = find_codecopy(funs_impl_data, base)
        assert_codecopy_valid(codecopy_info, funs_impl_data, base)
        divider_hex = codecopy_info[0][0] - base
        self.funs_impl = FunsImpl(funs_impl_data[:divider_hex.num*2], base)
        self.extra_data = Data(funs_impl_data[divider_hex.num*2:], divider_hex+base)
        base += self.funs_impl.length + self.extra_data.length
        self.cbor = Data(bc[cbor[0]:cbor[1]], base)

    @property
    def bytecode(self) -> str:
        all_blocks = [self.constructor, self.selector_generator, self.selector,
                      self.fallback_impl, self.funs_impl, self.extra_data, self.cbor]
        bytecode = ''
        for all_block in all_blocks:
            bytecode += all_block.bytecode
        return bytecode

    @property
    def formatted_bytecode(self):
        blocks = [self.constructor, self.selector_generator, self.selector, self.fallback_impl, self.funs_impl]
        fb = []
        for block in blocks:
            for line in block:
                target, opcode, operand = line
                fb.append([target + block.base, opcode, operand])
        return fb

    @property
    def middle(self):
        middle_blocks = [self.selector_generator, self.selector, self.fallback_impl, self.funs_impl]
        return Middle(middle_blocks)

    def __str__(self):
        blocks = [self.constructor, self.selector_generator, self.selector, self.fallback_impl, self.funs_impl]
        output = ''
        counter = 0
        for i, block in enumerate(blocks):
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
        output += ".byte 共 {} 字节\n{}\n".format(self.extra_data.length, self.extra_data.bytecode)
        output += ".Metadata 共 {} 字节\n{}".format(self.cbor.length, self.cbor.bytecode)
        return output


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
# @mode 为0, 对应情况0: 此跳转为 JUMP
# @mode 为1, 对应情况1: 此跳转为 JUMPI 但下一行为 JUMPDEST
# @mode 为2, 对应情况2: 此跳转为 JUMPI 且下一行不是 JUMPDEST
def trampoline_generator(patch_target: Hex, trampoline_length: Hex, mode):
    # 减 Hex('2') -> push 和 jump 两字节
    if mode == 0 or mode == 1:
        assert (trampoline_length >= Hex('3'))
        trampoline_bytecode = push_generator(patch_target, trampoline_length - Hex('2')) + op.jump
    # 减 Hex('3') -> push, jump, jumpdest 三字节
    elif mode == 2:
        assert (trampoline_length >= Hex('4'))
        trampoline_bytecode = push_generator(patch_target, trampoline_length - Hex('3')) + op.jump + op.jumpdest
    else:
        raise IndexError("此 mode 不存在")
    return Trampoline(trampoline_bytecode)


# 生成 jump 修正补丁
# @mode 为0, 对应情况0: 此跳转为 JUMP
# @mode 为1, 对应情况1: 此跳转为 JUMPI 但下一行为 JUMPDEST
# @mode 为2, 对应情况2: 此跳转为 JUMPI 且下一行不是 JUMPDEST
def jump_patch_generator(replaced_code: FBytecode, offset: Hex, back_target: Hex, mode,
                         mul_jump_code: FBytecode) -> FBytecode:
    added_code = ''
    if mul_jump_code is not None:
        jumps = []
        # 找到 jump(i) 所在行
        for i, line in enumerate(mul_jump_code):
            _, opcode, _ = line
            if opcode == op.jump or opcode == op.jumpi:
                jumps.append(i)
        insert_bytecode = push_generator(offset) + op.add
        _off = 0
        for jump in jumps:
            mul_jump_code.insert(_off + jump, insert_bytecode)
            _off += 2
        added_code = mul_jump_code.bytecode
    added_code += push_generator(offset) + op.add
    # patch = 被替换代码 + 新增代码 (+ 回位代码)
    if mode == 0:
        patch = op.jumpdest + replaced_code.bytecode + added_code + op.jump
    elif mode == 1 or mode == 2:
        patch = op.jumpdest + replaced_code.bytecode + added_code + op.jumpi + \
                push_generator(back_target) + op.jump
    else:
        raise IndexError("此 mode 不存在")
    return FBytecode(patch)


# 判断是否为 push, 一个过度函数
def is_push(opcode: str) -> bool:
    opcode_dec = int(opcode, 16)
    return int('60', 16) <= opcode_dec <= int('7F', 16)


# 合并字节码
def combine_bytecode(src: Source, add: Addition):
    # 方便提取出添加的 add 部分
    src.addition_target = src.funs_impl.code.length
    # 找到新合约 funs_impl 中所有 jump(i) 的行号
    jump_nums = list()
    for i, opcode in enumerate(add.funs_impl.code):
        if opcode[1] == op.jump or opcode[1] == op.jumpi:
            # 将相邻过近的jump(i)放在一起
            if len(jump_nums) > 0 and \
                    (add.funs_impl.code.blength_by_line(jump_nums[-1][-1] + 1, i)) <= Hex('4') and \
                    not add.funs_impl.have_jumpdest(jump_nums[-1][-1] + 1, i - 1):
                jump_nums[-1].append(i)
            else:
                jump_nums.append([i])
    # 需要将 .byte 合并到末尾, 因此需要减去其长度
    base_length = src.middle.length - src.funs_impl.data.length
    code_length = add.funs_impl.code.length
    patch_target = base_length + code_length
    offset = (src.middle.length - src.funs_impl.data.length) - add.funs_impl.base  # - add.funs_impl.base 获得相对偏移

    # 修正新合约 funs_impl 中所有 jump(i)
    patch = Patch(patch_target)  # patch 类
    start_end_trampolines = []  # 蹦床的开始+结尾+蹦床本身
    for jump_num in jump_nums:
        # 采用 CGF 的方案, 对 jump(i) 的上一行判断
        if len(jump_num) == 1:  # 仅对无连续jump(i)采用 CFG 方案
            opcode = add.funs_impl.code[jump_num[0] - 1][1]
            operand = add.funs_impl.code[jump_num[0] - 1][2]
            if is_push(opcode):
                limited_length = Hex(len(operand) // 2)  # 新的target不能超过此字节数
                # 以下所有类为 Hex 类
                old_target = Hex(operand)
                new_target = old_target + offset
                # 判断新的跳转目标可否在不影响直接偏置的情况加入
                if new_target.blength <= limited_length:
                    push_bytecode = push_generator(new_target, limited_length)
                    start_end_trampolines.append((jump_num[0] - 1, jump_num[0] - 1, Trampoline(push_bytecode)))
                    continue
        # 找到填充蹦床的起始位置(start)
        start = jump_num[0]  # 替换 jump(i) 本身, 从当前行开始
        min_trampoline_length = patch_target.blength + Hex('3')
        while True:
            curr_length = add.funs_impl.code.blength_by_line(start, jump_num[-1])
            if add.funs_impl.code[start][1] == op.jumpdest:  # 不能碰到基本块
                add.funs_impl.code.print_by_line(start, jump_num[-1])
                raise OverflowError("没有足够的空间")
            # 情况0: 当为修正的 JUMP 时, 可以少一字节, 因为无须为下一句代码设置 JUMPDEST
            # 情况1: 当为下一字节为 JUMPDEST 时, 可以少一字节, 因为跳转可以指向下一 JUMPDEST
            # 情况2: 正常修正, 蹦床带有 JUMPDEST
            if (curr_length >= min_trampoline_length - Hex('1') and add.funs_impl.code[jump_num[-1]][1] == op.jump) or \
                    (curr_length >= min_trampoline_length - Hex('1') and add.funs_impl.code[jump_num[-1] + 1][
                        1] == op.jumpdest) or \
                    curr_length >= min_trampoline_length:
                break
            start -= 1
        # 修正当前 jump(i)
        # ⑴ 生成当前补丁
        replaced_code = add.funs_impl.code.get_by_line(start, jump_num[0] - 1)
        # 跳转回来的位置为 -> jump(i)位置的当前字节, 这里会预设 jumpdest
        # src.middle.length 是未来合并后 add.funs_impl 的新基址
        if add.funs_impl.code[jump_num[-1]][1] == op.jump:  # 此时无须 back_target
            back_target = Hex('0')
            mode = 0
        elif add.funs_impl.code[jump_num[-1] + 1][1] == op.jumpdest:
            # back_target = 相对位置 + 加上基址
            back_target = add.funs_impl.code[jump_num[-1] + 1][0] + base_length
            mode = 1
        else:
            back_target = add.funs_impl.code[jump_num[-1]][0] + base_length
            mode = 2
        mul_jump = None
        if len(jump_num) > 1:
            mul_jump = add.funs_impl.code.get_by_line(jump_num[0], jump_num[-1] - 1)  # 最后一个 jump(i) 不取, 因为在 mode 中会添加
        patch_curr = jump_patch_generator(replaced_code, offset, back_target, mode, mul_jump)
        # ⑵ 生成蹦床
        start_end_trampolines.append((start, jump_num[-1], trampoline_generator(patch_target, curr_length, mode)))
        # ⑶ 生成补丁
        patch_target += patch_curr.length
        patch += patch_curr

    # 在 patch 末尾写入总结代码
    patch_end = FBytecode(op.invalid_fe)
    patch_target += patch_end.length
    patch += patch_end

    # 更新选择器与蹦床
    # 更新选择器
    revised_selector = add.selector.update_selector_offset(offset)  # 修正 selector 并以特定格式输出
    src.selector_revise_update(revised_selector)
    # 更新选择器蹦床蹦床
    selector_trampoline_target = patch_target + src.funs_impl.data.length + add.funs_impl.data.length
    src.selector_trampoline.update_target(selector_trampoline_target)

    # 修正 codecopy, 包含两部分修正 src 和 add
    # src 部分
    data_target = patch_target
    if src.funs_impl.data_info[0][2] is not None:
        for _, length, line in src.funs_impl.data_info:
            push_length = Hex(src.funs_impl.code[line - 3][1]) - Hex(op.push1) + Hex('1')  # 获得 push 所能承载的字节
            assert data_target.blength <= push_length, "codecopy替换空间不足"
            src.funs_impl.replace_by_line(line - 3, push_generator(data_target, push_length))
            data_target += length

    if add.funs_impl.data_info[0][2] is not None:
        # add 部分
        for _, length, line in add.funs_impl.data_info:
            push_length = Hex(add.funs_impl.code[line - 3][1]) - Hex(op.push1) + Hex('1')  # 获得 push 所能承载的字节
            assert data_target.blength <= push_length, "codecopy替换空间不足"
            add.funs_impl.replace_by_line(line - 3, push_generator(data_target, push_length))
            data_target += length

    # 修复 funs_impl 和 安装 jump_patch
    revised_funs_impl_code = add.funs_impl.code.replace_by_line_generator(start_end_trampolines)
    funs_impl_data = add.funs_impl.data
    src.append_funs_impl(revised_funs_impl_code, funs_impl_data, patch)  # 除合并 funs_impl 外

    # 更新 CBOR
    src.cbor_update(add.cbor)

    # 更新 constructor
    src.constructor_update()

    return src


def addition_to_source(add: Addition) -> Source:
    src = Source()
    src.selector_generator = copy.deepcopy(add.selector_generator)
    # 创建 selector_trampoline
    src.selector_trampoline = SelectorTrampoline(add.selector.bytecode, add.selector.base, add.middle.length)
    src.fallback_impl = copy.deepcopy(add.fallback_impl)
    src.funs_impl = copy.deepcopy(add.funs_impl)
    # 创建 selector_revise
    src.selector_revise = SelectorRevise(add.selector.bytecode, add.middle.length, add.fallback_impl.base)
    src.extra_data = Data(add.extra_data.bytecode, add.extra_data.base+src.selector_revise.length)  # 多了 selector_revise 到的长度
    src.cbor = Data(add.cbor.bytecode, add.cbor.base+src.selector_revise.length)
    # constructor 修正
    src.constructor_update()
    # codecopy 修正
    src.codecopy_revise(add.extra_data.base+src.selector_revise.length)

    return copy.deepcopy(src)


# 1. 提取 src 中与 add 相对应的 fun_impl 代码
# 2. 按行依次比较字节码是否相等, 但是要忽略三种不相等 ⑴进入补丁(push,jump) ⑵出去补丁的(push,jump,(jumpdest) ⑶补丁新增的代码(push,add)
# 3. 当进入补丁与出去补丁时的 jump 执行其跳转功能, 其余的 jump(i) 不实行
# 4. 终止条件为 add 执行到末尾, 此时返回 True; 否则在执行中一旦发现不同之处, 便返回 False 与 错误的具体位置
def test_equivalence(src: Source, add: Addition) -> bool:
    def is_op_equal(a: list, b: list) -> bool:
        return (a[1] == b[1]) & (a[2] == b[2])

    # ODO 总结, 内联函数可使用外置申请的参数
    def have_little_look(_p: int, _q: int, length=3):
        counter = 0
        first = True
        while counter < length:
            if not is_op_equal(addSrc_impl_code[_p], add_impl_code[_q]):
                if first:
                    print("~~~~~~~跳转中中不同之处~~~~~~")
                print("---------修正代码---------")
                addSrc_funsImpl_code.print_by_line(_p, _p)
                print("----------源代码----------")
                add_funsImpl_code.print_by_line(_q, _q)
                print("~~~~~~~~~~~~~~~~~~~~~~~~~")
            counter += 1
        if not first:
            print()

    addSrc_funsImpl_code = src.get_curr_add()
    add_funsImpl_code = add.funs_impl.code
    addSrc_impl_code = addSrc_funsImpl_code.formatted_bytecode
    add_impl_code = add_funsImpl_code.formatted_bytecode
    # 以下结构辅助用于跳转
    jump_helper1 = addSrc_funsImpl_code.address_lineNum
    jump_helper2 = add_funsImpl_code.address_lineNum
    base1 = src.addition_target + src.funs_impl.base
    base2 = add.funs_impl.base

    # 开始依次比较字节码的等价性
    p = q = 0  # p, q 分别指向 addSrc, add
    is_in_patch = False
    back_line = 0
    while q < len(add_impl_code):
        # 退出补丁
        # 条件 ⑴ 处于进入补丁状态 ⑵ 补丁结束条件1, 出现终止字节码fe  ⑶ 补丁结束条件2, 指向jumpdest, 下一个补丁开头
        if is_in_patch and (addSrc_impl_code[p][1] == op.invalid_fe or addSrc_impl_code[p][1] == op.jumpdest):
            assert (back_line != 0)
            p = back_line
            is_in_patch = False
        # 不相等的话, 判以下是否是需要排除的情况
        if not is_op_equal(addSrc_impl_code[p], add_impl_code[q]):
            # 可能可能是 CFG 修正
            # 条件 ⑴ 同样的 push ⑵ 下一行代码相等
            if is_push(addSrc_impl_code[p][1]) and addSrc_impl_code[p][1] == add_impl_code[q][1] and \
                    addSrc_impl_code[p + 1][1] == add_impl_code[q + 1][1]:
                p += 1
                q += 1
                # 悄悄比较一下跳转后是否相等
                target1 = jump_helper1[Hex(addSrc_impl_code[p - 1][2]) - base1] + 1
                target2 = jump_helper2[Hex(add_impl_code[q - 1][2]) - base2] + 1
                have_little_look(target1, target2)
                continue
            # 能在进入补丁, 首先尝试进入进入跳转
            # 条件 ⑴ addSrc 是 push ⑵ addSrc 下一行代码是 jump ⑶ addSrc 和 add 此字节不能一样（和 CFG 情况分离）
            elif is_push(addSrc_impl_code[p][1]) and addSrc_impl_code[p + 1][1] == op.jump and \
                    addSrc_impl_code[p][1] != add_impl_code[q][1]:
                back_line = p + 2
                target = Hex(addSrc_impl_code[p][2])
                target_line = jump_helper1[target - base1]
                p = target_line + 1  # 跳过 jumpdest
                is_in_patch = True
                continue
            # 判断是否是 add 的补丁
            # 条件 ⑴ 此行代码是 push ⑵ 下一行代码是 op.add
            elif is_push(addSrc_impl_code[p][1]) and addSrc_impl_code[p + 1][1] == op.add:
                p += 2
                continue
            # 判断是否是 codecopy 修正
            # 条件 ⑴ 此行与下行是 codecopy ⑵ 下3行是 codecopy
            elif is_push(addSrc_impl_code[p][1]) and is_push(addSrc_impl_code[p + 1][1]) and \
                    addSrc_impl_code[p + 3][1] == op.codecopy:
                p += 3
                q += 3
            else:  # 真的就是不相等
                print("---------修正代码---------")
                addSrc_funsImpl_code.print_by_line(p - 1, p + 1)
                print("----------源代码----------")
                add_funsImpl_code.print_by_line(q - 1, q + 1)
                print("-------------------------")
                return False

        # 补丁中的跳转, 悄悄比较下跳转后的地址是否相等
        # 条件 ⑴ 当前代码为 jump(i) ⑵ addSrc 的上3行为 push 上两行为 push, 上一行为 add, 代表在加偏置且可计算
        if (addSrc_impl_code[p][1] == op.jump or addSrc_impl_code[p][1] == op.jumpi) and \
                is_push(addSrc_impl_code[p - 3][1]) and is_push(addSrc_impl_code[p - 2][1]) and addSrc_impl_code[p - 1][
            1] == op.add:
            target1 = jump_helper1[Hex(addSrc_impl_code[p - 3][2]) - base1 + Hex(addSrc_impl_code[p - 2][2])] + 1
            target2 = jump_helper2[Hex(add_impl_code[q - 1][2]) - base2] + 1
            have_little_look(target1, target2)
        p += 1
        q += 1

    return True


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
            part = [curr.constructor, curr.selector_generator, curr.selector, curr.fallback_impl, curr.funs_impl,
                    curr.cbor]
            curr_res = list(map(lambda x: x.bytecode, part))
            cons = cons and curr_res == test_res
        return cons


    unknown_bytecode = '608060405234801561001057600080fd5b5060d48061001f6000396000f3fe608060405260043610601c5760003560e01c806312065fe014607f575b7f909c57d5c6ac08245cf2a6de3900e2b868513fa59099b92b27d8db823d92df9c5a60405190815260200160405180910390a160405162461bcd60e51b81526020600482015260016024820152606b60f81b604482015260640160405180910390fd5b348015608a57600080fd5b504760405190815260200160405180910390f3fea2646970667358221220145395ac7890445828b59945e9593ab8919952bb83ad366fc498e807b422da9864736f6c634300080b0033'
    add1_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663a836572881146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600101905600a165627a7a723058201b5930ac885210ff114b55848f959850c81886c515ec221eb475490f85e319a50029'
    double_bytecode = '6080604052348015600f57600080fd5b50609c8061001e6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663eee9720681146043575b600080fd5b348015604e57600080fd5b506058600435606a565b60408051918252519081900360200190f35b600202905600a165627a7a72305820f3a6ecd64c261907682d5ce13a40341199a16032194121592a8017e6692158de0029'
    fibonacci_bytecode = '608060405234801561001057600080fd5b5060d88061001f6000396000f300608060405260043610603e5763ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663421ec76581146043575b600080fd5b348015604e57600080fd5b50605b600435602435606d565b60408051918252519081900360200190f35b6000811515607b57508160a6565b8160011415608c57506001820160a6565b60978360028403606d565b60a28460018503606d565b0190505b929150505600a165627a7a72305820924e3776cadabeb78157c4953a03fef645eca8938de0cd5d40b5cdb2b23c24410029'
    receive_bytecode = '61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3006080604052600436106100435760003560e01c80633ccfd60b1461004f5780638da5cb5b1461006657806391fb54ca14610092578063f2fde38b146100b257600080fd5b3661004a57005b600080fd5b34801561005b57600080fd5b506100646100d2565b005b34801561007257600080fd5b50600054604080516001600160a01b039092168252519081900360200190f35b34801561009e57600080fd5b506100646100ad3660046103ad565b610142565b3480156100be57600080fd5b506100646100cd36600461038b565b610285565b6000546001600160a01b031633146101055760405162461bcd60e51b81526004016100fc90610479565b60405180910390fd5b600080546040516001600160a01b03909116914780156108fc02929091818181858888f1935050505015801561013f573d6000803e3d6000fd5b50565b6000546001600160a01b0316331461016c5760405162461bcd60e51b81526004016100fc90610479565b8051806101b25760405162461bcd60e51b81526020600482015260146024820152731059191c995cdcd95cc81b9bdd081c185cdcd95960621b60448201526064016100fc565b47806102005760405162461bcd60e51b815260206004820152601860248201527f5a65726f2062616c616e636520696e20636f6e7472616374000000000000000060448201526064016100fc565b600061020c83836104ae565b905060005b8381101561027e5784818151811061022b5761022b6104f9565b60200260200101516001600160a01b03166108fc839081150290604051600060405180830381858888f1935050505015801561026b573d6000803e3d6000fd5b5080610276816104d0565b915050610211565b5050505050565b6000546001600160a01b031633146102af5760405162461bcd60e51b81526004016100fc90610479565b6001600160a01b0381166103145760405162461bcd60e51b815260206004820152602660248201527f4f776e61626c653a206e6577206f776e657220697320746865207a65726f206160448201526564647265737360d01b60648201526084016100fc565b600080546040516001600160a01b03808516939216917f8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e091a3600080546001600160a01b0319166001600160a01b0392909216919091179055565b80356001600160a01b038116811461038657600080fd5b919050565b60006020828403121561039d57600080fd5b6103a68261036f565b9392505050565b600060208083850312156103c057600080fd5b823567ffffffffffffffff808211156103d857600080fd5b818501915085601f8301126103ec57600080fd5b8135818111156103fe576103fe61050f565b8060051b604051601f19603f830116810181811085821117156104235761042361050f565b604052828152858101935084860182860187018a101561044257600080fd5b600095505b8386101561046c576104588161036f565b855260019590950194938601938601610447565b5098975050505050505050565b6020808252818101527f4f776e61626c653a2063616c6c6572206973206e6f7420746865206f776e6572604082015260600190565b6000826104cb57634e487b7160e01b600052601260045260246000fd5b500490565b60006000198214156104f257634e487b7160e01b600052601160045260246000fd5b5060010190565b634e487b7160e01b600052603260045260246000fd5b634e487b7160e01b600052604160045260246000fdfea2646970667358221220594ba90ab1a8938f3f895b587b8a56160dd82a85f8823b4a95e1b9aec4a8a17964736f6c63430008070033'
    BasicMathLib_1_0425 = '61011e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3007300000000000000000000000000000000000000003014608060405260043610605f5763ffffffff7c01000000000000000000000000000000000000000000000000000000006000350416631d3b9edf81146064578063e39bbf6814608b575b600080fd5b60706004356024356097565b60408051921515835260208301919091528051918290030190f35b607060043560243560be565b60008282028215838204851417801560ad5760b6565b60019250600091505b509250929050565b600080808315801560d557600193506000925060e9565b604051858704602090910181905292508291505b505092509290505600a165627a7a72305820c9bd59df95a25fbb54d11f0274e5bf311273c1ee09f40d24c5c25f32453098ac0029'
    BasicMathLib_2_0425 = '61010d610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3007300000000000000000000000000000000000000003014608060405260043610605f5763ffffffff7c010000000000000000000000000000000000000000000000000000000060003504166366098d4f81146064578063f4f3bdc114608b575b600080fd5b60706004356024356097565b60408051921515835260208301919091528051918290030190f35b607060043560243560c3565b600082820182810384148382118285141716801560b25760bb565b60019250600091505b509250929050565b600081830380830184148482108286141716600114801560b25760bb5600a165627a7a72305820b7904782a0adc4afaeb0af37106bd6780e89c5e34c2bebd65b7df2332448f18b0029'

    # 单元测试 - 划分模块
    # print(test_divider())

    # 等价性测试 - 合并模块
    source_temp = Addition(BasicMathLib_1_0425)
    source = addition_to_source(source_temp)
    addition = Addition(BasicMathLib_2_0425)
    source = combine_bytecode(source, addition)
    print(test_equivalence(source, addition))
