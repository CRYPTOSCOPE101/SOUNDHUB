// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { IERC20 } from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import { SafeERC20 } from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import { Ownable } from "@openzeppelin/contracts/access/Ownable.sol";

/// @title SoundHubFaucet — testnet SND dispenser
/// @notice Lets testers claim a small amount of SND once per cooldown to try
///         the marketplace. Funded by the deployer; owner can pull funds back.
contract SoundHubFaucet is Ownable {
    using SafeERC20 for IERC20;

    IERC20 public snd;
    uint256 public amountPerClaim = 100 * 1e18; // 100 SND
    uint256 public cooldown = 1 days;

    mapping(address => uint256) public lastClaimAt;

    event Claimed(address indexed to, uint256 amount);
    event ParamsUpdated(uint256 amountPerClaim, uint256 cooldown);

    error CooldownNotElapsed();
    error NotEnoughFunds();

    constructor(address snd_) Ownable(msg.sender) {
        snd = IERC20(snd_);
    }

    function claim() external {
        if (block.timestamp < lastClaimAt[msg.sender] + cooldown) {
            revert CooldownNotElapsed();
        }
        if (snd.balanceOf(address(this)) < amountPerClaim) {
            revert NotEnoughFunds();
        }
        lastClaimAt[msg.sender] = block.timestamp;
        snd.safeTransfer(msg.sender, amountPerClaim);
        emit Claimed(msg.sender, amountPerClaim);
    }

    function setParams(uint256 amountPerClaim_, uint256 cooldown_) external onlyOwner {
        amountPerClaim = amountPerClaim_;
        cooldown = cooldown_;
        emit ParamsUpdated(amountPerClaim_, cooldown_);
    }

    /// @notice Pull any remaining SND back to the owner (testnet hygiene).
    function withdraw() external onlyOwner {
        snd.safeTransfer(msg.sender, snd.balanceOf(address(this)));
    }
}
