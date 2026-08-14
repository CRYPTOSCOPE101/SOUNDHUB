// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { ERC721 } from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import { ERC2981 } from "@openzeppelin/contracts/token/common/ERC2981.sol";
import { Ownable } from "@openzeppelin/contracts/access/Ownable.sol";
import { ReentrancyGuard } from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import { IERC20 } from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import { SafeERC20 } from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/// @title SoundHubRelease — music release NFTs
/// @notice A release token represents a finished track/project. It carries
///         an ERC-2981 royalty, an on-chain collaborator revenue split, and a
///         treasury that fans can fund with ETH or SND. Collaborators claim
///         their share of the treasury on-chain.
contract SoundHubRelease is ERC721, ERC2981, Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    struct Release {
        string name;
        string metadata; // on-chain JSON metadata
        address[] collaborators;
        uint256[] shares; // basis-point weights, must sum to 10_000
        uint256 totalShares;
        uint256 ethReceived; // total ETH ever funded (for correct split math)
        uint256 sndReceived; // total SND ever funded
    }

    uint256 public nextTokenId = 1;
    IERC20 public sndToken; // set after SND deployment
    uint96 public defaultRoyaltyBps = 500; // 5%

    mapping(uint256 => Release) private _releases;
    // per-collaborator amounts already claimed, keyed by (tokenId, address)
    mapping(uint256 => mapping(address => uint256)) public ethClaimed;
    mapping(uint256 => mapping(address => uint256)) public sndClaimed;

    event ReleaseMinted(uint256 indexed tokenId, address indexed minter, string name);
    event FundsAdded(uint256 indexed tokenId, address indexed funder, uint256 amount, bool isEth);
    event RoyaltyClaimed(uint256 indexed tokenId, address indexed collaborator, uint256 amount, bool isEth);

    error InvalidSplit();
    error ZeroAddress();
    error RoyaltyTooHigh();
    error NotCollaborator();
    error NothingToClaim();

    constructor() ERC721("SoundHub Release", "SNDREL") Ownable(msg.sender) {}

    /// @notice Mint a release NFT. Minter receives the token; collaborators
    ///         are set as the revenue split. Royalty goes to the minter.
    function mintRelease(
        string calldata name,
        string calldata metadata,
        address[] calldata collaborators,
        uint256[] calldata shares,
        uint96 royaltyBps
    ) external returns (uint256 tokenId) {
        if (collaborators.length == 0 || collaborators.length != shares.length) {
            revert InvalidSplit();
        }
        uint256 total;
        for (uint256 i = 0; i < shares.length; i++) {
            if (collaborators[i] == address(0)) revert ZeroAddress();
            total += shares[i];
        }
        if (total != 10_000) revert InvalidSplit();
        if (royaltyBps > 10_000) revert RoyaltyTooHigh();

        tokenId = nextTokenId++;
        _safeMint(msg.sender, tokenId);
        _setTokenRoyalty(tokenId, msg.sender, royaltyBps == 0 ? defaultRoyaltyBps : royaltyBps);

        Release storage r = _releases[tokenId];
        r.name = name;
        r.metadata = metadata;
        r.collaborators = collaborators;
        r.shares = shares;
        r.totalShares = total;

        emit ReleaseMinted(tokenId, msg.sender, name);
    }

    /// @notice Fund a release treasury with ETH.
    function fund(uint256 tokenId) external payable {
        if (msg.value == 0) revert NothingToClaim();
        _releases[tokenId].ethReceived += msg.value;
        emit FundsAdded(tokenId, msg.sender, msg.value, true);
    }

    /// @notice Fund a release treasury with SND.
    function fundWithSND(uint256 tokenId, uint256 amount) external {
        if (amount == 0) revert NothingToClaim();
        if (address(sndToken) == address(0)) revert ZeroAddress();
        sndToken.safeTransferFrom(msg.sender, address(this), amount);
        _releases[tokenId].sndReceived += amount;
        emit FundsAdded(tokenId, msg.sender, amount, false);
    }

    /// @notice A collaborator claims their proportional share of ETH and SND.
    ///         Splits are computed against the total ever received, so claim
    ///         order does not matter.
    function claim(uint256 tokenId) external nonReentrant {
        Release storage r = _releases[tokenId];
        uint256 share;
        bool found;
        for (uint256 i = 0; i < r.collaborators.length; i++) {
            if (r.collaborators[i] == msg.sender) {
                share = r.shares[i];
                found = true;
                break;
            }
        }
        if (!found) revert NotCollaborator();

        uint256 ethEntitled = (r.ethReceived * share) / r.totalShares;
        uint256 ethDue = ethEntitled - ethClaimed[tokenId][msg.sender];
        uint256 sndEntitled = (r.sndReceived * share) / r.totalShares;
        uint256 sndDue = sndEntitled - sndClaimed[tokenId][msg.sender];

        if (ethDue == 0 && sndDue == 0) revert NothingToClaim();

        if (ethDue > 0) {
            ethClaimed[tokenId][msg.sender] += ethDue;
            (bool ok, ) = payable(msg.sender).call{ value: ethDue }("");
            require(ok, "eth transfer failed");
            emit RoyaltyClaimed(tokenId, msg.sender, ethDue, true);
        }
        if (sndDue > 0) {
            sndClaimed[tokenId][msg.sender] += sndDue;
            sndToken.safeTransfer(msg.sender, sndDue);
            emit RoyaltyClaimed(tokenId, msg.sender, sndDue, false);
        }
    }

    function setSndToken(IERC20 token) external onlyOwner {
        sndToken = token;
    }

    function releaseOf(uint256 tokenId)
        external
        view
        returns (string memory name, string memory metadata, address[] memory collaborators, uint256[] memory shares, uint256 ethReceived, uint256 sndReceived)
    {
        Release storage r = _releases[tokenId];
        return (r.name, r.metadata, r.collaborators, r.shares, r.ethReceived, r.sndReceived);
    }

    /// @notice How much ETH/SND a collaborator can still claim.
    function claimable(uint256 tokenId, address collaborator)
        external
        view
        returns (uint256 ethDue, uint256 sndDue)
    {
        Release storage r = _releases[tokenId];
        for (uint256 i = 0; i < r.collaborators.length; i++) {
            if (r.collaborators[i] == collaborator) {
                uint256 share = r.shares[i];
                return (
                    (r.ethReceived * share) / r.totalShares - ethClaimed[tokenId][collaborator],
                    (r.sndReceived * share) / r.totalShares - sndClaimed[tokenId][collaborator]
                );
            }
        }
        return (0, 0);
    }

    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        Release storage r = _releases[tokenId];
        if (bytes(r.metadata).length > 0) return r.metadata;
        return string(
            abi.encodePacked(
                "data:application/json;base64,",
                _base64(bytes(string(abi.encodePacked('{"name":"', r.name, '"}'))))
            )
        );
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC721, ERC2981) returns (bool) {
        return super.supportsInterface(interfaceId);
    }

    // -- internal helpers --

    function _base64(bytes memory data) internal pure returns (string memory) {
        bytes memory table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        if (data.length == 0) return "";
        uint256 encodedLen = 4 * ((data.length + 2) / 3);
        bytes memory out = new bytes(encodedLen);
        uint256 j;
        for (uint256 i = 0; i < data.length; i += 3) {
            uint256 a = uint8(data[i]);
            uint256 b = i + 1 < data.length ? uint8(data[i + 1]) : 0;
            uint256 c = i + 2 < data.length ? uint8(data[i + 2]) : 0;
            out[j++] = table[(a >> 2) & 0x3f];
            out[j++] = table[((a & 0x03) << 4) | ((b >> 4) & 0x0f)];
            out[j++] = i + 1 < data.length ? table[((b & 0x0f) << 2) | ((c >> 6) & 0x03)] : bytes1("=");
            out[j++] = i + 2 < data.length ? table[c & 0x3f] : bytes1("=");
        }
        return string(out);
    }
}
