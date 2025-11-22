# waveform_plot.py
import logging
import pyqtgraph as pg
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPen
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget
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
        self._auto_y_enabled = True
        self._manual_x_override = False
        self._programmatic_x_change = False
        self._set_y_action = None
        self._origin_timestamp = None  # track earliest timestamp ever seen
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

        try:
            self.main_plot.sigXRangeChanged.connect(self._on_x_range_changed)
        except Exception:
            pass

        try:
            self._install_viewbox_menu()
        except Exception:
            logger.exception("Failed to install custom viewbox menu")
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

        # prepare optional band items (upper/lower + fill) to preserve min/max per block
        band_upper = None
        band_lower = None
        band_fill = None
        try:
            # create cosmetic pens (width 0) so lines remain thin in pixels
            up_pen = QPen(QColor(color))
            up_pen.setWidth(0)
            up_pen.setCosmetic(True)
            band_upper = pg.PlotDataItem(pen=up_pen)
            band_upper.setZValue(curve.zValue() - 1)

            low_pen = QPen(QColor(color))
            low_pen.setWidth(0)
            low_pen.setCosmetic(True)
            band_lower = pg.PlotDataItem(pen=low_pen)
            band_lower.setZValue(curve.zValue() - 1)

            # semi-transparent brush for fill (use alpha so band isn't visually thick)
            fill_color = QColor(color)
            fill_color.setAlpha(60)  # ~25% opaque
            brush = pg.mkBrush(fill_color)

            # try to create FillBetweenItem if available
            try:
                band_fill = pg.FillBetweenItem(band_upper, band_lower, brush=brush)
            except Exception:
                band_fill = None
        except Exception:
            band_upper = band_lower = band_fill = None

        self.main_plot.addItem(curve)
        if band_upper is not None and band_lower is not None:
            try:
                self.main_plot.addItem(band_upper)
                self.main_plot.addItem(band_lower)
                if band_fill is not None:
                    self.main_plot.addItem(band_fill)
            except Exception:
                pass

        self.curves[signal_id] = {
            "curve": curve,
            "band_upper": band_upper,
            "band_lower": band_lower,
            "band_fill": band_fill,
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
            # update band items if present
            try:
                upper = curve_info.get("band_upper")
                lower = curve_info.get("band_lower")
                if upper is not None:
                    try:
                        pen = QPen(QColor(color_hex))
                        pen.setWidth(0)
                        pen.setCosmetic(True)
                        upper.setPen(pen)
                    except Exception:
                        pass
                if lower is not None:
                    try:
                        pen = QPen(QColor(color_hex))
                        pen.setWidth(0)
                        pen.setCosmetic(True)
                        lower.setPen(pen)
                    except Exception:
                        pass
                fill = curve_info.get("band_fill")
                if fill is not None:
                    try:
                        fc = QColor(color_hex)
                        fc.setAlpha(60)
                        brush = pg.mkBrush(fc)
                        fill.setBrush(brush)
                    except Exception:
                        pass
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

        # keep a stable origin so the x-axis can continue to grow even if
        # we drop older samples for rendering performance
        ts0 = timestamps[0]
        if self._origin_timestamp is None or ts0 < self._origin_timestamp:
            self._origin_timestamp = ts0

        origin = self._origin_timestamp
        relative_times = [t - origin for t in timestamps]

        # 选择要显示的时间段：优先使用 DataBuffer 提供的索引选择器（包含基于采样估算的下采样）
        indices = []
        try:
            db = getattr(self.controller, "data_buffer", None)
            if db is not None and hasattr(db, "get_window_indices"):
                indices = db.get_window_indices(
                    self.current_time_range, self.max_display_points
                )
                # convert indices to relative times w.r.t origin
                if indices:
                    timestamps = self.controller.get_timestamps()
                    # origin already tracked in widget
                    origin = self._origin_timestamp or (
                        timestamps[0] if timestamps else 0
                    )
                    display_times = [
                        timestamps[i] - origin for i in indices if i < len(timestamps)
                    ]
                else:
                    display_times = []
            else:
                # fallback to previous behavior if helper not available
                latest_rel = relative_times[-1] if relative_times else 0
                display_start = max(0.0, latest_rel - float(self.current_time_range))
                indices = [
                    i for i, t in enumerate(relative_times) if t >= display_start
                ]
                if not indices:
                    return
                if len(indices) > self.max_display_points:
                    import math

                    step = math.ceil(len(indices) / float(self.max_display_points))
                    indices = indices[::step]
                display_times = [relative_times[i] for i in indices]
        except Exception:
            # on any error, abort plotting
            return

        # 为每个信号更新数据
        for signal_id, curve_info in self.curves.items():
            try:
                values = self.controller.get_signal_data(signal_id)
                if not values:
                    continue

                # 以与 display_times 相同的索引从 values 中抽取数据点
                # 如果数据长度与 timestamps 对齐（DataBuffer 保证），直接按 indices 抽取
                try:
                    values_list = list(values)
                    display_values = [
                        values_list[i] for i in indices if i < len(values_list)
                    ]
                except Exception:
                    # 退回到原先的末尾切片行为（降级兼容）
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
                    # 模拟信号：按块计算 (min, max, last) 并绘制带状区间 + last 折线
                    # 为此需要知道 full blocks 对应的索引块（由 indices 推断）
                    try:
                        # 如果 controller 提供 data_buffer，重建 full indices -> blocks
                        db = getattr(self.controller, "data_buffer", None)
                        timestamps = self.controller.get_timestamps()
                        if db is not None and timestamps:
                            # compute full indices in window
                            latest = timestamps[-1]
                            start = latest - float(self.current_time_range)
                            full_indices = [
                                i for i, t in enumerate(timestamps) if t >= start
                            ]
                            if not full_indices:
                                continue
                            if len(full_indices) <= self.max_display_points:
                                blocks = [[i] for i in full_indices]
                            else:
                                import math

                                step = math.ceil(
                                    len(full_indices) / float(self.max_display_points)
                                )
                                blocks = [
                                    full_indices[i : i + step]
                                    for i in range(0, len(full_indices), step)
                                ]
                        else:
                            # fallback: evenly map display_values to display_times
                            blocks = None

                        values_list = list(values)

                        if blocks:
                            mins = []
                            maxs = []
                            lasts = []
                            times = []
                            for blk in blocks:
                                blk_vals = [
                                    values_list[k] for k in blk if k < len(values_list)
                                ]
                                if not blk_vals:
                                    continue
                                mins.append(min(blk_vals))
                                maxs.append(max(blk_vals))
                                lasts.append(blk_vals[-1])
                                # time representative - use last timestamp in block
                                times.append((timestamps[blk[-1]] - origin))

                            if not times:
                                continue

                            times_arr = np.array(times)
                            lasts_arr = np.array(lasts)
                            mins_arr = np.array(mins)
                            maxs_arr = np.array(maxs)

                            # set main curve to last values
                            try:
                                curve_info["curve"].setData(times_arr, lasts_arr)
                            except Exception:
                                pass

                            # set band curves and fill if available
                            upper = curve_info.get("band_upper")
                            lower = curve_info.get("band_lower")
                            try:
                                if upper is not None:
                                    upper.setData(times_arr, maxs_arr)
                                if lower is not None:
                                    lower.setData(times_arr, mins_arr)
                                # If FillBetweenItem is unavailable we could draw
                                # a semi-transparent polygon manually as fallback.
                            except Exception:
                                pass
                        else:
                            # fallback to simple plotting
                            plot_times = np.array(plot_times)
                            plot_values = np.array(plot_values)
                            curve_info["curve"].setData(plot_times, plot_values)
                    except Exception as e:
                        logger.exception(f"模拟信号带状绘制失败: {e}")

            except Exception as e:
                logger.error(f"更新信号 {signal_id} 失败: {e}")

        # 自动调整Y轴范围
        if self._auto_y_enabled:
            self._auto_adjust_y_range()

        # 更新X轴范围
        if display_times:
            if not self._manual_x_override:
                current_time = display_times[-1]
                window = float(max(self.current_time_range, 1))

                self._programmatic_x_change = True
                try:
                    if current_time >= window:
                        self.main_plot.setXRange(current_time - window, current_time)
                    else:
                        self.main_plot.setXRange(0, max(current_time, window))
                finally:
                    self._programmatic_x_change = False

    def _auto_adjust_y_range(self):
        """自动调整Y轴范围"""
        if not self.curves:
            return

        # 检查信号类型
        has_bool = False
        analog_values = []
        for signal_id, curve_info in self.curves.items():
            if curve_info["type"] == "bool":
                has_bool = True
                continue
            values = self.controller.get_signal_data(signal_id)
            if values:
                recent_values = values[-50:] if len(values) > 50 else values
                analog_values.extend(recent_values)

        if analog_values:
            min_val = min(analog_values)
            max_val = max(analog_values)

            if abs(max_val - min_val) < 0.01:
                center = (min_val + max_val) / 2
                min_range = center - 1
                max_range = center + 1
            else:
                span = max_val - min_val
                margin = max(span * 0.1, 0.1)
                min_range = min_val - margin
                max_range = max_val + margin

            if has_bool:
                min_range = min(min_range, -0.2)
                max_range = max(max_range, 1.2)

            self.main_plot.setYRange(min_range, max_range)
        elif has_bool:
            # 只有布尔信号
            self.main_plot.setYRange(-0.2, 1.2)
        else:
            self.main_plot.setYRange(0, 100)

    def set_time_range(self, seconds):
        """设置时间显示范围"""
        self.current_time_range = seconds
        self._manual_x_override = False

        timestamps = self.controller.get_timestamps()
        if timestamps:
            start_time = timestamps[0]
            current_time = timestamps[-1] if timestamps else 0
            current_relative_time = current_time - start_time

            self._programmatic_x_change = True
            try:
                if current_relative_time > seconds:
                    self.main_plot.setXRange(
                        current_relative_time - seconds, current_relative_time
                    )
                else:
                    self.main_plot.setXRange(0, max(current_relative_time, 10))
            finally:
                self._programmatic_x_change = False

    def auto_range(self):
        """自动调整范围"""
        if not self._auto_y_enabled:
            return
        self._auto_adjust_y_range()

    def set_auto_y_enabled(self, enabled: bool):
        """Enable or disable automatic Y range updates."""
        self._auto_y_enabled = bool(enabled)

    def clear_plots(self):
        """清空所有绘图"""
        self._origin_timestamp = None
        for signal_id in list(self.curves.keys()):
            self.remove_signal_plot(signal_id)

    def _install_viewbox_menu(self):
        vb = self.main_plot.getViewBox()
        if vb is None:
            return

        try:
            menu = getattr(vb, "menu", None)
            if menu is None:
                menu = vb.getMenu(None)
        except Exception:
            menu = None

        if menu is None:
            return

        if self._set_y_action is None:
            self._set_y_action = QAction("设置Y轴范围...", self)
            self._set_y_action.triggered.connect(self._prompt_manual_y_range)

        if self._set_y_action not in menu.actions():
            menu.addSeparator()
            menu.addAction(self._set_y_action)

    def _prompt_manual_y_range(self):
        try:
            current_range = self.main_plot.viewRange()[1]
        except Exception:
            current_range = [0.0, 100.0]

        try:
            default_text = f"{current_range[0]:.3f}, {current_range[1]:.3f}"
        except Exception:
            default_text = "0, 100"

        text, ok = QInputDialog.getText(
            self,
            "设置Y轴范围",
            "输入最小值, 最大值 (例如 -10, 50):",
            text=default_text,
        )
        if not ok:
            return

        try:
            parts = [float(part.strip()) for part in text.split(",") if part.strip()]
            if len(parts) != 2 or parts[0] >= parts[1]:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self, "设置Y轴范围", "请输入两个递增的数值，例如 -10, 50"
            )
            return

        self.set_auto_y_enabled(False)
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "auto_range_check"):
                block = parent.auto_range_check.blockSignals(True)
                parent.auto_range_check.setChecked(False)
                parent.auto_range_check.blockSignals(block)
        except Exception:
            pass

        try:
            self.main_plot.setYRange(parts[0], parts[1])
        except Exception:
            QMessageBox.warning(self, "设置Y轴范围", "无法应用指定的范围")

    def _on_x_range_changed(self, *args):
        if self._programmatic_x_change:
            return
        self._manual_x_override = True

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
