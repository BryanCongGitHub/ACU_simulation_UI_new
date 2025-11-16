# data_buffer.py
import time
import logging
from collections import deque, defaultdict

# 创建日志记录器
logger = logging.getLogger("DataBuffer")
logger.setLevel(logging.INFO)


class DataBuffer:
    """改进的数据缓冲区，确保数据同步"""

    def __init__(self, max_points=5000):
        self.max_points = max_points
        self.data = defaultdict(lambda: deque(maxlen=max_points))
        self.timestamps = deque(maxlen=max_points)
        self.signal_order = []  # 记录信号添加顺序

    def add_data_point(self, signal_id, value, timestamp=None):
        """添加单个数据点（保留此方法用于兼容）"""
        if timestamp is None:
            timestamp = time.time()

        # 如果是新信号，用当前值填充之前的时间点
        if signal_id not in self.signal_order:
            self.signal_order.append(signal_id)
            # 为新信号填充历史数据
            for _ in range(len(self.timestamps)):
                self.data[signal_id].append(value)

        # 添加新数据点
        self.data[signal_id].append(value)
        self.timestamps.append(timestamp)

        # 强制同步所有信号的数据长度
        self._sync_data_length()
        logger.debug(
            f"添加单个数据点: {signal_id} = {value}, 时间戳数: {len(self.timestamps)}"
        )

    def add_data_points(self, signal_values, timestamp=None):
        """一次性添加多个信号的数据点（确保时间戳唯一）"""
        if timestamp is None:
            timestamp = time.time()

        if not signal_values:
            logger.warning("add_data_points 接收到空信号值")
            return

        # 只添加一个时间戳
        self.timestamps.append(timestamp)
        logger.debug(
            f"添加批量数据点: {list(signal_values.keys())}, 时间戳: {timestamp:.3f}"
        )

        # 为每个信号添加对应的值
        for signal_id, value in signal_values.items():
            # 新信号：填充历史数据
            if signal_id not in self.signal_order:
                self.signal_order.append(signal_id)
                for _ in range(len(self.timestamps) - 1):
                    self.data[signal_id].append(value)
                logger.debug(
                    f"新信号 {signal_id} 已添加, 填充 {len(self.timestamps)-1} 个历史点"
                )

            # 添加当前值
            self.data[signal_id].append(value)
            logger.debug(f"信号 {signal_id} 添加值: {value}")

        # 为未更新的信号填充保持值
        for signal_id in self.signal_order:
            if signal_id not in signal_values:
                last_val = self.data[signal_id][-1] if self.data[signal_id] else 0
                self.data[signal_id].append(last_val)
                logger.debug(f"信号 {signal_id} 未更新，保持值: {last_val}")

        self._sync_data_length()
        logger.debug(
            f"批量添加完成: 时间戳数={len(self.timestamps)}, 信号数={len(self.signal_order)}"
        )

    def _sync_data_length(self):
        """同步所有信号的数据长度"""
        target_length = len(self.timestamps)

        for signal_id in self.signal_order:
            current_length = len(self.data[signal_id])
            if current_length < target_length:
                # 用最后一个值填充缺失的数据
                last_value = self.data[signal_id][-1] if self.data[signal_id] else 0
                fill_count = target_length - current_length
                for _ in range(fill_count):
                    self.data[signal_id].append(last_value)
                logger.debug(
                    f"信号 {signal_id} 填充 {fill_count} 个值，目标长度: {target_length}"
                )
            elif current_length > target_length:
                # 移除多余的数据（理论上不应该发生）
                remove_count = current_length - target_length
                for _ in range(remove_count):
                    if self.data[signal_id]:
                        self.data[signal_id].pop()
                logger.warning(f"信号 {signal_id} 移除 {remove_count} 个多余数据")

    def get_data(self, signal_id):
        """获取信号数据"""
        values = list(self.data[signal_id])
        logger.debug(f"获取信号 {signal_id} 数据: {len(values)} 个点")
        return values

    def get_timestamps(self):
        """获取时间戳数据"""
        timestamps = list(self.timestamps)
        logger.debug(f"获取时间戳: {len(timestamps)} 个点")
        return timestamps

    def get_time_range_data(self, signal_id, start_time, end_time):
        """获取时间范围内的数据"""
        if signal_id not in self.data:
            logger.warning(f"信号 {signal_id} 不存在")
            return [], []

        timestamps = self.get_timestamps()
        values = self.get_data(signal_id)

        # 找到时间范围内的数据点
        result_times = []
        result_values = []

        for ts, val in zip(timestamps, values):
            if start_time <= ts <= end_time:
                result_times.append(ts)
                result_values.append(val)

        logger.debug(
            f"时间范围查询: {signal_id}, 原始点数={len(timestamps)}, 结果点数={len(result_times)}"
        )
        return result_times, result_values

    def clear(self):
        """清空缓冲区"""
        self.data.clear()
        self.timestamps.clear()
        self.signal_order.clear()
        logger.info("数据缓冲区已清空")

    def get_latest_value(self, signal_id):
        """获取最新值"""
        if signal_id in self.data and self.data[signal_id]:
            value = self.data[signal_id][-1]
            logger.debug(f"获取 {signal_id} 最新值: {value}")
            return value
        logger.debug(f"信号 {signal_id} 无数据")
        return None
