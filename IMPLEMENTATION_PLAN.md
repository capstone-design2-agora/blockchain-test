# Frontend × Quorum Voting Integration Plan

This plan converts the findings from the repository review into actionable implementation steps so the React frontend can interact reliably with the Quorum voting network and smart contract.

## 1. Synchronize On-Chain Artifacts
1. Run `quorum-lab/setup_and_deploy.sh` to ensure the desired consensus network is running and the `VotingWithNFT` contract is deployed.
2. Copy `quorum-lab/artifacts/VotingWithNFT.abi.json` to `frontend/src/abi/Voting.json` whenever the contract is recompiled so the ABI stays in lockstep with the running chain.
3. Record the deployed address and chain metadata from `quorum-lab/artifacts/deployment.json` for later environment configuration and documentation updates.

## 2. Frontend Environment Configuration
1. Create `frontend/.env.example` (or update it if it already exists) with the following keys and inline comments:
  - `REACT_APP_RPC=http://localhost:10545`
   - `REACT_APP_VOTING_ADDRESS=<deployed-contract-address>`
   - `REACT_APP_EXPECTED_VOTERS=<optional-turnout-base>`
2. Update project docs (README/RUN_GUIDE) to instruct contributors to copy `.env.example` to `.env.local` and set the deployed contract address before running `npm start`.
3. Add runtime validation inside `src/lib/web3.ts`/`voting.ts` that surfaces readable UI errors instead of throwing during module load when env vars are missing.

## 3. Provider & Wallet Lifecycle Enhancements
1. Extend `src/lib/web3.ts` to:
   - Detect the active chain ID and warn if it differs from the expected Quorum chain.
   - Listen for `accountsChanged`/`chainChanged` events and expose callbacks to the app.
   - Provide an explicit `disconnectWallet` helper (Metamask-specific via `wallet_requestPermissions` fallback) so the UI can reset to the initial state.
2. Update `VotingApp.tsx` to:
   - Subscribe to the new provider events and keep `currentUser` / `userHasVoted` in sync automatically.
   - Show a `Disconnect` / `Switch account` action when a wallet is connected.
   - Display friendly toasts for missing provider, wrong chain, or rejected signature cases.

## 4. Voting UX & On-Chain Feedback
1. Replace the current “demo mode” banner with a structured status panel that distinguishes between connection failures, wrong chain, and loading state.
2. After `castVote`, surface the transaction hash and link to Quorum Explorer (`http://localhost:25000/tx/<hash>`) so users can verify inclusion.
3. Add a lightweight “recent votes” view by querying Transfer events (using `web3.eth.getPastLogs`) limited to the last N blocks, giving observers immediate proof that proposals are updating on-chain.

## 5. Testing & Verification
1. Add a Cypress or React Testing Library smoke test that stubs `window.ethereum` and asserts the wallet flow (connect → vote button enabled → disconnect resets state).
2. Provide a CLI recipe in the docs for `quorum-lab/check_nft_receipt.py <address>` so operators can cross-check NFT receipts out-of-band.
3. Document manual QA: connect Metamask (chain ID 1337), import `rpcnode` key, perform a vote, confirm totals refresh, and validate the NFT receipt script output.

## 6. Documentation Updates
1. Expand `frontend/RUN_GUIDE.md` with the exact Metamask setup steps (RPC URL, chain ID, key import) and troubleshooting tips.
2. Add a “Verifying Votes” section to the root README summarizing both the UI flow and backend scripts for confirming successful transactions.
3. Capture the disconnect/account-switch workflow so multiple users can vote sequentially from the same browser session.

Following these steps will align the frontend with the Quorum network configuration, give end users a clear wallet lifecycle, and expose verifiable on-chain feedback for every vote.
