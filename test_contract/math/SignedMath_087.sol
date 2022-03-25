// SPDX-License-Identifier: MIT

pragma solidity 0.8.7;

/**
 * @dev Standard signed math utilities missing in the Solidity language.
 */
library SignedMath {
    /**
     * @dev Returns the average of two signed numbers without overflow.
     * The result is rounded towards zero.
     */
    function signed_average(int256 a, int256 b) public pure returns (int256) {
        // Formula from the book "Hacker's Delight"
        int256 x = (a & b) + ((a ^ b) >> 1);
        return x + (int256(uint256(x) >> 255) & (a ^ b));
    }

    /**
     * @dev Returns the absolute unsigned value of a signed value.
     */
    function signed_abs(int256 n) public pure returns (uint256) {
        unchecked {
            // must be unchecked in order to support `n = type(int256).min`
            return uint256(n >= 0 ? n : -n);
        }
    }

        /**
     * @dev Returns the largest of two signed numbers.
     */
    function signed_max(int256 a, int256 b) public pure returns (int256) {
        return a >= b ? a : b;
    }

    /**
     * @dev Returns the smallest of two signed numbers.
     */
    function signed_min(int256 a, int256 b) public pure returns (int256) {
        return a < b ? a : b;
    }
}
