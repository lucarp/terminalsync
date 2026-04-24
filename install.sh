#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/lucarp/terminalsync.git"
MIN_PYTHON="3.11"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}✓${RESET} $*"; }
info() { echo -e "${BOLD}→${RESET} $*"; }
warn() { echo -e "${YELLOW}!${RESET} $*"; }
die()  { echo -e "${RED}✗${RESET} $*" >&2; exit 1; }

echo -e "\n${BOLD}TerminalSync installer${RESET}\n"

# ── Python check ─────────────────────────────────────────────────────────────
info "Checking Python..."
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null)
        major=${ver%%.*}; minor=${ver##*.}
        req_major=${MIN_PYTHON%%.*}; req_minor=${MIN_PYTHON##*.}
        if [ "$major" -gt "$req_major" ] || { [ "$major" -eq "$req_major" ] && [ "$minor" -ge "$req_minor" ]; }; then
            PYTHON="$cmd"
            ok "Found $cmd $ver"
            break
        fi
    fi
done
[ -n "$PYTHON" ] || die "Python $MIN_PYTHON+ is required. Install it from https://python.org"

# ── Install method ───────────────────────────────────────────────────────────
if command -v pipx &>/dev/null; then
    info "Installing with pipx (isolated environment)..."
    pipx install "git+${REPO}#subdirectory=cli" && ok "Installed via pipx"
elif "$PYTHON" -m pipx --version &>/dev/null 2>&1; then
    info "Installing with pipx (python -m pipx)..."
    "$PYTHON" -m pipx install "git+${REPO}#subdirectory=cli" && ok "Installed via pipx"
else
    # Offer to install pipx first
    echo ""
    warn "pipx not found. pipx gives terminalsync its own isolated environment (recommended)."
    echo "  Install pipx: ${BOLD}$PYTHON -m pip install --user pipx${RESET}"
    echo ""
    read -rp "Install without pipx using pip instead? [y/N] " answer
    case "$answer" in
        [Yy]*)
            info "Installing with pip..."
            "$PYTHON" -m pip install --user "git+${REPO}#subdirectory=cli"
            ok "Installed via pip"
            ;;
        *)
            info "Run this first, then re-run install.sh:"
            echo "  $PYTHON -m pip install --user pipx"
            echo "  $PYTHON -m pipx ensurepath"
            exit 0
            ;;
    esac
fi

# ── PATH check ───────────────────────────────────────────────────────────────
echo ""
if command -v terminalsync &>/dev/null; then
    ok "terminalsync is in PATH"
else
    warn "'terminalsync' not found in PATH yet."
    echo "  Add this to your shell profile (~/.bashrc or ~/.zshrc):"
    echo ""
    echo '  export PATH="$HOME/.local/bin:$PATH"'
    echo ""
    echo "  Then reload: source ~/.bashrc"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}Done!${RESET} Run ${BOLD}terminalsync${RESET} in any terminal tab."
echo ""
echo "  Docs:   https://github.com/lucarp/terminalsync"
echo "  Issues: https://github.com/lucarp/terminalsync/issues"
echo ""
