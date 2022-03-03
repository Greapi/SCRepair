pragma solidity ^0.4.18;

/// 0.4.20
/// [{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"times","outputs":[{"name":"err","type":"bool"},{"name":"res","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"dividedBy","outputs":[{"name":"err","type":"bool"},{"name":"i","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]
/// 61017e610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3007300000000000000000000000000000000000000003014606060405260043610610063576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff1680631d3b9edf14610068578063e39bbf68146100a8575b600080fd5b61008760048080359060200190919080359060200190919050506100e8565b60405180831515151581526020018281526020019250505060405180910390f35b6100c76004808035906020019091908035906020019091905050610116565b60405180831515151581526020018281526020019250505060405180910390f35b60008082840290508383820414831517600081146101055761010e565b60019250600091505b509250929050565b6000806000831560008114610132576001935060009250610149565b848604915060405182602082015260208101519350505b505092509290505600a165627a7a72305820ab750985aefc75fe78e2313324cc14fb62fa1023aa5c817fc686feb8f8731d1c0029

library BasicMathLib_v1 {
  /// @dev Multiplies two numbers and checks for overflow before returning.
  /// Does not throw.
  /// @param a First number
  /// @param b Second number
  /// @return err False normally, or true if there is overflow
  /// @return res The product of a and b, or 0 if there is overflow
  function times(uint256 a, uint256 b) public pure returns (bool err,uint256 res) {
    assembly{
      res := mul(a,b)
      switch or(iszero(b), eq(div(res,b), a))
      case 0 {
        err := 1
        res := 0
      }
    }
  }
  /// @dev Divides two numbers but checks for 0 in the divisor first.
  /// Does not throw.
  /// @param a First number
  /// @param b Second number
  /// @return err False normally, or true if `b` is 0
  /// @return res The quotient of a and b, or 0 if `b` is 0
  function dividedBy(uint256 a, uint256 b) public pure returns (bool err,uint256 i) {
    uint256 res;
    assembly{
      switch iszero(b)
      case 0 {
        res := div(a,b)
        let loc := mload(0x40)
        mstore(add(loc,0x20),res)
        i := mload(add(loc,0x20))
      }
      default {
        err := 1
        i := 0
      }
    }
  }
}

/// 0.4.20
/// [{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"plus","outputs":[{"name":"err","type":"bool"},{"name":"res","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"a","type":"uint256"},{"name":"b","type":"uint256"}],"name":"minus","outputs":[{"name":"err","type":"bool"},{"name":"res","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]
/// 61017d610030600b82828239805160001a6073146000811461002057610022565bfe5b5030600052607381538281f3007300000000000000000000000000000000000000003014606060405260043610610063576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff16806366098d4f14610068578063f4f3bdc1146100a8575b600080fd5b61008760048080359060200190919080359060200190919050506100e8565b60405180831515151581526020018281526020019250505060405180910390f35b6100c7600480803590602001909190803590602001909190505061011b565b60405180831515151581526020018281526020019250505060405180910390f35b6000808284019050828114838211178484830314166000811461010a57610113565b60019250600091505b509250929050565b6000808284039050600184821485831017858584011416146000811461014057610149565b60019250600091505b5092509290505600a165627a7a7230582033b5d8afbe2a18242836b975fbdc1191288b4cecef20f779e7ab377cc5b61d3b0029

library BasicMathLib_v2 {
  /// @dev Adds two numbers and checks for overflow before returning.
  /// Does not throw.
  /// @param a First number
  /// @param b Second number
  /// @return err False normally, or true if there is overflow
  /// @return res The sum of a and b, or 0 if there is overflow
  function plus(uint256 a, uint256 b) public pure returns (bool err, uint256 res) {
    assembly{
      res := add(a,b)
      switch and(eq(sub(res,b), a), or(gt(res,b),eq(res,b)))
      case 0 {
        err := 1
        res := 0
      }
    }
  }

  /// @dev Subtracts two numbers and checks for underflow before returning.
  /// Does not throw but rather logs an Err event if there is underflow.
  /// @param a First number
  /// @param b Second number
  /// @return err False normally, or true if there is underflow
  /// @return res The difference between a and b, or 0 if there is underflow
  function minus(uint256 a, uint256 b) public pure returns (bool err,uint256 res) {
    assembly{
      res := sub(a,b)
      switch eq(and(eq(add(res,b), a), or(lt(res,a), eq(res,a))), 1)
      case 0 {
        err := 1
        res := 0
      }
    }
  }
}