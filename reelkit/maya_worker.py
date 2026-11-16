#!/usr/bin/env python3
"""Runs INSIDE the Maya venv (not the reelkit venv): loads Maya 2 once and speaks every line of a job file.

    /Users/madhurwadhwa/local-audio/.venv-maya2/bin/python maya_worker.py job.json

job.json: {"maya_dir", "voice", "lang", "seed", "retries", "result", "items": [{"id", "text", "out"}]}
Writes one 24 kHz mono WAV per item and a result JSON (rewritten after every item, so a crash loses nothing).
Stand-alone on purpose: it imports only maya2_say.py from maya_dir, per MAYA2_RUNBOOK.md.
"""
import json
import sys
import time


def main():
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    sys.path.insert(0, job["maya_dir"])
    import soundfile as sf
    from maya2_say import SR, Maya2, trim_and_peak

    tts = Maya2()
    print(f"[maya] loaded on {tts.dev} in {tts.load_s:.1f}s", flush=True)
    results = []
    try:
        for n, item in enumerate(job["items"], 1):
            t0 = time.perf_counter()
            tries = []
            for attempt in range(job.get("retries", 2) + 1):
                seed = job.get("seed", 0) + item["id"] * 17 + attempt * 101
                wav, info = tts.say(item["text"], job["voice"], job["lang"], seed=seed)
                reasons = [s["reason"] for s in info["stops"]]
                tries.append({"seed": seed, "stops": reasons})
                if all(r.startswith("aeos") for r in reasons):      # anything else = Maya never found the end
                    break
            wav = trim_and_peak(wav)
            sf.write(item["out"], wav, SR, subtype="PCM_16")
            res = {"id": item["id"], "out": item["out"], "audio_s": round(len(wav) / SR, 3),
                   "gen_s": round(time.perf_counter() - t0, 1), "tries": tries,
                   "clean": all(r.startswith("aeos") for r in tries[-1]["stops"])}
            results.append(res)
            json.dump({"load_s": round(tts.load_s, 1), "items": results}, open(job["result"], "w"), indent=1)
            print(f"[maya] {n}/{len(job['items'])} beat {item['id']}: {res['audio_s']}s audio in {res['gen_s']}s "
                  f"stops={tries[-1]['stops']}", flush=True)
    finally:
        tts.close()


if __name__ == "__main__":
    main()
