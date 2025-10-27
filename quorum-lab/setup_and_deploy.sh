#!/usr/bin/env bash
# 네트워크 시작 및 스마트 컨트랙트 배포 자동화 스크립트

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(realpath "${SCRIPT_DIR}/..")"
NETWORK_DIR="${PROJECT_ROOT}/quorum-test-network"
ARTIFACTS_DIR="${SCRIPT_DIR}/artifacts"

# 색상 출력
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Quorum Network Setup & Deployment${NC}"
echo -e "${GREEN}========================================${NC}"

# 1. 합의 알고리즘 확인
echo -e "\n${YELLOW}[1/5] Checking consensus algorithm...${NC}"
if [[ ! -f "${NETWORK_DIR}/.env" ]]; then
    echo -e "${YELLOW}No .env file found. Creating with CONSENSUS=raft${NC}"
    echo "CONSENSUS=raft" > "${NETWORK_DIR}/.env"
fi

CONSENSUS=$(grep CONSENSUS "${NETWORK_DIR}/.env" | cut -d= -f2)
echo -e "${GREEN}✓ Consensus algorithm: ${CONSENSUS}${NC}"

# 2. 네트워크 상태 확인
echo -e "\n${YELLOW}[2/5] Checking network status...${NC}"
cd "${NETWORK_DIR}"

if docker compose ps | grep -q "validator1.*Up"; then
    echo -e "${GREEN}✓ Network is already running${NC}"
else
    echo -e "${YELLOW}Starting network...${NC}"
    docker compose up -d
    
    # 네트워크가 완전히 시작될 때까지 대기
    echo -e "${YELLOW}Waiting for network to be ready...${NC}"
    sleep 10
    
    # 노드 상태 확인
    MAX_RETRIES=30
    RETRY=0
    while [ $RETRY -lt $MAX_RETRIES ]; do
        if curl -s -X POST http://localhost:8545 \
            -H "Content-Type: application/json" \
            --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
            > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Network is ready${NC}"
            break
        fi
        RETRY=$((RETRY+1))
        echo -n "."
        sleep 2
    done
    
    if [ $RETRY -eq $MAX_RETRIES ]; then
        echo -e "\n${RED}✗ Network failed to start${NC}"
        exit 1
    fi
fi

# 3. Node.js 의존성 확인
echo -e "\n${YELLOW}[3/6] Checking Node.js dependencies...${NC}"
cd "${SCRIPT_DIR}"

if [[ ! -d "node_modules" ]]; then
    echo -e "${YELLOW}Installing Node.js dependencies...${NC}"
    npm install solc@0.8.20 web3@1.10.2 @openzeppelin/contracts@4.9.6
else
    echo -e "${GREEN}✓ Node.js dependencies already installed${NC}"
fi

# 4. Python 의존성 확인
echo -e "\n${YELLOW}[4/6] Checking Python dependencies...${NC}"

if ! python3 -c "import web3" 2>/dev/null; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip3 install web3 eth-account python-dotenv 2>&1 | grep -v "Requirement already satisfied" || true
else
    echo -e "${GREEN}✓ Python dependencies already installed${NC}"
fi

# 5. 스마트 컨트랙트 배포 확인
echo -e "\n${YELLOW}[5/6] Checking smart contract deployment...${NC}"

SHOULD_DEPLOY=false

if [[ -f "${ARTIFACTS_DIR}/deployment.json" ]]; then
    echo -e "${YELLOW}Found existing deployment.json${NC}"
    
    # 배포된 컨트랙트가 실제로 존재하는지 확인
    CONTRACT_ADDRESS=$(node -p "require('${ARTIFACTS_DIR}/deployment.json').contract.address")
    
    RESPONSE=$(curl -s -X POST http://localhost:8545 \
        -H "Content-Type: application/json" \
        --data "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getCode\",\"params\":[\"${CONTRACT_ADDRESS}\",\"latest\"],\"id\":1}")
    
    CODE=$(echo "$RESPONSE" | node -p "JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8')).result")
    
    if [[ "$CODE" == "0x" ]]; then
        echo -e "${YELLOW}Contract not found on blockchain. Will redeploy.${NC}"
        SHOULD_DEPLOY=true
    else
        echo -e "${GREEN}✓ Contract is deployed at ${CONTRACT_ADDRESS}${NC}"
    fi
else
    echo -e "${YELLOW}No deployment.json found. Will deploy contract.${NC}"
    SHOULD_DEPLOY=true
fi

# 6. 스마트 컨트랙트 배포
if [ "$SHOULD_DEPLOY" = true ]; then
    echo -e "\n${YELLOW}[6/6] Deploying smart contract...${NC}"
    node deploy_contract.js
    
    if [[ -f "${ARTIFACTS_DIR}/deployment.json" ]]; then
        CONTRACT_ADDRESS=$(node -p "require('${ARTIFACTS_DIR}/deployment.json').contract.address")
        echo -e "${GREEN}✓ Contract deployed successfully at ${CONTRACT_ADDRESS}${NC}"
    else
        echo -e "${RED}✗ Deployment failed${NC}"
        exit 1
    fi
else
    echo -e "\n${YELLOW}[6/6] Skipping deployment (contract already exists)${NC}"
fi

# 완료
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Network:${NC} ${CONSENSUS}"
echo -e "${GREEN}RPC Endpoint:${NC} http://localhost:8545"
echo -e "${GREEN}Contract Address:${NC} $(node -p "require('${ARTIFACTS_DIR}/deployment.json').contract.address" 2>/dev/null || echo 'N/A')"
echo -e "${GREEN}Artifacts:${NC} ${ARTIFACTS_DIR}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Run benchmarks: ${GREEN}cd quorum-lab && ./run_raft_benchmarks.sh${NC}"
echo -e "  2. Check network: ${GREEN}cd quorum-test-network && docker compose ps${NC}"
echo -e "  3. View logs: ${GREEN}cd quorum-test-network && docker compose logs -f validator1${NC}"
echo ""
