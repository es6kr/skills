#!/usr/bin/env bash
# Phase 3 auto-publish prerequisites + tag parser sanity test.
# Run after `gh secret set CLAWHUB_TOKEN` + clawhub-publish environment creation.
set -euo pipefail

REPO="${REPO:-es6kr/skills}"

fail=0
note() { printf "  %s\n" "$*"; }
pass() { printf "  \033[0;32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[0;33m⚠\033[0m %s\n" "$*"; fail=$((fail + 1)); }

echo "1. publish.yml present in repo"
if gh workflow list -R "$REPO" --json name,path 2>/dev/null \
   | jq -e '.[] | select(.path | endswith("publish.yml"))' >/dev/null; then
  pass "publish.yml workflow registered"
else
  warn "publish.yml workflow not found in $REPO — has the PR been merged?"
fi

echo "2. CLAWHUB_TOKEN secret present"
if gh secret list -R "$REPO" 2>/dev/null | grep -q '^CLAWHUB_TOKEN'; then
  pass "CLAWHUB_TOKEN secret registered"
else
  warn "CLAWHUB_TOKEN missing — run: gh secret set CLAWHUB_TOKEN -R $REPO --body <token>"
fi

echo "3. clawhub-publish environment with required-reviewer protection"
env_json="$(gh api "repos/$REPO/environments/clawhub-publish" 2>/dev/null || true)"
if [ -n "$env_json" ] && \
   echo "$env_json" | jq -e '.protection_rules[]? | select(.type == "required_reviewers")' >/dev/null; then
  pass "clawhub-publish environment with required_reviewers protection found"
else
  warn "clawhub-publish environment missing or has no required_reviewers rule"
  note "create via: gh api repos/$REPO/environments/clawhub-publish -X PUT \\"
  note "             -F 'reviewers[][type]=User' -F 'reviewers[][id]=<github-user-id>'"
fi

echo "4. Tag pattern parser self-test"
for tag in "claude-session-v0.1.5" "skill-kit-v1.0.0" "next-v0.2.0" "wip-v0.3.0"; do
  slug="${tag%-v*}"
  version="${tag##*-v}"
  if [ "$slug" = "$tag" ] || [ -z "$version" ]; then
    warn "tag '$tag' did not parse cleanly (slug='$slug' version='$version')"
  else
    pass "$tag → slug=$slug version=$version"
  fi
done

echo "5. Negative test — non-skill tag must fail the parse"
neg_tag="infra-v1.0.0"
neg_slug="${neg_tag%-v*}"
if [ -d "skills/$neg_slug" ]; then
  warn "skills/$neg_slug exists; negative test inconclusive — pick a different non-skill name"
else
  pass "skills/$neg_slug absent — workflow Parse step would reject $neg_tag"
fi

echo
if [ "$fail" -eq 0 ]; then
  printf "\033[0;32mAll Phase 3 prerequisites satisfied.\033[0m\n"
  exit 0
else
  printf "\033[0;33m%d prerequisite(s) unmet — see warnings above.\033[0m\n" "$fail"
  exit 1
fi
