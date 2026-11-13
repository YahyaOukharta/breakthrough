#!/usr/bin/env python3
"""Train the NNUE-style evaluation for the Breakthrough bot.

Data: 24-byte records written by `BT_GEN` (see runGen in bot.cpp):
  own u64, opp u64 (side-to-move frame, a1 = bit 0), score i16, result i8 (1 = side to
  move won), ply u8, pad u32.
Net:  shared feature transformer 128 -> H for both perspectives, SCReLU, 2H -> 1 logit.
Output file: int16 W[128][H], int16 B[H], int16 O[2][H], int32 OB (QA=255, QB=64), the
exact layout bot.cpp loads with BT_NET / embeds for submission.

The whole data set lives on the GPU as raw bytes (16 per position); bitboards are
unpacked to the 128 inputs there with a 256x8 lookup table, so the CPU does nothing per
batch.

  train.py -o tools/nets/n0.bin data/g0_*.bin [--hidden 256] [--epochs 12] [--lam 0.6]
"""
import argparse, glob, time
import numpy as np
import torch
import torch.nn as nn

REC = np.dtype([("own", "<u8"), ("opp", "<u8"), ("score", "<i2"), ("result", "i1"), ("ply", "u1"), ("flags", "<u4")])
QA, QB = 255, 64


MIRROR = [(i // 64) * 64 + ((i % 64) // 8) * 8 + 7 - (i % 8) for i in range(128)]  # file a <-> h


class Net(nn.Module):
    """sym=True ties hidden units in left-right mirrored pairs: unit j+H/2 has the weights
    of unit j with the files mirrored, and the same output weight, so the evaluation of a
    position and of its mirror image are exactly equal and only half the weights are free."""

    def __init__(self, h, sym=False, buckets=1):
        super().__init__()
        self.h, self.sym, self.nb = h, sym, buckets
        k = h // 2 if sym else h
        self.ft = nn.Linear(128, k)
        self.out = nn.Linear(2 * k, buckets)   # one output head per piece-count bucket
        nn.init.uniform_(self.ft.weight, -0.1, 0.1)
        nn.init.constant_(self.ft.bias, 0.1)
        self.register_buffer("mirror", torch.tensor(MIRROR), persistent=False)

    def full(self):
        """(W [H,128], B [H], O [buckets, 2H]) of the equivalent untied network."""
        w, b, o = self.ft.weight, self.ft.bias, self.out.weight
        if not self.sym:
            return w, b, o
        k = w.shape[0]
        o = o.reshape(self.nb, 2, k)
        return (torch.cat([w, w[:, self.mirror]], 0), torch.cat([b, b]),
                torch.cat([o[:, 0], o[:, 0], o[:, 1], o[:, 1]], dim=1))

    def forward(self, a, b):
        w, bias, o = self.full()
        ha = torch.clamp(a @ w.t() + bias, 0, 1) ** 2
        hb = torch.clamp(b @ w.t() + bias, 0, 1) ** 2
        z = torch.cat([ha, hb], dim=1) @ o.t() + self.out.bias          # (B, buckets)
        if self.nb == 1:
            return z.squeeze(1)
        bk = ((a.sum(1) - 1) * self.nb / 32).floor().clamp(0, self.nb - 1).long()   # pawns on board
        return z.gather(1, bk[:, None]).squeeze(1)


def export(model, path):
    h = model.h
    fw, fb, fo = model.full()
    w = np.round(fw.detach().cpu().numpy().T * QA).astype(np.int16)        # [128][H]
    b = np.round(fb.detach().cpu().numpy() * QA).astype(np.int16)          # [H]
    o = np.round(fo.detach().cpu().numpy().reshape(model.nb, 2, h) * QB).astype(np.int16)
    ob = np.round(model.out.bias.detach().cpu().numpy() * QA * QB).astype(np.int32)
    with open(path, "wb") as f:
        f.write(w.tobytes()); f.write(b.tobytes()); f.write(o.tobytes()); f.write(ob.tobytes())
    return int(np.abs(w).max()), int(np.abs(o).max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=16384)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--lam", type=float, default=1.0, help="weight of game result vs search score")
    ap.add_argument("--k", type=float, default=200.0, help="score scale for sigmoid(score/k)")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else
                    ("mps" if torch.backends.mps.is_available() else "cpu"))
    ap.add_argument("--quiet", action="store_true", help="drop positions whose best move was a capture (flag bit 0)")
    ap.add_argument("--no-side", action="store_true", help="drop positions that come from side games (flag bit 1)")
    ap.add_argument("--dedup", action="store_true", help="merge identical positions, averaging their targets")
    ap.add_argument("--cosine", action="store_true", help="cosine decay to lr/400 instead of one-cycle")
    ap.add_argument("--lam-ply", type=float, default=0.0,
                    help="result weight grows by this much per ply (capped at 1): early moves trust search, late moves the result")
    ap.add_argument("--buckets", type=int, default=1, help="output heads by number of pawns on the board")
    ap.add_argument("--sym", action="store_true", help="tie hidden units in left-right mirrored pairs")
    ap.add_argument("--init", help="float checkpoint (.pt) to continue from")
    a = ap.parse_args()
    t0 = time.time()

    paths = sorted(set(p for f in a.files for p in glob.glob(f, recursive=True)))
    data = np.concatenate([np.fromfile(p, dtype=REC) for p in paths])
    if a.quiet:
        k0 = len(data)
        data = data[(data["flags"] & 1) == 0]
        print(f"quiet filter: {k0} -> {len(data)}", flush=True)
    if a.no_side:
        k0 = len(data)
        data = data[(data["flags"] & 2) == 0]
        print(f"no-side filter: {k0} -> {len(data)}", flush=True)
    np.random.default_rng(1).shuffle(data)
    n = len(data)
    nval = min(200000, n // 20)
    print(f"{n} positions from {len(paths)} files, win rate stm {data['result'].mean():.3f}", flush=True)

    dev = torch.device(a.device)
    # bytes 0..7 = own (rank 1 first), 8..15 = opp; bit i of a byte = file i
    raw = np.empty((n, 16), dtype=np.uint8)
    raw[:, :8] = np.ascontiguousarray(data["own"]).view(np.uint8).reshape(n, 8)
    raw[:, 8:] = np.ascontiguousarray(data["opp"]).view(np.uint8).reshape(n, 8)
    result = data["result"].astype(np.float32)
    target = result
    if a.lam < 1.0 or a.lam_ply > 0:
        sc = np.clip(data["score"].astype(np.float32), -2000, 2000)
        lam = np.minimum(1.0, a.lam + a.lam_ply * data["ply"].astype(np.float32))
        target = (lam * result + (1 - lam) / (1 + np.exp(-sc / a.k))).astype(np.float32)
    del data
    if a.dedup:
        keys = raw.view([("k", "V16")]).reshape(-1)
        _, first, inv, cnt = np.unique(keys, return_index=True, return_inverse=True, return_counts=True)
        del keys
        target = (np.bincount(inv, weights=target) / cnt).astype(np.float32)
        result = (np.bincount(inv, weights=result) / cnt).astype(np.float32)
        raw = raw[first]
        perm0 = np.random.default_rng(2).permutation(len(raw))
        raw, target, result = raw[perm0], target[perm0], result[perm0]
        print(f"dedup: {n} -> {len(raw)} unique positions ({100 * len(raw) / n:.1f}%)", flush=True)
        n = len(raw)
        nval = min(200000, n // 20)
    X = torch.from_numpy(raw).to(dev)
    Y = torch.from_numpy(target).to(dev)
    R = torch.from_numpy(result).to(dev)
    del raw
    table = torch.tensor([[(v >> i) & 1 for i in range(8)] for v in range(256)], dtype=torch.float32, device=dev)

    def feats(xb, mirror):
        bits = table[xb.long()]                       # (B, 16, 8)
        if mirror is not None:                        # left-right mirror augmentation
            bits = torch.where(mirror[:, None, None], bits.flip(2), bits)
        stm = bits.reshape(-1, 128)
        # other side's frame: reversing all 16 bytes flips both boards and swaps them
        oth = bits.flip(1).reshape(-1, 128)
        return stm, oth

    model = Net(a.hidden, a.sym, a.buckets).to(dev)
    if a.init:
        model.load_state_dict(torch.load(a.init, map_location=dev))
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    nb = (n - nval) // a.batch
    if a.cosine:
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs * nb, eta_min=a.lr / 400)
    else:
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.epochs * nb, pct_start=0.05)
    lossf = nn.BCEWithLogitsLoss()

    def evaluate():
        model.eval()
        tot = acc = 0.0
        with torch.no_grad():
            for i in range(0, nval, 65536):
                idx = torch.arange(i, min(i + 65536, nval), device=dev)  # gather, like training
                s, o = feats(X[idx], None)
                y = R[idx]
                z = model(s, o)
                tot += float(lossf(z, y)) * len(y)
                acc += float(((z > 0) == (y > 0.5)).sum())
        model.train()
        return tot / nval, acc / nval

    print(f"loaded in {time.time() - t0:.0f}s, training on {a.device}", flush=True)
    t0 = time.time()
    for ep in range(a.epochs):
        perm = (torch.randperm(n - nval) + nval).to(dev)
        run = torch.zeros((), device=dev)
        for i in range(nb):
            idx = perm[i * a.batch:(i + 1) * a.batch]
            s, o = feats(X[idx], None if a.sym else torch.rand(len(idx), device=dev) < 0.5)
            loss = lossf(model(s, o), Y[idx])
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            with torch.no_grad():
                model.out.weight.clamp_(-1.98, 1.98)
                run += loss.detach()
        vl, va = evaluate()
        print(f"epoch {ep + 1}/{a.epochs} train {float(run) / nb:.4f} val {vl:.4f} acc {va:.4f} ({time.time() - t0:.0f}s)", flush=True)
        torch.save(model.state_dict(), a.out + ".pt")
        mw, mo = export(model, a.out)
    print(f"saved {a.out} (max |W| {mw}, max |O| {mo})")


if __name__ == "__main__":
    main()
