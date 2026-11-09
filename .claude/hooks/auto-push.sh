#!/usr/bin/env bash
# HUMO PLASTIK — avtomatik GitHub'ga yuborish (Claude Code Stop hook).
# Claude ishini tugatganda: o'zgarish bo'lsa commit qiladi va origin/main ga push qiladi.
# Vercel GitHub'ga ulangan bo'lsa, har bir push'dan keyin sayt o'zi qayta joylanadi.

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

msg() { printf '{"systemMessage": "%s"}\n' "$1"; }

if [ -n "$(git status --porcelain)" ]; then
  git add -A

  # Xavfsizlik: bot tokeni yoki .env hech qachon GitHub'ga ketmasin
  if git diff --cached --name-only | grep -qE '(^|/)\.env$' \
     || git diff --cached -U0 | grep -qE '[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}'; then
    git reset -q
    msg "Avto-push to'xtatildi: o'zgarishlarda bot tokeni yoki .env bor. Tekshiring."
    exit 0
  fi

  files=$(git diff --cached --name-only | head -5 | tr '\n' ' ')
  count=$(git diff --cached --name-only | wc -l | tr -d ' ')
  git commit -q -m "Avtomatik yangilanish: ${count} ta fayl (${files% })" \
             -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || exit 0
fi

# Yuborilmagan commit bo'lsa — push
if [ -n "$(git log origin/main..HEAD --oneline 2>/dev/null)" ]; then
  if git push -q origin main 2>/tmp/humo-push-err.txt; then
    msg "GitHub'ga yuborildi ✓ — Vercel saytni avtomatik yangilaydi."
  else
    msg "GitHub'ga yuborib bo'lmadi: $(head -1 /tmp/humo-push-err.txt | tr -d '\"')"
  fi
fi
exit 0
