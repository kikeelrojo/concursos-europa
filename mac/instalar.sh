#!/bin/bash
# Instala el ayudante Concursos.app y registra el esquema concursos://
set -e
mkdir -p ~/Applications
rm -rf ~/Applications/Concursos.app
osacompile -o ~/Applications/Concursos.app "$(dirname "$0")/Concursos.applescript"
PL=~/Applications/Concursos.app/Contents/Info.plist
plutil -replace CFBundleIdentifier -string "eu.arrova.concursos" "$PL"
plutil -replace CFBundleURLTypes -json '[{"CFBundleURLName":"concursos","CFBundleURLSchemes":["concursos"]}]' "$PL"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f ~/Applications/Concursos.app
open -a ~/Applications/Concursos.app --args --registrar >/dev/null 2>&1 || true
echo "Ayudante instalado en ~/Applications/Concursos.app"
