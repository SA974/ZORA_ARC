#!/usr/bin/env python3
"""Count PDFs in folder (handles long paths better than PowerShell)."""

import sys
from pathlib import Path

root = Path(r"F:\Dropbox\ENTREPRISES\STEPHANE_ARNOUX\SERVICE_SI_RD\RECHERCHE\HOMO_SAPIENS_SAPIENS")
if not root.exists():
    print(f"Folder not found: {root}")
    sys.exit(1)

try:
    pdfs = list(root.glob("**/*.pdf"))
    print(f"Total PDFs found: {len(pdfs)}")
    print(f"Sample files:")
    for pdf in pdfs[:3]:
        print(f"  - {pdf.name}")
except Exception as e:
    print(f"Error: {e}")
