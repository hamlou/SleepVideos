#!/usr/bin/env bash
# Commit pipeline state (data/, topic files) with retries so parallel workflows never clobber each other.
set -u
git config user.name "sleep-factory-bot"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add data topics.txt topics_done.txt 2>/dev/null || true
if git diff --cached --quiet; then
  echo "no state changes"
  exit 0
fi
git commit -q -m "${1:-state update} [skip ci]"
for i in 1 2 3 4 5; do
  if git pull -q --rebase -X theirs && git push -q; then
    echo "state pushed"
    exit 0
  fi
  echo "push retry $i"
  sleep $((i * 5))
done
echo "could not push state" >&2
exit 1
