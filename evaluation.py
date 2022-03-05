from conbinPatch import Addition
from utils import to_opcode
import os
import csv


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


if __name__ == '__main__':
    # 批量测试划分模块是否正常
    test_divider('valid_dataset')

    # 用于测试某个特定的合约
    # constructor = '61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f300'
    # Addition(constructor+'608060405273ffffffffffffffffffffffffffffffffffffffff600054167fa619486e0000000000000000000000000000000000000000000000000000000060003514156050578060005260206000f35b3660008037600080366000845af43d6000803e60008114156070573d6000fd5b3d6000f3fea264697066735822122056e8ae02bde6776b1debb4cdca0d5f13ebc4d11705a6711c07d9ed69e0d5f37264736f6c63430006000033')
