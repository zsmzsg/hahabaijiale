"""
识别引擎 + 牌堆状态机（从原 PC 版 app.py 原样移植，已用示例图验证 100% 匹配）
- Recognizer: OpenCV 检测牌 + 模板匹配识别点数 (A/2-10/J/Q/K)
- DeckState: 8 副牌 416 张的剩余/对子概率/期望值/建议下注
本模块不依赖 tkinter / mss，可在安卓 (opencv-python) 与桌面同时运行。
"""
import cv2
import numpy as np
from pathlib import Path

RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

# 路径在运行时由 setup_paths() 设置（区分安卓 / 桌面）
TRAIN_IMG = None
PATCH_DIR = None
MODEL = None


def setup_paths(root: Path):
    """设置训练目录、模板目录、模型文件路径。root 为 assets 目录。"""
    global TRAIN_IMG, PATCH_DIR, MODEL
    root = Path(root)
    TRAIN_IMG = root / 'training_images'
    PATCH_DIR = root / 'training_patches'
    MODEL = root / 'rank_templates.npz'
    TRAIN_IMG.mkdir(exist_ok=True)
    PATCH_DIR.mkdir(exist_ok=True)


class DeckState:
    """管理 8 副牌共 416 张牌的剩余状态，每种点数初始 32 张。
    提供对子概率计算：下一手发出两张牌是同一点数的概率。"""

    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        self.initial_total = num_decks * 52
        self.initial_per_rank = num_decks * 4  # 每个点数 8*4 = 32 张
        self.reset()

    def reset(self):
        self.counts = {r: self.initial_per_rank for r in RANKS}
        self.dealt = []  # 记录所有已出牌的顺序

    def remaining_total(self):
        return sum(self.counts.values())

    def deal(self, ranks):
        """把识别出来的牌从牌堆中扣除。返回未能扣除的张数（用于提示）。"""
        miss = 0
        for r in ranks:
            if r in self.counts and self.counts[r] > 0:
                self.counts[r] -= 1
                self.dealt.append(r)
            elif r in self.counts:
                miss += 1
            # 不认识的 '?' 直接忽略
        return miss

    def pair_probability(self):
        """下一手发出两张牌组成对子的总概率。
        P = Σ_rank C(count(rank),2) / C(total,2)"""
        total = self.remaining_total()
        if total < 2:
            return 0.0
        pairs = sum(c * (c - 1) // 2 for c in self.counts.values())
        return pairs / (total * (total - 1) // 2)

    def per_rank_pair_probability(self):
        """每个点数对子概率：P(下一手两张都是该点数)。"""
        total = self.remaining_total()
        if total < 2:
            return {r: 0.0 for r in RANKS}
        return {r: (c * (c - 1)) / (total * (total - 1)) for r, c in self.counts.items()}

    def snapshot(self):
        """返回用于界面显示的快照：剩余张数表与概率表。"""
        total = self.remaining_total()
        per_rank = self.per_rank_pair_probability()
        rows = [(r, self.counts[r], per_rank[r]) for r in RANKS]
        return total, self.pair_probability(), rows

    def expected_value(self, odds=11):
        """期望值 EV：每次下注 1 元的期望回报率。庄对/闲对赔率 11:1。
        EV = (b+1) * p - 1 = 12p - 1"""
        p = self.pair_probability()
        if self.remaining_total() < 2:
            return 0.0
        return (odds + 1) * p - 1

    def suggested_bet(self, bankroll=10000, odds=11):
        """建议下注金额（启发式：-bankroll × p × |EV|）。非负表示可下注。"""
        p = self.pair_probability()
        if self.remaining_total() < 2:
            return 0.0
        ev = self.expected_value(odds)
        return -bankroll * p * abs(ev)

    def undo(self, n=1):
        """撤销最后 n 张出牌（从 dealt 列表末尾弹出，把对应的 count 加回）。"""
        n = max(0, n)
        actual = 0
        while actual < n and self.dealt:
            r = self.dealt.pop()
            self.counts[r] += 1
            actual += 1
        return actual


class Recognizer:
    def __init__(self):
        self.templates = {}
        self.load()

    def load(self):
        if MODEL is not None and MODEL.exists():
            d = np.load(MODEL, allow_pickle=False)
            self.templates = {k: d[k] for k in d.files}

    def detect(self, img):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        m = cv2.inRange(hsv, np.array([0, 0, 175], np.uint8), np.array([180, 110, 255], np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        H, W = img.shape[:2]
        boxes = []
        for c in cs:
            x, y, w, h = cv2.boundingRect(c)
            area = w * h
            ratio = max(w, h) / max(1, min(w, h))
            if 900 < area < W * H * .45 and 1.12 <= ratio <= 2.05 and m[y:y + h, x:x + w].mean() > 18:
                boxes.append((x, y, w, h))
        boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
        keep = []
        for b in boxes:
            x, y, w, h = b
            if not any((max(x, a[0]) < min(x + w, a[0] + a[2]) and
                        max(y, a[1]) < min(y + h, a[1] + a[3]) and
                        min(w, h) / max(w, h) > 0.7) for a in keep):
                keep.append(b)
        return sorted(keep, key=lambda b: (b[0], b[1]))

    def card_patch(self, card):
        h, w = card.shape[:2]
        if w > h:
            card = cv2.rotate(card, cv2.ROTATE_90_CLOCKWISE)
            h, w = card.shape[:2]
        roi = card[int(h * .015):int(h * .48), int(w * .015):int(w * .56)]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        red = ((hsv[:, :, 0] < 18) | (hsv[:, :, 0] > 160)) & (hsv[:, :, 1] > 45) & (hsv[:, :, 2] > 55)
        ink = (gray < 165) | red
        m = (ink.astype(np.uint8) * 255)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
        clean = np.zeros_like(m)
        for i in range(1, n):
            x, y, ww, hh, aa = stats[i]
            if aa >= 3:
                clean[lab == i] = 255
        ys, xs = np.where(clean > 0)
        if len(xs) < 8:
            return None
        x1, x2 = max(0, xs.min() - 2), min(clean.shape[1], xs.max() + 3)
        y1, y2 = max(0, ys.min() - 2), min(clean.shape[0], ys.max() + 3)
        return cv2.resize(clean[y1:y2, x1:x2], (64, 80), interpolation=cv2.INTER_AREA)

    def score(self, a, b):
        aa = a > 100
        bb = b > 100
        iou = np.logical_and(aa, bb).sum() / (np.logical_or(aa, bb).sum() + 1)
        c = float(cv2.matchTemplate(a.astype(np.float32), b.astype(np.float32), cv2.TM_CCOEFF_NORMED)[0, 0])
        return .72 * iou + .28 * ((c + 1) / 2)

    def classify(self, card):
        p = self.card_patch(card)
        if p is None or not self.templates:
            return '?', 0
        scores = {r: max(self.score(p, t) for t in ts) for r, ts in self.templates.items()}
        best = sorted(scores.items(), key=lambda z: z[1], reverse=True)
        r, s = best[0]
        margin = s - (best[1][1] if len(best) > 1 else 0)
        ok = s >= .56 and (len(best) == 1 or margin >= .018)
        return (r, s) if ok else ('?', s)

    def recognize(self, img):
        res = []
        for b in self.detect(img):
            x, y, w, h = b
            r, s = self.classify(img[y:y + h, x:x + w])
            res.append((r, s, b))
        return res

    def rebuild(self):
        collected = {}
        for r in RANKS:
            d = PATCH_DIR / r
            if d.exists():
                for p in d.iterdir():
                    if p.suffix.lower() == '.png':
                        q = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
                        if q is not None:
                            collected.setdefault(r, []).append(q)
        if not collected:
            raise RuntimeError('还没有训练样本。请先标注训练图片。')
        np.savez_compressed(MODEL, **{r: np.stack(v) for r, v in collected.items()})
        self.templates = {r: np.stack(v) for r, v in collected.items()}
        return {r: len(v) for r, v in collected.items()}


def visualize(img, res):
    """在图上画框 + 点数，返回副本（用于预览）。"""
    vis = img.copy()
    for r, s, (x, y, w, h) in res:
        cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(vis, r, (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, .75, (0, 0, 255), 2)
    return vis
