from conbinPatch import combine_bytecode, BytecodeAnalysis


class DISTLibrary:

    def __init__(self, proxy_addr='', imp_addr=''):
        if not proxy_addr and not imp_addr:
            self.imp_addr = imp_addr
            self.proxy_addr = proxy_addr
            # TODO: 从远端获取当前的字节码
            bytecode = ''
            self.curr_analysis_code = BytecodeAnalysis(bytecode)
        # TODO: 初始化部署代理合约与实现合约

    def append(self, bytecode: str):
        code_analysis = BytecodeAnalysis(bytecode)
        combined = combine_bytecode(self.curr_analysis_code, code_analysis)
        # TODO: 部署 combined.bytecode
        self.curr_analysis_code = combined
