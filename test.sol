contract Add1 {
   function add1(uint256 a) public pure returns(uint256) {
       return a + 1;
   }
}

contract Double {
   function double(uint256 num) public pure returns(uint256) {
       return num * 2;
   }
}

contract FibonacciLib {
    function fibonacci(uint start, uint n) public returns (uint) {
        if (n == 0) return start;
        else if (n == 1) return start + 1;
        else return fibonacci(start, n - 1) + fibonacci(start, n - 2);
    }
}

contract Math {
    function sqrt(uint y) public pure returns (uint z) {
        if (y > 3) {
            z = y;
            uint x = y / 2 + 1;
            while (x < z) {
                z = x;
                x = (y / x + x) / 2;
            }
        } else if (y != 0) {
            z = 1;
        }
        // else z = 0 (default value)
    }
}

contract Impl {
    function add_list(uint[] memory ls) public pure returns(uint z) {
        z = 0;
        for (uint i = 0; i < ls.length; i++){
            z += ls[i];
        }
    }
}