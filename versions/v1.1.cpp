// Breakthrough bot for CodinGame — alpha-beta engine (v1 line).
// Single file. Local-only knobs come from environment variables (unset on CodinGame):
//   BT_OPENING="a2a3 h7h6 ..."  pre-played moves (local referee forces opening diversity)
//   BT_MS / BT_FIRST_MS         time limits per turn in ms (default 100 / 1000)
//   BT_NODES                    fixed node budget per move (deterministic testing)
//   BT_PARAMS="v0,v1,..."       override evaluation parameters
//   BT_PERFT=N                  print perft(N) from the start position and exit
#ifdef __x86_64__
#pragma GCC optimize("O3,inline,omit-frame-pointer,unroll-loops")
#pragma GCC target("avx2,bmi,bmi2,popcnt,lzcnt")
#endif
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
using namespace std;

typedef uint64_t U64;

// Board: bit = rank*8 + file, a1 = bit 0. Inside the search the side to move always
// moves "up" (towards rank 8): after each move the board is flipped vertically and the
// two bitboards are swapped, so there is a single code path and no colour anywhere.
static const U64 FILE_A = 0x0101010101010101ULL, FILE_H = 0x8080808080808080ULL;
static const U64 R2 = 0xFFULL << 8, R3 = 0xFFULL << 16, R6 = 0xFFULL << 40,
                 R7 = 0xFFULL << 48;

static inline U64 flip(U64 x) { return __builtin_bswap64(x); }
static inline U64 attUp(U64 p) { return ((p << 7) & ~FILE_H) | ((p << 9) & ~FILE_A); }
static inline U64 attDn(U64 p) { return ((p >> 7) & ~FILE_A) | ((p >> 9) & ~FILE_H); }
static inline int pop(U64 x) { return __builtin_popcountll(x); }
static inline int lsb(U64 x) { return __builtin_ctzll(x); }

#ifndef ASP
#define ASP 30
#endif
#ifndef RFP
#define RFP 60
#endif
#ifndef NMP
#define NMP 0
#endif
#ifndef FUT
#define FUT 60
#endif
#ifndef RACE
#define RACE 0
#endif
#ifndef LMR_DIV
#define LMR_DIV 1.8
#endif
static const int WIN = 30000, MATE_BOUND = 29000, INF = 32000, MAXPLY = 96;

// ---- evaluation parameters -------------------------------------------------------
// P[0..6]: value of a pawn on rank index 0 (home row) .. 6; P[7]: supported bonus;
// P[8]: hanging (attacked and unsupported) penalty.
static int P[16] = {100, 100, 118, 142, 180, 240, 340, 6, 12};
static const int NPARAMS = 9;

static inline int sideScore(U64 me, U64 them) {  // "me" moves up
    int s = 0;
    for (int r = 0; r < 7; r++) s += pop(me & (0xFFULL << (8 * r))) * P[r];
    U64 myAtt = attUp(me), thAtt = attDn(them);
    s += P[7] * pop(me & myAtt);
    s -= P[8] * pop(me & thAtt & ~myAtt);
    return s;
}
static inline int evaluate(U64 own, U64 opp) {
    return sideScore(own, opp) - sideScore(flip(opp), flip(own));
}

// ---- move generation ---------------------------------------------------------------
// Move = from | to << 6.
static inline int genMoves(U64 own, U64 opp, uint16_t* mv) {
    int n = 0;
    U64 s = (own << 8) & ~(own | opp);
    while (s) { int t = lsb(s); s &= s - 1; mv[n++] = (uint16_t)((t - 8) | (t << 6)); }
    U64 l = (own << 7) & ~FILE_H & ~own;
    while (l) { int t = lsb(l); l &= l - 1; mv[n++] = (uint16_t)((t - 7) | (t << 6)); }
    U64 r = (own << 9) & ~FILE_A & ~own;
    while (r) { int t = lsb(r); r &= r - 1; mv[n++] = (uint16_t)((t - 9) | (t << 6)); }
    return n;
}
static inline int genCaptures(U64 own, U64 opp, uint16_t* mv) {
    int n = 0;
    U64 l = (own << 7) & ~FILE_H & opp;
    while (l) { int t = lsb(l); l &= l - 1; mv[n++] = (uint16_t)((t - 7) | (t << 6)); }
    U64 r = (own << 9) & ~FILE_A & opp;
    while (r) { int t = lsb(r); r &= r - 1; mv[n++] = (uint16_t)((t - 9) | (t << 6)); }
    return n;
}

// Side to move has a move onto rank 7 that cannot be captured (wins in 2 own moves,
// provided the opponent has no pawn one step from our home row).
static inline bool safe7(U64 own, U64 opp) {
    U64 p = own & R6;
    if (!p) return false;
    U64 t = ((p << 8) & ~(own | opp)) | (attUp(p) & ~own);
    return (t & ~attDn(opp)) != 0;
}
// Opponent threatens the same thing against us (it is our move).
static inline bool oppThreat(U64 own, U64 opp) {
    U64 p = opp & R3;
    if (!p) return false;
    U64 t = ((p >> 8) & ~(own | opp)) | (attDn(p) & ~opp);
    return (t & ~attUp(own)) != 0;
}

// Race rule. A pawn whose forward cone holds no enemy pawn can never be attacked or
// blocked, so it needs exactly (rows to go) moves. Returns +d when the side to move wins
// in d own moves (its runner is at least as fast as ANY enemy pawn could possibly be),
// -d when the opponent wins in d moves (its runner is strictly faster than any of our
// pawns could possibly be), 0 when unknown.
static U64 coneUp[64], coneDn[64];
static void initCones() {
    for (int s = 0; s < 64; s++) {
        int r = s >> 3, f = s & 7;
        for (int q = 0; q < 64; q++) {
            int r2 = q >> 3, f2 = q & 7;
            if (r2 > r && abs(f2 - f) <= r2 - r) coneUp[s] |= 1ULL << q;
            if (r2 < r && abs(f2 - f) <= r - r2) coneDn[s] |= 1ULL << q;
        }
    }
}
static inline int race(U64 own, U64 opp) {
    int oMin = lsb(opp) >> 3;
    int mMin = 7 - ((63 - __builtin_clzll(own)) >> 3);
    if (mMin <= oMin) {
        U64 c = own & (~0ULL << (8 * (7 - oMin)));
        while (c) {
            int s = 63 - __builtin_clzll(c);
            c ^= 1ULL << s;
            if (!(coneUp[s] & opp)) return 7 - (s >> 3);
        }
    } else {
        U64 c = opp & ((1ULL << (8 * mMin)) - 1);
        while (c) {
            int s = lsb(c);
            c &= c - 1;
            if (!(coneDn[s] & own)) return -(s >> 3);
        }
    }
    return 0;
}

// ---- transposition table -------------------------------------------------------------
struct TTEntry { U64 key; int16_t score; uint16_t move; uint8_t depth, flag; uint16_t pad; };
static const int TT_BITS = 21;
static TTEntry* tt;
enum { TT_NONE = 0, TT_EXACT = 1, TT_LOWER = 2, TT_UPPER = 3 };

static inline U64 hashPos(U64 a, U64 b) {
    U64 h = a * 0x9E3779B97F4A7C15ULL;
    h ^= h >> 32;
    h += b * 0xC2B2AE3D27D4EB4FULL;
    h ^= h >> 29;
    h *= 0xBF58476D1CE4E5B9ULL;
    h ^= h >> 32;
    return h;
}

// ---- search state ----------------------------------------------------------------------
static U64 nodes, nodeLimit;
static bool stopSearch;
static chrono::steady_clock::time_point deadline;
static uint16_t killers[MAXPLY][2];
static int hist[2][64][64];
static uint16_t rootMove;
static int lmr[64][64];

static inline void checkTime() {
    if (nodeLimit) { if (nodes >= nodeLimit) stopSearch = true; return; }
    if ((nodes & 1023) == 0 && chrono::steady_clock::now() >= deadline) stopSearch = true;
}

static int qsearch(U64 own, U64 opp, int alpha, int beta, int ply, int qd) {
    if (!own) return -(WIN - ply);
    if (own & R7) return WIN - ply - 1;
    U64 T = opp & R2;
    if (T) {
        if ((T & (T - 1)) || !(attUp(own) & T)) return -(WIN - ply - 2);
    } else if (safe7(own, opp)) return WIN - ply - 3;
    if (RACE && opp) {
        int rc = race(own, opp);
        if (rc > 0) return WIN - ply - (2 * rc - 1);
        if (rc < 0) return -(WIN - ply + 2 * rc);
    }
    ++nodes;
    checkTime();
    if (stopSearch) return 0;
    if (ply >= MAXPLY - 2) return evaluate(own, opp);

    bool evasion = !T && qd < 2 && oppThreat(own, opp);
    int best = -INF;
    if (!T && !evasion) {
        best = evaluate(own, opp);
        if (best >= beta) return best;
        if (best > alpha) alpha = best;
    }
    uint16_t mv[64];
    int sc[64];
    int n = evasion ? genMoves(own, opp, mv) : genCaptures(own, opp, mv);
    U64 oa = attDn(opp);
    int k = 0;
    for (int i = 0; i < n; i++) {
        int t = mv[i] >> 6;
        U64 tb = 1ULL << t;
        if (T && !(tb & T)) continue;
        int s = (opp & tb) ? 1000 + (7 - (t >> 3)) * 10 + ((oa & tb) ? 0 : 50) : (t >> 3);
        mv[k] = mv[i];
        sc[k++] = s;
    }
    n = k;
    for (int i = 0; i < n; i++) {
        int bi = i;
        for (int j = i + 1; j < n; j++) if (sc[j] > sc[bi]) bi = j;
        swap(mv[i], mv[bi]);
        swap(sc[i], sc[bi]);
        int f = mv[i] & 63, t = mv[i] >> 6;
        U64 no = (own ^ (1ULL << f)) | (1ULL << t), np = opp & ~(1ULL << t);
        int v = -qsearch(flip(np), flip(no), -beta, -alpha, ply + 1, qd + (evasion ? 1 : 0));
        if (stopSearch) return 0;
        if (v > best) {
            best = v;
            if (v > alpha) {
                alpha = v;
                if (v >= beta) break;
            }
        }
    }
    if (best == -INF) return -(WIN - ply - 2);  // only reachable with no legal reply
    return best;
}

static int search(U64 own, U64 opp, int depth, int alpha, int beta, int ply, bool allowNull = true) {
    if (!own) return -(WIN - ply);
    if (own & R7) return WIN - ply - 1;
    U64 T = opp & R2;
    bool forced = false;
    if (T) {
        if (ply > 0 && ((T & (T - 1)) || !(attUp(own) & T))) return -(WIN - ply - 2);
        forced = !(T & (T - 1)) && (attUp(own) & T);
    } else if (ply > 0 && safe7(own, opp)) return WIN - ply - 3;
    if (RACE && ply > 0 && opp) {
        int rc = race(own, opp);
        if (rc > 0) return WIN - ply - (2 * rc - 1);
        if (rc < 0) return -(WIN - ply + 2 * rc);
    }

    if (depth <= 0 && !forced) return qsearch(own, opp, alpha, beta, ply, 0);
    if (depth < 0) depth = 0;
    ++nodes;
    checkTime();
    if (stopSearch) return 0;
    if (ply >= MAXPLY - 2) return evaluate(own, opp);

    bool pv = beta - alpha > 1;
    U64 key = hashPos(own, opp);
    TTEntry* e = &tt[key & ((1ULL << TT_BITS) - 1)];
    uint16_t ttMove = 0;
    if (e->key == key && e->flag != TT_NONE) {
        ttMove = e->move;
        if (ply > 0 && e->depth >= depth && !pv) {
            int s = e->score;
            if (s > MATE_BOUND) s -= ply; else if (s < -MATE_BOUND) s += ply;
            if (e->flag == TT_EXACT) return s;
            if (e->flag == TT_LOWER && s >= beta) return s;
            if (e->flag == TT_UPPER && s <= alpha) return s;
        }
    }
    if (ply == 0 && rootMove) ttMove = rootMove;

    int se = 0;
    bool canPrune = !pv && !forced && ply > 0 && (RFP || NMP || FUT) && !oppThreat(own, opp);
    if (canPrune) {
        se = evaluate(own, opp);
        if (RFP && depth <= 3 && se - RFP * depth >= beta) return se;
        if (NMP && allowNull && depth >= 3 && se >= beta && pop(own) > 3) {
            int R = 2 + depth / 4;
            int v = -search(flip(opp), flip(own), depth - 1 - R, -beta, -beta + 1, ply + 1, false);
            if (stopSearch) return 0;
            if (v >= beta && v < MATE_BOUND) return v;
        }
    }

    uint16_t mv[64];
    int sc[64];
    int n = genMoves(own, opp, mv);
    U64 oa = attDn(opp);
    int k = 0;
    for (int i = 0; i < n; i++) {
        uint16_t m = mv[i];
        int f = m & 63, t = m >> 6;
        U64 tb = 1ULL << t;
        if (forced && !(tb & T)) continue;
        int s;
        bool supported = (attUp(own & ~(1ULL << f)) & tb) != 0;
        if (m == ttMove) s = 1 << 30;
        else if (opp & tb) {
            s = 2000000 + (7 - (t >> 3)) * 10000;
            if (!(oa & tb)) s += 50000; else if (supported) s += 20000;
        } else {
            s = hist[ply & 1][f][t];
            if (m == killers[ply][0]) s += 900000;
            else if (m == killers[ply][1]) s += 800000;
            if ((oa & tb) && !supported) s -= 1000000;
        }
        mv[k] = m;
        sc[k++] = s;
    }
    n = k;

    int best = -INF, origAlpha = alpha;
    uint16_t bestMove = 0;
    int ext = forced ? 1 : 0;
    for (int i = 0; i < n; i++) {
        int bi = i;
        for (int j = i + 1; j < n; j++) if (sc[j] > sc[bi]) bi = j;
        swap(mv[i], mv[bi]);
        swap(sc[i], sc[bi]);
        uint16_t m = mv[i];
        int f = m & 63, t = m >> 6;
        bool capture = (opp >> t) & 1;
        U64 no = (own ^ (1ULL << f)) | (1ULL << t), np = opp & ~(1ULL << t);
        U64 co = flip(np), cp = flip(no);
        int nd = depth - 1 + ext, v;
        if (FUT && canPrune && depth <= 2 && i > 0 && !capture && (t >> 3) < 5 && se + FUT * depth <= alpha) {
            if (best < se) best = se;
            continue;
        }
        if (i == 0) {
            v = -search(co, cp, nd, -beta, -alpha, ply + 1);
        } else {
            int r = 0;
            if (depth >= 3 && i >= 2 && !capture && !forced && sc[i] < 800000) {
                r = lmr[min(depth, 63)][min(i, 63)];
                if (sc[i] < 0) r++;
                if ((t >> 3) >= 5 && sc[i] >= 0) r = 0;
                if (pv && r > 0) r--;
                if (r > nd - 1) r = max(0, nd - 1);
            }
            v = -search(co, cp, nd - r, -alpha - 1, -alpha, ply + 1);
            if (v > alpha && r > 0 && !stopSearch) v = -search(co, cp, nd, -alpha - 1, -alpha, ply + 1);
            if (v > alpha && v < beta && !stopSearch) v = -search(co, cp, nd, -beta, -alpha, ply + 1);
        }
        if (stopSearch) return 0;
        if (v > best) {
            best = v;
            bestMove = m;
            if (v > alpha) {
                alpha = v;
                if (ply == 0) rootMove = m;
                if (v >= beta) {
                    if (!capture) {
                        if (killers[ply][0] != m) { killers[ply][1] = killers[ply][0]; killers[ply][0] = m; }
                        int& h = hist[ply & 1][f][t];
                        h += depth * depth;
                        if (h > 500000) h = 500000;
                    }
                    break;
                }
            }
        }
    }
    if (n == 0) return -(WIN - ply - 2);

    int flag = best >= beta ? TT_LOWER : (best > origAlpha ? TT_EXACT : TT_UPPER);
    if (e->key != key || depth >= e->depth || flag == TT_EXACT) {
        int s = best;
        if (s > MATE_BOUND) s += ply; else if (s < -MATE_BOUND) s -= ply;
        e->key = key;
        e->score = (int16_t)s;
        e->move = bestMove;
        e->depth = (uint8_t)depth;
        e->flag = (uint8_t)flag;
    }
    return best;
}

// ---- perft ------------------------------------------------------------------------------
static U64 perft(U64 own, U64 opp, int d) {
    uint16_t mv[64];
    int n = genMoves(own, opp, mv);
    if (d == 1) return n;
    U64 c = 0;
    for (int i = 0; i < n; i++) {
        int f = mv[i] & 63, t = mv[i] >> 6;
        U64 no = (own ^ (1ULL << f)) | (1ULL << t), np = opp & ~(1ULL << t);
        c += perft(flip(np), flip(no), d - 1);
    }
    return c;
}

// ---- game state / protocol ------------------------------------------------------------------
static U64 W = 0xFFFFULL, B = 0xFFFFULL << 48;
static bool whiteToMove = true;

static void applyMove(const string& s) {
    int f = (s[0] - 'a') + 8 * (s[1] - '1'), t = (s[2] - 'a') + 8 * (s[3] - '1');
    U64 fb = 1ULL << f, tb = 1ULL << t;
    if (whiteToMove) { W = (W ^ fb) | tb; B &= ~tb; }
    else { B = (B ^ fb) | tb; W &= ~tb; }
    whiteToMove = !whiteToMove;
}
static string moveName(uint16_t m) {
    int f = m & 63, t = m >> 6;
    if (!whiteToMove) { f ^= 56; t ^= 56; }
    string s;
    s += char('a' + (f & 7)); s += char('1' + (f >> 3));
    s += char('a' + (t & 7)); s += char('1' + (t >> 3));
    return s;
}

int main() {
    if (const char* p = getenv("BT_PARAMS")) {
        int i = 0;
        for (const char* q = p; *q && i < NPARAMS; i++) {
            P[i] = atoi(q);
            while (*q && *q != ',') q++;
            if (*q) q++;
        }
    }
    if (const char* p = getenv("BT_PERFT")) {
        printf("%llu\n", (unsigned long long)perft(W, B, atoi(p)));
        return 0;
    }
    int turnMs = 100, firstMs = 1000;
    if (const char* p = getenv("BT_MS")) turnMs = atoi(p);
    if (const char* p = getenv("BT_FIRST_MS")) firstMs = atoi(p);
    if (const char* p = getenv("BT_NODES")) nodeLimit = strtoull(p, 0, 10);
    if (const char* p = getenv("BT_OPENING")) {
        string s(p);
        size_t i = 0;
        while (i < s.size()) {
            while (i < s.size() && s[i] == ' ') i++;
            if (i + 4 <= s.size()) applyMove(s.substr(i, 4));
            i += 4;
        }
    }
    initCones();
    tt = (TTEntry*)calloc((size_t)1 << TT_BITS, sizeof(TTEntry));
    for (int d = 1; d < 64; d++)
        for (int i = 1; i < 64; i++) lmr[d][i] = (int)(0.5 + log((double)d) * log((double)i) / LMR_DIV);

    bool first = true;
    string line;
    while (getline(cin, line)) {
        auto start = chrono::steady_clock::now();
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
        int n = 0;
        string tmp;
        getline(cin, tmp);
        n = atoi(tmp.c_str());
        vector<string> legal(n);
        for (int i = 0; i < n; i++) {
            getline(cin, legal[i]);
            while (!legal[i].empty() && (legal[i].back() == '\r' || legal[i].back() == ' ')) legal[i].pop_back();
        }
        if (line != "None" && line.size() >= 4) applyMove(line);

        int budget = first ? firstMs : turnMs;
        int hard = first ? budget * 80 / 100 : budget * 85 / 100;
        int soft = hard * 55 / 100;
        first = false;
        deadline = start + chrono::milliseconds(hard);

        U64 own = whiteToMove ? W : flip(B), opp = whiteToMove ? B : flip(W);
        uint16_t best = 0;
        int bestScore = 0, bestDepth = 0;
        nodes = 0;
        stopSearch = false;
        memset(killers, 0, sizeof(killers));
        for (int a = 0; a < 2; a++)
            for (int f = 0; f < 64; f++)
                for (int t = 0; t < 64; t++) hist[a][f][t] /= 4;

        // Immediate win: a pawn on rank 7 always has a move to rank 8.
        if (own & R7) {
            uint16_t mv[64];
            int k = genMoves(own, opp, mv);
            for (int i = 0; i < k; i++) if ((mv[i] >> 6) >= 56) { best = mv[i]; break; }
            bestScore = WIN - 1;
        } else {
            rootMove = 0;
            for (int d = 1; d < 64; d++) {
                int v;
                if (ASP && d >= 4) {
                    int w = ASP, a = bestScore - w, b = bestScore + w;
                    for (;;) {
                        v = search(own, opp, d, a, b, 0);
                        if (stopSearch) break;
                        if (v <= a) { a = max(-INF, a - w); w *= 3; }
                        else if (v >= b) { b = min(INF, b + w); w *= 3; }
                        else break;
                        if (w > 2000) { a = -INF; b = INF; }
                    }
                } else v = search(own, opp, d, -INF, INF, 0);
                if (rootMove) best = rootMove;
                if (stopSearch) break;
                bestScore = v;
                bestDepth = d;
                if (v > MATE_BOUND || v < -MATE_BOUND) break;
                if (!nodeLimit && chrono::steady_clock::now() - start >= chrono::milliseconds(soft)) break;
            }
        }

        string out = best ? moveName(best) : string();
        bool ok = false;
        for (auto& s : legal) if (s == out) { ok = true; break; }
        char msg[64];
        if (ok) snprintf(msg, sizeof msg, "d%d s%d n%lluk", bestDepth, bestScore, (unsigned long long)(nodes / 1000));
        else { out = n ? legal[0] : "a2a3"; snprintf(msg, sizeof msg, "M:fb"); }
        printf("%s %s\n", out.c_str(), msg);
        fflush(stdout);
        applyMove(out);
    }
    return 0;
}
