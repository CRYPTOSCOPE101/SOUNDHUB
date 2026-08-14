// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { ERC20 } from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import { ERC20Permit } from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import { ERC20Votes } from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Votes.sol";
import { Ownable } from "@openzeppelin/contracts/access/Ownable.sol";
import { Nonces } from "@openzeppelin/contracts/utils/Nonces.sol";

/// @title SND — SoundHub platform token
/// @notice ERC-20 with permit and on-chain governance voting (ERC20Votes).
///         Fixed supply minted at deployment; no further minting.
contract SND is ERC20, ERC20Permit, ERC20Votes, Ownable {
    constructor(address initialOwner, uint256 initialSupply)
        ERC20("SoundHub Token", "SND")
        ERC20Permit("SoundHub Token")
        Ownable(initialOwner)
    {
        _mint(initialOwner, initialSupply);
    }

    // -- overrides required by Solidity (ERC20Votes <-> ERC20 / Permit) --

    function _update(address from, address to, uint256 value)
        internal
        override(ERC20, ERC20Votes)
    {
        super._update(from, to, value);
    }

    function nonces(address owner) public view override(ERC20Permit, Nonces) returns (uint256) {
        return super.nonces(owner);
    }
}
