import sys
import json
import os
import threading
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QSizePolicy, QScrollArea,
    QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, QRect
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QPainter, QRegion

CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "ollama_url": "http://localhost:11434",
    "model": "llama3.2",
    "interview_context": "",
    "response_style": "concise",
    "auto_analyze": True,
    "window_opacity": 0.85,
    "window_x": None,
    "window_y": None,
}


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            saved = json.load(f)
        return {**DEFAULT_CONFIG, **saved}
    return DEFAULT_CONFIG.copy()


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


class OllamaWorker(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    chunk_received = pyqtSignal(str)

    def __init__(self, ollama_url, model, prompt, system_prompt):
        super().__init__()
        self.ollama_url = ollama_url
        self.model = model
        self.prompt = prompt
        self.system_prompt = system_prompt

    def run(self):
        import requests
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": self.prompt,
                    "system": self.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 500,
                    }
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            self.response_ready.emit(data.get("response", ""))
        except Exception as e:
            self.error_occurred.emit(str(e))


class AudioTranscriber(QThread):
    transcript_update = pyqtSignal(str)
    partial_transcript = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.recognizer = None
        self.microphone = None

    def run(self):
        import speech_recognition as sr
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.running = True

        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            self.transcript_update.emit("Listening...")

        while self.running:
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)

                try:
                    text = self.recognizer.recognize_google(audio)
                    if text.strip():
                        self.transcript_update.emit(text)
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    self.error_occurred.emit(f"Speech service error: {e}")
            except Exception as e:
                if self.running:
                    self.error_occurred.emit(f"Audio error: {e}")

    def stop(self):
        self.running = False


class OverlayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.is_listening = False
        self.transcript_buffer = []
        self.worker = None
        self.audio_thread = None

        self.init_ui()
        self.load_position()

    def init_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setWindowOpacity(self.config.get("window_opacity", 0.85))

        self.resize(420, 550)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.central_widget.setGraphicsEffect(shadow)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(10, 10)
        self.status_dot.setStyleSheet("""
            QLabel {
                background-color: #666;
                border-radius: 5px;
            }
        """)
        header_layout.addWidget(self.status_dot)

        self.title_label = QLabel("Interview Assistant")
        self.title_label.setStyleSheet("""
            QLabel {
                color: #fff;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 4px;
                color: #fff;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)
        self.settings_btn.clicked.connect(self.open_settings)
        header_layout.addWidget(self.settings_btn)

        self.minimize_btn = QPushButton("−")
        self.minimize_btn.setFixedSize(28, 28)
        self.minimize_btn.setCursor(Qt.PointingHandCursor)
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 4px;
                color: #fff;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)
        self.minimize_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.minimize_btn)

        main_layout.addLayout(header_layout)

        transcript_label = QLabel("📝 Transcript")
        transcript_label.setStyleSheet("color: #aaa; font-size: 11px; font-weight: bold;")
        main_layout.addWidget(transcript_label)

        self.transcript_box = QTextEdit()
        self.transcript_box.setReadOnly(True)
        self.transcript_box.setPlaceholderText("Press the microphone button to start...")
        self.transcript_box.setStyleSheet("""
            QTextEdit {
                background: rgba(30, 30, 40, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 8px;
                color: #e0e0e0;
                font-size: 12px;
            }
        """)
        self.transcript_box.setMaximumHeight(150)
        main_layout.addWidget(self.transcript_box)

        response_label = QLabel("🤖 AI Response")
        response_label.setStyleSheet("color: #aaa; font-size: 11px; font-weight: bold;")
        main_layout.addWidget(response_label)

        self.response_box = QTextEdit()
        self.response_box.setReadOnly(True)
        self.response_box.setPlaceholderText("AI suggestions will appear here...")
        self.response_box.setStyleSheet("""
            QTextEdit {
                background: rgba(30, 30, 40, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 8px;
                color: #7dd3fc;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.response_box)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        self.mic_btn = QPushButton("🎤 Start Listening")
        self.mic_btn.setMinimumHeight(40)
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #8b5cf6);
                border: none;
                border-radius: 8px;
                color: #fff;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #7c3aed);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #6d28d9);
            }
        """)
        self.mic_btn.clicked.connect(self.toggle_listening)
        controls_layout.addWidget(self.mic_btn)

        self.analyze_btn = QPushButton("🔍 Analyze")
        self.analyze_btn.setMinimumHeight(40)
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                color: #fff;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        self.analyze_btn.clicked.connect(self.analyze_transcript)
        controls_layout.addWidget(self.analyze_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #aaa;
                font-size: 13px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: #fff;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_all)
        controls_layout.addWidget(self.clear_btn)

        main_layout.addLayout(controls_layout)

        self.central_widget.setStyleSheet("""
            QWidget {
                background: rgba(20, 20, 30, 0.6);
                border-radius: 12px;
            }
        """)

    def load_position(self):
        x = self.config.get("window_x")
        y = self.config.get("window_y")
        if x is not None and y is not None:
            self.move(x, y)
        else:
            screen = QApplication.primaryScreen().geometry()
            self.move(screen.width() - 440, 20)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_pos'):
            self.move(event.globalPos() - self.drag_pos)
            self.config["window_x"] = self.x()
            self.config["window_y"] = self.y()
            save_config(self.config)

    def toggle_listening(self):
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self):
        try:
            self.audio_thread = AudioTranscriber()
            self.audio_thread.transcript_update.connect(self.on_transcript)
            self.audio_thread.error_occurred.connect(self.on_audio_error)
            self.audio_thread.start()

            self.is_listening = True
            self.mic_btn.setText("⏹ Stop Listening")
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #dc2626);
                    border: none;
                    border-radius: 8px;
                    color: #fff;
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #b91c1c);
                }
            """)
            self.status_dot.setStyleSheet("""
                QLabel {
                    background-color: #22c55e;
                    border-radius: 5px;
                }
            """)
        except Exception as e:
            self.transcript_box.append(f"Error: {e}")

    def stop_listening(self):
        if self.audio_thread:
            self.audio_thread.stop()
            self.audio_thread.wait(2000)
            self.audio_thread = None

        self.is_listening = False
        self.mic_btn.setText("🎤 Start Listening")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #8b5cf6);
                border: none;
                border-radius: 8px;
                color: #fff;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #7c3aed);
            }
        """)
        self.status_dot.setStyleSheet("""
            QLabel {
                background-color: #666;
                border-radius: 5px;
            }
        """)

    def on_transcript(self, text):
        self.transcript_buffer.append(text)
        self.transcript_box.append(f"You: {text}")
        self.transcript_box.verticalScrollBar().setValue(
            self.transcript_box.verticalScrollBar().maximum()
        )

        if self.config.get("auto_analyze", True) and len(self.transcript_buffer) >= 3:
            self.analyze_transcript()

    def on_audio_error(self, error):
        self.transcript_box.append(f"[Error] {error}")

    def analyze_transcript(self):
        if not self.transcript_buffer:
            self.response_box.append("Nothing to analyze yet.")
            return

        full_transcript = " ".join(self.transcript_buffer[-10:])
        context = self.config.get("interview_context", "")

        system_prompt = f"""You are an AI interview assistant. Your job is to analyze interview questions and provide helpful suggestions for responding.

Interview Context: {context}
Response Style: {self.config.get('response_style', 'concise')}

Guidelines:
- Be concise and practical
- Provide key points the user should address
- Suggest specific examples or frameworks (STAR method, etc.)
- Keep responses under 150 words unless the question requires more detail"""

        prompt = f"""Based on this interview transcript, identify the key question being asked and provide a suggested response strategy:

Transcript: "{full_transcript}"

Provide:
1. The main question/topic identified
2. Key points to address
3. Suggested response structure"""

        self.response_box.append("🔄 Analyzing...")
        self.response_box.verticalScrollBar().setValue(
            self.response_box.verticalScrollBar().maximum()
        )

        self.worker = OllamaWorker(
            self.config["ollama_url"],
            self.config["model"],
            prompt,
            system_prompt
        )
        self.worker.response_ready.connect(self.on_response)
        self.worker.error_occurred.connect(self.on_response_error)
        self.worker.start()

    def on_response(self, response):
        self.response_box.append(response)
        self.response_box.verticalScrollBar().setValue(
            self.response_box.verticalScrollBar().maximum()
        )

    def on_response_error(self, error):
        self.response_box.append(f"Error: {error}")
        self.response_box.verticalScrollBar().setValue(
            self.response_box.verticalScrollBar().maximum()
        )

    def clear_all(self):
        self.transcript_buffer = []
        self.transcript_box.clear()
        self.response_box.clear()

    def open_settings(self):
        self.settings_window = SettingsWindow(self.config, self)
        self.settings_window.show()

    def closeEvent(self, event):
        self.stop_listening()
        self.config["window_x"] = self.x()
        self.config["window_y"] = self.y()
        save_config(self.config)
        event.accept()


class SettingsWindow(QMainWindow):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.parent_overlay = parent

        self.setWindowTitle("Settings")
        self.setWindowFlags(Qt.Window)
        self.resize(400, 500)
        self.setMinimumSize(400, 500)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout(self.central_widget)
        layout.setSpacing(16)

        ollama_url_layout = QHBoxLayout()
        ollama_url_layout.addWidget(QLabel("Ollama URL:"))
        from PyQt5.QtWidgets import QLineEdit
        self.ollama_url_edit = QLineEdit(config.get("ollama_url", "http://localhost:11434"))
        self.ollama_url_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(30, 30, 40, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 8px;
                color: #fff;
            }
        """)
        ollama_url_layout.addWidget(self.ollama_url_edit)
        layout.addLayout(ollama_url_layout)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_edit = QLineEdit(config.get("model", "llama3.2"))
        self.model_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(30, 30, 40, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 8px;
                color: #fff;
            }
        """)
        model_layout.addWidget(self.model_edit)
        layout.addLayout(model_layout)

        check_btn = QPushButton("Check Connection")
        check_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                border: none;
                border-radius: 6px;
                padding: 8px;
                color: #fff;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        check_btn.clicked.connect(self.check_ollama)
        layout.addWidget(check_btn)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("Interview Context:"))
        self.context_edit = QTextEdit()
        self.context_edit.setPlainText(config.get("interview_context", ""))
        self.context_edit.setMaximumHeight(100)
        self.context_edit.setStyleSheet("""
            QTextEdit {
                background: rgba(30, 30, 40, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 8px;
                color: #fff;
            }
        """)
        layout.addWidget(self.context_edit)

        layout.addWidget(QLabel("Response Style:"))
        from PyQt5.QtWidgets import QComboBox
        self.style_combo = QComboBox()
        self.style_combo.addItems(["concise", "detailed", "bullet-points", "example-focused"])
        self.style_combo.setCurrentText(config.get("response_style", "concise"))
        self.style_combo.setStyleSheet("""
            QComboBox {
                background: rgba(30, 30, 40, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 8px;
                color: #fff;
            }
        """)
        layout.addWidget(self.style_combo)

        from PyQt5.QtWidgets import QCheckBox
        self.auto_checkbox = QCheckBox("Auto-analyze after 3 transcriptions")
        self.auto_checkbox.setChecked(config.get("auto_analyze", True))
        self.auto_checkbox.setStyleSheet("color: #fff;")
        layout.addWidget(self.auto_checkbox)

        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("Window Opacity:"))
        from PyQt5.QtWidgets import QSlider
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setMinimum(50)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(int(config.get("window_opacity", 0.85) * 100))
        self.opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 0.2);
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #3b82f6;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
        """)
        opacity_layout.addWidget(self.opacity_slider)
        layout.addLayout(opacity_layout)

        save_btn = QPushButton("Save")
        save_btn.setMinimumHeight(40)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #22c55e;
                border: none;
                border-radius: 8px;
                color: #fff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background: #16a34a;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

        self.setStyleSheet("""
            QMainWindow {
                background: #1a1a2e;
            }
            QLabel {
                color: #fff;
                font-size: 13px;
            }
        """)

    def check_ollama(self):
        import requests
        url = self.ollama_url_edit.text()
        try:
            resp = requests.get(f"{url}/api/tags", timeout=5)
            if resp.ok:
                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]
                self.status_label.setText(f"✅ Connected\nAvailable models: {', '.join(model_names)}")
                self.status_label.setStyleSheet("color: #22c55e;")
            else:
                self.status_label.setText(f"❌ Error: {resp.status_code}")
                self.status_label.setStyleSheet("color: #ef4444;")
        except Exception as e:
            self.status_label.setText(f"❌ Cannot connect: {e}")
            self.status_label.setStyleSheet("color: #ef4444;")

    def save_settings(self):
        self.config["ollama_url"] = self.ollama_url_edit.text()
        self.config["model"] = self.model_edit.text()
        self.config["interview_context"] = self.context_edit.toPlainText()
        self.config["response_style"] = self.style_combo.currentText()
        self.config["auto_analyze"] = self.auto_checkbox.isChecked()
        self.config["window_opacity"] = self.opacity_slider.value() / 100

        save_config(self.config)

        if self.parent_overlay:
            self.parent_overlay.config = self.config
            self.parent_overlay.setWindowOpacity(self.config["window_opacity"])

        self.status_label.setText("✅ Settings saved!")
        self.status_label.setStyleSheet("color: #22c55e;")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(18, 18, 24))
    app.setPalette(palette)

    window = OverlayWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
