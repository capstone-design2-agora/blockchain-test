#!/usr/bin/env python3
"""블록체인 컨트랙트에서 투표 시간 정보를 확인하는 스크립트"""
import json
from datetime import datetime
from web3 import Web3

# Deployment artifact 로드
ARTIFACT_PATH = "artifacts/deployment.json"

def load_artifact():
    """배포 정보 로드"""
    with open(ARTIFACT_PATH, 'r') as f:
        return json.load(f)

def check_ballot_times():
    """컨트랙트에서 투표 시간 정보 조회"""
    
    # Artifact 로드
    artifact = load_artifact()
    contract_address = artifact['contract']['address']
    contract_abi = artifact['contract']['abi']
    rpc_url = artifact['network']['rpcUrl']
    
    # Web3 연결
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    if not web3.is_connected():
        print(f"❌ RPC 연결 실패: {rpc_url}")
        return
    
    print(f"✅ RPC 연결 성공: {rpc_url}")
    print(f"📄 Contract Address: {contract_address}")
    print("=" * 70)
    
    # Contract 인스턴스 생성
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=contract_abi
    )
    
    try:
        # ballotMetadata() 호출
        metadata = contract.functions.ballotMetadata().call()
        
        print("\n📋 투표 메타데이터:")
        print(f"  ID: {metadata[0]}")
        print(f"  제목: {metadata[1]}")
        print(f"  설명: {metadata[2]}")
        
        opens_at = metadata[3]
        closes_at = metadata[4]
        announces_at = metadata[5]
        expected_voters = metadata[6]
        
        print("\n⏰ 시간 정보 (Unix Timestamp):")
        print(f"  opensAt: {opens_at}")
        print(f"  closesAt: {closes_at}")
        print(f"  announcesAt: {announces_at}")
        
        print("\n📅 시간 정보 (사람이 읽기 쉬운 형식):")
        print(f"  투표 시작: {datetime.fromtimestamp(opens_at).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  투표 종료: {datetime.fromtimestamp(closes_at).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  결과 발표: {datetime.fromtimestamp(announces_at).strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"\n👥 예상 투표자 수: {expected_voters}")
        
        # 현재 시간과 비교
        now = datetime.now().timestamp()
        print("\n📊 현재 상태:")
        if now < opens_at:
            print(f"  ⏳ 투표 시작까지: {int((opens_at - now) / 60)}분")
        elif now < closes_at:
            print(f"  🗳️ 투표 진행 중 (종료까지 {int((closes_at - now) / 60)}분 남음)")
        elif now < announces_at:
            print(f"  ⌛ 투표 종료됨 (결과 발표까지 {int((announces_at - now) / 60)}분 남음)")
        else:
            print("  ✅ 투표 종료 및 결과 발표 완료")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_ballot_times()
