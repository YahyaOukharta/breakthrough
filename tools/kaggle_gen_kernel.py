# Self-play data generation for the Breakthrough bot. Compiles the engine from the
# attached private dataset and runs one generator process per CPU core.
import glob, os, subprocess, time
GAMES, NODES, SEED, NET, HID = 300, 3000, 9000, "n6w.bin", 384   # templated by tools/kaggle_gen.py
NB = 4
src = glob.glob("/kaggle/input/**/bot.cpp", recursive=True)[0]
d = os.path.dirname(src)
t0 = time.time()
subprocess.check_call(["g++", "-O3", "-std=c++17", "-march=native", "-DLOCAL", f"-DNN_H={HID}", "-DNN_B=" + str(globals().get("NB", 1)), "-o", "/kaggle/working/bot", src])
n = os.cpu_count()
print("cpus", n, "compile s", round(time.time() - t0, 1), flush=True)
print(subprocess.run("lscpu | grep -E 'Model name|^CPU\\(s\\)|MHz'; g++ --version | head -1", shell=True, capture_output=True, text=True).stdout, flush=True)
t0 = time.time()
procs = [subprocess.Popen(["/kaggle/working/bot"], env={**os.environ, "BT_NET": f"{d}/{NET}",
         "BT_GEN": f"{GAMES}:{NODES}:{SEED + i}:/kaggle/working/k_{SEED + i}.bin"}) for i in range(n)]
for p in procs:
    p.wait()
os.remove("/kaggle/working/bot")
el = time.time() - t0
pos = sum(os.path.getsize(f) for f in glob.glob("/kaggle/working/k_*.bin")) // 24
print(f"positions {pos} in {el:.0f}s = {pos / el * 60:.0f} per minute", flush=True)
