import os
import uuid
import math

from Qt import QtWidgets, QtCore, QtGui

from openpype.style import get_objected_colors
from openpype.lib import (
    run_subprocess,
    is_oiio_supported,
    get_oiio_tools_path,
    get_ffmpeg_tool_path,
)
from openpype.lib.transcoding import (
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)

from openpype.tools.utils import (
    paint_image_with_color,
)
from openpype.tools.publisher.control import CardMessageTypes

from .icons import get_image


class ThumbnailWidget(QtWidgets.QWidget):
    """Instance thumbnail widget."""

    thumbnail_created = QtCore.Signal(str)

    width_ratio = 3.0
    height_ratio = 2.0
    border_width = 1
    offset_sep = 4

    def __init__(self, controller, parent):
        # Missing implementation for thumbnail
        # - widget kept to make a visial offset of global attr widget offset
        super(ThumbnailWidget, self).__init__(parent)
        self.setAcceptDrops(True)

        border_color = get_objected_colors("bg-buttons").get_qcolor()
        thumbnail_bg_color = get_objected_colors("border").get_qcolor()
        overlay_color = get_objected_colors("font").get_qcolor()

        default_image = get_image("thumbnail")
        default_pix = paint_image_with_color(default_image, border_color)

        self._controller = controller
        self._output_dir = controller.get_thumbnail_temp_dir_path()

        self.border_color = border_color
        self.thumbnail_bg_color = thumbnail_bg_color
        self.overlay_color = overlay_color
        self._default_pix = default_pix

        self._drop_enabled = True

        self._current_pixes = None
        self._cached_pix = None

        self._review_extensions = set(IMAGE_EXTENSIONS) | set(VIDEO_EXTENSIONS)

        self._height = None
        self._width = None
        self._adapted_to_size = True
        self._last_width = None
        self._last_height = None

    def _get_filepath_from_event(self, event):
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            return None

        filepaths = []
        for url in mime_data.urls():
            filepath = url.toLocalFile()
            if os.path.exists(filepath):
                filepaths.append(filepath)

        if len(filepaths) == 1:
            filepath = filepaths[0]
            ext = os.path.splitext(filepath)[-1]
            if ext in self._review_extensions:
                return filepath
        return None

    def dragEnterEvent(self, event):
        if not self._drop_enabled:
            event.ignore()
            return

        filepath = self._get_filepath_from_event(event)
        if filepath:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()

    def dragLeaveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        if not self._drop_enabled:
            return

        filepath = self._get_filepath_from_event(event)
        if not filepath:
            return

        output = export_thumbnail(filepath, self._output_dir)
        if output:
            self.thumbnail_created.emit(output)
        else:
            self._controller.emit_card_message(
                "Couldn't convert the source for thumbnail",
                CardMessageTypes.error
            )

    def set_drop_enabled(self, enabled):
        if self._drop_enabled is enabled:
            return
        self._drop_enabled = enabled
        self._cached_pix = None
        self.repaint()

    def set_adapted_to_hint(self, enabled):
        self._adapted_to_size = enabled
        if self._width is not None:
            self.setMinimumHeight(0)
            self._width = None

        if self._height is not None:
            self.setMinimumWidth(0)
            self._height = None

    def set_width(self, width):
        if self._width == width:
            return

        self._adapted_to_size = False
        self._width = width
        self._cached_pix = None
        self.setMinimumHeight(int(
            (width / self.width_ratio) * self.height_ratio
        ))
        if self._height is not None:
            self.setMinimumWidth(0)
            self._height = None

    def set_height(self, height):
        if self._height == height:
            return

        self._height = height
        self._adapted_to_size = False
        self._cached_pix = None
        self.setMinimumWidth(int(
            (height / self.height_ratio) * self.width_ratio
        ))
        if self._width is not None:
            self.setMinimumHeight(0)
            self._width = None

    def set_current_thumbnails(self, thumbnail_paths=None):
        pixes = []
        if thumbnail_paths:
            for thumbnail_path in thumbnail_paths:
                pixes.append(QtGui.QPixmap(thumbnail_path))

        self._current_pixes = pixes or None
        self._cached_pix = None
        self.repaint()

    def _get_current_pixes(self):
        if not self._drop_enabled:
            # TODO different image for disabled drop
            return [self._default_pix]

        if self._current_pixes is None:
            return [self._default_pix]
        return self._current_pixes

    def _cache_pix(self):
        rect = self.rect()
        rect_width = rect.width()
        rect_height = rect.height()

        pix_x_offset = 0
        pix_y_offset = 0
        expected_height = int(
            (rect_width / self.width_ratio) * self.height_ratio
        )
        if expected_height > rect_height:
            expected_height = rect_height
            expected_width = int(
                (rect_height / self.height_ratio) * self.width_ratio
            )
            pix_x_offset = (rect_width - expected_width) / 2
        else:
            expected_width = rect_width
            pix_y_offset = (rect_height - expected_height) / 2

        pixes_to_draw = self._get_current_pixes()
        max_pix = 3
        if len(pixes_to_draw) > max_pix:
            pixes_to_draw = pixes_to_draw[:-max_pix]
        pixes_len = len(pixes_to_draw)

        width_offset, height_offset = self._get_pix_offset_size(
            expected_width, expected_height, pixes_len
        )
        pix_width = expected_width - width_offset
        pix_height = expected_height - height_offset
        full_border_width = 2 * self.border_width

        pix_bg_brush = QtGui.QBrush(self.thumbnail_bg_color)

        pix_pen = QtGui.QPen()
        pix_pen.setWidth(self.border_width)
        pix_pen.setColor(self.border_color)

        backgrounded_images = []
        for src_pix in pixes_to_draw:
            scaled_pix = src_pix.scaled(
                pix_width - full_border_width,
                pix_height - full_border_width,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            pos_x = int(
                (pix_width - scaled_pix.width()) / 2
            )
            pos_y = int(
                (pix_height - scaled_pix.height()) / 2
            )

            new_pix = QtGui.QPixmap(pix_width, pix_height)
            new_pix.fill(QtCore.Qt.transparent)
            pix_painter = QtGui.QPainter()
            pix_painter.begin(new_pix)
            pix_painter.setRenderHints(
                pix_painter.Antialiasing
                | pix_painter.SmoothPixmapTransform
                | pix_painter.HighQualityAntialiasing
            )
            pix_painter.setBrush(pix_bg_brush)
            pix_painter.setPen(pix_pen)
            pix_painter.drawRect(0, 0, pix_width - 1, pix_height - 1)
            pix_painter.drawPixmap(pos_x, pos_y, scaled_pix)
            pix_painter.end()
            backgrounded_images.append(new_pix)

        if pixes_len == 1:
            width_offset_part = 0
            height_offset_part = 0
        else:
            width_offset_part = int(float(width_offset) / (pixes_len - 1))
            height_offset_part = int(float(height_offset) / (pixes_len - 1))
        full_width_offset = width_offset + pix_x_offset

        final_pix = QtGui.QPixmap(rect_width, rect_height)
        final_pix.fill(QtCore.Qt.transparent)

        final_painter = QtGui.QPainter()
        final_painter.begin(final_pix)
        final_painter.setRenderHints(
            final_painter.Antialiasing
            | final_painter.SmoothPixmapTransform
            | final_painter.HighQualityAntialiasing
        )
        for idx, pix in enumerate(backgrounded_images):
            x_offset = full_width_offset - (width_offset_part * idx)
            y_offset = (height_offset_part * idx) + pix_y_offset
            final_painter.drawPixmap(x_offset, y_offset, pix)

        if not self._drop_enabled:
            overlay = self._get_drop_disabled_overlay(rect_width, rect_height)
            final_painter.drawPixmap(0, 0, overlay)

        final_painter.end()

        self._cached_pix = final_pix

    def _get_drop_disabled_overlay(self, width, height):
        min_size = min(width, height)
        circle_size = int(min_size * 0.8)
        pen_width = int(circle_size * 0.1)
        if pen_width < 1:
            pen_width = 1

        x_offset = int((width - circle_size) / 2)
        y_offset = int((height - circle_size) / 2)
        half_size = int(circle_size / 2)
        angle = math.radians(45)
        line_offset_p = QtCore.QPoint(
            half_size * math.cos(angle),
            half_size * math.sin(angle)
        )
        overlay_pix = QtGui.QPixmap(width, height)
        overlay_pix.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter()
        painter.begin(overlay_pix)
        painter.setRenderHints(
            painter.Antialiasing
            | painter.SmoothPixmapTransform
            | painter.HighQualityAntialiasing
        )
        painter.setBrush(QtCore.Qt.transparent)
        pen = QtGui.QPen(self.overlay_color)
        pen.setWidth(pen_width)
        painter.setPen(pen)
        rect = QtCore.QRect(x_offset, y_offset, circle_size, circle_size)
        painter.drawEllipse(rect)
        painter.drawLine(
            rect.center() - line_offset_p,
            rect.center() + line_offset_p
        )
        painter.end()

        return overlay_pix

    def _get_pix_offset_size(self, width, height, image_count):
        if image_count == 1:
            return 0, 0

        part_width = width / self.offset_sep
        part_height = height / self.offset_sep
        return part_width, part_height

    def paintEvent(self, event):
        if self._cached_pix is None:
            self._cache_pix()

        painter = QtGui.QPainter()
        painter.begin(self)
        painter.drawPixmap(0, 0, self._cached_pix)
        painter.end()

    def _adapt_to_size(self):
        if not self._adapted_to_size:
            return

        width = self.width()
        height = self.height()
        if width == self._last_width and height == self._last_height:
            return

        self._last_width = width
        self._last_height = height
        self._cached_pix = None

    def resizeEvent(self, event):
        super(ThumbnailWidget, self).resizeEvent(event)
        self._adapt_to_size()

    def showEvent(self, event):
        super(ThumbnailWidget, self).showEvent(event)
        self._adapt_to_size()


def _run_silent_subprocess(args):
    with open(os.devnull, "w") as devnull:
        run_subprocess(args, stdout=devnull, stderr=devnull)


def _convert_thumbnail_oiio(src_path, dst_path):
    if not is_oiio_supported():
        return None

    oiio_cmd = [
        get_oiio_tools_path(),
        "-i", src_path,
        "--subimage", "0",
        "-o", dst_path
    ]
    try:
        _run_silent_subprocess(oiio_cmd)
    except Exception:
        return None
    return dst_path


def _convert_thumbnail_ffmpeg(src_path, dst_path):
    ffmpeg_cmd = [
        get_ffmpeg_tool_path(),
        "-y",
        "-i", src_path,
        dst_path
    ]
    try:
        _run_silent_subprocess(ffmpeg_cmd)
    except Exception:
        return None
    return dst_path


def export_thumbnail(src_path, root_dir):
    if not os.path.exists(root_dir):
        os.makedirs(root_dir)

    ext = os.path.splitext(src_path)[-1]
    if ext not in (".jpeg", ".jpg", ".png"):
        ext = ".jpeg"
    filename = str(uuid.uuid4()) + ext
    dst_path = os.path.join(root_dir, filename)

    output_path = _convert_thumbnail_oiio(src_path, dst_path)
    if not output_path:
        output_path = _convert_thumbnail_ffmpeg(src_path, dst_path)
    return output_path
