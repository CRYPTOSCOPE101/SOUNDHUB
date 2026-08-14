// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { IERC20 } from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import { SafeERC20 } from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import { Ownable } from "@openzeppelin/contracts/access/Ownable.sol";
import { ReentrancyGuard } from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title SoundHubMarket — buy finished sounds, don't generate them
/// @notice A token-powered marketplace for ready-made presets, samples and
///         sound packs. Buyers pay SND into escrow, receive the asset pointer
///         + license, and sellers get paid after confirmation or the dispute
///         window. Owner acts as arbiter for refunds (later: DAO).
contract SoundHubMarket is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    enum License { Personal, Commercial, Sync, Exclusive }

    struct Listing {
        uint256 id;
        address seller;
        string name;
        string assetUri; // pointer to the sound file (repo path or IPFS)
        uint256 price; // in SND wei
        License license;
        bool active;
        // escrow state
        address buyer;
        uint256 escrowed;
        uint256 purchasedAt;
        bool released; // payout happened (buyer confirmed or window passed)
        bool refundRequested;
    }

    uint256 public nextListingId = 1;
    IERC20 public sndToken;
    uint256 public disputeWindow = 2 days;

    mapping(uint256 => Listing) public listings;

    event Listed(uint256 indexed id, address indexed seller, string name, uint256 price);
    event Delisted(uint256 indexed id);
    event Purchased(uint256 indexed id, address indexed buyer, uint256 amount);
    event RefundRequested(uint256 indexed id);
    event Refunded(uint256 indexed id, address indexed buyer, uint256 amount);
    event Withdrawn(uint256 indexed id, address indexed seller, uint256 amount);

    error NotSeller();
    error NotBuyer();
    error NotActive();
    error AlreadySold();
    error ZeroPrice();
    error NothingEscrowed();
    error WindowClosed();
    error AlreadyRequested();
    error NoRefundRequest();
    error AlreadyReleased();

    constructor(address snd_) Ownable(msg.sender) {
        sndToken = IERC20(snd_);
    }

    /// @notice Seller lists a finished sound/preset for sale in SND.
    function list(
        string calldata name,
        string calldata assetUri,
        uint256 price,
        License license_
    ) external returns (uint256 id) {
        if (price == 0) revert ZeroPrice();
        id = nextListingId++;
        listings[id] = Listing({
            id: id,
            seller: msg.sender,
            name: name,
            assetUri: assetUri,
            price: price,
            license: license_,
            active: true,
            buyer: address(0),
            escrowed: 0,
            purchasedAt: 0,
            released: false,
            refundRequested: false
        });
        emit Listed(id, msg.sender, name, price);
    }

    function delist(uint256 id) external {
        Listing storage l = listings[id];
        if (l.seller != msg.sender || !l.active) revert NotSeller();
        if (l.escrowed > 0) revert AlreadySold();
        l.active = false;
        emit Delisted(id);
    }

    /// @notice Buyer pays SND into escrow; receives asset + license.
    function buy(uint256 id) external nonReentrant {
        Listing storage l = listings[id];
        if (!l.active) revert NotActive();
        if (l.escrowed > 0) revert AlreadySold();
        sndToken.safeTransferFrom(msg.sender, address(this), l.price);
        l.buyer = msg.sender;
        l.escrowed = l.price;
        l.purchasedAt = block.timestamp;
        emit Purchased(id, msg.sender, l.price);
    }

    /// @notice Buyer confirms receipt — seller is paid immediately.
    function confirmReceipt(uint256 id) external {
        Listing storage l = listings[id];
        if (l.buyer != msg.sender) revert NotBuyer();
        if (l.released) revert AlreadyReleased();
        _release(id, l.seller);
    }

    /// @notice Seller pulls payment after the dispute window.
    function withdraw(uint256 id) external nonReentrant {
        Listing storage l = listings[id];
        if (l.seller != msg.sender) revert NotSeller();
        if (l.released) revert AlreadyReleased();
        if (block.timestamp <= l.purchasedAt + disputeWindow) revert WindowClosed();
        _release(id, l.seller);
    }

    /// @notice Buyer asks for a refund inside the dispute window.
    function requestRefund(uint256 id) external {
        Listing storage l = listings[id];
        if (l.buyer != msg.sender) revert NotBuyer();
        if (l.released) revert AlreadyReleased();
        if (block.timestamp > l.purchasedAt + disputeWindow) revert WindowClosed();
        if (l.refundRequested) revert AlreadyRequested();
        l.refundRequested = true;
        emit RefundRequested(id);
    }

    /// @notice Arbiter (owner today, DAO later) resolves a refund request.
    function resolveRefund(uint256 id, bool approve) external onlyOwner {
        Listing storage l = listings[id];
        if (!l.refundRequested) revert NoRefundRequest();
        if (l.released) revert AlreadyReleased();
        l.refundRequested = false;
        if (approve) {
            _release(id, l.buyer);
            emit Refunded(id, l.buyer, 0);
        }
    }

    function _release(uint256 id, address to) internal {
        Listing storage l = listings[id];
        uint256 amount = l.escrowed;
        l.escrowed = 0;
        l.released = true;
        sndToken.safeTransfer(to, amount);
        emit Withdrawn(id, to, amount);
    }
}
