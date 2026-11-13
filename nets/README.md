# Nets

Trained weights in the format `tools/train.py` exports and `tools/pack.py` embeds
(int16, see [docs/nnue.md](../docs/nnue.md)). In training order.

| File | Hidden (`-H`) | Buckets (`-B`) | Used in |
|---|---|---|---|
| `n0.bin` | 256 | 1 | v2.0 |
| `n1.bin` | 256 | 1 | v2.1 |
| `n2.bin` | 256 | 1 | v2.2 |
| `n2w.bin` | 512 | 1 | experiment |
| `n3.bin` | 256 | 1 | v2.3 |
| `n4.bin` | 256 | 1 | experiment |
| `n4b.bin` | 256 | 1 | v2.4 |
| `n4c.bin` | 256 | 1 | experiment |
| `n5.bin` | 256 | 1 | v2.5 |
| `n6a.bin` | 256 | 1 | experiment |
| `n6s.bin` | 256 | 1 | v2.6 |
| `n6w.bin` | 384 | 1 | v2.7 |
| `n7a.bin` | 512 | 1 | experiment |
| `n7s.bin` | 512 | 1 | experiment |
| `n7c.bin` | 384 | 1 | experiment |
| `n8a.bin` | 384 | 1 | experiment |
| `n8b.bin` | 384 | 4 | v2.8, v2.9 |
| `n8c.bin` | 384 | 1 | experiment |
| `n9a.bin` | 384 | 4 | experiment |
| `n9b.bin` | 384 | 4 | experiment |
| `n10a.bin` | 384 | 4 | experiment |
| `n10b.bin` | 384 | 4 | **v3.0** |
| `n11k.bin` | 384 | 8 | 8-bucket test (−17) |
| `n11a.bin` | 512 | 4 | 512 candidate (+33 ± 34 vs v3.0 at 100 ms; too large to embed untied) |

```sh
python3 tools/pack.py -n nets/n10b.bin -H 384 -B 4 -o out/submission.cpp
```
