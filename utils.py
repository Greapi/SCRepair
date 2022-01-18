# 16 进制的运算
from evmdasm import EvmBytecode


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
        opcode += '{}[{}] [{}] {}{}\n'.format(start, hex(i // 2 + base), hex(i // 2), op, end)
        # opcode += '{}\n'.format(op)
        i += inc
    return opcode