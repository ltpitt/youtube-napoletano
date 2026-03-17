# youtube-napoletano 🎶

Scarica video e audio da YouTube, senza pubblicità, direttamente dal browser.

---

## Requisiti

- Python 3.12 o superiore
- Git

---

## Installazione

**macOS / Linux**

```sh
git clone https://github.com/ltpitt/youtube-napoletano.git
cd youtube-napoletano
make install
```

**Windows** (PowerShell o Prompt dei comandi)

```bat
git clone https://github.com/ltpitt/youtube-napoletano.git
cd youtube-napoletano
python -m venv .venv
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
```

---

## Avvio

**macOS / Linux**

```sh
make run
```

**Windows** (PowerShell o Prompt dei comandi)

```bat
.venv\Scripts\python youtube_napoletano.py
```

Apri il browser su [http://localhost:8443](http://localhost:8443).

---

## Come si usa

1. Incolla il link di un video YouTube nel campo di testo
2. Scegli se scaricare il **video** o solo l'**audio (MP3)**
3. Clicca **Scarica** e aspetta la fine del download
4. Il file sarà nella cartella `downloads/`

---

## Aggiornamento yt-dlp

Se i download smettono di funzionare, clicca il pulsante **Aggiorna yt-dlp** nell'interfaccia web.

---

> _Solo per uso personale e didattico. Rispetta i Termini di Servizio di YouTube e le leggi vigenti._
