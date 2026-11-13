// Fast native referee for CodinGame Breakthrough. Mirrors the official Referee.java
// (darkhorse64/CG_Breakthrough): same legal-move order, same I/O protocol, same win rules.
//
// Usage: referee BOT_A BOT_B [-g games] [-j threads] [-t ms] [-f first_ms] [-o open_plies]
//                [-s seed] [-n nodes] [-x grace_ms] [-v]
// Games are played in pairs: each random opening is played twice with colours swapped.
// The opening is handed to both bots through the BT_OPENING environment variable.
// Prints one JSON line per game, then a JSON summary line.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <vector>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
using namespace std;

struct Board {
    char b[8][8];
    int turn = 0;
    Board() {
        for (int r = 0; r < 8; r++)
            for (int c = 0; c < 8; c++) b[r][c] = r < 2 ? 'b' : (r > 5 ? 'w' : '.');
    }
    static string mv(int r, int c, int nr, int nc) {
        string s;
        s += char(c + 'a'); s += char(8 - r + '0'); s += char(nc + 'a'); s += char(8 - nr + '0');
        return s;
    }
    vector<string> moves() const {
        vector<string> out;
        bool p1 = turn % 2 == 0;
        for (int r = 0; r < 8; r++)
            for (int c = 0; c < 8; c++) {
                if (p1 && b[r][c] == 'w') {
                    if (r > 0 && c < 7 && b[r - 1][c + 1] != 'w') out.push_back(mv(r, c, r - 1, c + 1));
                    if (r > 0 && b[r - 1][c] == '.') out.push_back(mv(r, c, r - 1, c));
                    if (r > 0 && c > 0 && b[r - 1][c - 1] != 'w') out.push_back(mv(r, c, r - 1, c - 1));
                } else if (!p1 && b[r][c] == 'b') {
                    if (r < 7 && c < 7 && b[r + 1][c + 1] != 'b') out.push_back(mv(r, c, r + 1, c + 1));
                    if (r < 7 && b[r + 1][c] == '.') out.push_back(mv(r, c, r + 1, c));
                    if (r < 7 && c > 0 && b[r + 1][c - 1] != 'b') out.push_back(mv(r, c, r + 1, c - 1));
                }
            }
        return out;
    }
    void play(const string& m) {
        int r = 8 - (m[1] - '0'), c = m[0] - 'a', nr = 8 - (m[3] - '0'), nc = m[2] - 'a';
        b[nr][nc] = b[r][c];
        b[r][c] = '.';
        turn++;
    }
    bool hasWinner() const {  // called after turn++, for the player who just moved
        if (turn % 2 == 1) {
            for (int c = 0; c < 8; c++) if (b[0][c] == 'w') return true;
            for (int r = 0; r < 8; r++) for (int c = 0; c < 8; c++) if (b[r][c] == 'b') return false;
        } else {
            for (int c = 0; c < 8; c++) if (b[7][c] == 'b') return true;
            for (int r = 0; r < 8; r++) for (int c = 0; c < 8; c++) if (b[r][c] == 'w') return false;
        }
        return true;
    }
};

static mutex forkMutex, outMutex;

struct Bot {
    pid_t pid = -1;
    int in = -1, out = -1;
    string buf;
    bool start(const string& path, const string& opening, int ms, int firstMs, long long nodes, const string& params) {
        lock_guard<mutex> lk(forkMutex);
        int a[2], b[2];
        if (pipe(a) || pipe(b)) return false;
        pid = fork();
        if (pid < 0) return false;
        if (pid == 0) {
            dup2(a[0], 0);
            dup2(b[1], 1);
            int dn = open("/dev/null", O_WRONLY);
            if (dn >= 0) dup2(dn, 2);
            for (int fd = 3; fd < 256; fd++) close(fd);
            setenv("BT_OPENING", opening.c_str(), 1);
            setenv("BT_MS", to_string(ms).c_str(), 1);
            setenv("BT_FIRST_MS", to_string(firstMs).c_str(), 1);
            if (nodes > 0) setenv("BT_NODES", to_string(nodes).c_str(), 1);
            if (!params.empty()) setenv("BT_PARAMS", params.c_str(), 1); else unsetenv("BT_PARAMS");
            execl(path.c_str(), path.c_str(), (char*)0);
            _exit(127);
        }
        close(a[0]);
        close(b[1]);
        in = a[1];
        out = b[0];
        fcntl(in, F_SETFD, FD_CLOEXEC);
        fcntl(out, F_SETFD, FD_CLOEXEC);
        return true;
    }
    bool send(const string& s) {
        size_t off = 0;
        while (off < s.size()) {
            ssize_t w = write(in, s.data() + off, s.size() - off);
            if (w <= 0) return false;
            off += (size_t)w;
        }
        return true;
    }
    // 1 = line read, 0 = timeout, -1 = closed/crashed
    int readLine(string& line, double timeoutMs) {
        auto end = chrono::steady_clock::now() + chrono::microseconds((long long)(timeoutMs * 1000));
        for (;;) {
            size_t p = buf.find('\n');
            if (p != string::npos) {
                line = buf.substr(0, p);
                buf.erase(0, p + 1);
                return 1;
            }
            auto now = chrono::steady_clock::now();
            if (now >= end) return 0;
            int left = (int)chrono::duration_cast<chrono::milliseconds>(end - now).count() + 1;
            pollfd pf{out, POLLIN, 0};
            int pr = poll(&pf, 1, left);
            if (pr == 0) return 0;
            if (pr < 0) continue;
            char tmp[512];
            ssize_t r = read(out, tmp, sizeof tmp);
            if (r <= 0) return -1;
            buf.append(tmp, (size_t)r);
        }
    }
    void stop() {
        if (in >= 0) close(in);
        if (out >= 0) close(out);
        if (pid > 0) { kill(pid, SIGKILL); waitpid(pid, 0, 0); }
        in = out = -1;
        pid = -1;
    }
};

struct Result { int winner; int plies; string reason; double maxMs[2]; };

// white = index (0/1) of the bot playing White.
static string botParams[2];
static long long nodesB = -1;  // optional different node budget for bot B
static Result playGame(const string paths[2], int white, const string& opening, int ms, int firstMs,
                       long long nodes, double grace) {
    Board bd;
    size_t i = 0;
    while (i + 4 <= opening.size()) { bd.play(opening.substr(i, 4)); i += 5; }
    Bot bots[2];
    Result res{-1, 0, "", {0, 0}};
    for (int k = 0; k < 2; k++)
        if (!bots[k].start(paths[k], opening, ms, firstMs, (k == 1 && nodesB >= 0) ? nodesB : nodes, botParams[k])) {
            res.winner = 1 - k; res.reason = "spawn";
            bots[0].stop(); bots[1].stop();
            return res;
        }
    bool firstTurn[2] = {true, true};
    string last = "None";
    while (bd.turn < 209) {
        int who = (bd.turn % 2 == 0) ? white : 1 - white;
        vector<string> legal = bd.moves();
        string msg = last + "\n" + to_string(legal.size()) + "\n";
        for (auto& m : legal) msg += m + "\n";
        double limit = (firstTurn[who] ? firstMs : ms) + grace;
        if (nodes > 0) limit = 60000;
        firstTurn[who] = false;
        auto t0 = chrono::steady_clock::now();
        string line;
        int rc = bots[who].send(msg) ? bots[who].readLine(line, limit) : -1;
        double el = chrono::duration<double, milli>(chrono::steady_clock::now() - t0).count();
        res.maxMs[who] = max(res.maxMs[who], el);
        if (rc != 1) {
            res.winner = 1 - who;
            res.reason = rc == 0 ? "timeout" : "crash";
            if (rc == 0) {  // diagnostic: how late was the answer?
                string late;
                int r2 = bots[who].readLine(late, 3000);
                double el2 = chrono::duration<double, milli>(chrono::steady_clock::now() - t0).count();
                res.reason += r2 == 1 ? " late=" + to_string((int)el2) + "ms out=" + late : " never";
            }
            break;
        }
        string move = line.substr(0, line.find_first_of(" \t\r"));
        if (find(legal.begin(), legal.end(), move) == legal.end()) {
            res.winner = 1 - who; res.reason = "illegal:" + move; break;
        }
        bd.play(move);
        last = move;
        if (bd.hasWinner()) { res.winner = who; res.reason = "win"; break; }
    }
    if (res.winner < 0) { res.winner = -1; res.reason = "maxturns"; }
    res.plies = bd.turn;
    bots[0].stop();
    bots[1].stop();
    return res;
}

int main(int argc, char** argv) {
    signal(SIGPIPE, SIG_IGN);
    if (argc < 3) {
        fprintf(stderr, "usage: referee A B [-g games] [-j threads] [-t ms] [-f first_ms] [-o open_plies] [-s seed] [-n nodes] [-x grace_ms] [-v]\n");
        return 2;
    }
    string paths[2] = {argv[1], argv[2]};
    int games = 100, threads = 4, ms = 50, firstMs = -1, openPlies = 4;
    long long nodes = 0;
    unsigned seed = (unsigned)chrono::system_clock::now().time_since_epoch().count();
    double grace = 15;
    bool verbose = false;
    for (int i = 3; i < argc; i++) {
        string a = argv[i];
        auto next = [&]() { return i + 1 < argc ? argv[++i] : (char*)"0"; };
        if (a == "-g") games = atoi(next());
        else if (a == "-j") threads = atoi(next());
        else if (a == "-t") ms = atoi(next());
        else if (a == "-f") firstMs = atoi(next());
        else if (a == "-o") openPlies = atoi(next());
        else if (a == "-s") seed = (unsigned)strtoul(next(), 0, 10);
        else if (a == "-n") nodes = atoll(next());
        else if (a == "-x") grace = atof(next());
        else if (a == "-v") verbose = true;
        else if (a == "-pa") botParams[0] = next();
        else if (a == "-nb") nodesB = atoll(next());
        else if (a == "-pb") botParams[1] = next();
    }
    if (firstMs < 0) firstMs = ms * 10;

    // Openings: openPlies random legal plies, one opening per pair of games.
    mt19937 rng(seed);
    vector<string> openings((games + 1) / 2);
    for (auto& o : openings) {
        Board bd;
        for (int p = 0; p < openPlies; p++) {
            auto l = bd.moves();
            string m = l[rng() % l.size()];
            if (!o.empty()) o += " ";
            o += m;
            bd.play(m);
        }
    }

    atomic<int> nextGame(0);
    int wins[2] = {0, 0}, whiteWins = 0, faults[2] = {0, 0}, done = 0;
    double maxMs[2] = {0, 0};
    long long totalPlies = 0;
    auto worker = [&]() {
        for (;;) {
            int g = nextGame.fetch_add(1);
            if (g >= games) return;
            int white = g % 2;
            const string& op = openings[g / 2];
            Result r = playGame(paths, white, op, ms, firstMs, nodes, grace);
            lock_guard<mutex> lk(outMutex);
            if (r.winner >= 0) {
                wins[r.winner]++;
                if (r.winner == white) whiteWins++;
                if (r.reason != "win") faults[1 - r.winner]++;
            }
            done++;
            totalPlies += r.plies;
            for (int k = 0; k < 2; k++) maxMs[k] = max(maxMs[k], r.maxMs[k]);
            if (verbose) {
                printf("{\"game\":%d,\"white\":\"%s\",\"winner\":\"%s\",\"plies\":%d,\"reason\":\"%s\",\"opening\":\"%s\"}\n",
                       g, white == 0 ? "A" : "B", r.winner == 0 ? "A" : (r.winner == 1 ? "B" : "-"), r.plies,
                       r.reason.c_str(), op.c_str());
                fflush(stdout);
            }
        }
    };
    vector<thread> pool;
    for (int t = 0; t < threads; t++) pool.emplace_back(worker);
    for (auto& t : pool) t.join();

    printf("{\"summary\":true,\"games\":%d,\"wins_a\":%d,\"wins_b\":%d,\"white_wins\":%d,\"faults_a\":%d,\"faults_b\":%d,"
           "\"avg_plies\":%.1f,\"max_ms_a\":%.1f,\"max_ms_b\":%.1f,\"ms\":%d,\"first_ms\":%d,\"nodes\":%lld,\"seed\":%u}\n",
           done, wins[0], wins[1], whiteWins, faults[0], faults[1], done ? (double)totalPlies / done : 0.0,
           maxMs[0], maxMs[1], ms, firstMs, nodes, seed);
    return 0;
}
