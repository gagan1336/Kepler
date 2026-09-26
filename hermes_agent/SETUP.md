# 🤖 Hermes AI Setup Guide

## Step 1 — Install Ollama

Download and install Ollama for Windows:
👉 **https://ollama.com/download**

Run the installer, then verify it's working:
```powershell
ollama --version
```

---

## Step 2 — Pull Nous Hermes 3

Open PowerShell and run:
```powershell
ollama pull hermes3
```

> This downloads ~4.7 GB. Takes a few minutes depending on your internet speed.

Verify it works:
```powershell
ollama run hermes3 "Say hello in one sentence"
```

---

## Step 3 — Run Hermes (Python dependencies already installed ✅)

Open a terminal in the `hermes_agent` folder:
```powershell
cd "F:\Stock market analysis\hermes_agent"
```

### Commands

```powershell
# Analyse all trades and update memory
python main.py analyze

# Generate today's daily debrief
python main.py debrief

# Generate last week's full review
python main.py weekly

# Show what Hermes has learned about you
python main.py status

# Auto-run daily + weekly (leave running in background)
python main.py watch
```

---

## How It Works

```
Your journal notes (markdown)
        ↓
   vault_reader.py  ←  parses all .md files
        ↓
   hermes_client.py ←  sends to Ollama (local AI)
        ↓
   Nous Hermes 3    ←  generates insights
        ↓
   writer.py        ←  writes back to vault
        ↓
🤖 AI Insights/ folder in Obsidian
```

---

## Self-Learning Memory

Every time you run `analyze`, Hermes reads your trades and extracts patterns into `memory.json`.
The more you journal, the smarter it gets.

View what it's learned:
```powershell
python main.py status
```

The `🤖 AI Insights/Hermes Memory.md` note in your vault always shows the latest summary.
