import os
# 用于将 Remix 中拷贝出来一行的字节码，转化成多行形式
def _convert_remix(codes: str):
    num = 0
    converted = '0x0 '
    i = 0
    codes = codes.split(' ')
    while True:
        converted += codes[i]
        if codes[i].startswith('PUSH'):
            bytes_num = int(codes[i].replace('PUSH', ''))  # 计算压栈的 byte 数目
            i += 1  # 指针指向下一个参数, 也就是实际的压栈数据
            add_zero = bytes_num * 2 - len(codes[i][2:])  # 根据 PUSH? 确定需要补零的数目
            hex_num = '0x' + '0' * add_zero + codes[i][2:]
            converted += ' => ' + hex_num
            num += bytes_num  # 加入压栈的 byte 数目
        if i == len(codes) - 1:  # 最后一个
            break
        num += 1
        converted += '\n' + hex(num) + ' '
        i += 1
    return converted

def convert_remix(fileName: str):
    fileName = "double-opcode.txt"
    with open(fileName) as f:
        convert = _convert_remix(f.read())
    os.remove(fileName)
    with open(fileName, 'w') as f:
        f.write(convert)

def index_opcode(file: str):
    with open(file) as f:
        convert = ''
        for line in f.readlines():
            divide = line.split(' ')
            num = int(divide[0].replace('[', '').replace(']', '')) - 1
            hex_num = hex(num)
            new_line = '[' + hex_num + ']' + line.replace(divide[0], '')
            convert += new_line
    with open('_' + file, 'w') as f:
        f.write(convert)

if __name__ == "__main__":
    index_opcode('c.txt')
    print("ok")