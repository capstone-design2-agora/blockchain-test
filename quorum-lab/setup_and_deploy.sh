#!/usr/bin/env bash
# 네트워크 시작 및 스마트 컨트랙트 배포 자동화 스크립트

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(realpath "${SCRIPT_DIR}/..")"
NETWORK_DIR="${PROJECT_ROOT}/quorum-test-network"
ARTIFACTS_DIR="${SCRIPT_DIR}/artifacts"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
FRONTEND_ABI_DIR="${FRONTEND_DIR}/src/abi"
FRONTEND_ABI_TARGET="${FRONTEND_ABI_DIR}/Voting.json"
CONTRACT_ABI_SOURCE="${ARTIFACTS_DIR}/VotingWithNFT.abi.json"
FRONTEND_ENV_EXAMPLE="${FRONTEND_DIR}/.env.example"
FRONTEND_ENV_FILE="${FRONTEND_DIR}/.env"
FRONTEND_ENV_LOCAL="${FRONTEND_DIR}/.env.local"
# Optional deployment metadata overrides are read from deploy.env.
DEPLOY_ENV_FILE="${SCRIPT_DIR}/deploy.env"
DEPLOY_ENV_SOURCED="false"

if [[ -f "${DEPLOY_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${DEPLOY_ENV_FILE}"
    set +a
    DEPLOY_ENV_SOURCED="true"
fi

DEFAULT_RPC_ENDPOINT="http://localhost:10545"
DEFAULT_EXPECTED_VOTERS="${REACT_APP_EXPECTED_VOTERS:-1000}"
DEFAULT_CHAIN_ID_HEX="${REACT_APP_CHAIN_ID:-0x539}"
DEFAULT_CHAIN_NAME="${REACT_APP_CHAIN_NAME:-Quorum Local}"
DEFAULT_PROPOSALS="Alice,Bob,Charlie"

# Helper function to convert date string to Unix timestamp in nanoseconds
# Accepts format: "YYYY-MM-DD HH:MM:SS" or Unix timestamp (auto-detects seconds/nanoseconds)
date_to_timestamp() {
    local input="$1"
    # If already a number (Unix timestamp)
    if [[ "$input" =~ ^[0-9]+$ ]]; then
        # Check if it's in seconds (< year 2286) or nanoseconds
        if [[ ${#input} -le 10 ]]; then
            # It's in seconds, convert to nanoseconds
            echo "${input}000000000"
        else
            # Already in nanoseconds
            echo "$input"
        fi
    else
        # Convert date string to Unix timestamp in nanoseconds
        local seconds
        seconds=$(date -d "$input" +%s 2>/dev/null || echo "")
        if [[ -n "$seconds" ]]; then
            echo "${seconds}000000000"
        else
            echo "$input"
        fi
    fi
}

NOW_NANOSECONDS=$(date +%s%N)
DEFAULT_BALLOT_OPEN=${BALLOT_OPENS_AT:-$NOW_NANOSECONDS}
# 1시간 = 3,600,000,000,000 나노초, 7일 = 604,800,000,000,000 나노초
DEFAULT_BALLOT_CLOSE=${BALLOT_CLOSES_AT:-$((DEFAULT_BALLOT_OPEN + 3600000000000))}
DEFAULT_BALLOT_ANNOUNCE=${BALLOT_ANNOUNCES_AT:-$((DEFAULT_BALLOT_CLOSE + 180000000000))}
DEFAULT_BALLOT_ID="${BALLOT_ID:-citizen-2025}"
DEFAULT_BALLOT_TITLE="${BALLOT_TITLE:-제 25대 대통령 선거}"
DEFAULT_BALLOT_DESCRIPTION="${BALLOT_DESCRIPTION:-대한민국 제 25대 대통령을 선출하는 공식 선거입니다.}"

# Convert date strings to timestamps if needed
DEFAULT_BALLOT_OPEN=$(date_to_timestamp "${DEFAULT_BALLOT_OPEN}")
DEFAULT_BALLOT_CLOSE=$(date_to_timestamp "${DEFAULT_BALLOT_CLOSE}")
DEFAULT_BALLOT_ANNOUNCE=$(date_to_timestamp "${DEFAULT_BALLOT_ANNOUNCE}")

# 색상 출력
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

if [[ "${DEPLOY_ENV_SOURCED}" == "true" ]]; then
    echo -e "${YELLOW}Using deployment configuration from ${DEPLOY_ENV_FILE}${NC}"
else
    echo -e "${YELLOW}No deploy.env found. Using inline defaults for deployment metadata.${NC}"
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Quorum Network Setup & Deployment${NC}"
echo -e "${GREEN}========================================${NC}"

escape_sed_replacement() {
    printf '%s' "$1" | sed -e 's/[&|]/\\&/g'
}

replace_or_append_env_key() {
    local file="$1"
    local key="$2"
    local value="$3"

    mkdir -p "$(dirname "${file}")"
    touch "${file}"

    local escaped
    escaped=$(escape_sed_replacement "${value}")

    if grep -q "^${key}=" "${file}"; then
        sed -i "s|^${key}=.*$|${key}=${escaped}|" "${file}"
    else
        echo "${key}=${value}" >> "${file}"
    fi
}

sync_frontend_abi() {
    if [[ ! -f "${CONTRACT_ABI_SOURCE}" ]]; then
        echo -e "${RED}✗ ABI file not found: ${CONTRACT_ABI_SOURCE}${NC}"
        echo -e "${YELLOW}Please compile the contract before re-running this script.${NC}"
        exit 1
    fi

    mkdir -p "${FRONTEND_ABI_DIR}"
    cp "${CONTRACT_ABI_SOURCE}" "${FRONTEND_ABI_TARGET}"
    echo -e "${GREEN}✓ ABI synced to frontend at ${FRONTEND_ABI_TARGET}${NC}"
}

write_env_example() {
    mkdir -p "${FRONTEND_DIR}"
    cat > "${FRONTEND_ENV_EXAMPLE}" <<'EOF'
# Frontend environment template for the Quorum voting UI.
# Copy this file to .env.local and update the values before running npm start.

# RPC endpoint for the local GoQuorum network
REACT_APP_RPC=http://localhost:10545

# Deployed VotingWithNFT contract address (from quorum-lab/artifacts/deployment.json)
REACT_APP_VOTING_ADDRESS=<deployed-contract-address>

# Optional expected voter turnout baseline (used for UI percentage)
REACT_APP_EXPECTED_VOTERS=1000

# Chain metadata used for network validation in the wallet flow
REACT_APP_CHAIN_ID=0x539
REACT_APP_CHAIN_NAME=Quorum Local
EOF
    echo -e "${GREEN}✓ Generated frontend/.env.example template${NC}"
}

ensure_env_template() {
    if [[ ! -f "${FRONTEND_ENV_EXAMPLE}" ]]; then
        write_env_example
    fi
}

ensure_env_file_exists() {
    local target="$1"
    ensure_env_template
    if [[ ! -f "${target}" ]]; then
        cp "${FRONTEND_ENV_EXAMPLE}" "${target}"
        echo -e "${GREEN}✓ Created ${target} from template${NC}"
    fi
}

sync_frontend_env_files() {
    local contract_address="$1"

    ensure_env_template
    ensure_env_file_exists "${FRONTEND_ENV_FILE}"
    ensure_env_file_exists "${FRONTEND_ENV_LOCAL}"

    local address_value="${contract_address:-<deployed-contract-address>}"

    for env_file in "${FRONTEND_ENV_FILE}" "${FRONTEND_ENV_LOCAL}"; do
        replace_or_append_env_key "${env_file}" "REACT_APP_RPC" "${DEFAULT_RPC_ENDPOINT}"
        replace_or_append_env_key "${env_file}" "REACT_APP_EXPECTED_VOTERS" "${DEFAULT_EXPECTED_VOTERS}"
        replace_or_append_env_key "${env_file}" "REACT_APP_CHAIN_ID" "${DEFAULT_CHAIN_ID_HEX}"
        replace_or_append_env_key "${env_file}" "REACT_APP_CHAIN_NAME" "${DEFAULT_CHAIN_NAME}"
        replace_or_append_env_key "${env_file}" "REACT_APP_VOTING_ADDRESS" "${address_value}"
    done

    echo -e "${GREEN}✓ Updated frontend env files with contract metadata${NC}"
}

# 1. 합의 알고리즘 확인
echo -e "\n${YELLOW}[1/6] Checking consensus algorithm...${NC}"
if [[ ! -f "${NETWORK_DIR}/.env" ]]; then
    echo -e "${RED}✗ .env file not found in quorum-test-network/${NC}"
    echo -e "${YELLOW}Please copy .env.example or create .env file with GOQUORUM_CONS_ALGO${NC}"
    echo -e "${YELLOW}Example: GOQUORUM_CONS_ALGO=raft${NC}"
    exit 1
fi

CONSENSUS=$(grep "^GOQUORUM_CONS_ALGO=" "${NETWORK_DIR}/.env" | cut -d= -f2)
if [[ -z "$CONSENSUS" ]]; then
    echo -e "${RED}✗ GOQUORUM_CONS_ALGO not set in .env${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Consensus algorithm: ${CONSENSUS}${NC}"

# 합의 알고리즘 변경 경고
if [[ -f "${ARTIFACTS_DIR}/deployment.json" ]]; then
    LAST_CONSENSUS=$(node -p "try { require('${ARTIFACTS_DIR}/deployment.json').network.consensus || '' } catch(e) { '' }" 2>/dev/null || echo "")
    if [[ -n "$LAST_CONSENSUS" ]] && [[ "$LAST_CONSENSUS" != "$CONSENSUS" ]]; then
        echo -e "${RED}⚠ WARNING: Consensus algorithm changed from ${LAST_CONSENSUS} to ${CONSENSUS}${NC}"
        echo -e "${YELLOW}You must reset the blockchain data:${NC}"
        echo -e "${YELLOW}  cd quorum-test-network && docker-compose down -v && docker-compose up -d${NC}"
        echo -e "${YELLOW}Press Ctrl+C to abort, or wait 5 seconds to continue...${NC}"
        sleep 5
    fi
fi

# Docker Compose 명령어 감지
if docker compose version &>/dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}✗ Neither 'docker compose' nor 'docker-compose' found${NC}"
    exit 1
fi

# 2. 네트워크 상태 확인
echo -e "\n${YELLOW}[2/6] Checking network status...${NC}"
cd "${NETWORK_DIR}"

if $DOCKER_COMPOSE ps 2>/dev/null | grep -q "validator1.*Up"; then
    echo -e "${GREEN}✓ Network is already running${NC}"
else
    echo -e "${YELLOW}Starting network...${NC}"
    $DOCKER_COMPOSE up -d
    
    # 네트워크가 완전히 시작될 때까지 대기
    echo -e "${YELLOW}Waiting for network to be ready...${NC}"
    sleep 10
    
    # 노드 상태 확인
    MAX_RETRIES=30
    RETRY=0
    while [ $RETRY -lt $MAX_RETRIES ]; do
        if curl -s -X POST "${DEFAULT_RPC_ENDPOINT}" \
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
        echo -e "\n${RED}✗ Network failed to start on ${DEFAULT_RPC_ENDPOINT}${NC}"
        exit 1
    fi
fi

# 3. Node.js 의존성 확인
echo -e "\n${YELLOW}[3/6] Checking Node.js dependencies...${NC}"
cd "${SCRIPT_DIR}"

if [[ ! -d "node_modules" ]]; then
    echo -e "${YELLOW}Installing Node.js dependencies...${NC}"
    npm install solc@0.8.20 web3@1.10.2 @openzeppelin/contracts@5.0.0
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
    
    RESPONSE=$(curl -s -X POST "${DEFAULT_RPC_ENDPOINT}" \
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

    if [[ -z "${PROPOSALS:-}" ]]; then
        PROPOSALS="${DEFAULT_PROPOSALS}"
    fi
    if [[ -z "${BALLOT_ID:-}" ]]; then
        BALLOT_ID="${DEFAULT_BALLOT_ID}"
    fi
    if [[ -z "${BALLOT_TITLE:-}" ]]; then
        BALLOT_TITLE="${DEFAULT_BALLOT_TITLE}"
    fi
    if [[ -z "${BALLOT_DESCRIPTION:-}" ]]; then
        BALLOT_DESCRIPTION="${DEFAULT_BALLOT_DESCRIPTION}"
    fi
    if [[ -z "${BALLOT_OPENS_AT:-}" ]]; then
        BALLOT_OPENS_AT="${DEFAULT_BALLOT_OPEN}"
    else
        BALLOT_OPENS_AT=$(date_to_timestamp "${BALLOT_OPENS_AT}")
    fi
    if [[ -z "${BALLOT_CLOSES_AT:-}" ]]; then
        BALLOT_CLOSES_AT="${DEFAULT_BALLOT_CLOSE}"
    else
        BALLOT_CLOSES_AT=$(date_to_timestamp "${BALLOT_CLOSES_AT}")
    fi
    if [[ -z "${BALLOT_ANNOUNCES_AT:-}" ]]; then
        BALLOT_ANNOUNCES_AT="${DEFAULT_BALLOT_ANNOUNCE}"
    else
        BALLOT_ANNOUNCES_AT=$(date_to_timestamp "${BALLOT_ANNOUNCES_AT}")
    fi
    if [[ -z "${BALLOT_EXPECTED_VOTERS:-}" ]]; then
        BALLOT_EXPECTED_VOTERS="${DEFAULT_EXPECTED_VOTERS}"
    fi

    export PROPOSALS BALLOT_ID BALLOT_TITLE BALLOT_DESCRIPTION
    export BALLOT_OPENS_AT BALLOT_CLOSES_AT BALLOT_ANNOUNCES_AT BALLOT_EXPECTED_VOTERS

    GOQUORUM_CONS_ALGO="${CONSENSUS}" node deploy_contract.js
    
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

echo -e "\n${YELLOW}Syncing ABI with frontend...${NC}"
sync_frontend_abi

DEPLOYMENT_ADDRESS=$(node -p "try { require('${ARTIFACTS_DIR}/deployment.json').contract.address || '' } catch(e) { '' }")
if [[ -z "${DEPLOYMENT_ADDRESS}" ]]; then
    echo -e "${YELLOW}Deployment address not found. Frontend env files will contain a placeholder until deployment succeeds.${NC}"
fi
sync_frontend_env_files "${DEPLOYMENT_ADDRESS}"

# 완료
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Network:${NC} ${CONSENSUS}"
echo -e "${GREEN}RPC Endpoint:${NC} ${DEFAULT_RPC_ENDPOINT}"
echo -e "${GREEN}Contract Address:${NC} $(node -p "require('${ARTIFACTS_DIR}/deployment.json').contract.address" 2>/dev/null || echo 'N/A')"
echo -e "${GREEN}Artifacts:${NC} ${ARTIFACTS_DIR}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Run benchmarks: ${GREEN}cd quorum-lab && ./run_raft_benchmarks.sh${NC}"
echo -e "  2. Check network: ${GREEN}cd quorum-test-network && docker compose ps${NC}"
echo -e "  3. View logs: ${GREEN}cd quorum-test-network && docker compose logs -f validator1${NC}"
echo ""
