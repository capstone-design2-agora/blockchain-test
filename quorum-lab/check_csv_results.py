#!/usr/bin/env python3
"""CSV 파일에서 특정 계정의 투표 결과 확인"""
import csv
import sys
from pathlib import Path

CSV_PATH = "benchmarks/raft.csv"

def check_account_in_csv(account_address):
    """CSV에서 계정의 투표 결과 확인"""
    
    if not Path(CSV_PATH).exists():
        print(f"❌ CSV 파일을 찾을 수 없습니다: {CSV_PATH}")
        return
    
    account_lower = account_address.lower()
    found = False
    
    print(f"🔍 계정 검색: {account_address}")
    print(f"📁 파일: {CSV_PATH}")
    print("-" * 80)
    
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            if row['account'].lower() == account_lower:
                found = True
                print(f"\n✅ 투표 기록 발견!")
                print(f"  Index: {row['index']}")
                print(f"  Account: {row['account']}")
                print(f"  Tx Hash: {row['tx_hash']}")
                print(f"  Status: {'✅ 성공' if row['status'] == '1' else '❌ 실패'}")
                print(f"  Gas Used: {row['gas_used']}")
                print(f"  Latency: {row['latency_sec']} seconds")
                print(f"  Token ID: {row['token_id']}")
                print(f"  Proposal ID: {row['proposal_id']}")
                print(f"  Phase: {row.get('phase', 'N/A')}")
                print(f"  Submitted at: {row['submitted_sec']}s")
                print(f"  Completed at: {row['completed_sec']}s")
                
                if row['status'] == '1':
                    print(f"\n🎫 NFT 영수증:")
                    print(f"  ✅ 이 계정은 Token ID {row['token_id']}의 NFT를 받았습니다")
                    print(f"  📝 Proposal #{row['proposal_id']}에 투표했습니다")
    
    if not found:
        print(f"\n❌ 해당 계정의 투표 기록을 찾을 수 없습니다.")
        print(f"\n💡 Tip: 계정 주소가 정확한지 확인하세요 (대소문자 구분 없음)")

def list_all_accounts():
    """모든 투표 계정 목록 출력"""
    
    if not Path(CSV_PATH).exists():
        print(f"❌ CSV 파일을 찾을 수 없습니다: {CSV_PATH}")
        return
    
    print(f"📋 모든 투표 계정 목록")
    print(f"📁 파일: {CSV_PATH}")
    print("-" * 80)
    
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        
        success_count = 0
        failed_count = 0
        
        for row in reader:
            status_icon = "✅" if row['status'] == '1' else "❌"
            token_info = f"NFT #{row['token_id']}" if row['token_id'] else "No NFT"
            
            print(f"{status_icon} [{row['index']}] {row['account']} - {token_info} (Proposal #{row['proposal_id']})")
            
            if row['status'] == '1':
                success_count += 1
            else:
                failed_count += 1
        
        print("-" * 80)
        print(f"📊 총계: 성공 {success_count} / 실패 {failed_count}")

def main():
    if len(sys.argv) < 2:
        print("사용법:")
        print("  1. 특정 계정 조회: python check_csv_results.py <account_address>")
        print("  2. 전체 목록 조회: python check_csv_results.py --list")
        print("\n예시:")
        print("  python check_csv_results.py 0x0f543cd194Fb79a9F34d16E6B450992F360F1146")
        print("  python check_csv_results.py --list")
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        list_all_accounts()
    else:
        account_address = sys.argv[1]
        check_account_in_csv(account_address)

if __name__ == "__main__":
    main()
