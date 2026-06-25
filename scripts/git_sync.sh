#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"
EXPECTED_ORIGIN_URL="${EXPECTED_ORIGIN_URL:-https://github.com/caidaxing/meirifupan.git}"

usage() {
  cat <<EOF
用法: scripts/git_sync.sh <命令> [提交说明]

命令:
  status      查看本地分支、远程地址、未提交内容
  doctor      检查远程地址、上游分支和 GitHub 登录状态
  pull        从 ${REMOTE}/${BRANCH} 拉取，自动 rebase，本地改动会临时保存再恢复
  push        推送当前已提交内容到 ${REMOTE}/${BRANCH}
  sync        先 pull，再 push
  save        提交当前改动，然后 pull，再 push

示例:
  scripts/git_sync.sh pull
  scripts/git_sync.sh save "update premarket agent"
  scripts/git_sync.sh sync

可选环境变量:
  REMOTE=origin
  BRANCH=main
EOF
}

cd "${ROOT_DIR}"

current_branch() {
  git branch --show-current
}

ensure_remote() {
  if ! git remote get-url "${REMOTE}" >/dev/null 2>&1; then
    echo "找不到远程仓库: ${REMOTE}"
    echo "当前远程仓库:"
    git remote -v
    exit 2
  fi
}

ensure_branch() {
  local branch
  branch="$(current_branch)"
  if [ "${branch}" != "${BRANCH}" ]; then
    echo "当前分支是 ${branch}，脚本默认同步 ${BRANCH}。"
    echo "如需同步当前分支，请这样运行: BRANCH=${branch} scripts/git_sync.sh $*"
    exit 2
  fi
}

print_auth_hint() {
  cat <<EOF

如果这里提示 403 或使用了错误账号，请在终端运行:
  gh auth logout -h github.com
  gh auth login -h github.com -p https -w
  gh auth setup-git

授权时确认登录的是 caidaxing。
EOF
}

cmd_status() {
  echo "目录: ${ROOT_DIR}"
  echo "分支: $(current_branch)"
  echo
  echo "远程仓库:"
  git remote -v
  echo
  echo "上游分支:"
  git branch -vv
  echo
  echo "工作区:"
  git status --short --branch
}

cmd_doctor() {
  cmd_status
  echo
  echo "GitHub 登录:"
  if command -v gh >/dev/null 2>&1; then
    gh auth status -h github.com || true
  else
    echo "未找到 gh。建议安装 GitHub CLI，方便 Git 使用正确账号。"
  fi
  echo
  local origin_url
  origin_url="$(git remote get-url origin 2>/dev/null || true)"
  if [ "${origin_url}" = "${EXPECTED_ORIGIN_URL}" ]; then
    echo "origin 已指向新仓库: ${EXPECTED_ORIGIN_URL}"
  else
    echo "origin 当前不是预期地址。"
    echo "当前: ${origin_url:-未设置}"
    echo "预期: ${EXPECTED_ORIGIN_URL}"
  fi
}

cmd_pull() {
  ensure_remote
  ensure_branch "$@"
  echo "拉取 ${REMOTE}/${BRANCH}"
  git pull --rebase --autostash "${REMOTE}" "${BRANCH}" || {
    print_auth_hint
    exit 1
  }
}

cmd_push() {
  ensure_remote
  ensure_branch "$@"
  echo "推送 ${BRANCH} -> ${REMOTE}/${BRANCH}"
  git push "${REMOTE}" "${BRANCH}" || {
    print_auth_hint
    exit 1
  }
}

cmd_sync() {
  cmd_pull "$@"
  cmd_push "$@"
}

cmd_save() {
  ensure_remote
  ensure_branch "$@"
  local message="${1:-auto sync $(date '+%Y-%m-%d %H:%M:%S')}"

  if [ -n "$(git status --porcelain)" ]; then
    echo "提交当前改动: ${message}"
    git add -A
    git commit -m "${message}"
  else
    echo "没有未提交改动，跳过提交。"
  fi

  cmd_sync "$@"
}

case "${1:-}" in
  status) cmd_status ;;
  doctor) cmd_doctor ;;
  pull) shift; cmd_pull "$@" ;;
  push) shift; cmd_push "$@" ;;
  sync) shift; cmd_sync "$@" ;;
  save) shift; cmd_save "$@" ;;
  -h|--help|help|"") usage ;;
  *)
    echo "未知命令: $1"
    usage
    exit 2
    ;;
esac
