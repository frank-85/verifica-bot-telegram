# Verifica Bot

**Un semaforo per capire quanto fidarsi di un bot o di una Mini App Telegram.**

🇮🇹 Italiano · [🇬🇧 English](README.en.md)

Su Telegram i bot che imitano marchi noti, promettono guadagni o chiedono un deposito «per sbloccare il prelievo» sono sempre più frequenti. Verifica Bot aiuta a riconoscerne i segnali prima di cliccare: raccoglie indizi, li pesa con regole pubbliche e restituisce un esito 🟢 🟡 🔴 con le ragioni e con cosa fare o non fare.

**Provalo:** https://frank-85.github.io/verifica-bot-telegram/

L'app è in italiano. Una versione inglese è in programma.

> **L'esito è un'indicazione, non una prova.** Ha valore puramente orientativo: non è un parere legale, forense o tecnico certificato e non ha valore giuridico o probatorio. Può sbagliare in entrambe le direzioni. Un rosso non è un'accusa, un verde non è una garanzia. La decisione di usare o no un bot resta sempre e soltanto di chi lo usa.

## Cosa fa

Ti guida in pochi passi:

1. **Il nome del bot.** Lo strumento controlla da sé se imita un marchio noto (lettere aggiunte, tolte o sostituite, cifre al posto di lettere) e se contiene parole usate come esca.
2. **Quello che il bot ti ha mostrato.** Puoi incollare il testo o caricare uno screenshot: il testo viene letto sul tuo dispositivo e confrontato con un elenco di frasi tipiche (rendimenti garantiti, richiesta di seed phrase, prelievo condizionato a un deposito).
3. **Il link della Mini App**, se c'è.
4. **Alcune domande semplici**, a cui puoi rispondere anche «Non so».

Se un controllo automatico contraddice una tua risposta, prevale il controllo, e il report lo dichiara.

Alla fine ottieni un report con l'esito, il rischio per ciascuna area, i motivi, cosa non è stato possibile verificare e i comportamenti consigliati. Puoi stamparlo o scaricarlo.

## Come decide

Il colore non lo sceglie un'intelligenza artificiale. Lo calcola un motore a regole: a parità di indizi, l'esito è sempre lo stesso, e chiunque può leggere perché.

- **37 segnali** in un catalogo fisso ([`segnali.json`](segnali.json)), ciascuno con un punteggio.
- **6 aree**: identità, promesse, richieste, tecnica, reputazione, trasparenza. Identità, richieste e tecnica pesano il doppio.
- **Soglie**: fino a 30 verde, da 31 a 60 giallo, oltre 60 rosso.
- **10 linee rosse**: segnali così gravi che, se provati direttamente, portano al rosso da soli. Per esempio la richiesta della seed phrase o del codice di accesso a Telegram.
- **Regole di prudenza contro i falsi verdi**: niente verde se le prove sono poche, e niente verde se anche una sola area è al massimo del rischio. Un pericolo grave non deve diluirsi nella media.

Ogni esito è accompagnato dalla **certezza della valutazione**, che dice quanto erano solide le prove. Con la sola autovalutazione la certezza non arriva mai al livello più alto.

## Privacy

- L'app è **un unico file HTML**. Funziona nel browser, anche da telefono, e si può scaricare e aprire senza connessione.
- Quello che scrivi o carichi **non viene inviato a nessuno** e non viene salvato: sparisce quando chiudi la pagina. Niente cookie, niente statistiche, niente account.
- **Unica connessione facoltativa:** se carichi uno screenshot, il browser scarica la libreria open source che legge il testo ([Tesseract.js](https://github.com/naptha/tesseract.js), da cdn.jsdelivr.net). L'immagine resta sul tuo dispositivo. Se preferisci, incolla il testo.
- Una regola di sicurezza della pagina (Content-Security-Policy) blocca le connessioni verso qualsiasi altro indirizzo.
- Se usi la versione online, GitHub Pages riceve i dati tecnici della connessione, come ogni sito web. Per evitarlo, scarica [`index.html`](index.html) e aprilo dal tuo dispositivo.

## Limiti

- Lo strumento vede solo ciò che è pubblico o che gli mostri tu. Il codice che gira sui server di un bot non è visibile a nessuno dall'esterno.
- Un bot nuovo, senza storia, non può ottenere un verde pieno: mancano le prove, in un senso o nell'altro.
- L'elenco dei marchi ([`marchi.txt`](marchi.txt)) e quello delle frasi riconosciute sono per forza incompleti.
- La lettura degli screenshot può sbagliare, soprattutto con immagini piccole o testi in lingue diverse da italiano e inglese.
- I controlli sui file ricevuti (solo nella versione da riga di comando) usano Microsoft Defender e funzionano quindi su Windows.

## Cosa c'è nel repository

| Percorso | Contenuto |
|---|---|
| [`index.html`](index.html) | L'app, pronta all'uso. È generata: non si modifica a mano. |
| `app/` | Interfaccia e motore JavaScript, da cui nasce `index.html`. |
| `punteggio.py`, `nome.py`, `pagina.py`, `rete.py`, `file_check.py`, `resoconto.py` | Il motore Python: calcolo dell'esito, analisi del nome, analisi statica delle pagine, età dei domini, controllo dei file, report. |
| `controlli.py` | Riga di comando del motore Python. |
| `costruisci_app.py` | Assembla `index.html` a partire da `app/` e dai cataloghi. |
| `segnali.json`, `marchi.txt` | Catalogo dei segnali e marchi spesso imitati. |
| `skill/SKILL.md` | Le istruzioni per usare il motore con un assistente AI (Claude Code): l'assistente raccoglie le prove, il motore calcola l'esito. |
| `tests/` | 385 test automatici. |

Il motore esiste in due versioni, Python e JavaScript. Una serie di **test di parità** dà gli stessi casi a entrambe e verifica che producano lo stesso risultato: una correzione fatta da una parte sola fa fallire i test.

Nel repository non ci sono verifiche svolte su bot reali: i nomi usati nei test sono campioni costruiti per le prove.

## Eseguire i test e rigenerare l'app

Servono Python (provato con 3.13), `pytest` e Node.js (provato con la versione 24) per i test della parte JavaScript.

```
python -m pytest -q
python -I costruisci_app.py --numero-test 385
```

Le tarature si fanno nel motore Python e si riportano in quello JavaScript: i test di parità lo impongono.

## Come è nato, e chi l'ha fatto

Mi chiamo Francesco Guerra. Lavoro tra marketing, automazione e adozione dell'intelligenza artificiale, e non sono uno sviluppatore di professione.

Questo progetto risponde a un problema concreto: capire quanto fidarsi di un bot Telegram prima di usarlo. L'ho ideato, ne ho definito regole, limiti e parole, ho preso le decisioni di taratura e l'ho collaudato a mano. Il codice è stato scritto con l'assistenza di un'intelligenza artificiale (Claude, di Anthropic), che ho diretto passo dopo passo. Durante l'uso dell'app, invece, non interviene alcuna AI.

Lo pubblico per due ragioni: può essere utile ad altri, e mostra il modo in cui lavoro. Parto da un problema concreto, mi documento, fisso regole verificabili, faccio scrivere i test prima del codice e dichiaro i limiti di ciò che ho costruito. È un progetto piccolo e migliorabile, fatto con cura.

[LinkedIn](https://www.linkedin.com/in/frguerra/) · [GitHub](https://github.com/frank-85)

## Segnalazioni

Hai trovato un errore, un falso allarme o una truffa che lo strumento non riconosce? Apri una [Issue](https://github.com/frank-85/verifica-bot-telegram/issues). Per favore non pubblicare dati personali, tuoi o di altri.

## Avvertenze

Questo strumento è stato realizzato con cura, con il solo scopo di aiutare chi lo usa a orientarsi, ma non può offrire garanzie assolute. Non sostituisce le verifiche delle autorità né il parere di un professionista. Se pensi di essere stato vittima di una truffa, rivolgiti alla polizia o all'autorità competente del tuo paese. Non condividere mai seed phrase, codici o password, e non inviare denaro per «sbloccare» un prelievo.

Telegram, Anthropic e i titolari dei marchi citati non sono coinvolti nel progetto, non lo approvano e non ne sono responsabili. I marchi presenti in `marchi.txt` appartengono ai rispettivi titolari e sono elencati al solo scopo di riconoscerne le imitazioni.

## Licenza

[MIT](LICENSE). Il software è fornito così com'è, senza garanzie di alcun tipo.
