"""
平台无关的识别+牌堆编排逻辑（不依赖 kivy / tkinter / mss）。
- Monitor: 实时帧处理。用"稳定帧"机制避免发牌动画误扣、避免重复扣同一手牌。
- run_once: 单张图立刻识别并扣牌（手动模式）。
Kivy 界面只负责调用本模块并把结果画出来。
"""
from collections import Counter
from recognizer import Recognizer, DeckState, RANKS, visualize


class Monitor:
    def __init__(self, recognizer, num_decks=8, stable_frames=8):
        self.rec = recognizer
        self.deck = DeckState(num_decks=num_decks)
        self.STABLE_FRAMES_REQUIRED = stable_frames
        # 待扣状态
        self.pending_sig = None
        self.pending_norm_sig = None
        self.pending_ranks = []
        self.pending_res = []
        self.pending_stable = 0
        # 已扣状态
        self.last_norm_sig = None
        self.last_deal_count = 0
        self.last_recognized = 0
        self.unrecognized = 0

    # ---------- 工具 ----------
    @staticmethod
    def _is_superset(big, small):
        c = Counter(small)
        cb = Counter(big)
        return all(cb[k] >= v for k, v in c.items())

    # ---------- 实时帧处理 ----------
    def process_frame(self, frame):
        """输入一帧 BGR，返回状态字典。会自动在稳定后扣牌。"""
        res = self.rec.recognize(frame)
        ranks = [r for r, s, b in res if r != '?']
        norm_sig = tuple(sorted(ranks))
        self.last_recognized = len(res)
        self.unrecognized = sum(1 for r, _, _ in res if r == '?')

        if norm_sig:
            if norm_sig == self.last_norm_sig:
                # 已经扣过这手牌（动画/位置抖动），不重复扣
                self._reset_pending()
            elif self.pending_norm_sig is None:
                self._set_pending(res, ranks, norm_sig, stable=1)
            elif norm_sig == self.pending_norm_sig:
                self.pending_stable += 1
            elif len(norm_sig) > len(self.pending_norm_sig) and \
                    self._is_superset(norm_sig, self.pending_norm_sig):
                # 发牌中补牌：重置计数
                self._set_pending(res, ranks, norm_sig, stable=1)
            else:
                # 牌组完全变化 -> 新一手
                self._set_pending(res, ranks, norm_sig, stable=1)

            committed = False
            if self.pending_stable >= self.STABLE_FRAMES_REQUIRED and \
                    norm_sig != self.last_norm_sig:
                self._commit()
                committed = True

            if committed:
                status = (f'自动识别（已稳定）：{len(res)} 张牌 — '
                          f'已扣减，剩余 {self.deck.remaining_total()} 张')
            else:
                status = (f'识别到 {len(res)} 张牌（待稳定 '
                          f'{self.pending_stable}/{self.STABLE_FRAMES_REQUIRED}）…')
        else:
            # 无牌：牌已离开桌面，忽略
            if self.pending_norm_sig is not None:
                status = '牌已离开桌面（视为无效，已忽略）'
            else:
                status = '等待下一轮牌……'
            self._reset_pending()
            self.last_norm_sig = None

        return {
            'status': status,
            'ranks': ranks,
            'result_text': ' '.join(ranks) if ranks else '未检测到牌',
            'recognized': self.last_recognized,
            'unrecognized': self.unrecognized,
            'committed': committed,
            'res': res,
            'deck_snapshot': self.deck.snapshot(),
        }

    def _set_pending(self, res, ranks, norm_sig, stable):
        self.pending_sig = res
        self.pending_norm_sig = norm_sig
        self.pending_ranks = list(ranks)
        self.pending_res = res
        self.pending_stable = stable

    def _reset_pending(self):
        self.pending_sig = None
        self.pending_norm_sig = None
        self.pending_ranks = []
        self.pending_res = []
        self.pending_stable = 0

    def _commit(self):
        ranks = self.pending_ranks
        miss = self.deck.deal(ranks)
        self.last_norm_sig = self.pending_norm_sig
        self.last_deal_count = len(ranks)
        self._reset_pending()
        return miss

    # ---------- 手动单图模式 ----------
    def run_once(self, frame):
        res = self.rec.recognize(frame)
        ranks = [r for r, s, b in res if r != '?']
        self.last_recognized = len(res)
        self.unrecognized = sum(1 for r, _, _ in res if r == '?')
        self.deck.deal(ranks)
        self.last_norm_sig = tuple(sorted(ranks))
        self.last_deal_count = len(ranks)
        return {
            'res': res,
            'ranks': ranks,
            'result_text': ' '.join(ranks) if ranks else '未检测到牌',
            'deck_snapshot': self.deck.snapshot(),
        }

    # ---------- 控制 ----------
    def undo_last(self):
        if self.last_deal_count <= 0:
            return 0
        n = self.deck.undo(self.last_deal_count)
        self.last_deal_count = 0
        self.last_norm_sig = None
        return n

    def reset_deck(self):
        self.deck.reset()
        self.last_deal_count = 0
        self.last_norm_sig = None
        self._reset_pending()
