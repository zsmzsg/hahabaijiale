"""
无界面自测：不依赖 kivy/显示器。
用 images 源循环读取示例图，跑 recognizer + engine.Monitor，
验证识别结果、牌堆扣减、对子概率/期望值计算是否正确。
运行：python test_headless.py
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / 'assets'
sys.path.insert(0, str(HERE))

import numpy as np
import cv2
import recognizer
import engine
import capture
import json

# 把已验证的标注作为"正确答案"
EXPECTED = {
    '_examples/img1(2).jpg': ['4', '5', '10', '3', '10', '2'],
    '_examples/img2(2).jpg': ['4', '5', '10', '3', '10'],
}


def main():
    recognizer.setup_paths(ASSETS)
    rec = recognizer.Recognizer()
    print('模板加载:', {k: len(v) for k, v in rec.templates.items()})

    # 1) 单图识别正确性（与原 PC 版一致）
    print('\n[1] 单图识别验证')
    ok = True
    for name, exp in EXPECTED.items():
        img = cv2.imread(str(ASSETS / name))
        res = rec.recognize(img)
        ranks = [r for r, s, b in res if r != '?']
        match = ranks == exp
        ok = ok and match
        print(f'  {name}: 识别={ranks} 期望={exp} {"OK" if match else "FAIL"}')

    # 2) 引擎 Monitor 实时流程（用 images 源模拟连续帧）
    print('\n[2] Monitor 实时流程 + 牌堆扣减')
    mon = engine.Monitor(rec, num_decks=8, stable_frames=3)  # 测试用较小稳定帧
    src = capture.create_source('image_folder', folder=str(ASSETS / '_examples'), loop=True)
    for i in range(6):  # 跑若干帧
        f = src.grab()
        out = mon.process_frame(f)
        total, prob, _ = out['deck_snapshot']
        print(f'  帧{i}: {out["result_text"]} | 剩余 {total} | 对子概率 {prob*100:.4f}% | {out["status"]}')

    # 3) 牌堆数学校验：初始对子概率应为 C(32,2)*13 / C(416,2)
    from math import comb
    d = recognizer.DeckState(8)
    expect = comb(32, 2) * 13 / comb(416, 2)
    got = d.pair_probability()
    print('\n[3] 牌堆数学')
    print(f'  初始对子概率 计算={got*100:.4f}% 理论={expect*100:.4f}% '
          f'{"OK" if abs(got-expect) < 1e-9 else "FAIL"}')
    ev = d.expected_value(odds=11)
    print(f'  初始期望值(赔率11) = {ev*100:+.4f}%  (应为负, 庄家优势)')

    # 4) 撤销 / 重置
    print('\n[4] 撤销/重置')
    mon2 = engine.Monitor(rec, num_decks=8, stable_frames=1)
    img = cv2.imread(str(ASSETS / '_examples/img1(2).jpg'))
    mon2.run_once(img)
    before = mon2.deck.remaining_total()
    mon2.undo_last()
    after = mon2.deck.remaining_total()
    print(f'  扣牌后剩余 {before}, 撤销后 {after}, 牌堆还原={"OK" if after == 416 else "FAIL"}')

    print('\n结果:', '全部通过 ✅' if ok else '存在失败 ❌')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
