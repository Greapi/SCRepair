// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Impl {
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

contract Proxy {
    address public implLibrary;

    constructor (address impl) {
        implLibrary = impl;
    }

    function exec (bytes memory input_data) public returns (bool, bytes memory) {
        (bool success, bytes memory data) = implLibrary.delegatecall(input_data);
        return (success, data);
    }

    function updateImpl (address newImpl) public {
        implLibrary = newImpl;
    }
}