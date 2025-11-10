import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getWeb3, onAccountsChanged } from "../lib/web3";
import { getRewardNFTs } from "../lib/sbt";

export default function MyNFTsPage() {
    const navigate = useNavigate();
    const [nfts, setNfts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [walletAddress, setWalletAddress] = useState<string | null>(null);

    useEffect(() => {
        const loadNFTs = async () => {
            try {
                const web3 = getWeb3();
                const accounts = await web3.eth.getAccounts();

                if (accounts.length === 0) {
                    navigate("/auth");
                    return;
                }

                const address = accounts[0];
                setWalletAddress(address);
                const userNFTs = await getRewardNFTs(address);
                setNfts(userNFTs);
            } catch (error) {
                console.error("Error loading NFTs:", error);
            } finally {
                setLoading(false);
            }
        };

        loadNFTs();

        // 지갑 연결 상태 감지
        const unsubscribe = onAccountsChanged(async (accounts) => {
            if (accounts.length === 0) {
                // 지갑 연결 해제 시 Auth 페이지로 이동
                navigate("/auth");
            } else {
                // 지갑 변경 시 새 지갑의 NFT 로드
                const newAddress = accounts[0];
                setWalletAddress(newAddress);
                setLoading(true);

                try {
                    const userNFTs = await getRewardNFTs(newAddress);
                    setNfts(userNFTs);
                } catch (error) {
                    console.error("Error reloading NFTs:", error);
                } finally {
                    setLoading(false);
                }
            }
        });

        return () => unsubscribe();
    }, [navigate]);

    if (loading) {
        return <div style={{ textAlign: "center", padding: "50px" }}>로딩 중...</div>;
    }

    return (
        <div style={{ padding: "20px", maxWidth: "1200px", margin: "0 auto" }}>
            <h1>📦 내 NFT 컬렉션</h1>
            <p>보유 NFT: {nfts.length}개</p>

            {nfts.length === 0 ? (
                <div style={{ textAlign: "center", padding: "50px", background: "#f5f5f5", borderRadius: "10px" }}>
                    <p>아직 NFT가 없습니다. 투표에 참여하여 NFT를 받으세요!</p>
                    <button
                        onClick={() => navigate("/voting")}
                        style={{ padding: "10px 20px", marginTop: "20px", cursor: "pointer" }}
                    >
                        투표하러 가기
                    </button>
                </div>
            ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "20px", marginTop: "20px" }}>
                    {nfts.map((nft) => (
                        <div
                            key={nft.tokenId}
                            style={{
                                border: "2px solid #ddd",
                                borderRadius: "10px",
                                padding: "20px",
                                background: "white"
                            }}
                        >
                            <h3>NFT #{nft.tokenId}</h3>
                            <p>Ballot ID: {nft.ballotId}</p>
                            <p>Proposal: {nft.proposalId}</p>
                        </div>
                    ))}
                </div>
            )}

            <button
                onClick={() => navigate("/voting")}
                style={{
                    marginTop: "30px",
                    padding: "10px 20px",
                    cursor: "pointer"
                }}
            >
                ← 투표 페이지로 돌아가기
            </button>
        </div>
    );
}
