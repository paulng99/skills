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

## Pipeline

PowerShell cannot use `&&`. Run steps separately.

1. Download the original-language video with `yt-dlp` at 720p plus the original audio, merged to mp4. A 10-minute 720p file stays under a typical upload limit; this free path does not upload it.
2. YouTube timedtext often returns an empty body. Transcribe the extracted 16 kHz mono wav locally with `faster-whisper` `small.en`. PyAV 19 rejects `metadata_errors`. Before `transcribe`, replace `av.open` with a wrapper that drops that keyword.
3. Group the transcript into windows of about 9 seconds. Translate those windows twice: a spoken line and, separately, the written sentence or sentences.
4. Synthesize, fit, and mix the spoken clips into one wav. Replace the original audio.
5. Burn the written SRT. Deliver the mp4 path and say that the voice is a standard Cantonese voice, not the original speaker, and that the mouth does not move with the new speech.

## Check

- Play two spots: the opening and a later teaching line.
- The soundtrack is colloquial Cantonese.
- The burned text is written Chinese and each caption is a complete sentence.
- The picture and duration match the source.
