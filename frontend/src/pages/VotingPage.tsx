import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getWeb3, onAccountsChanged } from "../lib/web3";
import { checkHasSBT, voteWithSBT } from "../lib/sbt";
import "./VotingPage.css";

export default function VotingPage() {
    const navigate = useNavigate();
    const [walletAddress, setWalletAddress] = useState<string | null>(null);
    const [selectedProposal, setSelectedProposal] = useState<number | null>(null);
    const [isVoting, setIsVoting] = useState(false);
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    const proposals = [
        { id: 0, name: "반일씹덕" },
        { id: 1, name: "펨코충" },
        { id: 2, name: "디씨충" },
    ];

    useEffect(() => {
        const init = async () => {
            try {
                const web3 = getWeb3();
                const accounts = await web3.eth.getAccounts();

                if (accounts.length === 0) {
                    navigate("/auth");
                    return;
                }

                const address = accounts[0];
                setWalletAddress(address);

                const hasSBT = await checkHasSBT(address);
                if (!hasSBT) {
                    navigate("/auth");
                    return;
                }
            } catch (error) {
                console.error("Initialization error:", error);
                navigate("/auth");
            }
        };

        init();

        const unsubscribe = onAccountsChanged(async (accounts) => {
            if (accounts.length === 0) {
                // 지갑 연결 해제 시 Auth 페이지로 이동
                navigate("/auth");
            } else {
                // 지갑 변경 시 새 지갑의 SBT 확인
                const newAddress = accounts[0];
                setWalletAddress(newAddress);

                try {
                    const hasSBT = await checkHasSBT(newAddress);
                    if (!hasSBT) {
                        // 새 지갑에 SBT가 없으면 Auth 페이지로 이동
                        navigate("/auth");
                    }
                } catch (error) {
                    console.error("SBT check error on account change:", error);
                    navigate("/auth");
                }
            }
        });

        return () => unsubscribe();
    }, [navigate]);

    const handleDisconnect = async () => {
        try {
            // MetaMask는 프로그래매틱하게 연결 해제할 수 없으므로
            // Auth 페이지로 이동하고 사용자에게 안내
            if (window.confirm("지갑 연결을 해제하시겠습니까?\n\nMetaMask에서 직접 연결을 해제하려면:\n1. MetaMask 확장 프로그램 클릭\n2. 연결된 사이트 관리\n3. 이 사이트 연결 해제")) {
                // 세션 스토리지 정리
                sessionStorage.clear();
                localStorage.removeItem("walletAddress");

                // Auth 페이지로 이동
                navigate("/auth");
            }
        } catch (error) {
            console.error("Disconnect error:", error);
            navigate("/auth");
        }
    };

    const handleVote = async () => {
        if (selectedProposal === null) {
            setMessage({ type: "error", text: "후보를 선택해주세요." });
            return;
        }

        if (!walletAddress) {
            setMessage({ type: "error", text: "지갑이 연결되지 않았습니다." });
            return;
        }

        try {
            setIsVoting(true);
            setMessage(null);

            const result = await voteWithSBT(selectedProposal, walletAddress);

            setMessage({
                type: "success",
                text: `투표가 완료되었습니다! NFT Token ID: ${result.rewardTokenId}`,
            });

            setTimeout(() => {
                navigate("/my-nfts");
            }, 3000);
        } catch (error: any) {
            console.error("Voting error:", error);
            setMessage({
                type: "error",
                text: error.message || "투표 중 오류가 발생했습니다.",
            });
        } finally {
            setIsVoting(false);
        }
    };

    return (
        <div className="voting-page">
            <div className="voting-container">
                <header className="voting-header">
                    <h1>🗳️ 근첩을 찾아라</h1>
                    <p className="description">누가 근첩이지?</p>
                    <div className="wallet-info">
                        <div className="wallet-badge">
                            지갑: {walletAddress?.substring(0, 6)}...
                            {walletAddress?.substring(walletAddress.length - 4)}
                        </div>
                        <button
                            className="disconnect-button"
                            onClick={handleDisconnect}
                            disabled={isVoting}
                        >
                            🔌 연결 해제
                        </button>
                        <button
                            className="nft-header-button"
                            onClick={() => navigate("/my-nfts")}
                            disabled={isVoting}
                        >
                            📦 내 NFT
                        </button>
                    </div>
                </header>

                <div className="proposals-section">
                    <h2>후보 선택</h2>
                    <div className="proposals-grid">
                        {proposals.map((proposal) => (
                            <div
                                key={proposal.id}
                                className={`proposal-card ${selectedProposal === proposal.id ? "selected" : ""
                                    }`}
                                onClick={() => !isVoting && setSelectedProposal(proposal.id)}
                            >
                                <div className="proposal-number">{proposal.id + 1}</div>
                                <div className="proposal-name">{proposal.name}</div>
                                {selectedProposal === proposal.id && (
                                    <div className="check-mark">✓</div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {message && (
                    <div className={`message ${message.type}`}>
                        {message.text}
                    </div>
                )}

                <button
                    className="vote-button"
                    onClick={handleVote}
                    disabled={isVoting || selectedProposal === null}
                >
                    {isVoting ? "투표 중..." : "투표하기"}
                </button>

                <button
                    className="nft-button"
                    onClick={() => navigate("/my-nfts")}
                    disabled={isVoting}
                >
                    📦 내 NFT 컬렉션 보기
                </button>
            </div>
        </div>
    );
}
