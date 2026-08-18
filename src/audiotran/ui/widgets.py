from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from audiotran.domain import SubtitleCue


def _make_button(name: str, text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    return button


class ProjectPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("project-pane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        project_box = QGroupBox("Project")
        project_layout = QVBoxLayout(project_box)
        project_layout.setSpacing(8)
        self.new_button = _make_button("new-project-button", "New Project")
        self.open_button = _make_button("open-project-button", "Open Project")
        self.save_button = _make_button("save-project-button", "Save Project")
        project_layout.addWidget(self.new_button)
        project_layout.addWidget(self.open_button)
        project_layout.addWidget(self.save_button)
        layout.addWidget(project_box)

        import_box = QGroupBox("Imports")
        import_layout = QVBoxLayout(import_box)
        import_layout.setSpacing(8)
        self.audio_button = _make_button("audio-button", "Import Audio")
        self.image_button = _make_button("image-button", "Import Image")
        self.script_button = _make_button("script-button", "Import Script")
        import_layout.addWidget(self.audio_button)
        import_layout.addWidget(self.image_button)
        import_layout.addWidget(self.script_button)
        layout.addWidget(import_box)

        paths_box = QGroupBox("Current Files")
        paths_layout = QFormLayout(paths_box)
        self.audio_value = QLabel("No audio selected")
        self.image_value = QLabel("No image selected")
        self.script_value = QLabel("No script selected")
        for label in (self.audio_value, self.image_value, self.script_value):
            label.setWordWrap(True)
        paths_layout.addRow("Audio", self.audio_value)
        paths_layout.addRow("Image", self.image_value)
        paths_layout.addRow("Script", self.script_value)
        layout.addWidget(paths_box)

        process_box = QGroupBox("Processing")
        process_layout = QVBoxLayout(process_box)
        process_layout.setSpacing(8)
        self.align_button = _make_button("align-script-button", "Align Script")
        self.asr_button = _make_button("asr-button", "Run ASR")
        self.translate_button = _make_button("translate-button", "Translate")
        process_layout.addWidget(self.align_button)
        process_layout.addWidget(self.asr_button)
        process_layout.addWidget(self.translate_button)
        layout.addWidget(process_box)
        layout.addStretch(1)

    def set_paths(self, audio_path: str, image_path: str, script_path: str | None) -> None:
        self.audio_value.setText(audio_path or "No audio selected")
        self.image_value.setText(image_path or "No image selected")
        self.script_value.setText(script_path or "No script selected")


class SubtitleTable(QTableWidget):
    headers = ["Start", "End", "Script", "Recognized", "Chinese", "Source", "Reviewed"]

    def __init__(self) -> None:
        super().__init__(0, len(self.headers))
        self.setObjectName("subtitle-table")
        self.setHorizontalHeaderLabels(self.headers)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

    def set_cues(self, cues: list[SubtitleCue]) -> None:
        self.blockSignals(True)
        try:
            self.setRowCount(len(cues))
            for row, cue in enumerate(cues):
                values = [
                    f"{cue.start:.3f}",
                    f"{cue.end:.3f}",
                    cue.japanese_script,
                    cue.japanese_recognized,
                    cue.chinese,
                    cue.source,
                    "",
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column in {0, 1, 5}:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.setItem(row, column, item)

                reviewed_item = self.item(row, 6)
                reviewed_item.setFlags(
                    (reviewed_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    & ~Qt.ItemFlag.ItemIsEditable
                )
                reviewed_item.setCheckState(Qt.CheckState.Checked if cue.reviewed else Qt.CheckState.Unchecked)
        finally:
            self.blockSignals(False)


class PreviewPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("preview-pane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        mode_box = QGroupBox("Display Mode")
        mode_layout = QHBoxLayout(mode_box)
        self.zh_mode_button = QRadioButton("Chinese")
        self.zh_mode_button.setObjectName("mode-zh")
        self.bilingual_mode_button = QRadioButton("Bilingual")
        self.bilingual_mode_button.setObjectName("mode-bilingual")
        self.zh_mode_button.setChecked(True)
        mode_layout.addWidget(self.zh_mode_button)
        mode_layout.addWidget(self.bilingual_mode_button)
        layout.addWidget(mode_box)

        preview_box = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_text = QTextEdit()
        self.preview_text.setObjectName("preview-text")
        self.preview_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_text)
        layout.addWidget(preview_box, 1)

        export_row = QHBoxLayout()
        self.show_all_button = _make_button("show-all-button", "Show All")
        self.export_button = _make_button("export-button", "Export")
        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)
        export_row.addWidget(self.show_all_button)
        export_row.addWidget(self.export_button)
        export_row.addWidget(self.status_label, 1)
        layout.addLayout(export_row)

    def set_preview_text(self, text: str) -> None:
        self.preview_text.setPlainText(text)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
