// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

contract Impl {
    function hello() public pure returns(bytes memory) {
        return "hello world";
    }
}

contract Proxy {
    address implLibrary;

    constructor (address impl) {
        implLibrary = impl;
    }

    function exec (bytes memory funsig) public returns (bool, bytes memory) {
        (bool success, bytes memory data) = implLibrary.delegatecall(funsig);
        return (success, data);
    }

    function updateImpl (address newImpl) public {
        implLibrary = newImpl;
    }
}