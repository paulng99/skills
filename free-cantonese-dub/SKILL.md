---
name: free-cantonese-dub
description: >-
  Dub a YouTube video into spoken Hong Kong Cantonese for free, and burn
  Traditional Chinese subtitles written as complete sentences. Use when the
  user asks to convert, translate, or dub a YouTube video into 廣東話 or
  Cantonese, especially with 免費, 口語, 字幕, or 完整句子.
---

# Free Cantonese dub

Two texts, never one. The user's rule, verbatim:

字幕用完整句子, 不是用口語, 但廣東話用口語.

Spoken audio is colloquial Cantonese. Subtitles are written Traditional Chinese, and each caption is one or more complete sentences. Do not copy the spoken lines onto the subtitles.

When the user asks for a free method, do not call fal, HeyGen, VEED, or any other paid dubbing or lip-sync model. Do not clone the original voice. Do not change the picture except to burn subtitles. There is no lip sync on this path.

## Speech

Write colloquial Hong Kong Cantonese for the voice: 咗、嘅、喺、嗰、呢、唔、冇、佢、咁. Keep names, product names, and golf or technical terms that Hong Kong speakers say in English (`Swing Clutch`, `lag`).

Fit each spoken line to the source speech window. Use `edge-tts` voice `zh-HK-WanLungNeural` for a male presenter and `zh-HK-HiuMaanNeural` for a female presenter, rate about `+12%`. Place each clip at the source start time. If it overruns the gap before the next line, speed it with `atempo`, capped at 1.55. Leave the demonstration pauses silent.

## Subtitles

Rewrite the same meaning in written Chinese. Each caption must end with `。`, `？`, or `！`. Do not end a caption on a comma or a spoken fragment.

Use written words, not the spoken ones:

| Spoken | Subtitle |
| --- | --- |
| 嘅 / 咗 / 喺 / 嗰 | 的 / 了 / 在 / 那 |
| 呢個 / 咁 / 咩 | 這個 / 這樣 / 什麼 |
| 唔 / 冇 / 佢哋 | 不 / 沒有 / 他們 |
| 我就想同你分享呢個概念。 | 我想與你分享這個概念。 |

A caption may cover several spoken clips when they form one sentence. Split a long caption into separate complete sentences, and divide that time window by character count. Keep a line short enough for two rows on a 1280-wide frame. Burn with `Microsoft JhengHei`. Dates, if any, use `yyyy-mm-dd`.

## Program

The program is [scripts/dub.py](scripts/dub.py). Run that file. Do not write a new one-off script for each video. Install its dependencies once from [requirements.txt](requirements.txt):

```
python -m pip install -r requirements.txt
```

PowerShell cannot use `&&`. Run each command separately. `WORK` is an empty working directory.

```
python scripts/dub.py download URL --workdir WORK
python scripts/dub.py transcribe --workdir WORK --language en
python scripts/dub.py group --workdir WORK
```

`download` saves a 720p mp4 and a 16 kHz wav. YouTube captions are often empty, so `transcribe` uses local Whisper. `group` writes `chunks.json`, windows of about 9 seconds.

Write `cues.json` from those windows. Each item has both texts:

```json
{"start": 0.05, "end": 8.25, "spoken": "口語", "written": "完整句子。"}
```

`end` is the end of that window, usually the next item's `start`. `written` is one or more complete sentences. Then render:

```
python scripts/dub.py render --workdir WORK --cues cues.json --out OUT.mp4
```

The default voice is `zh-HK-WanLungNeural`. For a female presenter pass `--voice zh-HK-HiuMaanNeural`. Deliver the mp4 path and say that the voice is a standard Cantonese voice, not the original speaker, and that the mouth does not move with the new speech.

## Check

- Play two spots: the opening and a later teaching line.
- The soundtrack is colloquial Cantonese.
- The burned text is written Chinese and each caption is a complete sentence.
- The picture and duration match the source.
