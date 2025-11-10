import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { connectWallet, switchNetwork, CHAIN_ID, CHAIN_NAME, onAccountsChanged } from "../lib/web3";
import { checkHasSBT } from "../lib/sbt";
import "./AuthPage.css";

export default function AuthPage() {
    const navigate = useNavigate();
    const [name, setName] = useState("");
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // 페이지 로드 시 지갑 연결 상태 감지
        const unsubscribe = onAccountsChanged(async (accounts) => {
            if (accounts.length === 0) {
                // 지갑 연결 해제됨 - 현재 페이지 유지
                console.log("Wallet disconnected on Auth page");
            }
        });

        return () => unsubscribe();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!name.trim()) {
            setError("이름을 입력해주세요.");
            return;
        }

        if (name.trim().length < 2) {
            setError("이름은 최소 2자 이상이어야 합니다.");
            return;
        }

        try {
            setIsConnecting(true);
            setError(null);

            // Connect wallet
            const accounts = await connectWallet();
            if (accounts.length === 0) {
                throw new Error("지갑 연결에 실패했습니다.");
            }

            // Switch to correct network
            await switchNetwork(
                CHAIN_ID,
                CHAIN_NAME,
                process.env.REACT_APP_RPC_URL || "http://localhost:10545"
            );

            const walletAddress = accounts[0];

            // Check if already has SBT
            const hasSBT = await checkHasSBT(walletAddress);

            if (hasSBT) {
                // Already has SBT, go directly to voting
                navigate("/voting");
            } else {
                // Need to register and mint SBT
                navigate("/register", { state: { name } });
            }
        } catch (error: any) {
            console.error("Error during authentication:", error);
            setError(error.message || "인증 중 오류가 발생했습니다.");
            setIsConnecting(false);
        }
    };

    return (
        <div className="auth-page">
            <div className="auth-container">
                <h1>🗳️ 블록체인 투표 시스템</h1>
                <p className="subtitle">SBT 기반 안전한 투표 시스템</p>

                <form onSubmit={handleSubmit} className="auth-form">
                    <div className="form-group">
                        <label htmlFor="name">이름</label>
                        <input
                            id="name"
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="홍길동"
                            disabled={isConnecting}
                            autoComplete="name"
                        />
                    </div>

                    {error && (
                        <div className="error-message">
                            <p>❌ {error}</p>
                        </div>
                    )}

                    <button
                        type="submit"
                        className="connect-button"
                        disabled={isConnecting || !name.trim()}
                    >
                        {isConnecting ? "연결 중..." : "🔗 지갑 연결하기"}
                    </button>
                </form>

                <div className="info-box">
                    <h3>ℹ️ 안내사항</h3>
                    <ul>
                        <li>MetaMask 지갑이 필요합니다.</li>
                        <li>최초 1회 SBT(신원 토큰) 발급이 필요합니다.</li>
                        <li>SBT는 양도할 수 없으며 영구적으로 지갑에 바인딩됩니다.</li>
                        <li>1인 1투표가 보장됩니다.</li>
                    </ul>
                </div>
            </div>
        </div>
    );
}
