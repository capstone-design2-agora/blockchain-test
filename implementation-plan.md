## Test Execution Plan

- **시스템 스냅샷**: 테스트 전 `uname -a`, `lsb_release -a`, `nproc`, `free -h`, `df -h /`를 실행해 `logs/00_env.txt`에 기록하고 디스크 여유 ≥40GB, RAM ≥8GB를 확인.
- **도구 점검표**: `docker --version`, `docker compose version`, `node -v`, `npm -v`, `python3 --version`, `pip3 list | rg 'web3|pandas|matplotlib|requests'` 결과를 `logs/01_tooling.txt`에 저장하고 누락 패키지는 설치 후 재확인.
- **작업 디렉터리 및 권한**: `/opt/quorum-lab`(또는 지정 경로)에 로그·산출물용 하위 폴더(`logs`, `benchmarks`, `charts`, `reports`)를 생성하고 현재 계정이 `docker` 그룹에 속해 있는지 `groups`로 검증.
- **로그 수집 규칙**: 모든 핵심 명령은 `tee`로 기록(`cmd | tee logs/<phase>-<name>.log`), Docker 관련 명령은 `docker events --since`로 백업, 오류 발생 시 즉시 타임스탬프와 함께 `logs/issues.md`에 남김.

- **Phase 1 – 환경 준비**: `sudo apt update && sudo apt upgrade -y` 후 Docker·Compose·Git·Node.js·npm·Python3·pip 설치, `sudo systemctl status docker`와 `docker ps`로 데몬 정상 동작 확인, Python 의존성(`pip3 install web3 requests matplotlib pandas`) 설치 후 `python3 -c "import web3,requests,matplotlib,pandas"`로 모듈 임포트 검증.
- **Phase 2 – 예제 확보**: `git clone https://github.com/ConsenSys/quorum-examples.git`를 `workdir/repos/`에 수행, `git rev-parse HEAD`로 사용 커밋 고정, `docker-compose-*.yml` 세 파일의 주요 포트·컨테이너명을 `logs/02_compose-summary.md`에 요약.
- **Phase 3 – 네트워크 배포**: Clique→IBFT→Raft 순으로 `docker compose` 실행(`docker compose -f docker-compose-<type>.yml up -d`), 각 단계마다 `docker ps --format '{{.Names}}\t{{.Status}}'`로 노드 수 확인, `docker logs quorum-node1 --tail 50`로 합의 로그 확인, 종료 시 `docker compose down -v`로 깨끗한 상태 보장.
- **Phase 3 검증 포인트**: Clique는 4개 노드, 블록 생성 간격 로그(≈5s) 확인; IBFT는 `validator` 관련 로그와 4 노드 합의 메시지 확인; Raft는 7개 노드 중 leader 선출 로그 존재 확인, 이상 시 컨테이너 재기동 후 재검증.

- **Phase 4 – 스마트 컨트랙트**: `quorum-examples` 루트에서 `contracts/VotingWithNFT.sol` 작성, OpenZeppelin ERC-721 상속으로 투표 시 NFT 발급과 `hasVoted` 검증 포함; `npm init -y`, `npm install web3 solc @openzeppelin/contracts` 실행; `deploy.js`로 컴파일·배포, 실행 전 RPC 엔드포인트(`http://localhost:8545`) 응답을 `curl`로 확인, `node deploy.js | tee logs/04_deploy.log`로 결과 저장, 컨트랙트 주소·ABI·NFT 메타데이터를 `artifacts/deployment.json`에 정리.
- **Phase 5 – 성능 벤치마킹**: `benchmark.py` 작성 시 입력 파라미터(네트워크 타입, 트랜잭션 수, 병렬도)를 argparse로 받도록 구성하고, 각 트랜잭션에 대해 NFT 발급 여부와 가스 사용량을 기록; 실행 전에 `python3 -m compileall benchmark.py`로 구문 검증, 실행(`python3 benchmark.py --consensus clique --tx-count 100`) 후 TPS/지연/NFT 발급 수·평균 가스량을 `benchmarks/<consensus>.csv`로 저장, 이상치 시 동일 조건으로 3회 반복.
- **TPS 검증 로직**: 전송 성공률이 100%인지 확인(`status == 1`), 평균·최댓값·표준편차를 `pandas`로 계산, `matplotlib`로 `charts/tps_<consensus>.png` 생성, 로그에 RPC 오류가 있을 경우 재시도 지점 명시.
- **Phase 6 – 모니터링**: Prometheus 설치 후 `prometheus.yml`에 각 노드 엔드포인트 추가, `systemctl status prometheus` 확인, Grafana 설치·로그인(`admin/admin` 초기값 변경), Prometheus 데이터 소스 연결, TPS/블록 시간/CPU 사용률 위젯을 포함하는 대시보드 ID와 스크린샷을 `logs/06_grafana.md`에 기록.

- **Phase 7 – 실험 실행**: Clique·IBFT·Raft 각각에 대해 동일 파라미터로 벤치마크 수행, 실행 순서와 타임스탬프를 `reports/run-order.md`에 남김, 각 실행 전후 `docker stats --no-stream`으로 자원 사용 비교, Prometheus에서 15분 동안 지표 수집 후 `.json` 내보내기.
- **Phase 8 – 결과 정리**: `reports/results.csv`에 TPS·평균 지연·블록 시간·CPU·메모리·합의 특성(정성) 입력, `charts/comparison.png`로 시각화, 각 합의 알고리즘의 적합성 평가 및 재현 절차 개선안(자동화 스크립트 필요 여부) 작성, 미해결 이슈와 추후 과제를 `reports/findings.md`에 정리.
- **종료 및 청소**: 모든 컨테이너 `docker compose down -v`로 제거, `docker volume ls`로 남은 볼륨 여부 점검, `logs/cleanup.txt`에 최종 상태 기록, 재현 가능하도록 `README-test-run.md` 초안 작성.

- **리스크 및 예비 조치**: Docker 리소스 부족 시 swap 확장 계획, RPC 실패 시 `NODE_URL` 재확인, Prometheus 포트 충돌 시 대체 포트 문서화, 모든 오류는 즉시 로그와 재현 단계 포함해 기록.
