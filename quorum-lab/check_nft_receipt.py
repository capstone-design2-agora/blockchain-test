#!/usr/bin/env python3
"""특정 계정의 NFT 투표 영수증 확인 스크립트"""
import json
import sys
from web3 import Web3

# Deployment artifact 로드
ARTIFACT_PATH = "artifacts/deployment.json"

def load_artifact():
    """배포 정보 로드"""
    with open(ARTIFACT_PATH, 'r') as f:
        return json.load(f)

def check_account_receipt(account_address):
    """계정의 투표 영수증 확인"""
    
    # Artifact 로드
    artifact = load_artifact()
    contract_address = artifact['contract']['address']
    contract_abi = artifact['contract']['abi']
    rpc_url = artifact['network']['rpcUrl']
    
    # Web3 연결
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    if not web3.is_connected():
        print(f"❌ RPC 연결 실패: {rpc_url}")
        return None
    
    print(f"✅ RPC 연결 성공: {rpc_url}")
    print(f"📄 Contract Address: {contract_address}")
    print(f"👤 Checking Account: {account_address}")
    print("-" * 70)
    
    # Contract 인스턴스 생성
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=contract_abi
    )
    
    try:
        checksum_account = Web3.to_checksum_address(account_address)
        
        # 1. 투표 여부 확인
        has_voted = contract.functions.hasVoted(checksum_account).call()
        print(f"\n🗳️  투표 여부: {'✅ 투표함' if has_voted else '❌ 미투표'}")
        
        if not has_voted:
            print("\n이 계정은 아직 투표하지 않았습니다.")
            return None
        
        # 2. NFT 소유 개수 확인
        nft_balance = contract.functions.balanceOf(checksum_account).call()
        print(f"🎫 NFT 보유 개수: {nft_balance}")
        
        if nft_balance == 0:
            print("\n⚠️  투표는 했지만 NFT가 없습니다 (비정상)")
            return None
        
        # 3. Transfer 이벤트로 NFT 토큰 ID 찾기
        # 블록 범위를 넓게 설정 (최근 10000개 블록)
        latest_block = web3.eth.block_number
        from_block = max(0, latest_block - 10000)
        
        print(f"\n🔍 NFT Transfer 이벤트 검색 중... (블록 {from_block} ~ {latest_block})")
        
        # Transfer 이벤트 필터 (to=account_address)
        transfer_filter = contract.events.Transfer.create_filter(
            from_block=from_block,
            to_block='latest',
            argument_filters={'to': checksum_account}
        )
        
        transfers = transfer_filter.get_all_entries()
        
        if not transfers:
            print("⚠️  Transfer 이벤트를 찾을 수 없습니다.")
            return None
        
        print(f"\n📋 찾은 NFT Transfer: {len(transfers)}개")
        print("-" * 70)
        
        # 각 NFT에 대한 상세 정보
        for idx, event in enumerate(transfers, 1):
            token_id = event['args']['tokenId']
            from_addr = event['args']['from']
            block_num = event['blockNumber']
            tx_hash = event['transactionHash'].hex()
            
            print(f"\n[NFT #{idx}]")
            print(f"  Token ID: {token_id}")
            print(f"  From: {from_addr}")
            print(f"  Block: {block_num}")
            print(f"  Tx Hash: {tx_hash}")
            
            # NFT 영수증 정보 가져오기
            try:
                receipt = contract.functions.getReceipt(token_id).call()
                proposal_id = receipt[0]
                receipt_block = receipt[1]
                
                # 제안 정보 가져오기
                proposal = contract.functions.getProposal(proposal_id).call()
                proposal_name = proposal[0]
                vote_count = proposal[1]
                
                print(f"  📝 투표 제안: #{proposal_id} - {proposal_name}")
                print(f"  📊 현재 득표수: {vote_count}")
                print(f"  🔢 영수증 블록: {receipt_block}")
                
            except Exception as e:
                print(f"  ⚠️  영수증 조회 실패: {e}")
        
        return transfers
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    if len(sys.argv) < 2:
        print("사용법: python check_nft_receipt.py <account_address>")
        print("\n예시:")
        print("  python check_nft_receipt.py 0x1234567890abcdef1234567890abcdef12345678")
        sys.exit(1)
    
    account_address = sys.argv[1]
    check_account_receipt(account_address)

if __name__ == "__main__":
    main()
