# SBT-Based Wallet Binding Implementation Specification

## Overview

This document outlines the implementation of a Soulbound Token (SBT) based wallet binding system for the voting platform. The system ensures one-person-one-vote by binding a verified identity to a single wallet address permanently.

## Objectives

1. **Prevent Sybil Attacks**: Ensure that one person can only vote once, regardless of how many wallets they create
2. **Wallet Binding**: Permanently bind a verified identity to a single wallet address using SBT
3. **Dummy Verification**: Implement a mock identity verification flow for development and testing
4. **User Experience**: Create a smooth onboarding flow for first-time users

## Architecture

```
┌─────────────────┐
│  Frontend       │
│  - Auth Page    │──┐
│  - Voting Page  │  │
└─────────────────┘  │
                     │
                     ▼
┌─────────────────────────────────────┐
│  Smart Contracts                    │
│  - CitizenSBT (ERC-721, Soulbound) │
│  - VotingWithSBT                    │
└─────────────────────────────────────┘
                     │
                     ▼
┌─────────────────┐
│  Blockchain     │
│  - Identity Hash│
│  - SBT Binding  │
└─────────────────┘
```

## Components

### 1. CitizenSBT Smart Contract

**Purpose**: Issue non-transferable SBT tokens to verified users

**Key Features**:
- ERC-721 compliant but non-transferable (Soulbound)
- Maps identity hash to wallet address
- Prevents duplicate registrations
- Only authorized verifier can mint

**Interface**:

```solidity
contract CitizenSBT is ERC721 {
    // Identity hash => wallet address
    mapping(bytes32 => address) public identityToWallet;
    
    // Wallet => has SBT
    mapping(address => bool) public hasSBT;
    
    // Verifier address (for dummy verification)
    address public verifier;
    
    // Mint SBT to a wallet with identity hash
    function mint(address to, bytes32 identityHash) external;
    
    // Check if identity hash is already registered
    function isIdentityRegistered(bytes32 identityHash) external view returns (bool);
    
    // Override transfer functions to make it soulbound
    function _transfer(...) internal pure override;
    function approve(...) public pure override;
    function setApprovalForAll(...) public pure override;
}
```

### 2. VotingWithSBT Smart Contract

**Purpose**: Voting contract that requires SBT for participation

**Key Features**:
- Checks SBT ownership before allowing votes
- Issues reward NFT (transferable) after voting
- Ballot metadata and proposal management

**Interface**:

```solidity
contract VotingWithSBT {
    CitizenSBT public citizenSBT;
    VotingRewardNFT public rewardNFT;
    
    // Vote with SBT verification
    function vote(uint256 proposalId) external returns (uint256 rewardTokenId);
    
    // Check if address can vote
    function canVote(address voter) external view returns (bool);
}
```

### 3. VotingRewardNFT Smart Contract

**Purpose**: Issue transferable reward NFTs with mascot images

**Key Features**:
- Standard ERC-721 (transferable)
- Each ballot has unique mascot image
- TokenURI returns metadata with image URL

**Interface**:

```solidity
contract VotingRewardNFT is ERC721 {
    // Base URI for mascot images
    string private _baseTokenURI;
    
    // Ballot ID => Image URI
    mapping(string => string) public ballotImages;
    
    // Mint reward NFT
    function mint(address to, string memory ballotId) external returns (uint256);
    
    // Get token metadata
    function tokenURI(uint256 tokenId) public view override returns (string memory);
}
```

### 4. Frontend - Auth Page (`/auth`)

**Purpose**: Identity verification and SBT issuance page

**User Flow**:
1. User connects MetaMask wallet
2. Check if wallet already has SBT
   - If yes: Redirect to `/voting`
   - If no: Show verification form
3. User enters dummy identity information (name, birth date)
4. System generates identity hash
5. Check if identity hash is already registered
   - If yes: Show error "Already registered"
   - If no: Request SBT minting
6. After SBT issuance, redirect to `/voting`

**UI Components**:
- Wallet connection button
- Warning message about permanent wallet binding
- Dummy identity input form (name, birth date)
- Submit button for verification
- Loading state during SBT minting
- Success/Error messages

**State Management**:
```typescript
interface AuthState {
  walletAddress: string | null;
  hasSBT: boolean;
  isChecking: boolean;
  isMinting: boolean;
  error: string | null;
}
```

### 5. Frontend - Voting Page (`/voting`)

**Purpose**: Main voting interface (protected route)

**Access Control**:
- Redirect to `/auth` if no wallet connected
- Redirect to `/auth` if wallet has no SBT
- Show voting UI only for SBT holders

**UI Components**:
- Authentication badge showing verified status
- Existing voting interface (VotingApp component)
- My NFT collection link

### 6. Frontend - My NFTs Page (`/my-nfts`)

**Purpose**: Display user's voting reward NFT collection

**Features**:
- List all reward NFTs owned by user
- Display mascot images
- Show ballot information for each NFT
- Voting participation history

## Dummy Identity Verification

### Mock Verification Process

For development and testing purposes, implement a simple dummy verification:

**Input**:
- Name (string)
- Birth Date (YYYY-MM-DD)

**Identity Hash Generation**:
```typescript
function generateIdentityHash(name: string, birthDate: string): string {
  const data = `${name.toLowerCase()}-${birthDate}`;
  return web3.utils.keccak256(data);
}
```

**Verification Logic**:
```typescript
async function dummyVerify(name: string, birthDate: string) {
  // Basic validation
  if (!name || name.length < 2) {
    throw new Error('Invalid name');
  }
  
  if (!birthDate || !isValidDate(birthDate)) {
    throw new Error('Invalid birth date');
  }
  
  // Generate identity hash
  const identityHash = generateIdentityHash(name, birthDate);
  
  // Check if already registered
  const isRegistered = await citizenSBT.methods
    .isIdentityRegistered(identityHash)
    .call();
  
  if (isRegistered) {
    throw new Error('This identity is already registered');
  }
  
  return identityHash;
}
```

### Warning Messages

Display clear warnings to users:
- "This is a test verification. In production, real identity verification will be required."
- "Once you bind your wallet, you cannot change it."
- "Make sure you are using the correct wallet address."

## Data Flow

### 1. First-Time User Registration

```
User → Connect Wallet → Enter Dummy Info → Generate Hash → 
Check Duplicate → Mint SBT → Redirect to Voting
```

### 2. Returning User

```
User → Connect Wallet → Check SBT → Redirect to Voting
```

### 3. Voting Process

```
User → Check SBT → Vote → Receive Reward NFT → View in Collection
```

## Security Considerations

### Smart Contract Level
1. **Non-Transferable SBT**: Override all transfer functions to revert
2. **Identity Hash Storage**: Store hashed identity, not raw data
3. **Access Control**: Only authorized verifier can mint SBT
4. **Duplicate Prevention**: Check both identity hash and wallet address

### Frontend Level
1. **Client-Side Validation**: Validate input before blockchain interaction
2. **Error Handling**: Clear error messages for all failure cases
3. **Loading States**: Show progress during blockchain transactions
4. **Wallet Verification**: Always verify wallet connection before operations

## Implementation Phases

### Phase 1: Smart Contracts
- [ ] Implement CitizenSBT contract
- [ ] Implement VotingRewardNFT contract
- [ ] Update VotingWithSBT contract
- [ ] Write unit tests
- [ ] Deploy to test network

### Phase 2: Frontend - Auth Flow
- [ ] Create AuthPage component
- [ ] Implement wallet connection
- [ ] Implement dummy verification form
- [ ] Add SBT checking logic
- [ ] Add SBT minting UI
- [ ] Handle error states

### Phase 3: Frontend - Protected Routes
- [ ] Update VotingPage with SBT check
- [ ] Implement route protection
- [ ] Add authentication badge
- [ ] Test routing flow

### Phase 4: Frontend - NFT Collection
- [ ] Create MyNFTsPage component
- [ ] Implement NFT listing
- [ ] Display mascot images
- [ ] Show voting history

### Phase 5: Integration & Testing
- [ ] End-to-end testing
- [ ] Test edge cases (no wallet, no SBT, etc.)
- [ ] Performance testing
- [ ] UI/UX refinement

## Testing Scenarios

### Happy Path
1. New user connects wallet → enters dummy info → receives SBT → votes
2. Returning user connects wallet → automatically redirected to voting
3. User votes → receives reward NFT → views in collection

### Error Cases
1. User tries to register with same identity twice → Error shown
2. User without SBT tries to access voting page → Redirected to auth
3. User tries to vote without SBT → Transaction reverts
4. User disconnects wallet during process → Proper error handling

### Edge Cases
1. User has SBT but contract address changed → Handle gracefully
2. User changes wallet in MetaMask → Re-check SBT status
3. Network errors during minting → Show retry option
4. Gas estimation fails → Show clear error message

## API Reference

### Web3 Methods

```typescript
// Check SBT ownership
const hasSBT = await citizenSBT.methods.balanceOf(address).call();

// Check identity registration
const isRegistered = await citizenSBT.methods
  .isIdentityRegistered(identityHash)
  .call();

// Mint SBT (verifier only)
await citizenSBT.methods
  .mint(address, identityHash)
  .send({ from: verifierAddress });

// Vote (requires SBT)
await votingContract.methods
  .vote(proposalId)
  .send({ from: userAddress });

// Get reward NFT count
const nftCount = await rewardNFT.methods.balanceOf(address).call();

// Get token URI
const uri = await rewardNFT.methods.tokenURI(tokenId).call();
```

## File Structure

```
blockchain-test/
├── contracts/
│   ├── CitizenSBT.sol           (new)
│   ├── VotingRewardNFT.sol      (new)
│   └── VotingWithSBT.sol        (modified)
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── AuthPage.tsx     (new)
│   │   │   ├── VotingPage.tsx   (modified)
│   │   │   └── MyNFTsPage.tsx   (new)
│   │   ├── components/
│   │   │   └── VotingApp.tsx    (existing)
│   │   ├── lib/
│   │   │   ├── sbt.ts           (new)
│   │   │   ├── voting.ts        (existing)
│   │   │   └── web3.ts          (existing)
│   │   └── abi/
│   │       ├── CitizenSBT.json  (new)
│   │       └── VotingRewardNFT.json (new)
└── quorum-lab/
    ├── deploy_sbt.js            (new)
    └── test_sbt.js              (new)
```

## Configuration

### Environment Variables

```bash
# Frontend (.env.local)
REACT_APP_CITIZEN_SBT_ADDRESS=0x...
REACT_APP_VOTING_CONTRACT_ADDRESS=0x...
REACT_APP_REWARD_NFT_ADDRESS=0x...
REACT_APP_VERIFIER_ADDRESS=0x...

# Deployment (deploy.env)
VERIFIER_PRIVATE_KEY=0x...
MASCOT_BASE_URI=https://yourdomain.com/mascots/
```

## Future Enhancements

1. **Real Identity Verification**: Integrate Korean identity verification API (NICE, Pass)
2. **Backend Integration**: Add backend service for signature-based verification
3. **IPFS Storage**: Store mascot images on IPFS for decentralization
4. **Dynamic NFT Metadata**: Generate on-chain metadata for reward NFTs
5. **Social Features**: Share NFT collection on social media
6. **Gamification**: Add achievements, badges, leaderboards

## References

- [EIP-721: Non-Fungible Token Standard](https://eips.ethereum.org/EIPS/eip-721)
- [Soulbound Token Concept](https://vitalik.ca/general/2022/01/26/soulbound.html)
- [OpenZeppelin Contracts](https://docs.openzeppelin.com/contracts/)

## Notes

- This implementation uses dummy verification for development
- Production deployment requires real identity verification
- SBT binding is permanent and cannot be reversed
- Consider wallet recovery mechanisms for production
