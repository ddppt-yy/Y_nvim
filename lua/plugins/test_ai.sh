#!/usr/bin/env bash
#
# test-all-models.sh
# 动态获取 /v1/models 返回的模型列表，逐个测试可用性（只输出到终端，不写文件）
#
# 使用前必须设置环境变量：
#   export MINUET_END_POINT="https://new-api.aiplan.mthreads.com/v1"
#   export MINUET_API_KEY="sk-mtcode-xxxxx"
#
set -uo pipefail

# ============ 配置（从环境变量读取） ============
RAW_BASE_URL="${MINUET_END_POINT:-}"
API_KEY="${MINUET_API_KEY:-}"

if [ -z "$RAW_BASE_URL" ]; then
    echo "错误：未设置环境变量 MINUET_END_POINT" >&2
    echo "示例：export MINUET_END_POINT='https://new-api.aiplan.mthreads.com/v1'" >&2
    exit 1
fi

if [ -z "$API_KEY" ]; then
    echo "错误：未设置环境变量 MINUET_API_KEY" >&2
    echo "示例：export MINUET_API_KEY='sk-mtcode-xxxxx'" >&2
    exit 1
fi

# 规范化：只保留到 /v1 为止
if [[ "$RAW_BASE_URL" == *"/v1"* ]]; then
    BASE_URL="${RAW_BASE_URL%%/v1*}/v1"
else
    BASE_URL="${RAW_BASE_URL%/}"
fi

if [ "$BASE_URL" != "$RAW_BASE_URL" ]; then
    echo "提示：BASE_URL 已规范化"
    echo "  原始 : $RAW_BASE_URL"
    echo "  使用 : $BASE_URL"
    echo
fi

TIMEOUT="${TIMEOUT:-30}"

AUTH="Authorization: Bearer $API_KEY"
CT="Content-Type: application/json"

echo "=============================================="
echo " New API 模型批量测试（动态列表）"
echo " Endpoint : $BASE_URL"
echo " 超时     : ${TIMEOUT}s"
echo "=============================================="
echo

# ============ 步骤 0：查 /v1/models 拿可用列表 ============
echo ">>> [0] 查询 /v1/models 可用模型列表"
echo "----------------------------------------------"
models_resp=$(curl -sS --max-time 10 -H "$AUTH" "$BASE_URL/models" 2>&1)

# 检查 /v1/models 是否成功
if ! printf '%s' "$models_resp" | jq -e '.data' >/dev/null 2>&1; then
    echo "错误：/v1/models 请求失败或返回格式异常" >&2
    echo "原始响应：" >&2
    printf '%s\n' "$models_resp" >&2
    exit 1
fi

# 动态提取模型列表到数组
mapfile -t MODELS < <(printf '%s' "$models_resp" | jq -r '.data[].id' | sort)

available_count=${#MODELS[@]}
echo "网关返回可用模型数：$available_count"
echo "可用模型列表："
for m in "${MODELS[@]}"; do
    echo "  - $m"
done
echo

if [ "$available_count" -eq 0 ]; then
    echo "没有可测试的模型，退出"
    exit 0
fi

# ============ 逐个测试 ============
ok=0; fail=0; total=$available_count
ok_list=""
fail_list=""

for MODEL in "${MODELS[@]}"; do
    body="{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":8,\"stream\":false}"

    start_ms=$(date +%s%3N)

    resp=$(curl -sS --max-time "$TIMEOUT" \
        -X POST \
        -H "$AUTH" \
        -H "$CT" \
        -w "\n__HTTP_CODE__:%{http_code}" \
        -d "$body" \
        "$BASE_URL/chat/completions" 2>&1)

    end_ms=$(date +%s%3N)
    latency=$((end_ms - start_ms))

    http_code=$(printf '%s' "$resp" | sed -n 's/.*__HTTP_CODE__:\([0-9]*\).*/\1/p')
    json_body=$(printf '%s' "$resp" | sed 's/\n__HTTP_CODE__:[0-9]*//')

    if [ "$http_code" = "200" ]; then
        note=$(printf '%s' "$json_body" | jq -r '.choices[0].message.content // "ok"' 2>/dev/null | head -c 40)
        ok=$((ok + 1))
        ok_list="${ok_list}${MODEL}"$'\n'
        printf '%-8s %-32s %6sms  %s\n' "[OK]" "$MODEL" "$latency" "$note"
    else
        code=$(printf '%s' "$json_body" | jq -r '.error.code // empty' 2>/dev/null)
        msg=$(printf '%s' "$json_body" | jq -r '.error.message // "unknown error"' 2>/dev/null)
        fail=$((fail + 1))
        fail_list="${fail_list}${MODEL}"$'\t'"${code}"$'\t'"${msg}"$'\n'
        printf '%-8s %-32s %6sms  [%s] %s\n' "[FAIL]" "$MODEL" "$latency" "$code" "$msg"
    fi
done

# ============ 汇总 ============
echo
echo "=============================================="
echo " 测试完成"
echo "  总数   : $total"
echo "  成功   : $ok"
echo "  失败   : $fail"
echo "=============================================="
echo
echo ">>> 成功模型："
if [ -n "$ok_list" ]; then
    printf '%s' "$ok_list" | sed 's/^/  /'
else
    echo "  （无）"
fi
echo
echo ">>> 失败模型（按错误类型分组）："
if [ -n "$fail_list" ]; then
    printf '%s' "$fail_list" | awk -F'\t' '{print $3}' \
        | sort | uniq -c | sort -rn | while read -r cnt msg; do
            echo "  ($cnt 个) $msg"
        done
else
    echo "  （无）"
fi
echo
