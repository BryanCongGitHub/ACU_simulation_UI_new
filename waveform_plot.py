# waveform_plot.py
import logging
import pyqtgraph as pg
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QLabel
import time

# 配置pyqtgraph
pg.setConfigOptions(
    useOpenGL=False,
    enableExperimental=False,
    antialias=True,  # 启用抗锯齿让细线更平滑
    background="w",
    foreground="k",
)

logger = logging.getLogger("WaveformPlot")


class WaveformPlotWidget(QWidget):
    """波形绘图组件 - 极细线版本"""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.curves = {}
        self.current_time_range = 600
        self.last_plt_update = 0
        self.max_display_points = 1000
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 创建图形窗口
        self.graphics_view = pg.GraphicsLayoutWidget()
        self.main_plot = self.graphics_view.addPlot(title="通信信号波形显示")
        self.main_plot.showGrid(x=True, y=True, alpha=0.3)
        self.main_plot.setLabel("left", "信号值")
        self.main_plot.setLabel("bottom", "时间", "s")
        # keep a reference to legend so we can toggle visibility later
        self.legend = self.main_plot.addLegend(offset=(-10, 10))

        # 设置合理的初始范围
        self.main_plot.setYRange(0, 100)
        self.main_plot.setXRange(0, 600)

        # 提高图形部件的最小高度
        self.graphics_view.setMinimumHeight(500)
        layout.addWidget(self.graphics_view)
        # store last hover info for tests/interaction
        self.last_hover = {}
        # UI hover label (throttled updates)
        self.hover_label = QLabel("", self.graphics_view)
        self.hover_label.setVisible(False)
        self.hover_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hover_label.setStyleSheet(
            "background: rgba(255,255,225,230); border: 1px solid #888; padding: 4px;"
        )
        # last hover UI update timestamp (ms)
        self._last_hover_update = 0

        # connect mouse move on the scene to capture hover info
        try:
            self.graphics_view.scene().sigMouseMoved.connect(self._on_scene_mouse_moved)
        except Exception:
            # some headless or older environments may not support this signal
            pass
        logger.info("WaveformPlotWidget UI初始化完成")

    def add_signal_plot(self, signal_id, signal_info):
        """添加信号绘图"""
        if signal_id in self.curves:
            logger.warning(f"信号 {signal_id} 已存在")
            return

        # 为不同信号类型设置不同颜色
        colors = [
            "#FF0000",
            "#0000FF",
            "#00AA00",
            "#FF00FF",
            "#FFA500",
            "#00FFFF",
            "#800080",
            "#008080",
        ]
        color_index = len(self.curves) % len(colors)
        color = colors[color_index]

        # 【关键修复】使用极细线宽
        pen = QPen(QColor(color))
        pen.setWidth(0)  # 设置为0，使用最细的线
        pen.setCosmetic(True)  # cosmetic pens ignore transformations

        if signal_info["type"] == "bool":
            # 布尔信号使用虚线（使用枚举以满足类型检查）
            pen.setStyle(Qt.PenStyle.DashLine)
        else:
            # 模拟信号使用实线
            pen.setStyle(Qt.PenStyle.SolidLine)

        curve = pg.PlotDataItem(pen=pen, name=signal_info["name"])

        self.main_plot.addItem(curve)
        self.curves[signal_id] = {
            "curve": curve,
            "type": signal_info["type"],
            "info": signal_info,
            "color": color,
            "pen": pen,
        }
        logger.info(
            f"添加信号曲线: {signal_info['name']}, 类型: {signal_info['type']}, 颜色: {color}"
        )

    def set_curve_color(self, signal_id, color_hex: str):
        """Change the color of an existing curve identified by signal_id.

        color_hex should be a hex string like '#RRGGBB'. This updates the pen
        and keeps the cosmetic width behavior.
        """
        if signal_id not in self.curves:
            return
        try:
            from PySide6.QtGui import QColor, QPen

            curve_info = self.curves[signal_id]
            pen = QPen(QColor(color_hex))
            pen.setWidth(0)
            pen.setCosmetic(True)
            if curve_info.get("type") == "bool":
                pen.setStyle(Qt.PenStyle.DashLine)
            else:
                pen.setStyle(Qt.PenStyle.SolidLine)
            curve_info["pen"] = pen
            curve_info["color"] = color_hex
            curve = curve_info["curve"]
            # re-create the PlotDataItem with new pen by updating pen property
            try:
                curve.setPen(pen)
            except Exception:
                # fallback: remove and re-add
                try:
                    self.main_plot.removeItem(curve)
                    new_curve = pg.PlotDataItem(pen=pen, name=curve.name())
                    self.main_plot.addItem(new_curve)
                    curve_info["curve"] = new_curve
                except Exception:
                    pass
        except Exception:
            logger.exception("设置曲线颜色失败")

    def set_theme(self, theme: str):
        """Switch plot theme between 'light' and 'dark'."""
        try:
            if theme == "dark":
                pg.setConfigOption("background", "k")
                pg.setConfigOption("foreground", "w")
                self.main_plot.showGrid(x=True, y=True, alpha=0.2)
            else:
                pg.setConfigOption("background", "w")
                pg.setConfigOption("foreground", "k")
                self.main_plot.showGrid(x=True, y=True, alpha=0.3)
            # apply immediately to the plot area
            try:
                self.graphics_view.setBackground(pg.getConfig("background"))
            except Exception:
                pass
        except Exception:
            logger.exception("切换主题失败")

    def show_legend(self, visible: bool):
        """Show or hide the legend."""
        try:
            if getattr(self, "legend", None) is not None:
                try:
                    self.legend.setVisible(visible)
                except Exception:
                    # some versions may require removing/adding
                    if not visible:
                        try:
                            self.legend.scene().removeItem(self.legend)
                        except Exception:
                            pass
                    else:
                        try:
                            self.legend = self.main_plot.addLegend(offset=(-10, 10))
                        except Exception:
                            pass
        except Exception:
            pass

    def set_curve_visible(self, signal_id, visible: bool):
        """Set visibility of a specific curve without removing it."""
        try:
            if signal_id not in self.curves:
                return
            curve_info = self.curves[signal_id]
            curve = curve_info.get("curve")
            if curve is not None:
                try:
                    curve.setVisible(bool(visible))
                except Exception:
                    # fallback: remove or re-add as needed
                    if not visible:
                        try:
                            self.main_plot.removeItem(curve)
                        except Exception:
                            pass
                    else:
                        try:
                            new_curve = pg.PlotDataItem(
                                pen=curve_info.get("pen"), name=curve.name()
                            )
                            self.main_plot.addItem(new_curve)
                            curve_info["curve"] = new_curve
                        except Exception:
                            pass
        except Exception:
            logger.exception("设置曲线可见性失败")

    def remove_signal_plot(self, signal_id):
        """移除信号绘图"""
        if signal_id in self.curves:
            curve_info = self.curves[signal_id]
            self.main_plot.removeItem(curve_info["curve"])
            del self.curves[signal_id]
            logger.info(f"移除信号曲线: {signal_id}")

    def update_all_plots(self):
        """更新所有绘图"""
        if not self.curves:
            return

        # 限制更新频率
        import time

        current_ms = int(time.time() * 1000)
        if current_ms - self.last_plt_update < 200:  # 200ms间隔
            return
        self.last_plt_update = current_ms

        # 获取时间数据
        timestamps = self.controller.get_timestamps()
        if not timestamps or len(timestamps) < 2:
            return

        start_time = timestamps[0]
        relative_times = [t - start_time for t in timestamps]

        # 限制显示点数
        if len(relative_times) > self.max_display_points:
            start_idx = len(relative_times) - self.max_display_points
            display_times = relative_times[start_idx:]
        else:
            display_times = relative_times

        # 为每个信号更新数据
        for signal_id, curve_info in self.curves.items():
            try:
                values = self.controller.get_signal_data(signal_id)
                if not values:
                    continue

                if len(values) > self.max_display_points:
                    value_start = len(values) - self.max_display_points
                    display_values = values[value_start:]
                else:
                    display_values = values

                # 确保数据长度匹配
                min_len = min(len(display_times), len(display_values))
                if min_len == 0:
                    continue

                plot_times = display_times[-min_len:]
                plot_values = display_values[-min_len:]

                # 布尔信号处理
                if curve_info["type"] == "bool":
                    # 布尔信号：创建步进效果
                    step_times = []
                    step_values = []

                    for i in range(min_len):
                        current_time = plot_times[i]
                        current_value = 1.0 if plot_values[i] else 0.0

                        if i == 0:
                            # 第一个点
                            step_times.append(current_time)
                            step_values.append(current_value)
                        else:
                            # 从前一个值过渡到当前值
                            prev_time = plot_times[i - 1]
                            prev_value = 1.0 if plot_values[i - 1] else 0.0

                            if prev_value != current_value:
                                # 值变化时，在变化点前后都设置点
                                step_times.extend([prev_time, current_time])
                                step_values.extend([prev_value, current_value])
                            else:
                                # 值不变时，只添加当前点
                                step_times.append(current_time)
                                step_values.append(current_value)

                    if step_times:
                        step_times = np.array(step_times)
                        step_values = np.array(step_values)
                        curve_info["curve"].setData(step_times, step_values)

                else:
                    # 模拟信号：直接绘制
                    plot_times = np.array(plot_times)
                    plot_values = np.array(plot_values)
                    curve_info["curve"].setData(plot_times, plot_values)

            except Exception as e:
                logger.error(f"更新信号 {signal_id} 失败: {e}")

        # 自动调整Y轴范围
        self._auto_adjust_y_range()

        # 更新X轴范围
        if display_times:
            current_time = display_times[-1]
            view_range = self.main_plot.viewRange()
            current_range_width = view_range[0][1] - view_range[0][0]

            if current_time > view_range[0][1]:
                self.main_plot.setXRange(
                    current_time - current_range_width, current_time
                )

    def _auto_adjust_y_range(self):
        """自动调整Y轴范围"""
        if not self.curves:
            return

        # 检查信号类型
        has_bool = any(
            curve_info["type"] == "bool" for curve_info in self.curves.values()
        )
        has_analog = any(
            curve_info["type"] != "bool" for curve_info in self.curves.values()
        )

        if has_bool and not has_analog:
            # 只有布尔信号
            self.main_plot.setYRange(-0.2, 1.2)

        elif has_analog and not has_bool:
            # 只有模拟信号
            all_values = []
            for signal_id, curve_info in self.curves.items():
                if curve_info["type"] != "bool":
                    values = self.controller.get_signal_data(signal_id)
                    if values and len(values) > 0:
                        # 取最近的数据点
                        recent_values = values[-50:] if len(values) > 50 else values
                        all_values.extend(recent_values)

            if all_values:
                min_val = min(all_values)
                max_val = max(all_values)

                if abs(max_val - min_val) < 0.01:
                    # 数据基本不变，设置固定范围
                    center = (min_val + max_val) / 2
                    self.main_plot.setYRange(center - 1, center + 1)
                else:
                    margin = max((max_val - min_val) * 0.1, 0.1)
                    self.main_plot.setYRange(min_val - margin, max_val + margin)
            else:
                self.main_plot.setYRange(0, 100)

        else:
            # 混合信号
            self.main_plot.setYRange(-1, 100)

    def set_time_range(self, seconds):
        """设置时间显示范围"""
        self.current_time_range = seconds

        timestamps = self.controller.get_timestamps()
        if timestamps:
            start_time = timestamps[0]
            current_time = timestamps[-1] if timestamps else 0
            current_relative_time = current_time - start_time

            if current_relative_time > seconds:
                self.main_plot.setXRange(
                    current_relative_time - seconds, current_relative_time
                )
            else:
                self.main_plot.setXRange(0, max(current_relative_time, 10))

    def auto_range(self):
        """自动调整范围"""
        self._auto_adjust_y_range()

    def clear_plots(self):
        """清空所有绘图"""
        for signal_id in list(self.curves.keys()):
            self.remove_signal_plot(signal_id)

    def _on_scene_mouse_moved(self, pos):
        """Capture hover position and nearest sample values.

        Stores a mapping in `self.last_hover` where keys are signal ids (string)
        and values are dicts with `time` and `value` for the nearest timestamp.
        This is intentionally best-effort and swallows exceptions so it is
        safe to run in headless CI.
        """
        try:
            if not hasattr(self, "controller"):
                return

            # map scene position to plot coordinates (view coordinates)
            try:
                view_pt = self.main_plot.vb.mapSceneToView(pos)
                x = float(view_pt.x())
            except Exception:
                # fallback: if mapping fails, treat x as 0
                x = 0.0

            timestamps = self.controller.get_timestamps() or []
            if not timestamps:
                return

            start = timestamps[0]
            rel = [t - start for t in timestamps]

            # find nearest index to x (relative time)
            try:
                idx = min(range(len(rel)), key=lambda i: abs(rel[i] - x))
            except Exception:
                idx = 0

            info = {}
            for sid, curve_info in self.curves.items():
                try:
                    data = self.controller.get_signal_data(sid) or []
                    if idx < len(data):
                        info[str(sid)] = {"time": timestamps[idx], "value": data[idx]}
                except Exception:
                    # ignore individual signal errors
                    pass

            # always update last_hover for tests or other logic
            self.last_hover = info

            # Throttle UI updates to avoid high-frequency redraws
            try:
                current_ms = int(time.time() * 1000)
                if current_ms - self._last_hover_update >= 150:
                    # Build a short tooltip text (limit to first 6 signals)
                    lines = []
                    for i, sid in enumerate(sorted(info.keys())):
                        if i >= 6:
                            break
                        val = info[sid]["value"]
                        try:
                            # try to recover a friendly name from curves
                            key = int(sid) if sid.isdigit() else sid
                            name = (
                                self.curves.get(key, self.curves.get(sid, {}))
                                .get("info", {})
                                .get("name", str(sid))
                            )
                        except Exception:
                            name = str(sid)
                        lines.append(f"{name}: {val}")

                    if lines:
                        txt = "\n".join(lines)
                        # try to position label near the pointer
                        try:
                            views = self.graphics_view.scene().views()
                            if views:
                                view_widget = views[0]
                                widget_pt = view_widget.mapFromScene(pos)
                                self.hover_label.setText(txt)
                                self.hover_label.adjustSize()
                                # place with small offset
                                self.hover_label.move(
                                    widget_pt.x() + 12, widget_pt.y() + 12
                                )
                                self.hover_label.setVisible(True)
                        except Exception:
                            # fallback to Qt tooltip if positioning fails
                            try:
                                from PySide6.QtWidgets import QToolTip

                                QToolTip.showText(self.mapToGlobal(self.pos()), txt)
                            except Exception:
                                pass

                    else:
                        try:
                            self.hover_label.setVisible(False)
                        except Exception:
                            pass

                    self._last_hover_update = current_ms
            except Exception:
                # swallow UI hover exceptions
                pass
        except Exception:
            # never raise from hover handling
            pass
