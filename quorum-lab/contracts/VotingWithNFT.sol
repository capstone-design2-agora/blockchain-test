// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title VotingWithNFT
/// @notice Simple ballot where each voter receives an ERC-721 receipt after casting a vote.
contract VotingWithNFT is ERC721, Ownable {
    struct Proposal {
        string name;
        uint256 voteCount;
    }

    struct BallotReceipt {
        uint256 proposalId;
        uint256 blockNumber;
    }

    uint256 private _nextTokenId;
    Proposal[] private _proposals;

    mapping(address => bool) public hasVoted;
    mapping(uint256 => BallotReceipt) private _receipts;

    event ProposalAdded(uint256 indexed proposalId, string name);
    event VoteCast(address indexed voter, uint256 indexed proposalId, uint256 indexed tokenId);

    constructor(
        string memory name_,
        string memory symbol_,
        string[] memory proposalNames
    ) ERC721(name_, symbol_) Ownable(msg.sender) {
        for (uint256 i = 0; i < proposalNames.length; i++) {
            _proposals.push(Proposal({name: proposalNames[i], voteCount: 0}));
            emit ProposalAdded(i, proposalNames[i]);
        }
    }

    /// @notice Add a proposal to the current ballot.
    /// @dev Restricted to the contract owner to keep the ballot curated.
    function addProposal(string calldata name) external onlyOwner returns (uint256 proposalId) {
        proposalId = _proposals.length;
        _proposals.push(Proposal({name: name, voteCount: 0}));
        emit ProposalAdded(proposalId, name);
    }

    /// @notice Cast a vote for an existing proposal and receive an NFT receipt.
    /// @param proposalId Proposal index the caller is voting for.
    /// @return tokenId Minted ERC-721 token identifier representing the vote.
    function vote(uint256 proposalId) external returns (uint256 tokenId) {
        require(proposalId < _proposals.length, "Proposal does not exist");
        require(!hasVoted[msg.sender], "Already voted");

        hasVoted[msg.sender] = true;
        _proposals[proposalId].voteCount += 1;

        tokenId = _nextTokenId;
        unchecked {
            _nextTokenId += 1;
        }

        _safeMint(msg.sender, tokenId);

        _receipts[tokenId] = BallotReceipt({
            proposalId: proposalId,
            blockNumber: block.number
        });

        emit VoteCast(msg.sender, proposalId, tokenId);
    }

    /// @notice Number of proposals currently registered.
    function proposalCount() external view returns (uint256) {
        return _proposals.length;
    }

    /// @notice View helper for a single proposal.
    function getProposal(uint256 proposalId) external view returns (Proposal memory) {
        require(proposalId < _proposals.length, "Proposal does not exist");
        return _proposals[proposalId];
    }

    /// @notice Retrieve the receipt metadata associated with a minted vote NFT.
    function getReceipt(uint256 tokenId) external view returns (BallotReceipt memory) {
        _requireOwned(tokenId);
        return _receipts[tokenId];
    }
}
