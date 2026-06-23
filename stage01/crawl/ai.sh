#!/bin/bash

echo "请选择要启动的工具："
echo "1) Claude"
echo "2) Codex"
read -p "输入选项 (1/2): " choice

export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
export OPENAI_API_KEY=sk-SvMpwUYNUb0KTPhfAWm2bTSJE7VF9RsdP70ICTdINlF89BPA
export OPENAI_BASE_URL=https://sinsy.eu.cc/
export ANTHROPIC_AUTH_TOKEN=sk-SvMpwUYNUb0KTPhfAWm2bTSJE7VF9RsdP70ICTdINlF89BPA
export ANTHROPIC_BASE_URL=https://sinsy.eu.cc/

case $choice in
  1)
#    export ANTHROPIC_MODEL=accounts/fireworks/models/glm-5p2
    export ANTHROPIC_MODEL=claude-opus-4-7-max
    echo "启动 Claude..."
    claude --dangerously-skip-permissions
    ;;
  2)
    export OPENAI_MODEL=glm-5.1
    echo "启动 Codex..."
    codex --full-auto
    ;;
  *)
    echo "无效选项，请输入 1 或 2"
    exit 1
    ;;
esac