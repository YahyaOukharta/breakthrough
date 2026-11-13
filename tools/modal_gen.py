"""Self-play data generation on Modal.

  modal run tools/modal_gen.py --workers 1 --cpu 4 --games 300 --seed 50000 --net tools/nets/n6w.bin --hid 384 --tag test
Each worker is one container with `cpu` cores; it compiles the engine and runs one
generator process per available hardware thread. Output goes to the Modal volume
"bt-data" under /<tag>/; download with:  modal volume get bt-data /<tag> data_modal/
"""
import os
import modal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NET = os.environ.get("BT_MODAL_NET", "tools/nets/n6w.bin")
app = modal.App("bt-gen")
image = (modal.Image.debian_slim().apt_install("g++")
         .add_local_file(os.path.join(ROOT, "bot.cpp"), "/src/bot.cpp")
         .add_local_file(os.path.join(ROOT, NET), "/src/net.bin"))
vol = modal.Volume.from_name("bt-data", create_if_missing=True)


@app.function(image=image, cpu=8, memory=4096, timeout=4 * 3600, volumes={"/out": vol})
def gen(seed: int, games: int, nodes: int, hid: int, tag: str, nb: int = 1):
    import glob, subprocess, time
    subprocess.check_call(["g++", "-O3", "-std=c++17", "-march=native", "-DLOCAL", f"-DNN_H={hid}", f"-DNN_B={nb}", "-o", "/tmp/bot", "/src/bot.cpp"])
    n = len(os.sched_getaffinity(0))
    os.makedirs(f"/out/{tag}", exist_ok=True)
    t0 = time.time()
    # Generators append straight to the volume; a background commit every 90 s means a
    # container that is stopped early (spend cap, preemption) loses at most 90 s of data.
    procs = [subprocess.Popen(["/tmp/bot"], env={**os.environ, "BT_NET": "/src/net.bin",
             "BT_GEN": f"{games}:{nodes}:{seed + i}:/out/{tag}/m_{seed + i}.bin"}) for i in range(n)]
    last = time.time()
    while any(p.poll() is None for p in procs):
        time.sleep(5)
        if time.time() - last > 90:
            vol.commit()
            last = time.time()
    el = time.time() - t0
    pos = sum(os.path.getsize(f) // 24 for f in glob.glob(f"/out/{tag}/m_*.bin") if int(f.rsplit("_", 1)[1][:-4]) // 100 == seed // 100)
    vol.commit()
    cpu = subprocess.run("grep -m1 'model name' /proc/cpuinfo", shell=True, capture_output=True, text=True).stdout.strip()
    return {"seed": seed, "threads": n, "positions": pos, "seconds": round(el), "per_min": round(pos / el * 60), "cpu": cpu}


@app.local_entrypoint()
def main(workers: int = 1, games: int = 300, nodes: int = 3000, seed: int = 50000, hid: int = 384, tag: str = "test", nb: int = 1):
    args = [(seed + 100 * w, games, nodes, hid, tag, nb) for w in range(workers)]
    tot = 0
    for r in gen.starmap(args, return_exceptions=True):
        print(r, flush=True)
        if isinstance(r, dict):
            tot += r["positions"]
    print("total positions", tot)
