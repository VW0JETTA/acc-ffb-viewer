"""ACC 力反馈（FFB）实时曲线：单张图，纵轴固定 -1 ~ 1，用来看是否削峰。

曲线在 ±1 处变成平顶 = 削峰（游戏侧 FFB 已经到上限）。
ACC 的 MoTeC 录制文件里没有 FFB，只有游戏运行时共享内存里有 finalFF，
所以这个工具必须开着 ACC 跑才有数据；默认顺手把原始数据记成 CSV。

用法:
    python ffb_view.py                    实时曲线 + 自动记录 CSV
    python ffb_view.py --no-log           只看曲线，不记录
    python ffb_view.py --csv-only --hz 200   不画图，只高速记录（分析削峰更准）
    python ffb_view.py --self-test a.png  用假数据生成示例图
"""

import argparse
import csv
import datetime
import os
import sys
import time
from collections import deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

from acc_shm import get_physics  # noqa: E402

HEADER = ['t', 'ffb', 'slip', 'kerb', 'g', 'abs', 'steer', 'speed']


def sample(phys):
    return (
        float(phys.finalFF),
        float(phys.slipVibrations),
        float(phys.kerbVibration),
        float(phys.gVibrations),
        float(phys.absVibrations),
        float(phys.steerAngle),
        float(phys.speedKmh),
    )


def new_log_path(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(log_dir, 'ffb_%s.csv' % stamp)


def open_log(args):
    if args.no_log:
        return None, None, None
    path = args.log or new_log_path(os.path.join(HERE, 'logs'))
    fh = open(path, 'w', newline='', encoding='utf-8')
    w = csv.writer(fh)
    w.writerow(HEADER)
    print('记录到:', path)
    return fh, w, path


def wait_for_physics():
    """阻塞等待 ACC 共享内存出现，返回 physics 对象。"""
    last_msg = 0.0
    while True:
        try:
            return get_physics()
        except Exception:
            now = time.perf_counter()
            if now - last_msg > 2:
                print('等待 ACC 运行 ...（共享内存 acpmf_physics 还没出现）')
                last_msg = now
            time.sleep(0.2)


def run_csv_only(args):
    log_fh, log_w, log_path = open_log(args)
    if log_fh is None:
        print('--csv-only 需要记录，不能同时用 --no-log。')
        return 1
    obj = None
    t0 = time.perf_counter()
    next_t = t0
    peak = 0.0
    n = 0
    last_msg = 0.0
    try:
        while True:
            now = time.perf_counter()
            if args.seconds and now - t0 > args.seconds:
                break
            if obj is None:
                try:
                    obj = get_physics()
                    print('已连接 ACC 共享内存，开始记录（%.0f Hz）。' % args.hz)
                except Exception:
                    if now - last_msg > 2:
                        print('等待 ACC 运行 ...')
                        last_msg = now
                    time.sleep(0.1)
                    continue
            try:
                vals = sample(obj)
            except Exception:
                obj = None
                continue
            t = now - t0
            log_w.writerow(('%.4f' % t,) + tuple('%.5f' % v for v in vals))
            n += 1
            peak = max(peak, abs(vals[0]))
            if now - last_msg > 3:
                print('已记录 %.1f s，%d 样本，峰值 %.3f' % (t, n, peak))
                last_msg = now
            next_t += 1.0 / args.hz
            dt = next_t - time.perf_counter()
            if dt > 0:
                time.sleep(dt)
            else:
                next_t = time.perf_counter()
    except KeyboardInterrupt:
        pass
    finally:
        log_fh.flush()
        log_fh.close()
        print('结束：%d 样本，峰值 %.3f，已保存 %s' % (n, peak, log_path))
    return 0


def run_live(args):
    import matplotlib
    if args.agg:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    log_fh, log_w, log_path = open_log(args)

    plt.ion()
    fig, ax = plt.subplots(figsize=(12, 4.8))
    try:
        fig.canvas.manager.set_window_title('ACC FFB')
    except Exception:
        pass
    fig.subplots_adjust(left=0.07, right=0.99, top=0.93, bottom=0.12)

    ax.set_ylim(-1.0, 1.0)
    ax.set_xlim(0.0, args.window)
    ax.axhline(0.0, color='#bbbbbb', lw=.6)
    ax.set_ylabel('finalFF')
    ax.set_xlabel('time (s)')
    ax.grid(True, alpha=.3)
    ax.set_title('ACC FFB')
    line, = ax.plot([], [], lw=1.0, color='#1f77b4')
    status = ax.text(0.01, 0.97, '', transform=ax.transAxes, va='top', fontsize=9,
                     family='monospace')
    hint = ax.text(0.5, 0.5, 'waiting for ACC ...', transform=ax.transAxes,
                   ha='center', va='center', fontsize=14, color='#999999')

    print('窗口已打开；启动 ACC 后会自动开始画曲线。')
    print('（图形后端: %s）' % matplotlib.get_backend())
    fig.canvas.draw()
    plt.pause(0.05)

    hist = deque(maxlen=int(args.window * args.hz) + 4)
    obj = None
    t0 = time.perf_counter()
    next_t = t0
    last_msg = 0.0
    drew = 0.0
    peak = 0.0
    n_samples = 0
    n_over = 0
    ylim = 1.0

    try:
        while True:
            now = time.perf_counter()
            if args.seconds and now - t0 > args.seconds:
                break
            if obj is None:
                try:
                    obj = get_physics()
                    hint.set_visible(False)
                    print('已连接 ACC 共享内存，开始画曲线。')
                except Exception:
                    if now - last_msg > 2:
                        print('等待 ACC 运行 ...（共享内存 acpmf_physics 还没出现）')
                        last_msg = now
                    if log_fh:
                        log_fh.flush()
                    fig.canvas.draw_idle()
                    plt.pause(0.05)
                    if not plt.fignum_exists(fig.number):
                        break
                    continue
            try:
                vals = sample(obj)
            except Exception:
                obj = None
                continue

            t = now - t0
            hist.append((t,) + vals)
            if log_w:
                log_w.writerow(('%.4f' % t,) + tuple('%.5f' % v for v in vals))
            peak = max(peak, abs(vals[0]))
            n_samples += 1
            if abs(vals[0]) > 1.0:
                n_over += 1

            if now - drew > 1.0 / 30.0:
                drew = now
                arr = np.asarray(hist, dtype=float)
                ts, ffb = arr[:, 0], arr[:, 1]
                line.set_data(ts, ffb)
                ax.set_xlim(max(0.0, ts[-1] - args.window), ts[-1] + 0.05)
                if peak * 1.08 > ylim:
                    ylim = max(1.0, 0.5 * np.ceil(peak * 1.08 / 0.5))
                    ax.set_ylim(-ylim, ylim)
                over = 100.0 * n_over / max(1, n_samples)
                status.set_text('now %+.3f   peak %.3f   >1.0 %.1f%%'
                                % (ffb[-1], peak, over))
                fig.canvas.draw_idle()
                plt.pause(0.001)
                if not plt.fignum_exists(fig.number):
                    break

            next_t += 1.0 / args.hz
            dt = next_t - time.perf_counter()
            if dt > 0:
                time.sleep(dt)
            else:
                next_t = time.perf_counter()
    except KeyboardInterrupt:
        pass
    finally:
        if log_fh:
            log_fh.flush()
            log_fh.close()
            print('已保存:', log_path)
        plt.ioff()
        plt.close(fig)
    return 0


def run_self_test(out_png):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(7)
    t = np.arange(0, 20, 0.01)
    ffb = 1.25 * np.sin(2 * np.pi * 0.42 * t) + 0.18 * np.sin(2 * np.pi * 9.0 * t)
    ffb += rng.normal(0, 0.03, t.size)
    ffb = np.clip(ffb, -1.0, 1.0)  # 削峰：顶部变成平顶

    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(t, ffb, lw=1.0, color='#1f77b4')
    ax.set_ylim(-1.0, 1.0)
    ax.set_xlim(0, 20)
    ax.axhline(0, color='#bbbbbb', lw=.6)
    ax.set_ylabel('finalFF')
    ax.set_xlabel('time (s)')
    ax.grid(True, alpha=.3)
    ax.set_title('ACC FFB  (-1 ~ 1, flat top at +/-1 = clipping)')
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
    print('示例图已保存:', out_png)
    return 0


def main():
    p = argparse.ArgumentParser(description='ACC FFB 实时曲线（-1 ~ 1）')
    p.add_argument('--hz', type=float, default=50.0, help='采样率（默认 50）')
    p.add_argument('--window', type=float, default=10.0, help='窗口秒数（默认 10）')
    p.add_argument('--seconds', type=float, default=0.0, help='采集 N 秒后退出')
    p.add_argument('--log', default='', help='CSV 输出路径')
    p.add_argument('--no-log', action='store_true', help='不写 CSV')
    p.add_argument('--agg', action='store_true', help='无窗口模式（调试）')
    p.add_argument('--csv-only', action='store_true', help='只记录 CSV，不画图')
    p.add_argument('--self-test', default='', help='生成示例图到指定 PNG')
    args = p.parse_args()

    if args.self_test:
        return run_self_test(args.self_test)
    if args.csv_only:
        return run_csv_only(args)
    return run_live(args)


if __name__ == '__main__':
    sys.exit(main())
