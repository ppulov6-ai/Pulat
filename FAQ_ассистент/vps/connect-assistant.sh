#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export MODEL_DIR="${MODEL_DIR:-$HOME/pulat-model/qwen}"
mkdir -p "$MODEL_DIR"
docker_cmd=(sudo docker)
if [[ $(id -u) = 0 || ${CI:-} = true ]]; then docker_cmd=(docker); fi
base=("${docker_cmd[@]}" compose -p pulat-portfolio -f compose.yaml)
if [[ -f compose.override.yaml ]]; then base+=(-f compose.override.yaml); fi
candidate=("${base[@]}" -f qwen.yaml)
# Pass the model directory through sudo without relying on its environment policy.
if [[ ${docker_cmd[0]} = sudo ]]; then candidate=(sudo env "MODEL_DIR=$MODEL_DIR" "${candidate[@]:1}"); fi
base_url=${PUBLIC_URL:-https://promtengenier.pulatdesk.com.ru}
if curl -fsS --max-time 3 "$base_url/health" 2>/dev/null | python3 -c 'import json,sys;sys.exit(json.load(sys.stdin).get("model")!="pulat-qwen")' 2>/dev/null; then
  python3 check-dialogue.py "$base_url"
  echo ASSISTANT_LIVE
  exit 0
fi
hash=6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e
if ! echo "$hash  $MODEL_DIR/assistant.gguf" | sha256sum --check --status 2>/dev/null; then
  curl --fail --location --retry 3 -C - 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf' -o "$MODEL_DIR/assistant.part"
  echo "$hash  $MODEL_DIR/assistant.part" | sha256sum --check
  mv "$MODEL_DIR/assistant.part" "$MODEL_DIR/assistant.gguf"
fi
# Download and build before stopping the isolated ruGPT test instance.
"${candidate[@]}" pull qwen
"${candidate[@]}" build portfolio
if [[ $("${docker_cmd[@]}" inspect -f '{{.State.Running}}' pulat-portfolio-dialogue-1 2>/dev/null || true) = true ]]; then
  "${docker_cmd[@]}" stop pulat-portfolio-dialogue-1 >/dev/null
fi
stage=
public_ok=false
cleanup() {
  if [[ -n "$stage" ]]; then "${docker_cmd[@]}" rm -f "$stage" >/dev/null || true; fi
  if ! $public_ok; then
    "${candidate[@]}" stop qwen || true
    if [[ ${promoting:-false} = true ]]; then "${base[@]}" up -d --no-deps --force-recreate --wait portfolio; fi
  fi
}
trap cleanup EXIT
"${candidate[@]}" up -d --no-deps qwen
stage=$("${candidate[@]}" run -d --no-deps -e DB_PATH=:memory: -p 127.0.0.1::8080 portfolio | tail -1)
port=$("${docker_cmd[@]}" port "$stage" 8080/tcp | cut -d: -f2)
ready=false
for i in {1..60}; do
  if "${docker_cmd[@]}" exec "$stage" node -e "fetch('http://qwen:8080/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"; then ready=true; break; fi
  sleep 2
done
$ready || { echo 'Модель не готова'; exit 1; }
python3 check-dialogue.py "http://127.0.0.1:$port"
promoting=true
"${candidate[@]}" up -d --no-deps --wait portfolio
base_url=${PUBLIC_URL:-https://promtengenier.pulatdesk.com.ru}
curl -fsS --max-time 95 "$base_url/chat" -H 'Content-Type: application/json' -d '{"message":"Здравствуйте"}' | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("model")=="pulat-qwen" and d["answer"].strip(); print(d["model"],d["answer"])'
public_ok=true
echo ASSISTANT_LIVE
