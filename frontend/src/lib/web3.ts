import Web3 from "web3";

const fallbackRpc = process.env.REACT_APP_RPC;
const browserProvider =
  typeof window !== "undefined" ? (window as any).ethereum : undefined;

const fallbackProvider = fallbackRpc
  ? new Web3.providers.HttpProvider(fallbackRpc)
  : null;

let fallbackWeb3Instance: Web3 | null = fallbackProvider
  ? new Web3(fallbackProvider)
  : null;
let browserWeb3Instance: Web3 | null = browserProvider
  ? new Web3(browserProvider)
  : null;
const missingProviderMessage =
  "RPC 엔드포인트가 설정되지 않았고 브라우저 지갑도 감지되지 않았어요. frontend/.env.local 파일의 REACT_APP_RPC를 확인하거나 MetaMask를 연결해 주세요.";

const expectedChainName = process.env.REACT_APP_CHAIN_NAME ?? "Quorum Local";
const expectedChainIdRaw =
  process.env.REACT_APP_CHAIN_ID ??
  process.env.REACT_APP_QUORUM_CHAIN_ID ??
  "0x539"; // 1337 in hex
const expectedChainId = normalizeChainId(expectedChainIdRaw);
const expectedChainDecimal = expectedChainId
  ? Number.parseInt(expectedChainId, 16)
  : null;

type AccountsChangedCallback = (
  accounts: string[]
) => void | Promise<void>;
type ChainChangedCallback = (chainId: string) => void | Promise<void>;

const accountsChangedCallbacks = new Set<AccountsChangedCallback>();
const chainChangedCallbacks = new Set<ChainChangedCallback>();
let eventsBound = false;
let lastKnownChainId: string | null = null;

function normalizeChainId(
  value: string | number | bigint | null | undefined
): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === "number" || typeof value === "bigint") {
    return `0x${value.toString(16)}`;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  if (/^0x/i.test(trimmed)) {
    const parsed = Number.parseInt(trimmed, 16);
    if (Number.isNaN(parsed)) {
      return null;
    }
    return `0x${parsed.toString(16)}`;
  }

  const decimal = Number.parseInt(trimmed, 10);
  if (Number.isNaN(decimal)) {
    return null;
  }
  return `0x${decimal.toString(16)}`;
}

function bindProviderEvents(): void {
  if (eventsBound || !browserProvider?.on) {
    return;
  }

  eventsBound = true;
  browserProvider.on("accountsChanged", (accounts: string[]) => {
    accountsChangedCallbacks.forEach((callback) => {
      Promise.resolve(callback(accounts)).catch((error) =>
        console.warn("Account change handler failed:", error)
      );
    });
  });

  browserProvider.on("chainChanged", (chainId: string | number) => {
    const normalized = normalizeChainId(chainId);
    if (normalized) {
      lastKnownChainId = normalized;
      if (!isExpectedChain(normalized)) {
        console.warn(
          `Wallet connected to chain ${normalized}, expected ${expectedChainId}.`
        );
      }

      if (!browserWeb3Instance) {
        browserWeb3Instance = new Web3(browserProvider as any);
      }
    }
    const payload = typeof chainId === "string" ? chainId : String(chainId);
    chainChangedCallbacks.forEach((callback) => {
      Promise.resolve(callback(payload)).catch((error) =>
        console.warn("Chain change handler failed:", error)
      );
    });
  });
}

async function readChainId(): Promise<string | null> {
  if (browserProvider?.request) {
    try {
      const chainId = await browserProvider.request({ method: "eth_chainId" });
      return normalizeChainId(chainId as string);
    } catch (error) {
      console.warn("Unable to read chain from wallet provider:", error);
    }
  }

  try {
    const numeric = await requireWeb3Instance().eth.getChainId();
    return normalizeChainId(numeric);
  } catch (error) {
    console.warn("Unable to read chain ID from RPC provider:", error);
    return null;
  }
}

export function hasBrowserWallet(): boolean {
  return Boolean(browserProvider?.request);
}

export function getExpectedChainLabel(): string {
  if (!expectedChainId) {
    return expectedChainName;
  }
  if (expectedChainDecimal !== null) {
    return `${expectedChainName} (#${expectedChainDecimal})`;
  }
  return `${expectedChainName} (${expectedChainId})`;
}

export function isExpectedChain(
  chainId: string | number | null | undefined
): boolean {
  if (!expectedChainId) {
    return true;
  }
  const normalized = normalizeChainId(chainId);
  if (!normalized) {
    return true;
  }
  return normalized === expectedChainId;
}

export async function ensureWalletConnection(): Promise<void> {
  if (!browserProvider?.request) {
    if (fallbackRpc) {
      return;
    }
    throw new Error(
      "브라우저 지갑이 감지되지 않았어요. MetaMask 또는 호환 지갑을 설치해 주세요."
    );
  }

  await browserProvider.request({ method: "eth_requestAccounts" });
  await assertCorrectChain();
}

export async function assertCorrectChain(): Promise<void> {
  const currentChainId = await getActiveChainId();
  if (!currentChainId || !expectedChainId) {
    return;
  }

  if (!isExpectedChain(currentChainId)) {
    const readableCurrent =
      currentChainId && currentChainId.startsWith("0x")
        ? Number.parseInt(currentChainId, 16)
        : currentChainId;
    const readableExpected =
      expectedChainDecimal !== null ? expectedChainDecimal : expectedChainId;
    throw new Error(
      `지갑이 올바른 네트워크에 연결되어 있지 않아요. 현재 체인: ${readableCurrent}, 기대 체인: ${readableExpected}`
    );
  }
}

export async function getActiveChainId(): Promise<string | null> {
  if (lastKnownChainId) {
    return lastKnownChainId;
  }
  lastKnownChainId = await readChainId();
  return lastKnownChainId;
}

export function onAccountsChanged(
  callback: AccountsChangedCallback
): () => void {
  accountsChangedCallbacks.add(callback);
  bindProviderEvents();
  return () => accountsChangedCallbacks.delete(callback);
}

export function onChainChanged(callback: ChainChangedCallback): () => void {
  chainChangedCallbacks.add(callback);
  bindProviderEvents();
  return () => chainChangedCallbacks.delete(callback);
}

export async function disconnectWallet(): Promise<void> {
  if (!browserProvider?.request) {
    return;
  }

  const permissionsPayload = [{ eth_accounts: {} }];
  try {
    await browserProvider.request({
      method: "wallet_revokePermissions",
      params: permissionsPayload,
    });
  } catch (revokeError) {
    try {
      await browserProvider.request({
        method: "wallet_requestPermissions",
        params: permissionsPayload,
      });
    } catch (requestError) {
      console.warn("Wallet disconnect request failed:", requestError);
    }
  } finally {
    accountsChangedCallbacks.forEach((callback) => {
      Promise.resolve(callback([])).catch((error) =>
        console.warn("Account handler failed after disconnect:", error)
      );
    });
  }
}

function requireWeb3Instance(): Web3 {
  const resolved = browserWeb3Instance ?? fallbackWeb3Instance;
  if (!resolved) {
    throw new Error(missingProviderMessage);
  }
  return resolved;
}

export function getWeb3(): Web3 {
  return requireWeb3Instance();
}

export function getReadOnlyWeb3(): Web3 {
  if (fallbackWeb3Instance) {
    return fallbackWeb3Instance;
  }
  return getWeb3();
}

bindProviderEvents();
