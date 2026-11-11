"""ACC（Assetto Corsa Competizione）共享内存读取。

只实现 physics 页面里画 FFB 曲线需要的字段。结构体布局遵循 Kunos 公布的
ACC shared memory 接口；字段顺序与社区常用的 pyacc 项目一致
(https://github.com/gotzl/pyacc, GPLv3)。
"""

import ctypes
import ctypes.wintypes
import mmap
import sys

PAGE_NAME = 'Local\\acpmf_physics'
MAP_SIZE = 2048  # ACC 实际映射的大小，用于判断共享内存是否存在


class SPageFilePhysics(ctypes.LittleEndianStructure):
    _fields_ = [
        ('packetId', ctypes.c_int),
        ('gas', ctypes.c_float),
        ('brake', ctypes.c_float),
        ('fuel', ctypes.c_float),
        ('gear', ctypes.c_int),
        ('rpms', ctypes.c_int),
        ('steerAngle', ctypes.c_float),
        ('speedKmh', ctypes.c_float),
        ('velocity', ctypes.c_float * 3),
        ('accG', ctypes.c_float * 3),
        ('wheelSlip', ctypes.c_float * 4),
        ('wheelLoad', ctypes.c_float * 4),
        ('wheelsPressure', ctypes.c_float * 4),
        ('wheelAngularSpeed', ctypes.c_float * 4),
        ('tyreWear', ctypes.c_float * 4),
        ('tyreDirtyLevel', ctypes.c_float * 4),
        ('tyreCoreTemperature', ctypes.c_float * 4),
        ('camberRAD', ctypes.c_float * 4),
        ('suspensionTravel', ctypes.c_float * 4),
        ('drs', ctypes.c_float),
        ('tc', ctypes.c_float),
        ('heading', ctypes.c_float),
        ('pitch', ctypes.c_float),
        ('roll', ctypes.c_float),
        ('cgHeight', ctypes.c_float),
        ('carDamage', ctypes.c_float * 5),
        ('numberOfTyresOut', ctypes.c_int),
        ('pitLimiterOn', ctypes.c_int),
        ('abs', ctypes.c_float),
        ('kersCharge', ctypes.c_float),
        ('kersInput', ctypes.c_float),
        ('autoShifterOn', ctypes.c_int),
        ('rideHeight', ctypes.c_float * 2),
        ('turboBoost', ctypes.c_float),
        ('ballast', ctypes.c_float),
        ('airDensity', ctypes.c_float),
        ('airTemp', ctypes.c_float),
        ('roadTemp', ctypes.c_float),
        ('localAngularVel', ctypes.c_float * 3),
        ('finalFF', ctypes.c_float),
        ('performanceMeter', ctypes.c_float),
        ('engineBrake', ctypes.c_int),
        ('ersRecoveryLevel', ctypes.c_int),
        ('ersPowerLevel', ctypes.c_int),
        ('ersHeatCharging', ctypes.c_int),
        ('ersIsCharging', ctypes.c_int),
        ('kersCurrentKJ', ctypes.c_int),
        ('drsAvailable', ctypes.c_int),
        ('drsEnabled', ctypes.c_int),
        ('brakeTemp', ctypes.c_float * 4),
        ('clutch', ctypes.c_float),
        ('tyreTempI', ctypes.c_float * 4),
        ('tyreTempM', ctypes.c_float * 4),
        ('tyreTempO', ctypes.c_float * 4),
        ('isAIControlled', ctypes.c_int),
        ('tyreContactPoint', ctypes.c_float * 3 * 4),
        ('tyreContactNormal', ctypes.c_float * 3 * 4),
        ('tyreContactHeading', ctypes.c_float * 3 * 4),
        ('brakeBias', ctypes.c_float),
        ('localVelocity', ctypes.c_float * 3),
        ('P2PActivations', ctypes.c_int),
        ('P2PStatus', ctypes.c_int),
        ('currentMaxRpm', ctypes.c_int),
        ('mz', ctypes.c_float * 4),
        ('fx', ctypes.c_float * 4),
        ('fy', ctypes.c_float * 4),
        ('slipRatio', ctypes.c_float * 4),
        ('slipAngle', ctypes.c_float * 4),
        ('tcInAction', ctypes.c_int),
        ('absInAction', ctypes.c_int),
        ('suspensionDamage', ctypes.c_float * 4),
        ('tyreTemp', ctypes.c_float * 4),
        ('waterTemp', ctypes.c_float),
        ('brakePressure', ctypes.c_float * 4),
        ('frontBrakeCompound', ctypes.c_int),
        ('rearBrakeCompound', ctypes.c_int),
        ('padLife', ctypes.c_float * 4),
        ('discLife', ctypes.c_float * 4),
        ('ignitionOn', ctypes.c_int),
        ('starterEngineOn', ctypes.c_int),
        ('kerbVibration', ctypes.c_float),
        ('slipVibrations', ctypes.c_float),
        ('gVibrations', ctypes.c_float),
        ('absVibrations', ctypes.c_float),
    ]


def _mapping_exists(name, size):
    """检查同名共享内存是否已存在（ACC 未启动时不要凭空创建）。"""
    create = ctypes.windll.kernel32.CreateFileMappingW
    close = ctypes.windll.kernel32.CloseHandle
    get_last_error = ctypes.windll.kernel32.GetLastError
    invalid = ctypes.wintypes.HANDLE(-1).value
    page_readwrite = 0x04
    error_already_exists = 0xB7

    handle = create(ctypes.wintypes.HANDLE(-1), None, page_readwrite, 0, size,
                    ctypes.c_wchar_p(name))
    exists = (handle != invalid) and (get_last_error() == error_already_exists)
    if handle != invalid:
        close(handle)
    return exists


def get_physics():
    """返回映射到 ACC physics 页面的结构体。

    ACC 没运行时抛 FileNotFoundError，调用方可以捕获后重试。
    """
    if sys.platform != 'win32':
        raise RuntimeError('ACC shared memory is only available on Windows')

    size = ctypes.sizeof(SPageFilePhysics)
    if not _mapping_exists(PAGE_NAME, MAP_SIZE):
        raise FileNotFoundError(PAGE_NAME)
    return SPageFilePhysics.from_buffer(mmap.mmap(-1, size, PAGE_NAME))
