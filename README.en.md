# Verifica Bot

**A traffic light that helps you decide how far to trust a Telegram bot or Mini App.**

[🇮🇹 Italiano](README.md) · 🇬🇧 English

Telegram bots that imitate well-known brands, promise earnings, or ask for a deposit "to unlock your withdrawal" are increasingly common. Verifica Bot ("Bot Check") helps you spot the warning signs before you tap. It collects clues, weighs them with public rules, and returns a 🟢 🟡 🔴 result with the reasons behind it and what to do or avoid.

**Try it:** https://frank-85.github.io/verifica-bot-telegram/

The app is currently in Italian. An English version is planned.

> **The result is an indication, not evidence.** It is for guidance only. It is not legal, forensic, or certified technical advice, and it has no legal or evidentiary value. It can be wrong in both directions. Red is not an accusation and green is not a guarantee. Whether to use a bot is always your decision alone.

## What it does

It walks you through a few steps:

1. **The bot's name.** The tool checks whether it imitates a known brand (added, missing, or swapped letters, digits in place of letters) and whether it contains common bait words.
2. **What the bot showed you.** You can paste the text or upload a screenshot. The text is read on your device and compared with a list of typical phrases, such as guaranteed returns, requests for a seed phrase, or withdrawals that require a deposit first.
3. **The Mini App link**, if there is one.
4. **A few simple questions.** "I don't know" is a valid answer.

If an automatic check contradicts one of your answers, the check wins, and the report says so.

You get a report with the result, the risk for each area, the reasons, what could not be verified, and recommended actions. You can print it or download it.

## How it decides

No AI picks the color. A rule engine computes it: the same clues always give the same result, and anyone can read why.

- **37 signals** in a fixed catalog ([`segnali.json`](segnali.json)), each with a score.
- **6 areas**: identity, promises, requests, technical, reputation, transparency. Identity, requests, and technical count double.
- **Thresholds**: up to 30 is green, 31 to 60 is yellow, above 60 is red.
- **10 red lines**: signals serious enough to turn the result red on their own when there is direct proof. One example is a request for your seed phrase or your Telegram login code.
- **Caution rules against false greens**: no green when evidence is thin, and no green when even one area is at maximum risk. A serious danger must not be averaged away.

Every result comes with a **confidence level** that says how solid the evidence was. A self-assessment alone never reaches the highest level.

## Privacy

- The app is **a single HTML file**. It runs in the browser, on phones too, and can be downloaded and opened offline.
- What you type or upload **is not sent to anyone** and is not stored. It is gone when you close the page. No cookies, no analytics, no accounts.
- **One optional connection:** if you upload a screenshot, the browser downloads the open-source library that reads the text ([Tesseract.js](https://github.com/naptha/tesseract.js), from cdn.jsdelivr.net). The image stays on your device. You can paste the text instead.
- A Content-Security-Policy on the page blocks connections to any other address.
- If you use the online version, GitHub Pages receives the technical data of your connection, as any website does. To avoid that, download [`index.html`](index.html) and open it from your device.

## Limits

- The tool only sees what is public or what you show it. Code running on a bot's servers is not visible from outside.
- A new bot with no history cannot get a full green. There is not enough evidence either way.
- The brand list ([`marchi.txt`](marchi.txt)) and the list of recognized phrases are necessarily incomplete.
- Screenshot reading can make mistakes, especially with small images or languages other than Italian and English.
- Checks on received files (command-line version only) use Microsoft Defender, so they work on Windows.

## What is in this repository

| Path | Contents |
|---|---|
| [`index.html`](index.html) | The app, ready to use. It is generated and should not be edited by hand. |
| `app/` | Interface and JavaScript engine, the sources for `index.html`. |
| `punteggio.py`, `nome.py`, `pagina.py`, `rete.py`, `file_check.py`, `resoconto.py` | The Python engine: scoring, name analysis, static page analysis, domain age, file checks, report. |
| `controlli.py` | Command line for the Python engine. |
| `costruisci_app.py` | Builds `index.html` from `app/` and the catalogs. |
| `segnali.json`, `marchi.txt` | Signal catalog and frequently imitated brands. |
| `skill/SKILL.md` | Instructions for using the engine with an AI assistant (Claude Code): the assistant gathers the evidence, the engine computes the result. |
| `tests/` | 385 automated tests. |

The engine exists in two versions, Python and JavaScript. A set of **parity tests** feeds the same cases to both and checks that they return the same result, so a fix applied to only one side makes the tests fail.

The repository contains no checks carried out on real bots. Names used in the tests are samples built for testing.

Code, comments, and file names are in Italian.

## Running the tests and rebuilding the app

You need Python (tested with 3.13), `pytest`, and Node.js (tested with version 24) for the JavaScript tests.

```
python -m pytest -q
python -I costruisci_app.py --numero-test 385
```

Tuning is done in the Python engine and then carried over to the JavaScript one. The parity tests enforce this.

## How it started, and who made it

My name is Francesco Guerra. I work across marketing, automation, and AI adoption, and I am not a software developer by trade.

This project addresses a concrete problem: knowing how far to trust a Telegram bot before using it. I came up with the idea, defined its rules, limits, and wording, made the tuning decisions, and tested it by hand. The code was written with the help of an AI assistant (Claude, by Anthropic), which I directed step by step. No AI runs while you use the app.

I am publishing it for two reasons. It may be useful to others, and it shows how I work: I start from a concrete problem, do the research, set rules that can be checked, have the tests written before the code, and state the limits of what I built. It is a small project with room to improve, made with care.

[LinkedIn](https://www.linkedin.com/in/frguerra/) · [GitHub](https://github.com/frank-85)

## Feedback

Found a mistake, a false alarm, or a scam the tool misses? Open an [Issue](https://github.com/frank-85/verifica-bot-telegram/issues). Please do not post personal data, yours or anyone else's.

## Disclaimer

This tool was built with care, with the sole aim of helping people make better-informed choices, but it cannot offer absolute guarantees. It does not replace checks by the authorities or advice from a professional. If you think you have been the victim of a scam, contact the police or the competent authority in your country. Never share seed phrases, codes, or passwords, and never send money to "unlock" a withdrawal.

Telegram, Anthropic, and the owners of the brands mentioned are not involved in this project, do not endorse it, and are not responsible for it. The brands in `marchi.txt` belong to their respective owners and are listed only to detect imitations of them.

## License

[MIT](LICENSE). The software is provided as is, without warranty of any kind.
