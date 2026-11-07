#!/bin/bash
set -euo pipefail

region=ap-northeast-3
registry=610331149158.dkr.ecr.ap-northeast-3.amazonaws.com
image_tag='__IMAGE_TAG__'

dnf install -y docker
systemctl enable --now docker

install -d /usr/local/lib/docker/cli-plugins
curl -fsSL --retry 3 \
  https://github.com/docker/compose/releases/download/v5.6.0/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

install -d /opt/study-task-tracker/certs
cd /opt/study-task-tracker

curl -fsSL --retry 3 \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  -o certs/global-bundle.pem

install -m 600 /dev/null api.aws.env
aws ssm get-parameter --region "$region" --name /cc-cea/app/db-env \
  --with-decryption --query Parameter.Value --output text --no-cli-pager > api.aws.env

cat > compose.aws.yaml <<'COMPOSE_EOF'
__COMPOSE_YAML__
COMPOSE_EOF

export WEB_IMAGE="$registry/study-tracker-web:$image_tag"
export API_IMAGE="$registry/study-tracker-api:$image_tag"

aws ecr get-login-password --region "$region" |
  docker login --username AWS --password-stdin "$registry"
trap 'docker logout "$registry" >/dev/null 2>&1 || true' EXIT

docker compose -f compose.aws.yaml pull
docker compose -f compose.aws.yaml up -d --wait --wait-timeout 180
curl -fsS http://127.0.0.1/health
