#!/bin/bash
sed 's/@APP@/CHROME/g; s/@app@/chrome/g' app_template.kbd >chrome.kbd
sed 's/@APP@/FOOT/g; s/@app@/foot/g' app_template.kbd >foot.kbd
sed 's/@APP@/OBSIDIAN/g; s/@app@/obsidian/g' app_template.kbd >obsidian.kbd
sed 's/@APP@/ZELLIJ/g; s/@app@/zellij/g' app_template.kbd >zellij.kbd
sed 's/@APP@/NVIM/g; s/@app@/nvim/g' app_template.kbd >nvim.kbd
sed 's/@APP@/DOLPHIN/g; s/@app@/dolphin/g' app_template.kbd >dolphin.kbd
