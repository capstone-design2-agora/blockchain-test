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

    struct BallotMetadata {
        string id;
        string title;
        string description;
        uint256 opensAt;
        uint256 closesAt;
        uint256 announcesAt;
        uint256 expectedVoters;
    }

    uint256 private _nextTokenId;
    Proposal[] private _proposals;

    mapping(address => bool) public hasVoted;
    mapping(uint256 => BallotReceipt) private _receipts;
    BallotMetadata private _ballot;

    event ProposalAdded(uint256 indexed proposalId, string name);
    event VoteCast(address indexed voter, uint256 indexed proposalId, uint256 indexed tokenId);
    event BallotDetailsUpdated(string title, string description);
    event BallotScheduleUpdated(uint256 opensAt, uint256 closesAt, uint256 announcesAt);
    event ExpectedVotersUpdated(uint256 expectedVoters);

    constructor(
        string memory name_,
        string memory symbol_,
        string[] memory proposalNames,
        string memory ballotId,
        string memory title_,
        string memory description_,
        uint256 opensAt,
        uint256 closesAt,
        uint256 announcesAt,
        uint256 expectedVoters
    ) ERC721(name_, symbol_) Ownable(msg.sender) {
        for (uint256 i = 0; i < proposalNames.length; i++) {
            _proposals.push(Proposal({name: proposalNames[i], voteCount: 0}));
            emit ProposalAdded(i, proposalNames[i]);
        }

        _ballot = BallotMetadata({
            id: ballotId,
            title: title_,
            description: description_,
            opensAt: opensAt,
            closesAt: closesAt,
            announcesAt: announcesAt,
            expectedVoters: expectedVoters
        });

        emit BallotDetailsUpdated(title_, description_);
        emit BallotScheduleUpdated(opensAt, closesAt, announcesAt);
        emit ExpectedVotersUpdated(expectedVoters);
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
        if (_ballot.opensAt != 0) {
            require(block.timestamp >= _ballot.opensAt, "Voting has not opened");
        }
        if (_ballot.closesAt != 0) {
            require(block.timestamp <= _ballot.closesAt, "Voting has closed");
        }

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

    /// @notice Return the ballot level metadata including schedule information.
    function ballotMetadata() external view returns (BallotMetadata memory) {
        return _ballot;
    }

    /// @notice Update the descriptive details of the ballot.
    function updateBallotDetails(string calldata title_, string calldata description_) external onlyOwner {
        _ballot.title = title_;
        _ballot.description = description_;
        emit BallotDetailsUpdated(title_, description_);
    }

    /// @notice Update the ballot schedule timestamps.
    function updateBallotSchedule(uint256 opensAt, uint256 closesAt, uint256 announcesAt) external onlyOwner {
        if (closesAt != 0) {
            require(closesAt >= opensAt, "Close time must be after open");
        }
        if (announcesAt != 0 && closesAt != 0) {
            require(announcesAt >= closesAt, "Announce time must be after close");
        }
        _ballot.opensAt = opensAt;
        _ballot.closesAt = closesAt;
        _ballot.announcesAt = announcesAt;
        emit BallotScheduleUpdated(opensAt, closesAt, announcesAt);
    }

    /// @notice Update the expected voter count used for turnout calculations.
    function updateExpectedVoters(uint256 expectedVoters) external onlyOwner {
        _ballot.expectedVoters = expectedVoters;
        emit ExpectedVotersUpdated(expectedVoters);
    }
}
