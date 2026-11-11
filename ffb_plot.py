"""回看 ffb_view.py 记录的 CSV：单张 FFB 曲线（-1 ~ 1），并判断是否削峰。

削峰在曲线上就是顶部/底部贴到 ±1 变成平顶。脚本会算出贴顶占比、
最长平顶时长，并把贴顶段用红色阴影标出来。

用法:
    python ffb_plot.py                    打开 logs 里最新的 CSV
    python ffb_plot.py --csv 某个.csv
    python ffb_plot.py --csv 文件.csv --out out.png   # 只出图不开窗口
"""

import argparse
import glob
import os
import sys

import numpy as np


def load(path):
    return np.genfromtxt(path, delimiter=',', names=True, dtype=float)


def latest_log():
    logs = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'ffb_*.csv'))
    if not logs:
        return None
    return max(logs, key=os.path.getmtime)


def spans_of(t, mask):
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append((float(t[i]), float(t[j])))
            i = j + 1
        else:
            i += 1
    return out


def clipping_report(t, ffb):
    if len(ffb) < 5:
        return None
    peak = float(np.max(np.abs(ffb)))
    if peak <= 0:
        return None
    thr = 0.995 * peak
    mask = np.abs(ffb) >= thr
    spans = spans_of(t, mask)
    over_mask = np.abs(ffb) > 1.0
    over_spans = spans_of(t, over_mask)
    return {
        'peak': peak,
        'thr': thr,
        'frac': float(mask.mean()),
        'count': len(spans),
        'longest': max((b - a for a, b in spans), default=0.0),
        'duration': float(t[-1] - t[0]),
        'spans': spans,
        'over_frac': float(over_mask.mean()),
        'over_count': len(over_spans),
        'over_longest': max((b - a for a, b in over_spans), default=0.0),
        'p99': float(np.percentile(np.abs(ffb), 99)),
    }


def verdict(r):
    if r is None:
        return '样本太少，无法判断。'
    if r['frac'] < 0.002 and r['longest'] < 0.10:
        return '没有出现平顶，游戏侧没有把信号截断。'
    if r['frac'] < 0.01 and r['longest'] < 0.25:
        return '偶尔贴顶。'
    return '顶部反复压平：信号被截断，削峰明显。'


def main():
    p = argparse.ArgumentParser(description='回看 ACC FFB 记录并判断削峰')
    p.add_argument('--csv', default='', help='CSV 文件路径')
    p.add_argument('--out', default='', help='保存图片路径（不弹窗口）')
    args = p.parse_args()

    path = args.csv or latest_log()
    if not path or not os.path.isfile(path):
        print('找不到 CSV，请先用 ffb_view.py 记录。')
        return 1
    d = load(path)
    t, ffb = d['t'], d['ffb']
    r = clipping_report(t, ffb)

    print('文件:', path)
    print('样本 %d，时长 %.1f s，finalFF 范围 %.3f ~ %.3f'
          % (len(t), float(t[-1] - t[0]), float(np.min(ffb)), float(np.max(ffb))))
    if r:
        print('99%% 分位 |finalFF| = %.3f' % r['p99'])
        print('贴顶样本 %.2f%%（约 %.2f s），贴顶段 %d 段，最长 %.3f s'
              % (100 * r['frac'], r['frac'] * r['duration'], r['count'], r['longest']))
        print('超过 1.0 的时间 %.2f%%，%d 段，最长 %.3f s（1.0 不是绝对满量程，仅供参考）'
              % (100 * r['over_frac'], r['over_count'], r['over_longest']))
    print('判断:', verdict(r))

    import matplotlib
    if args.out:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False

    peak = r['peak'] if r else 1.0
    lim = max(1.0, 0.5 * float(np.ceil(peak * 1.05 / 0.5)))
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(t, ffb, lw=1.0, color='#1f77b4')
    ax.set_ylim(-lim, lim)
    ax.set_xlim(float(t[0]), float(t[-1]))
    ax.axhline(1.0, color='#d62728', ls='--', lw=.8)
    ax.axhline(-1.0, color='#d62728', ls='--', lw=.8)
    ax.axhline(0.0, color='#bbbbbb', lw=.6)
    ax.set_ylabel('finalFF')
    ax.set_xlabel('time (s)')
    ax.grid(True, alpha=.3)
    ax.set_title('%s   |   peak %.2f   |   %s' % (os.path.basename(path), peak, verdict(r)))
    fig.tight_layout()

    if args.out:
        fig.savefig(args.out, dpi=110)
        print('已保存:', args.out)
    else:
        plt.show()
    return 0


if __name__ == '__main__':
    sys.exit(main())
